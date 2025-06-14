# Media Renamer

A Python tool for renaming movie folders and files with proper IMDB-style formatting using The Movie Database (TMDB) API.

## What it does

Media Renamer takes movie folders with inconsistent naming and renames them (and all files within) to a standardised format that includes IMDB identifiers. This is particularly useful for media server applications like Plex that benefit from consistent, metadata-rich file naming.

### Example transformation

**Before:**
```
Beverly Hills Cop Axel F (2024)/
├── Beverly Hills Cop Axel F (2024).mkv
├── Beverly Hills Cop Axel F (2024).1208527.srt
├── Beverly Hills Cop Axel F (2024).1208528.srt
└── Beverly Hills Cop Axel F (2024).1208529.srt
```

**After:**
```
Beverly Hills Cop -- Axel F (2024) {imdb-tt3083016}/
├── Beverly Hills Cop -- Axel F (2024) {imdb-tt3083016}.mkv
├── Beverly Hills Cop -- Axel F (2024) {imdb-tt3083016}.1208527.srt
├── Beverly Hills Cop -- Axel F (2024) {imdb-tt3083016}.1208528.srt
└── Beverly Hills Cop -- Axel F (2024) {imdb-tt3083016}.1208529.srt
```

## Features

- **Interactive search**: Presents multiple options from TMDB with cast information
- **Intelligent filename sanitisation**: Replaces problematic characters (`:` becomes ` --`, `/` becomes ` or`, etc.)
- **Comprehensive renaming**: Renames both folders and all files within them
- **Flexible input**: Accepts custom rename strings or skips items entirely
- **Safe operation**: Checks for existing target folders to prevent conflicts
- **Comprehensive test suite**: Includes pytest-based tests with mocked API calls

## Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd media-renamer
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Make scripts executable:**
   ```bash
   chmod +x media-renamer
   chmod +x replace-structure
   ```

## Setup

### Get a TMDB API Key

1. Create a free account at [The Movie Database](https://www.themoviedb.org/signup)
2. Go to [API Settings](https://www.themoviedb.org/settings/api) and request an API key
3. Create a `.env` file in the project directory:
   ```
   TMDB_API_KEY=your_api_key_here
   ```

The `.gitignore` file is already configured to keep your API key secure.

## Usage

### Basic usage

```bash
./media-renamer <folder_pattern>
```

### Examples

**Rename all movie folders in current directory:**
```bash
./media-renamer "*"
```

**Rename specific folders:**
```bash
./media-renamer "Beverly Hills Cop*" "Bridget Jones*"
```

### Interactive process

When you run the tool, it will:

1. Parse each folder name to extract title and year
2. Search TMDB for matching movies
3. Present up to 3 options with cast information:
   ```
   Looking up Beverly Hills Cop Axel F (2024)...
   1) Beverly Hills Cop -- Axel F (2024) {imdb-tt3083016} (Beverly Hills Cop: Axel F; 2024; Eddie Murphy, Joseph Gordon-Levitt, Taylour Paige)
   2) Beverly Hills Cop -- Axel F (2024) {imdb-tt8874500} (Beverly Hills Cop: Axel F; 2024; Behind the Scenes)
   3) Beverly Hills Cop -- Axel F (2024) {imdb-tt9876543} (Beverly Hills Cop: Axel F; 2024; Documentary)
   Choose 1-3, or enter a new rename string, or nothing to skip:
   >
   ```

4. You can:
   - Enter a number (1-3) to select one of the options
   - Type a custom rename string
   - Press Enter to skip this folder

### Filename formatting rules

The tool follows these character replacement rules for safe filenames:

| Character | Replacement | Reason |
|-----------|-------------|--------|
| `:`       | ` --`       | Subtitle separator |
| `/`       | ` or `      | Alternative indicator |
| `\`       | ` or `      | Alternative indicator |
| `<>`      | `()`        | Bracket substitution |
| `"`       | `'`         | Quote substitution |
| `\|`      | `,`         | List separator |
| `?`       | `!`         | Question to exclamation |
| `*`       | `x`         | Wildcard to letter |

## Testing

The project includes a comprehensive test suite using pytest.

### Run tests

```bash
python test_media_renamer.py
```

### Create test data

Use the included `replace-structure` script to create a test directory structure:

```bash
./replace-structure /path/to/your/movies ./test-data
```

This creates a copy of your directory structure with empty files, perfect for testing without risking your actual media files.

### Test coverage

The test suite covers:
- Folder name parsing
- Filename sanitisation
- Movie name formatting
- TMDB API integration (mocked)
- Complete renaming workflows
- Edge cases and error handling

## File structure

```
media-renamer/
├── media-renamer           # Main script
├── replace-structure       # Test data generator
├── test_media_renamer.py   # Test suite
├── requirements.txt        # Python dependencies
├── .env                    # API key (create this)
├── .gitignore             # Git ignore file
└── README.md              # This file
```

## Requirements

- Python 3.7+
- `requests` - For TMDB API calls
- `python-dotenv` - For environment variable management
- `pytest` - For running tests
- `pytest-mock` - For test mocking

## Compatibility

This tool is designed to work with:
- **Plex Media Server** - The naming format is optimised for Plex's metadata agents
- **Other media servers** - The standardised format should work with most media management tools
- **General file organisation** - Useful for anyone wanting consistent movie file naming

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run the test suite
5. Submit a pull request


## Acknowledgements

- **The Movie Database (TMDB)** for providing the comprehensive movie API
- **Plex** for inspiring the naming format standards
- Originally designed to complement a browser extension for enhanced IMDB search results https://github.com/lorenzowood/plex_name_formatter_extension
