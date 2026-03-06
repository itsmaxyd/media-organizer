# Media Organizer

An intelligent media file organizer that uses AI to analyze and categorize your photos and videos.

## Features

- **AI-Powered Analysis**: Uses LLM to understand your media content
- **Smart Categorization**: Automatically sorts files into categories (nature, food, travel, etc.)
- **Video Support**: Analyzes video keyframes and extracts audio transcripts
- **Local Processing**: Optional local Whisper for audio transcription (no cloud needed)
- **GUI Mode**: User-friendly graphical interface
- **CLI Mode**: Headless mode for automation and scripting
- **Caching**: Avoids re-analyzing previously processed files

## Screenshot

```
+--------------------------------------------------+
|  📁 Source  |  📂 Output  |  ⚙️ Settings  [Test]  |
+--------------------------------------------------+
|  Results Table  |     Preview Panel              |
|  ----------------|----------------------        |
|  image1.jpg     |  [Image Preview]             |
|  video.mp4      |                               |
|  photo.png      |  Category: nature             |
|                 |  Name: sunset_beach           |
|                 |  Confidence: 0.95             |
+--------------------------------------------------+
|  [▶ Analyze] [✅ Approve All] [👁 Preview]       |
|  [🚀 Execute (Dry Run)] [🚀 Execute (For Real)] |
+--------------------------------------------------+
|  Progress: 50%  |  5/10 files | ⏱️ 30s | 🔑 5000 |
+--------------------------------------------------+
```

## Getting an API Key

This application uses the [FrogAPI](https://frogapi.app) service for AI analysis.

1. Visit [frogapi.app](https://frogapi.app)
2. Create an account
3. Generate an API key
4. Enter the API key in the application Settings

## Setup

### Prerequisites

- Python 3.8+
- ffmpeg
- tesseract (for OCR)
- (Optional) CUDA-capable GPU for faster Whisper transcription

### Installation

Run the installation script:

```bash
chmod +x install.sh
./install.sh
```

Or manually install dependencies:

```bash
# Install system dependencies
# Arch Linux
sudo pacman -S python python-pip ffmpeg tesseract

# Ubuntu/Debian
sudo apt install python3 python3-pip ffmpeg tesseract-ocr

# Install Python packages
pip install -r requirements.txt
```

### First Run

1. Launch the application:
   ```bash
   python main.py
   ```

2. Go to **Settings** and enter your API key from [frogapi.app](https://frogapi.app)

3. Select a **Source Directory** containing your media files

4. Select an **Output Directory** where organized files will be placed

## Testing Mode

Testing mode is enabled by default and limits processing to 3 files. This is useful for:
- Verifying the setup works correctly
- Testing categorization results
- Avoiding API usage during development

To process all files, uncheck "Test Mode" in the toolbar or use CLI with `--limit 0`.

## Usage

### GUI Mode

```bash
python main.py
```

1. Select source directory
2. Select output directory
3. Click **Analyze**
4. Review results in the table
5. Click **Preview Plan** to see what will happen
6. Click **Execute (Dry Run)** to test, or **Execute (For Real)** to actually move files

### CLI Mode

Headless mode for automation:

```bash
# Dry run (preview only)
python main.py --cli --source /path/to/media --output /path/out --limit 5 --dry-run

# Execute for real
python main.py --cli --source /path/to/media --output /path/out --no-dry-run

# Process all files (no limit)
python main.py --cli --source /path/to/media --output /path/out --limit 0
```

### Command Line Options

| Option | Description |
|--------|-------------|
| `--cli` | Run in headless CLI mode |
| `--source` | Source directory containing media |
| `--output` | Output directory for organized files |
| `--limit N` | Limit to N files (0 = no limit) |
| `--dry-run` | Preview without moving files (default) |
| `--no-dry-run` | Actually move files |
| `--verbose` | Enable debug logging |

## Configuration

Settings are stored in `config.json` in the application directory.

### Settings Options

- **API Key**: Your FrogAPI key
- **API Base URL**: API endpoint (default: https://frogapi.app/v1)
- **Model**: LLM model to use (default: gpt-5-nano)
- **Testing Mode**: Limit to 3 files
- **Keyframes per Video**: Number of frames to extract (default: 8)
- **Max Image Size**: Resize images to this max dimension (default: 512px)
- **Use Local Whisper**: Enable local audio transcription

## Cache

Analysis results are cached in `cache/cache.json` to avoid re-analyzing files. 
Delete this file to clear the cache.

## Project Structure

```
media_organizer/
├── core/                    # Core processing modules
│   ├── cache_manager.py     # Result caching
│   ├── extractor.py         # Image/video frame extraction
│   ├── llm_client.py       # LLM API client
│   ├── local_processor.py  # Local Whisper/OCR
│   └── organizer.py        # File organization logic
├── gui/                     # GUI components
│   ├── main_window.py      # Main application window
│   ├── preview_panel.py    # Media preview
│   ├── results_table.py    # Results display
│   ├── settings_dialog.py  # Settings UI
│   └── worker.py            # Background processing
├── cache/                   # Cache directory
├── main.py                  # Entry point
├── requirements.txt         # Python dependencies
├── install.sh              # Installation script
└── README.md               # This file
```

## License

MIT License
