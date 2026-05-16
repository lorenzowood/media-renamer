#!/usr/bin/env python3
"""
Media file renamer with TMDB integration
Renames movie folders and files with IMDB-style formatting
"""

import argparse
import configparser
import os
import sys
import glob
import re
import requests
from pathlib import Path

CONFIG_PATH = Path.home() / '.media-renamer.conf'
_CONFIG_SECTION = 'media-renamer'

DEFAULT_STOP_WORDS = [
    '480p', '576p', '720p', '1080p', '1080i', '2160p', '4K',
    'BluRay', 'Blu-Ray', 'BDRip', 'BDRemux',
    'WEBRip', 'WEB-DL', 'WEBDL', 'HDTV', 'DVDRip', 'DVD',
    'AMZN', 'NF', 'HULU', 'DSNP', 'ATVP', 'HBO', 'PCOK',
    'x264', 'x265', 'H264', 'H265', 'HEVC', 'AVC', 'XviD', 'DivX',
    'DDP', 'DTS', 'AAC', 'AC3', 'FLAC', 'TrueHD', 'Atmos',
    'HDR', 'HDR10', 'SDR', 'DoVi', 'HLG',
    'REMUX', 'IMAX', 'REPACK', 'PROPER',
]


def load_api_key():
    if CONFIG_PATH.exists():
        config = configparser.ConfigParser()
        config.read(CONFIG_PATH)
        key = config.get(_CONFIG_SECTION, 'tmdb_api_key', fallback=None)
        if key:
            return key
    return os.environ.get('TMDB_API_KEY')


def set_api_key(key):
    config = configparser.ConfigParser()
    if CONFIG_PATH.exists():
        config.read(CONFIG_PATH)
    if _CONFIG_SECTION not in config:
        config[_CONFIG_SECTION] = {}
    config[_CONFIG_SECTION]['tmdb_api_key'] = key
    with open(CONFIG_PATH, 'w') as f:
        config.write(f)
    print(f"API key saved to {CONFIG_PATH}")


def load_stop_words():
    """
    Load stop words from config. If the stop_words key is absent, write the
    default list into the config file so users can see and edit it.
    """
    config = configparser.ConfigParser()
    if CONFIG_PATH.exists():
        config.read(CONFIG_PATH)

    has_section = _CONFIG_SECTION in config
    has_stop_words = has_section and 'stop_words' in config[_CONFIG_SECTION]

    if not has_stop_words:
        if not has_section:
            config[_CONFIG_SECTION] = {}
        config[_CONFIG_SECTION]['stop_words'] = ', '.join(DEFAULT_STOP_WORDS)
        with open(CONFIG_PATH, 'w') as f:
            config.write(f)
        return list(DEFAULT_STOP_WORDS)

    words_str = config[_CONFIG_SECTION]['stop_words']
    return [w.strip() for w in re.split(r'[,\n]+', words_str) if w.strip()]


