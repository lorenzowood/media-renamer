import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys

# Add the current directory to the path so we can import the media renamer
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Since the script is named 'media-renamer' without .py extension, we need to import it differently
import importlib.util
import importlib.machinery

# Load the media-renamer script as a module
script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "media-renamer")

# Check if file exists
if not os.path.exists(script_path):
    raise ImportError(f"Script not found at {script_path}")

# Read the file and execute it as a module
with open(script_path, 'r') as f:
    script_content = f.read()

# Create a module object
media_renamer = type(sys)('media_renamer')

# Execute the script content in the module's namespace
exec(script_content, media_renamer.__dict__)

# Add to sys.modules so it can be imported normally
sys.modules['media_renamer'] = media_renamer

class TestMediaRenamer:
    
    @pytest.fixture
    def temp_test_dir(self):
        """Create a temporary directory for testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def mock_api_key(self):
        """Mock the API key environment variable"""
        with patch.dict(os.environ, {'TMDB_API_KEY': 'test_api_key'}):
            yield
    
    @pytest.fixture
    def renamer(self, mock_api_key):
        """Create a MediaRenamer instance with mocked API key"""
        return media_renamer.MediaRenamer()
    
    def create_test_structure(self, base_dir, folder_name, files):
        """Create a test directory structure"""
        folder_path = base_dir / folder_name
        folder_path.mkdir()
        
        for file_name in files:
            file_path = folder_path / file_name
            file_path.touch()
        
        return folder_path
    
    def test_parse_folder_name(self, renamer):
        """Test folder name parsing"""
        # Test with year
        title, year = renamer.parse_folder_name("Beverly Hills Cop Axel F (2024)")
        assert title == "Beverly Hills Cop Axel F"
        assert year == "2024"
        
        # Test without year
        title, year = renamer.parse_folder_name("Some Movie")
        assert title == "Some Movie"
        assert year is None
        
        # Test with year in middle (should not match)
        title, year = renamer.parse_folder_name("Movie (2024) Extended")
        assert title == "Movie (2024) Extended"
        assert year is None
    
    def test_sanitise_filename(self, renamer):
        """Test filename sanitisation"""
        test_cases = [
            ("Movie: Subtitle", "Movie -- Subtitle"),
            ("Movie/Part", "Movie or Part"),
            ("Movie\\Part", "Movie or Part"),
            ("Movie<>", "Movie()"),
            ('Movie"Quote', "Movie'Quote"),
            ("Movie|Pipe", "Movie,Pipe"),
            ("Movie?Question", "Movie!Question"),
            ("Movie*Star", "MoviexStar"),
        ]
        
        for input_str, expected in test_cases:
            result = renamer.sanitise_filename(input_str)
            assert result == expected
    
    def test_format_movie_name(self, renamer):
        """Test movie name formatting"""
        movie_data = {
            'title': 'Beverly Hills Cop: Axel F',
            'release_date': '2024-07-03',
            'imdb_id': 'tt3083016'
        }
        
        result = renamer.format_movie_name(movie_data)
        expected = "Beverly Hills Cop -- Axel F (2024) {imdb-tt3083016}"
        assert result == expected
        
        # Test without IMDB ID
        movie_data_no_imdb = {
            'title': 'Some Movie',
            'release_date': '2023-01-01',
            'imdb_id': None
        }
        
        result = renamer.format_movie_name(movie_data_no_imdb)
        expected = "Some Movie (2023)"
        assert result == expected
    
    @patch('requests.get')
    def test_search_tmdb(self, mock_get, renamer):
        """Test TMDB search functionality"""
        # Mock successful response
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            'results': [
                {'id': 1, 'title': 'Test Movie', 'release_date': '2024-01-01'}
            ]
        }
        mock_get.return_value = mock_response
        
        results = renamer.search_tmdb("Test Movie", "2024")
        
        assert len(results) == 1
        assert results[0]['title'] == 'Test Movie'
        
        # Verify the API was called correctly
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        
        # Check the URL
        assert call_args[0][0] == 'https://api.themoviedb.org/3/search/movie'
        
        # Check the parameters
        params = call_args[1]['params']
        assert params['query'] == 'Test Movie'
        assert params['year'] == '2024'
        assert params['api_key'] == 'test_api_key'
    
    @patch('requests.get')
    def test_get_movie_details(self, mock_get, renamer):
        """Test getting detailed movie information"""
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
    
    def test_rename_folder_and_files_beverly_hills_cop(self, temp_test_dir, renamer):
        """Test complete renaming for Beverly Hills Cop example"""
        # Create test structure
        original_files = [
            "Beverly Hills Cop Axel F (2024).1208527.srt",
            "Beverly Hills Cop Axel F (2024).1208528.srt", 
            "Beverly Hills Cop Axel F (2024).1208529.srt",
            "Beverly Hills Cop Axel F (2024).mkv"
        ]
        
        folder_path = self.create_test_structure(
            temp_test_dir, 
            "Beverly Hills Cop Axel F (2024)", 
            original_files
        )
        
        # Perform rename
        new_name = "Beverly Hills Cop -- Axel F (2024) {imdb-tt3083016}"
        success = renamer.rename_folder_and_files(folder_path, new_name)
        
        assert success == True
        
        # Check that old folder doesn't exist
        assert not folder_path.exists()
        
        # Check that new folder exists
        new_folder_path = temp_test_dir / new_name
        assert new_folder_path.exists()
        
        # Check that files were renamed correctly
        expected_files = [
            "Beverly Hills Cop -- Axel F (2024) {imdb-tt3083016}.1208527.srt",
            "Beverly Hills Cop -- Axel F (2024) {imdb-tt3083016}.1208528.srt",
            "Beverly Hills Cop -- Axel F (2024) {imdb-tt3083016}.1208529.srt",
            "Beverly Hills Cop -- Axel F (2024) {imdb-tt3083016}.mkv"
        ]
        
        actual_files = sorted([f.name for f in new_folder_path.iterdir() if f.is_file()])
        expected_files = sorted(expected_files)
        
        assert actual_files == expected_files
    
    def test_rename_folder_and_files_bridget_jones(self, temp_test_dir, renamer):
        """Test complete renaming for Bridget Jones example"""
        # Create test structure
        original_files = [
            "Bridget Jones The Edge of Reason (2004).462364.srt",
            "Bridget Jones The Edge of Reason (2004).mkv"
        ]
        
        folder_path = self.create_test_structure(
            temp_test_dir,
            "Bridget Jones The Edge of Reason (2004)",
            original_files
        )
        
        # Perform rename
        new_name = "Bridget Jones -- The Edge of Reason (2004) {imdb-tt0317198}"
        success = renamer.rename_folder_and_files(folder_path, new_name)
        
        assert success == True
        
        # Check that old folder doesn't exist
        assert not folder_path.exists()
        
        # Check that new folder exists
        new_folder_path = temp_test_dir / new_name
        assert new_folder_path.exists()
        
        # Check that files were renamed correctly
        expected_files = [
            "Bridget Jones -- The Edge of Reason (2004) {imdb-tt0317198}.462364.srt",
            "Bridget Jones -- The Edge of Reason (2004) {imdb-tt0317198}.mkv"
        ]
        
        actual_files = sorted([f.name for f in new_folder_path.iterdir() if f.is_file()])
        expected_files = sorted(expected_files)
        
        assert actual_files == expected_files
    
    def test_rename_folder_and_files_files_not_matching_folder_name(self, temp_test_dir, renamer):
        """Test renaming when some files don't start with folder name"""
        # Create test structure with mixed file names
        original_files = [
            "Some Movie (2024).mkv",
            "Some Movie (2024).srt",
            "poster.jpg",  # Doesn't start with folder name
            "fanart.jpg"   # Doesn't start with folder name
        ]
        
        folder_path = self.create_test_structure(
            temp_test_dir,
            "Some Movie (2024)",
            original_files
        )
        
        # Perform rename
        new_name = "Some Movie -- Director's Cut (2024) {imdb-tt1234567}"
        success = renamer.rename_folder_and_files(folder_path, new_name)
        
        assert success == True
        
        # Check results
        new_folder_path = temp_test_dir / new_name
        actual_files = sorted([f.name for f in new_folder_path.iterdir() if f.is_file()])
        
        expected_files = [
            "Some Movie -- Director's Cut (2024) {imdb-tt1234567}.mkv",
            "Some Movie -- Director's Cut (2024) {imdb-tt1234567}.srt",
            "poster.jpg",  # Should remain unchanged
            "fanart.jpg"   # Should remain unchanged
        ]
        expected_files = sorted(expected_files)
        
        assert actual_files == expected_files
    
    def test_rename_folder_and_files_target_exists(self, temp_test_dir, renamer):
        """Test renaming when target folder already exists"""
        # Create original folder
        folder_path = self.create_test_structure(
            temp_test_dir,
            "Original (2024)",
            ["Original (2024).mkv"]
        )
        
        # Create target folder that already exists
        target_name = "Target (2024)"
        (temp_test_dir / target_name).mkdir()
        
        # Attempt rename - should fail
        success = renamer.rename_folder_and_files(folder_path, target_name)
        
        assert success == False
        assert folder_path.exists()  # Original should still exist


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
