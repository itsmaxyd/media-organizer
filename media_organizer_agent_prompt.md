# 🗂️ Agentic Prompt: Media File Organizer Application

## OBJECTIVE
Build a Python GUI desktop application for Linux (Arch Linux) that organizes images and short video files (~1 min) from a directory using local processing and LLM-powered context analysis. The app uses an OpenAI-compatible API endpoint with a configurable base URL and API key.

---

## SYSTEM CONTEXT & CONSTRAINTS

- **OS**: Arch Linux
- **GPU**: NVIDIA GTX 980 Ti (CUDA, ~6GB VRAM) — use for local processing where possible
- **Python**: 3.10+
- **GUI Framework**: PyQt6 (preferred) or PySide6
- **LLM API**: OpenAI-compatible, model `gpt-5-nano`, endpoint `https://frogapi.app/v1`
- **LLM has vision capability** (accepts image inputs via base64 or URL in OpenAI message format)
- **Testing mode MUST be implemented first** to limit token usage during development/testing

---

## IMPLEMENT IN THESE EXACT STEPS — DO NOT SKIP OR COMBINE STEPS

Work through each step completely before moving to the next. After each step, state what was completed and what comes next.

---

### STEP 1 — Project Scaffold & Settings
**Goal**: Create the base project structure and a persistent settings system.

1. Create the following directory structure:
   ```
   media_organizer/
   ├── main.py
   ├── settings.py
   ├── config.json           # persisted user config (gitignored)
   ├── core/
   │   ├── __init__.py
   │   ├── extractor.py      # keyframe + audio extraction
   │   ├── local_processor.py # local OCR / thumbnail / whisper
   │   ├── llm_client.py     # API wrapper
   │   ├── analyzer.py       # orchestrates context building
   │   └── organizer.py      # rename/move logic + dry-run
   ├── gui/
   │   ├── __init__.py
   │   ├── main_window.py
   │   ├── settings_dialog.py
   │   ├── preview_panel.py
   │   └── results_table.py
   ├── cache/                # local JSON cache per file hash
   └── requirements.txt
   ```

2. Implement `settings.py` with a `Settings` dataclass that loads/saves `config.json`:
   - `api_key: str` (default: `""`)
   - `api_base_url: str` (default: `"https://frogapi.app/v1"`)
   - `model_name: str` (default: `"gpt-5-nano"`)
   - `source_dir: str`
   - `output_dir: str`
   - `testing_mode: bool` (default: `True`)
   - `testing_limit: int` (default: `3`) — max files in testing mode
   - `keyframes_per_video: int` (default: `8`) — range 6–12
   - `max_image_size_px: int` (default: `512`) — resize before API call
   - `use_local_whisper: bool` (default: `True`)
   - `whisper_model: str` (default: `"base"`) — options: tiny, base, small
   - `dry_run: bool` (default: `True`) — never move files unless user confirms
   - `naming_template: str` (default: `"{category}/{descriptive_name}{ext}"`)

3. Write `requirements.txt`:
   ```
   PyQt6
   openai
   opencv-python
   pillow
   faster-whisper   # GPU-accelerated whisper for CUDA
   numpy
   ffmpeg-python
   pathlib
   ```

**Test**: Run `python main.py` — app must launch (even if empty window).

---

### STEP 2 — Local Media Processing (`core/extractor.py`)
**Goal**: Extract keyframes from videos and prep images — entirely offline, no API calls.

#### 2a. Image Preprocessing
```python
def preprocess_image(path: Path, max_size: int = 512) -> bytes:
    """
    - Open image with Pillow
    - Resize so longest side = max_size (preserve aspect ratio)
    - Convert to RGB if needed (handle RGBA, palette modes)
    - Return as JPEG bytes (quality=85)
    - DO NOT modify original file
    """
```

#### 2b. Video Keyframe Extraction
```python
def extract_keyframes(video_path: Path, n_frames: int = 8) -> list[bytes]:
    """
    - Use OpenCV (cv2) to open video
    - Get total frame count and FPS
    - Evenly sample n_frames timestamps across duration
    - Skip first 2% and last 2% of video (avoid black frames)
    - For each timestamp: seek, grab frame, convert BGR→RGB
    - Resize each frame to max 512px longest side
    - Return list of JPEG bytes
    - Handle corrupt/unreadable videos gracefully (return empty list, log warning)
    """
```

#### 2c. Audio Extraction for Video
```python
def extract_audio(video_path: Path, tmp_dir: Path) -> Path | None:
    """
    - Use ffmpeg-python to extract audio track to tmp WAV (16kHz mono)
    - If video has no audio stream, return None
    - Store in tmp_dir with hashed filename
    - Return path to WAV file or None
    """
```