def get_search_candidates(folder_name, stop_words):
    """
    Parse a folder name into an ordered list of (title, year) search candidates.

    Steps:
    1. Normalise underscores and dots to spaces.
    2. Scan tokens for the first stop word — everything before it is the
       title zone; everything after is technical metadata noise.
    3. Strip trailing [...] release-group tags from the title zone.
    4. Extract a delimited (YYYY) or [YYYY] year as a definitive signal and
       remove it from the title zone.
    5. Split the title zone on strong delimiters: runs of 2+ spaces or
       spaced dash(es), e.g. "Site    -    Title" → ["Site", "Title"].
    6. For each segment:
       - If a definitive year was found, pair the segment with it.
       - If the segment contains a bare 19xx/20xx year, generate two
         candidates: the full segment (year as title word) and the segment
         with the year stripped. Both use the bare year for proximity ranking.
       - URL-like segments (containing 'www') are deprioritised.
    7. Sort: non-URL segments first, longer segments before shorter ones.
    8. Append word-drop variants of the top candidate as fallbacks (tried
       only if all primary candidates return no results).
    """
    # Normalise word separators
    name = folder_name.replace('_', ' ').replace('.', ' ')

    # Find stop word boundary
    stop_words_lower = {w.lower() for w in stop_words}
    title_zone = name
    for m in re.finditer(r'\S+', name):
        clean = re.sub(r'^[\(\[\{]+|[\)\]\}.,;:!?]+$', '', m.group()).lower()
        if clean in stop_words_lower:
            title_zone = name[:m.start()].strip()
            break

    # Strip trailing [...] release-group tags (e.g. [UTR], [YTS])
    title_zone = re.sub(r'(\s*\[[^\]]*\])+\s*$', '', title_zone).strip()

    # Extract a delimited year — definitive, removed from title zone
    global_year = None
    dm = re.search(r'[\(\[]((?:19|20)\d{2})[\)\]]', title_zone)
    if dm:
        global_year = dm.group(1)
        title_zone = (title_zone[:dm.start()] + title_zone[dm.end():]).strip()

    # Split on strong delimiters
    segments = re.split(r'\s{2,}|\s+-{1,2}\s+', title_zone)
    segments = [s.strip() for s in segments if s.strip()]

    if not segments:
        return []

    url_re = re.compile(r'\bwww\b', re.IGNORECASE)
    bare_year_re = re.compile(r'\b((?:19|20)\d{2})\b')

    scored = []  # (title, year, is_url, word_count)

    for seg in segments:
        is_url = bool(url_re.search(seg))
        wc = len(seg.split())
        bm = bare_year_re.search(seg)

        if global_year:
            scored.append((seg, global_year, is_url, wc))
        elif bm:
            bare_year = bm.group(1)
            without_year = (seg[:bm.start()] + seg[bm.end():]).strip()
            # Full segment first (year as title word), then without year
            scored.append((seg, bare_year, is_url, wc))
            if without_year:
                scored.append((without_year, bare_year, is_url, len(without_year.split())))
        else:
            scored.append((seg, global_year, is_url, wc))

    # Non-URL first, then longer segments before shorter ones
    scored.sort(key=lambda x: (x[2], -x[3]))

    result = [(t, y) for t, y, _, _ in scored]

    # Word-drop fallbacks from the top non-URL candidate
    top = next(((t, y) for t, y, u, _ in scored if not u), None)
    if top:
        words = top[0].split()
        for i in range(1, len(words)):
            cand = (' '.join(words[i:]), top[1])
            if cand not in result:
                result.append(cand)

    return result


