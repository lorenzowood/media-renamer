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


class MediaRenamer:
    def __init__(self):
        self.api_key = load_api_key()
        if not self.api_key:
            print("Error: TMDB API key not configured.")
            print("Run: media-renamer --set-api-key <your_key>")
            print("Get a free key at: https://www.themoviedb.org/settings/api")
            sys.exit(1)

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

    def parse_folder_name(self, folder_name):
        # Normalise common word separators (underscores, dots) to spaces
        folder_name = folder_name.replace('_', ' ').replace('.', ' ')
        folder_name = re.sub(r' +', ' ', folder_name).strip()

        # First (YYYY) group is the year; everything before it is the title.
        # Handles "Aniara (2019) (1080p BluRay x265) [UTR]" and "Film (2024)".
        year_match = re.search(r'\((\d{4})\)', folder_name)
        if year_match:
            year = year_match.group(1)
            title = folder_name[:year_match.start()].strip()
            return title, year

        # Bare year (19xx or 20xx) without parentheses, e.g. dot-separated
        # torrent names like "Advantageous 2015 1080p WEBRip x264-RARBG".
        # Restricted to 19xx/20xx so "1080" and similar numbers are ignored.
        year_match = re.search(r'\b((?:19|20)\d{2})\b', folder_name)
        if year_match:
            year = year_match.group(1)
            title = folder_name[:year_match.start()].strip()
            return title, year

        # No year found — strip trailing noise groups like [...] and (...) then
        # use whatever remains as the title.
        cleaned = re.sub(r'(\s*[\[(][^\]\[()]*[\])])+\s*$', '', folder_name).strip()
        return cleaned if cleaned else folder_name, None

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
        title, year = self.parse_folder_name(folder_name)
        results = self.search_tmdb(title, year)
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
