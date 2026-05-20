import configparser
import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import media_renamer


SW = media_renamer.DEFAULT_STOP_WORDS  # convenience alias in tests


class TestMediaRenamer:

    @pytest.fixture
    def temp_test_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def mock_api_key(self, tmp_path):
        """Redirect CONFIG_PATH to a temp file so the real ~/.media-renamer.conf
        is never read or written during tests. API key comes from env var."""
        temp_conf = tmp_path / '.media-renamer.conf'
        with patch.object(media_renamer, 'CONFIG_PATH', temp_conf):
            with patch.dict(os.environ, {'TMDB_API_KEY': 'test_api_key'}):
                yield

    @pytest.fixture
    def renamer(self, mock_api_key):
        return media_renamer.MediaRenamer()

    def create_test_structure(self, base_dir, folder_name, files):
        folder_path = base_dir / folder_name
        folder_path.mkdir()
        for file_name in files:
            (folder_path / file_name).touch()
        return folder_path

    # ------------------------------------------------------------------
    # API key loading / saving
    # ------------------------------------------------------------------

    def test_load_api_key_from_config(self, tmp_path):
        conf = tmp_path / '.media-renamer.conf'
        conf.write_text('[media-renamer]\ntmdb_api_key = conf_key\n')
        with patch.object(media_renamer, 'CONFIG_PATH', conf):
            assert media_renamer.load_api_key() == 'conf_key'

    def test_load_api_key_falls_back_to_env(self, tmp_path):
        missing = tmp_path / 'no-conf'
        with patch.object(media_renamer, 'CONFIG_PATH', missing):
            with patch.dict(os.environ, {'TMDB_API_KEY': 'env_key'}):
                assert media_renamer.load_api_key() == 'env_key'

    def test_load_api_key_config_takes_priority_over_env(self, tmp_path):
        conf = tmp_path / '.media-renamer.conf'
        conf.write_text('[media-renamer]\ntmdb_api_key = conf_key\n')
        with patch.object(media_renamer, 'CONFIG_PATH', conf):
            with patch.dict(os.environ, {'TMDB_API_KEY': 'env_key'}):
                assert media_renamer.load_api_key() == 'conf_key'

    def test_set_api_key_writes_config(self, tmp_path):
        conf = tmp_path / '.media-renamer.conf'
        with patch.object(media_renamer, 'CONFIG_PATH', conf):
            media_renamer.set_api_key('new_key')
        config = configparser.ConfigParser()
        config.read(conf)
        assert config.get('media-renamer', 'tmdb_api_key') == 'new_key'

    def test_set_api_key_preserves_existing_config(self, tmp_path):
        conf = tmp_path / '.media-renamer.conf'
        conf.write_text('[media-renamer]\nother_setting = value\n')
        with patch.object(media_renamer, 'CONFIG_PATH', conf):
            media_renamer.set_api_key('new_key')
        config = configparser.ConfigParser()
        config.read(conf)
        assert config.get('media-renamer', 'other_setting') == 'value'
        assert config.get('media-renamer', 'tmdb_api_key') == 'new_key'

    # ------------------------------------------------------------------
    # Stop words
    # ------------------------------------------------------------------

    def test_load_stop_words_writes_defaults_when_absent(self, tmp_path):
        conf = tmp_path / '.media-renamer.conf'
        with patch.object(media_renamer, 'CONFIG_PATH', conf):
            words = media_renamer.load_stop_words()
        assert '1080p' in words
        assert 'BluRay' in words
        # Defaults should have been written to conf
        config = configparser.ConfigParser()
        config.read(conf)
        assert 'stop_words' in config['media-renamer']

    def test_load_stop_words_reads_custom_list(self, tmp_path):
        conf = tmp_path / '.media-renamer.conf'
        conf.write_text('[media-renamer]\nstop_words = CUSTOM1, CUSTOM2\n')
        with patch.object(media_renamer, 'CONFIG_PATH', conf):
            words = media_renamer.load_stop_words()
        assert words == ['CUSTOM1', 'CUSTOM2']

    def test_load_stop_words_appends_to_existing_conf(self, tmp_path):
        conf = tmp_path / '.media-renamer.conf'
        conf.write_text('[media-renamer]\ntmdb_api_key = mykey\n')
        with patch.object(media_renamer, 'CONFIG_PATH', conf):
            media_renamer.load_stop_words()
        config = configparser.ConfigParser()
        config.read(conf)
        # API key must still be there after stop_words were added
        assert config.get('media-renamer', 'tmdb_api_key') == 'mykey'
        assert 'stop_words' in config['media-renamer']

    # ------------------------------------------------------------------
    # Candidate generation
    # ------------------------------------------------------------------

    def _first(self, name):
        """Return the first candidate for a folder name using default stop words."""
        return media_renamer.get_search_candidates(name, SW)[0]

    def test_candidates_clean_name_with_delimited_year(self):
        title, year = self._first("Beverly Hills Cop Axel F (2024)")
        assert title == "Beverly Hills Cop Axel F"
        assert year == "2024"

    def test_candidates_torrent_quality_noise_stripped(self):
        title, year = self._first(
            "Aniara (2019) (1080p BluRay x265 HEVC 10bit DTS 5.1 Qman) [UTR]"
        )
        assert title == "Aniara"
        assert year == "2019"

    def test_candidates_bracket_tag_stripped_by_stop_word(self):
        # [1080p] — the token stripped of brackets matches the stop word
        title, year = self._first("The Congress (2013) [1080p]")
        assert title == "The Congress"
        assert year == "2013"

    def test_candidates_dot_separated_bare_year_as_title_word(self):
        # before-year is the cleanest candidate and should come first
        candidates = media_renamer.get_search_candidates(
            "Advantageous.2015.1080p.WEBRip.x264-RARBG", SW
        )
        assert candidates[0] == ("Advantageous", "2015")
        # Full segment (year as title word) follows as a fallback
        assert candidates[1] == ("Advantageous 2015", "2015")

    def test_candidates_url_noise_prefix_deprioritised(self):
        name = "www.UIndex.org    -    The Quiet Earth 1985 1080p AMZN WEB-DL DDP2 0 H 264-GPRS"
        candidates = media_renamer.get_search_candidates(name, SW)
        # before-year "The Quiet Earth" is the cleanest candidate; URL segment last
        assert candidates[0] == ("The Quiet Earth", "1985")
        assert candidates[1] == ("The Quiet Earth 1985", "1985")
        url_titles = [t for t, _ in candidates]
        assert url_titles.index("www UIndex org") > url_titles.index("The Quiet Earth")

    def test_candidates_no_year_trailing_tag_stripped(self):
        title, year = self._first("Some Movie [YTS]")
        assert title == "Some Movie"
        assert year is None

    def test_candidates_underscore_separators(self):
        title, year = self._first("The_Dark_Knight_(2008)")
        assert title == "The Dark Knight"
        assert year == "2008"

    def test_candidates_bare_year_only_title(self):
        # Film titled "1984" — bare year is both title and year signal
        candidates = media_renamer.get_search_candidates("1984", SW)
        assert ("1984", "1984") in candidates

    def test_candidates_genre_year_parenthetical_extracted(self):
        # "(War Drama 1956)" is a descriptor — year extracted, whole group removed
        candidates = media_renamer.get_search_candidates(
            "Reach for the Sky  (War Drama 1956)  Kenneth More  720p", SW
        )
        assert candidates[0] == ("Reach for the Sky", "1956")

    def test_candidates_before_year_is_first_for_trailing_noise(self):
        # "WS" appears after the year — before-year "Sexy Beast" must be first
        candidates = media_renamer.get_search_candidates(
            "Sexy.Beast.2000.WS.1080p.BluRay.x265.HEVC.EAC3-SARTRE", SW
        )
        assert candidates[0] == ("Sexy Beast", "2000")

    def test_candidates_multi_language_tag_does_not_pollute_title(self):
        # "Multi" appears after the year — before-year "The Mummy" must be first
        candidates = media_renamer.get_search_candidates(
            "The.Mummy.1999.Multi.2160p.BluRay.x265.HDR.DTS-HDMA.7.1.[En+Hi]-DTOne", SW
        )
        assert candidates[0] == ("The Mummy", "1999")

    def test_candidates_word_drops_appended(self):
        candidates = media_renamer.get_search_candidates("The Quiet Earth 1985", SW)
        titles = [t for t, _ in candidates]
        # Word-drop variants should appear after the primary candidates
        assert "Quiet Earth 1985" in titles or "Quiet Earth" in titles

    # ------------------------------------------------------------------
    # TMDB search
    # ------------------------------------------------------------------

    @patch('requests.get')
    def test_search_tmdb_year_not_in_api_params(self, mock_get, renamer):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            'results': [{'id': 1, 'title': 'Test Movie', 'release_date': '2024-01-01'}]
        }
        mock_get.return_value = mock_response

        results = renamer.search_tmdb("Test Movie", "2024")

        assert len(results) == 1
        assert results[0]['title'] == 'Test Movie'
        params = mock_get.call_args[1]['params']
        assert params['query'] == 'Test Movie'
        assert 'year' not in params

    @patch('requests.get')
    def test_search_tmdb_year_proximity_sorting(self, mock_get, renamer):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            'results': [
                {'id': 1, 'title': 'Aniara', 'release_date': '2017-01-01'},
                {'id': 2, 'title': 'Aniara', 'release_date': '2020-01-01'},
                {'id': 3, 'title': 'Aniara', 'release_date': '2019-01-01'},
            ]
        }
        mock_get.return_value = mock_response

        results = renamer.search_tmdb("Aniara", "2019")

        assert results[0]['release_date'][:4] == '2019'
        assert results[1]['release_date'][:4] == '2020'
        assert results[2]['release_date'][:4] == '2017'

    @patch('requests.get')
    def test_search_candidates_stops_at_first_hit(self, mock_get, renamer):
        """search_candidates() returns results from first successful candidate."""
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            'results': [{'id': 42, 'title': 'The Quiet Earth', 'release_date': '1985-01-01'}]
        }
        mock_get.return_value = mock_response

        candidates = [("The Quiet Earth 1985", "1985"), ("The Quiet Earth", "1985")]
        results = renamer.search_candidates(candidates)

        assert len(results) == 1
        assert results[0]['id'] == 42
        # Only one API call made — stopped after first hit
        assert mock_get.call_count == 1

    @patch('requests.get')
    def test_search_candidates_falls_through_to_next_on_empty(self, mock_get, renamer):
        """search_candidates() tries the next candidate when one returns nothing."""
        no_results = MagicMock()
        no_results.raise_for_status.return_value = None
        no_results.json.return_value = {'results': []}

        hit = MagicMock()
        hit.raise_for_status.return_value = None
        hit.json.return_value = {
            'results': [{'id': 7, 'title': 'Aniara', 'release_date': '2019-01-01'}]
        }

        mock_get.side_effect = [no_results, hit]

        candidates = [("no match title", "2019"), ("Aniara", "2019")]
        results = renamer.search_candidates(candidates)

        assert results[0]['id'] == 7
        assert mock_get.call_count == 2

    # ------------------------------------------------------------------
    # Movie details / credits
    # ------------------------------------------------------------------

    @patch('requests.get')
    def test_get_movie_details(self, mock_get, renamer):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            'id': 1,
            'title': 'Beverly Hills Cop: Axel F',
            'release_date': '2024-07-03',
            'imdb_id': 'tt3083016'
        }
        mock_get.return_value = mock_response

        result = renamer.get_movie_details(1)
        assert result['title'] == 'Beverly Hills Cop: Axel F'
        assert result['imdb_id'] == 'tt3083016'

    # ------------------------------------------------------------------
    # Filename sanitisation / formatting
    # ------------------------------------------------------------------

    def test_sanitise_filename(self, renamer):
        cases = [
            ("Movie: Subtitle", "Movie -- Subtitle"),
            ("Movie/Part", "Movie or Part"),
            ("Movie\\Part", "Movie or Part"),
            ("Movie<>", "Movie()"),
            ('Movie"Quote', "Movie'Quote"),
            ("Movie|Pipe", "Movie,Pipe"),
            ("Movie?Question", "Movie!Question"),
            ("Movie*Star", "MoviexStar"),
        ]
        for input_str, expected in cases:
            assert renamer.sanitise_filename(input_str) == expected

    def test_format_movie_name(self, renamer):
        result = renamer.format_movie_name({
            'title': 'Beverly Hills Cop: Axel F',
            'release_date': '2024-07-03',
            'imdb_id': 'tt3083016'
        })
        assert result == "Beverly Hills Cop -- Axel F (2024) {imdb-tt3083016}"

        result = renamer.format_movie_name({
            'title': 'Some Movie',
            'release_date': '2023-01-01',
            'imdb_id': None
        })
        assert result == "Some Movie (2023)"

    # ------------------------------------------------------------------
    # Folder / file renaming
    # ------------------------------------------------------------------

    def test_rename_folder_and_files_beverly_hills_cop(self, temp_test_dir, renamer):
        original_files = [
            "Beverly Hills Cop Axel F (2024).1208527.srt",
            "Beverly Hills Cop Axel F (2024).1208528.srt",
            "Beverly Hills Cop Axel F (2024).1208529.srt",
            "Beverly Hills Cop Axel F (2024).mkv"
        ]
        folder_path = self.create_test_structure(
            temp_test_dir, "Beverly Hills Cop Axel F (2024)", original_files
        )
        new_name = "Beverly Hills Cop -- Axel F (2024) {imdb-tt3083016}"
        assert renamer.rename_folder_and_files(folder_path, new_name) is True

        new_folder = temp_test_dir / new_name
        assert new_folder.exists()
        assert not folder_path.exists()
        actual = sorted(f.name for f in new_folder.iterdir() if f.is_file())
        expected = sorted([
            "Beverly Hills Cop -- Axel F (2024) {imdb-tt3083016}.1208527.srt",
            "Beverly Hills Cop -- Axel F (2024) {imdb-tt3083016}.1208528.srt",
            "Beverly Hills Cop -- Axel F (2024) {imdb-tt3083016}.1208529.srt",
            "Beverly Hills Cop -- Axel F (2024) {imdb-tt3083016}.mkv",
        ])
        assert actual == expected

    def test_rename_folder_and_files_bridget_jones(self, temp_test_dir, renamer):
        original_files = [
            "Bridget Jones The Edge of Reason (2004).462364.srt",
            "Bridget Jones The Edge of Reason (2004).mkv"
        ]
        folder_path = self.create_test_structure(
            temp_test_dir, "Bridget Jones The Edge of Reason (2004)", original_files
        )
        new_name = "Bridget Jones -- The Edge of Reason (2004) {imdb-tt0317198}"
        assert renamer.rename_folder_and_files(folder_path, new_name) is True

        new_folder = temp_test_dir / new_name
        actual = sorted(f.name for f in new_folder.iterdir() if f.is_file())
        expected = sorted([
            "Bridget Jones -- The Edge of Reason (2004) {imdb-tt0317198}.462364.srt",
            "Bridget Jones -- The Edge of Reason (2004) {imdb-tt0317198}.mkv",
        ])
        assert actual == expected

    def test_rename_folder_and_files_non_matching_files_preserved(self, temp_test_dir, renamer):
        original_files = [
            "Some Movie (2024).mkv",
            "Some Movie (2024).srt",
            "poster.jpg",
            "fanart.jpg",
        ]
        folder_path = self.create_test_structure(
            temp_test_dir, "Some Movie (2024)", original_files
        )
        new_name = "Some Movie -- Director's Cut (2024) {imdb-tt1234567}"
        assert renamer.rename_folder_and_files(folder_path, new_name) is True

        new_folder = temp_test_dir / new_name
        actual = sorted(f.name for f in new_folder.iterdir() if f.is_file())
        expected = sorted([
            "Some Movie -- Director's Cut (2024) {imdb-tt1234567}.mkv",
            "Some Movie -- Director's Cut (2024) {imdb-tt1234567}.srt",
            "poster.jpg",
            "fanart.jpg",
        ])
        assert actual == expected

    def test_rename_folder_and_files_target_exists(self, temp_test_dir, renamer):
        folder_path = self.create_test_structure(
            temp_test_dir, "Original (2024)", ["Original (2024).mkv"]
        )
        (temp_test_dir / "Target (2024)").mkdir()
        assert renamer.rename_folder_and_files(folder_path, "Target (2024)") is False
        assert folder_path.exists()

    # ------------------------------------------------------------------
    # Glob / literal-path handling
    # ------------------------------------------------------------------

    def test_literal_directory_with_brackets_is_found(self, temp_test_dir):
        """glob.glob() misinterprets [...] as a char class; os.path.isdir() does not."""
        import glob as glob_module
        folder_path = temp_test_dir / "Aniara (2019) (1080p BluRay x265) [UTR]"
        folder_path.mkdir()
        assert glob_module.glob(str(folder_path)) == []
        assert os.path.isdir(str(folder_path))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