class MediaRenamer:
    def __init__(self):
        self.api_key = load_api_key()
        if not self.api_key:
            print("Error: TMDB API key not configured.")
            print("Run: media-renamer --set-api-key <your_key>")
            print("Get a free key at: https://www.themoviedb.org/settings/api")
            sys.exit(1)

        self.stop_words = load_stop_words()
        self.base_url = "https://api.themoviedb.org/3"

    def sanitise_filename(self, s):
        replacements = {
            '<': '(',
            '>': ')',
            ':': ' --',
            '"': "'",
            '/': ' or ',
            '\\': ' or ',
            '|': ',',
            '?': '!',
            '*': 'x'
        }
        for char, replacement in replacements.items():
            s = s.replace(char, replacement)
        return s

    def search_tmdb(self, title, year=None):
        """
        Search TMDB for movies matching title and year.
        Year is used as a soft ranking signal, not a hard API filter, so
        off-by-one years and label errors don't discard correct results.
        """
        url = f"{self.base_url}/search/movie"
        params = {
            'api_key': self.api_key,
            'query': title
        }

        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            results = response.json().get('results', [])

            if year:
                def year_proximity(movie):
                    movie_year = movie.get('release_date', '')[:4]
                    if not movie_year.isdigit():
                        return 999
                    return abs(int(movie_year) - int(year))
                results.sort(key=year_proximity)

            return results
        except requests.RequestException as e:
            print(f"Error searching TMDB: {e}")
            return []

    def search_candidates(self, candidates):
        """Try each (title, year) candidate in order; stop at first hit."""
        for title, year in candidates:
            if not title:
                continue
            results = self.search_tmdb(title, year)
            if results:
                return results
        return []

    def format_movie_name(self, movie_data):
        title = movie_data.get('title', '')
        release_date = movie_data.get('release_date', '')
        imdb_id = movie_data.get('imdb_id')

        year = release_date[:4] if release_date else None
        formatted_title = self.sanitise_filename(title)

        result = formatted_title
        if year:
            result += f" ({year})"
        if imdb_id:
            result += f" {{imdb-{imdb_id}}}"

        return result

    def get_movie_details(self, movie_id):
        url = f"{self.base_url}/movie/{movie_id}"
        params = {'api_key': self.api_key}

        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error getting movie details: {e}")
            return None

    def get_movie_credits(self, movie_id):
        url = f"{self.base_url}/movie/{movie_id}/credits"
        params = {'api_key': self.api_key}

        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error getting movie credits: {e}")
            return None

    def display_search_results(self, folder_name, results):
        if not results:
            print(f"No results found for '{folder_name}'")
            return None

        print(f"Looking up {folder_name}...")

        detailed_results = []
        for movie in results[:3]:
            details = self.get_movie_details(movie['id'])
            if details:
                credits = self.get_movie_credits(movie['id'])
                cast_names = []
                if credits and 'cast' in credits:
                    cast_names = [actor['name'] for actor in credits['cast'][:3]]

                detailed_results.append({
                    'movie': details,
                    'cast': cast_names,
                    'formatted_name': self.format_movie_name(details)
                })

        for i, result in enumerate(detailed_results, 1):
            movie = result['movie']
            cast_str = ', '.join(result['cast']) if result['cast'] else 'Cast info unavailable'
            release_year = movie.get('release_date', '')[:4] or 'Unknown'
            print(f"{i}) {result['formatted_name']} ({movie.get('title', 'Unknown')}; {release_year}; {cast_str})")

        while True:
            choice = input(f"Choose 1-{len(detailed_results)}, or enter a new rename string, or nothing to skip:\n> ").strip()

            if not choice:
                return None

            try:
                choice_num = int(choice)
                if 1 <= choice_num <= len(detailed_results):
                    return detailed_results[choice_num - 1]['formatted_name']
                else:
                    print(f"Please choose a number between 1 and {len(detailed_results)}")
                    continue
            except ValueError:
                return choice

    def rename_folder_and_files(self, old_folder_path, new_name):
        old_folder_path = Path(old_folder_path)
        parent_dir = old_folder_path.parent
        new_folder_path = parent_dir / new_name

        if new_folder_path.exists():
            print(f"Error: Target folder '{new_folder_path}' already exists")
            return False

        try:
            old_folder_name = old_folder_path.name

            for file_path in old_folder_path.iterdir():
                if file_path.is_file():
                    file_name = file_path.name
                    if file_name.startswith(old_folder_name):
                        suffix = file_name[len(old_folder_name):]
                        new_file_name = new_name + suffix
                    else:
                        new_file_name = file_name

                    new_file_path = file_path.parent / new_file_name
                    file_path.rename(new_file_path)
                    print(f"  Renamed file: {file_name} → {new_file_name}")

            old_folder_path.rename(new_folder_path)
            print(f"Renamed folder: {old_folder_path.name} → {new_name}")
            return True

        except OSError as e:
            print(f"Error renaming: {e}")
            return False

    def process_folder(self, folder_path):
        folder_name = Path(folder_path).name
        candidates = get_search_candidates(folder_name, self.stop_words)
        results = self.search_candidates(candidates)
        choice = self.display_search_results(folder_name, results)

        if choice:
            print(f"Renaming to {choice}")
            if self.rename_folder_and_files(folder_path, choice):
                print("✓ Rename successful\n")
            else:
                print("✗ Rename failed\n")
        else:
            print("Skipped\n")


def main():
    parser = argparse.ArgumentParser(
        description='Rename movie folders and files using TMDB metadata.'
    )
    parser.add_argument(
        '--set-api-key',
        metavar='KEY',
        help=f'Save your TMDB API key to {CONFIG_PATH}'
    )
    parser.add_argument(
        'patterns',
        nargs='*',
        metavar='pattern',
        help='Folder name patterns to process (e.g. "*" or "Film*")'
    )
    args = parser.parse_args()

    if args.set_api_key:
        set_api_key(args.set_api_key)
        return

    if not args.patterns:
        parser.print_help()
        sys.exit(1)

    renamer = MediaRenamer()

    for pattern in args.patterns:
        # If the shell already expanded a glob and passed a literal directory
        # name, glob.glob() would misinterpret brackets like [UTR] as character
        # class patterns and fail to match. Check for a literal path first.
        if os.path.isdir(pattern):
            folders = [pattern]
        else:
            folders = [f for f in glob.glob(pattern) if os.path.isdir(f)]

        if not folders:
            print(f"No directories found matching pattern: {pattern}")
            continue

        for folder in folders:
            renamer.process_folder(folder)


if __name__ == "__main__":
    main()