#### 2d. File Hashing
```python
def file_hash(path: Path) -> str:
    """SHA256 of first 1MB + file size — fast fingerprint for caching"""
```

**Test**: Run extractor on 1 test image and 1 test video. Print number of keyframes and whether audio was found. Confirm no files were modified.

---

### STEP 3 — Local Whisper Transcription (`core/local_processor.py`)
**Goal**: Transcribe video audio locally on GPU using faster-whisper (free, no API cost).

```python
class LocalProcessor:
    def __init__(self, whisper_model: str = "base", device: str = "cuda"):
        """
        - Load faster-whisper WhisperModel
        - device: "cuda" if torch.cuda.is_available() else "cpu"
        - compute_type: "float16" for CUDA (980 Ti supports fp16), "int8" for CPU
        - Log which device is being used
        """

    def transcribe_audio(self, wav_path: Path) -> str:
        """
        - Transcribe WAV file
        - Join all segment texts
        - Truncate to 500 words max (sufficient for context, saves tokens)
        - Return empty string on failure
        """

    def get_image_ocr_hint(self, image_bytes: bytes) -> str:
        """
        - OPTIONAL: Use pytesseract if installed to extract any visible text
        - Return empty string if tesseract not available
        - This is a bonus hint, not required
        """
```

**Test**: Transcribe a short video. Print first 100 chars of transcript. Confirm GPU is used (check nvidia-smi).

---

### STEP 4 — LLM Client (`core/llm_client.py`)
**Goal**: Thin wrapper around OpenAI SDK with the custom endpoint.

```python
class LLMClient:
    def __init__(self, settings: Settings):
        """
        - Initialize openai.OpenAI(api_key=..., base_url=...)
        - Store model name
        """

    def describe_media(
        self,
        image_frames: list[bytes],   # JPEG bytes (1 image OR keyframes)
        transcript: str = "",         # from whisper or ""
        ocr_hint: str = "",
        media_type: str = "image",    # "image" or "video"
    ) -> dict:
        """
        Build this exact message structure:
        
        system: "You are a media file analyzer. Respond ONLY in valid JSON."
        
        user content (multimodal):
          - text: context block (see below)
          - image_url blocks: one per frame, base64 encoded
            format: {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,<b64>"}}
        
        Context block template:
        ---
        Analyze this {media_type}. 
        {"Audio transcript: " + transcript[:500] if transcript else ""}
        {"Visible text detected: " + ocr_hint if ocr_hint else ""}
        
        Return JSON with these exact keys:
        {
          "category": "<single folder name, lowercase, no spaces, e.g. nature, food, receipts, people, pets, travel, gaming, documents, misc>",
          "subcategory": "<optional second level, or null>",
          "descriptive_name": "<2-4 word snake_case description, e.g. sunset_beach_waves>",
          "tags": ["tag1", "tag2"],
          "confidence": <0.0 to 1.0>,
          "reasoning": "<one sentence>"
        }
        ---
        
        - Parse and return the JSON dict
        - On API error: retry once after 2 seconds, then return fallback dict with category="misc"
        - Log token usage (prompt_tokens, completion_tokens) for cost tracking
        """

    def get_token_usage(self) -> dict:
        """Return cumulative token counts for this session"""
```

**Test (with testing_mode=True, limit=1 file)**: Send 1 image to the API. Print the returned JSON. Print token usage. If API key is not set, skip and print a warning.

---

### STEP 5 — Analyzer Orchestrator (`core/analyzer.py`)
**Goal**: Coordinate extraction → local processing → LLM → caching for each file.

```python
class MediaAnalyzer:
    def __init__(self, settings: Settings, local_proc: LocalProcessor, llm: LLMClient):
        self.cache = {}  # hash → result dict, loaded from cache/cache.json on init

    def analyze_file(self, path: Path, progress_callback=None) -> dict:
        """
        Full pipeline for one file:
        
        1. Compute file hash
        2. Check cache — if hit, return cached result immediately
        3. Determine media type (image: jpg/png/webp/gif/bmp, video: mp4/mov/avi/mkv/webm)
        4. If IMAGE:
             a. preprocess_image() → image_bytes
             b. local_processor.get_image_ocr_hint(image_bytes) → ocr_hint
             c. llm.describe_media([image_bytes], ocr_hint=ocr_hint, media_type="image")
        5. If VIDEO:
             a. extract_keyframes() → frames (use settings.keyframes_per_video)
             b. extract_audio() → wav_path
             c. If wav_path and settings.use_local_whisper:
                  local_processor.transcribe_audio(wav_path) → transcript
                else: transcript = ""
             d. llm.describe_media(frames, transcript=transcript, media_type="video")
        6. Build result dict:
             {
               "original_path": str(path),
               "filename": path.name,
               "media_type": "image"|"video",
               "hash": hash,
               "analysis": <llm result dict>,
               "proposed_name": <built from naming_template>,
               "status": "pending"  # pending | approved | skipped
             }
        7. Save to cache
        8. Call progress_callback(result) if provided
        9. Return result
        
        proposed_name logic:
          - category = analysis["category"]
          - subcategory = analysis["subcategory"] or ""
          - descriptive_name = analysis["descriptive_name"]
          - Handle naming conflicts: append _2, _3 etc if proposed name exists
        """

    def analyze_directory(self, directory: Path, progress_callback=None) -> list[dict]:
        """
        - Scan for all supported media files (recursive optional)
        - If testing_mode: shuffle list, take first settings.testing_limit files
        - For each file, call analyze_file()
        - Return list of result dicts
        """
```

**Test**: Run on 2–3 files in testing mode. Print proposed names. Confirm cache.json is written.

---

### STEP 6 — Organizer / Dry-Run Engine (`core/organizer.py`)
**Goal**: Compute and execute file moves/renames — always dry-run first.

```python
class Organizer:
    def __init__(self, settings: Settings):
        pass

    def build_plan(self, results: list[dict]) -> list[dict]:
        """
        For each approved result:
        - Compute destination path: output_dir / proposed_name
        - Check for conflicts, resolve with suffix
        - Return list of {source, destination, action: "move"|"copy"} dicts
        """

    def preview_plan(self, plan: list[dict]) -> str:
        """Return human-readable summary of what will happen"""

    def execute_plan(self, plan: list[dict], dry_run: bool = True) -> list[dict]:
        """
        - If dry_run=True: simulate, return plan with status="would_move"
        - If dry_run=False: actually move/copy files, create subdirs
        - Return executed plan with status per file
        - NEVER execute if dry_run=True
        """
```

---

### STEP 7 — GUI: Main Window (`gui/main_window.py`)
**Goal**: Build the main application window with all panels.

#### Layout (use QSplitter for resizable panes):
```
┌─────────────────────────────────────────────────────────┐
│  [📁 Source Dir] [📂 Output Dir] [⚙️ Settings] [? Help] │  ← Toolbar
├────────────────────┬────────────────────────────────────┤
│                    │                                    │
│   FILE LIST        │      PREVIEW PANEL                 │
│   (results table)  │  (image/video thumbnail +          │
│                    │   proposed name + tags +            │
│   ✓ file1.jpg      │   reasoning text)                  │
│   ✓ file2.mp4      │                                    │
│   ✗ file3.png      │                                    │
│                    │                                    │
├────────────────────┴────────────────────────────────────┤
│  Progress: [████████░░░░░░] 60%   5/8 files   ⏱ 12s    │
│  Tokens used: 1,240 prompt / 380 completion             │
├─────────────────────────────────────────────────────────┤
│  [🧪 Test Mode ON] [▶ Analyze] [✅ Approve All]         │
│  [👁 Preview Plan] [🚀 Execute (Dry Run)]               │
└─────────────────────────────────────────────────────────┘
```

#### Implement these GUI components:

**Toolbar**:
- Source directory picker (QFileDialog)
- Output directory picker  
- Settings button → opens SettingsDialog
- Testing mode toggle (QCheckBox, prominently colored yellow when ON)

**Results Table** (`gui/results_table.py`):
- Columns: `[ ] | Original Name | Type | Category | Proposed Name | Confidence | Status`
- Checkboxes per row (approve/skip individual files)
- Click row → updates preview panel
- Color coding: green=approved, red=skipped, gray=pending, blue=processing
- Right-click context menu: Approve / Skip / Edit Proposed Name / Reanalyze

**Preview Panel** (`gui/preview_panel.py`):
- Show image thumbnail (max 400px) or video thumbnail (first keyframe)
- Show proposed path
- Show tags as colored chips
- Show confidence meter (QProgressBar styled)
- Show LLM reasoning text
- Editable proposed name field (user can override)

**Progress Bar**:
- Overall progress (files processed / total)
- Current file name being processed
- Elapsed time
- Live token usage counter (updates after each API call)
- Cancel button

**Action Buttons**:
- `Analyze` — start analysis (disabled if no source dir)
- `Approve All` — check all rows
- `Preview Plan` — open modal showing what will happen
- `Execute (Dry Run)` — run dry run, show diff in modal
- `Execute (For Real)` — only enabled after dry run is confirmed; requires checkbox confirmation dialog

---

### STEP 8 — Settings Dialog (`gui/settings_dialog.py`)
**Goal**: A clean settings UI with all configurable options.

Sections:
1. **API Configuration**
   - API Key field (password masked, with show/hide toggle)
   - Base URL field (default: `https://frogapi.app/v1`)
   - Model name field
   - [Test Connection] button → makes a trivial API call and shows OK/FAIL

2. **Processing**
   - Keyframes per video (QSpinBox, 6–12)
   - Max image size px (256 / 512 / 768 dropdown)
   - Use local Whisper transcription (checkbox)
   - Whisper model size (tiny / base / small — note VRAM usage)

3. **Output**
   - Naming template (text field with live preview)
   - Conflict resolution (skip / rename with suffix)

4. **Testing Mode**
   - Testing mode ON/OFF
   - File limit spinner (1–10)
   - Warning label: "⚠️ Testing mode limits processing to N files to save tokens"

Save/Cancel buttons. Changes apply immediately on Save.

---

### STEP 9 — Worker Thread for Analysis
**Goal**: Run analysis in background without freezing GUI.

```python
class AnalysisWorker(QThread):
    progress = pyqtSignal(int, int, dict)      # current, total, result
    file_done = pyqtSignal(dict)               # one file result
    all_done = pyqtSignal(list)                # all results
    error = pyqtSignal(str)                    # error message
    token_update = pyqtSignal(int, int)        # prompt_tokens, completion_tokens

    def __init__(self, analyzer: MediaAnalyzer, directory: Path):
        ...

    def run(self):
        # Call analyzer.analyze_directory() with callbacks
        # Emit signals for each file completion
        # Handle cancellation via self._cancelled flag
        ...

    def cancel(self):
        self._cancelled = True
```

Connect signals to:
- Update progress bar
- Add/update row in results table
- Update token counter label
- Show error in status bar

---

### STEP 10 — Cache System
**Goal**: Avoid re-processing already analyzed files (saves tokens on re-runs).

- Cache file: `cache/cache.json` — dict of `{file_hash: result_dict}`
- Load on startup, save after each file
- In the results table, show a cache icon `⚡` for cached results
- Add "Clear Cache" button in Settings
- Cache is keyed by file hash (not filename) — robust to renames

---

### STEP 11 — Error Handling & Edge Cases

Handle all of these gracefully (show in UI, don't crash):
- API key not configured → show banner: "⚠️ API key not set. Go to Settings."
- API request fails / timeout → mark file as "API Error", show retry button
- Video has no audio → proceed with keyframes only, no transcript
- Video is corrupt / unreadable → mark as "Unreadable", skip
- Image is corrupt → mark as "Unreadable", skip  
- Output directory doesn't exist → create it on execute
- Proposed name collision → auto-suffix `_2`, `_3`
- GPU not available → fall back to CPU for Whisper, log warning in status bar
- API returns malformed JSON → retry once with stricter prompt, then use fallback

---

### STEP 12 — Final Polish & Packaging

1. Add `--cli` argument for headless mode (for scripting):
   ```bash
   python main.py --cli --source /path/to/media --output /path/out --limit 5 --dry-run
   ```

2. Add a log panel (collapsible) at the bottom showing:
   - Timestamps
   - Each step per file
   - API errors
   - Token usage per file

3. Create `install.sh`:
   ```bash
   #!/bin/bash
   # Install system deps
   sudo pacman -S python ffmpeg tesseract
   pip install -r requirements.txt
   # Check for CUDA
   python -c "import torch; print('CUDA:', torch.cuda.is_available())"
   ```

4. Create `README.md` with:
   - Setup instructions
   - Screenshot placeholder
   - How to get an API key for frogapi.app
   - Testing mode explanation

---

## SUMMARY OF LOCAL (FREE) vs API PROCESSING

| Task | Where | Cost |
|---|---|---|
| Keyframe extraction | OpenCV (local) | Free |
| Image resize | Pillow (local) | Free |
| Audio extraction | FFmpeg (local) | Free |
| Audio transcription | faster-whisper + CUDA | Free |
| Image OCR hints | Tesseract (local, optional) | Free |
| Image/video description | LLM API (gpt-5-nano) | Paid |
| Category + naming | LLM API (same call) | Paid |

**Estimated token usage per file** (testing mode helps validate this):
- Image: ~300–600 prompt tokens, ~100 completion tokens
- Video (8 frames + transcript): ~800–1500 prompt tokens, ~100 completion tokens

---

## DEFINITION OF DONE

The application is complete when:
- [ ] GUI launches cleanly on Arch Linux
- [ ] Settings dialog saves/loads API key and endpoint
- [ ] Testing mode limits to N files and shows token usage
- [ ] Images are analyzed and proposed names are shown in the table
- [ ] Videos are analyzed using keyframes + Whisper transcript
- [ ] Preview panel shows thumbnail + proposed rename + tags
- [ ] Dry run shows exact files that would be moved
- [ ] Execute only runs after explicit user confirmation
- [ ] Cache prevents re-processing already analyzed files
- [ ] GPU (CUDA) is used for Whisper when available
- [ ] App does not crash on corrupt/missing files
