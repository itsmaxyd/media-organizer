"""Worker thread for running media analysis without freezing the GUI."""

import logging
from pathlib import Path
from typing import Callable, List, Dict, Optional
from dataclasses import dataclass

from PyQt5.QtCore import QThread, pyqtSignal

from ..core.llm_client import LLMClient, Settings
from ..core.extractor import preprocess_image, extract_keyframes, extract_audio, file_hash
from ..core.local_processor import LocalProcessor
from ..core.cache_manager import CacheManager

logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    """Result of analyzing a single media file."""
    source: str
    category: str
    subcategory: Optional[str]
    descriptive_name: str
    tags: List[str]
    confidence: float
    reasoning: str
    status: str = "pending"


class MediaAnalyzer:
    """Analyzes media files using LLM and local processing."""
    
    def __init__(self, settings: Settings, cache_manager: Optional[CacheManager] = None):
        """
        Initialize the analyzer with settings.
        
        Args:
            settings: Settings instance containing API configuration
            cache_manager: Optional CacheManager instance for caching results
        """
        self.settings = settings
        self.llm_client = LLMClient(settings)
        self.local_processor: Optional[LocalProcessor] = None
        self.cache_manager = cache_manager or CacheManager()
        
        if settings.use_local_whisper:
            try:
                self.local_processor = LocalProcessor(settings.whisper_model)
            except ImportError:
                logger.warning("Local whisper not available, audio transcription disabled")
    
    def analyze_directory(
        self,
        directory: Path,
        progress_callback: Callable[[int, int, Dict], None],
        file_done_callback: Callable[[Dict], None],
        token_callback: Callable[[int, int], None],
        should_cancel: Callable[[], bool]
    ) -> List[Dict]:
        """
        Analyze all media files in a directory.
        
        Args:
            directory: Path to directory containing media files
            progress_callback: Called with (current, total, partial_result) during processing
            file_done_callback: Called with result dict when a file is completed
            token_callback: Called with (prompt_tokens, completion_tokens) for each file
            should_cancel: Function that returns True if analysis should be cancelled
            
        Returns:
            List of analysis result dictionaries
        """
        # Collect media files
        media_files = []
        for ext in ["*.jpg", "*.jpeg", "*.png", "*.gif", "*.mp4", "*.mov", "*.avi"]:
            media_files.extend(directory.glob(ext))
        
        # Apply testing limit if in testing mode
        if self.settings.testing_mode and self.settings.testing_limit > 0:
            media_files = media_files[:self.settings.testing_limit]
        
        results = []
        total = len(media_files)
        
        for i, file_path in enumerate(media_files):
            # Check for cancellation
            if should_cancel():
                logger.info("Analysis cancelled by user")
                break
            
            try:
                # Check cache first
                file_hash_val = file_hash(file_path)
                cached_result = self.cache_manager.get(file_hash_val)
                
                if cached_result:
                    # Use cached result
                    result = dict(cached_result)
                    result["cached"] = True
                    logger.info(f"Using cached result for {file_path.name}")
                else:
                    # Analyze and cache result
                    result = self._analyze_single_file(file_path)
                    result["cached"] = False
                    # Store in cache (without the cached flag)
                    cache_data = {k: v for k, v in result.items() if k != "cached"}
                    self.cache_manager.set(file_hash_val, cache_data)
                
                results.append(result)
                
                # Report progress
                progress_callback(i + 1, total, result)
                file_done_callback(result)
                
                # Report token usage (only for non-cached results)
                if not result.get("cached", False):
                    token_usage = self.llm_client.get_token_usage()
                    token_callback(token_usage["prompt_tokens"], token_usage["completion_tokens"])
                
            except Exception as e:
                logger.error(f"Failed to analyze {file_path}: {e}")
                error_result = {
                    "source": str(file_path),
                    "category": "misc",
                    "subcategory": None,
                    "descriptive_name": file_path.stem,
                    "tags": [],
                    "confidence": 0.0,
                    "reasoning": f"Error: {str(e)}",
                    "status": "error"
                }
                results.append(error_result)
                progress_callback(i + 1, total, error_result)
                file_done_callback(error_result)
        
        return results
    
    def _analyze_single_file(self, file_path: Path) -> Dict:
        """
        Analyze a single media file.
        
        Args:
            file_path: Path to the media file
            
        Returns:
            Dictionary with analysis results
        """
        file_path = Path(file_path)
        is_video = file_path.suffix.lower() in [".mp4", ".mov", ".avi"]
        
        # Prepare image frames
        if is_video:
            frames = extract_keyframes(file_path, self.settings.keyframes_per_video)
        else:
            frames = [preprocess_image(file_path, self.settings.max_image_size_px)]
        
        # Get transcript for videos
        transcript = ""
        if is_video and self.local_processor:
            import tempfile
            with tempfile.TemporaryDirectory() as tmp_dir:
                audio_path = extract_audio(file_path, Path(tmp_dir))
                if audio_path:
                    transcript = self.local_processor.transcribe_audio(audio_path)
        
        # Get OCR hint for images
        ocr_hint = ""
        if not is_video and self.local_processor:
            ocr_hint = self.local_processor.get_image_ocr_hint(frames[0])
        
        # Call LLM for analysis
        llm_result = self.llm_client.describe_media(
            image_frames=frames,
            transcript=transcript,
            ocr_hint=ocr_hint,
            media_type="video" if is_video else "image"
        )
        
        # Build result
        result = {
            "source": str(file_path),
            "category": llm_result.get("category", "misc"),
            "subcategory": llm_result.get("subcategory"),
            "descriptive_name": llm_result.get("descriptive_name", file_path.stem),
            "tags": llm_result.get("tags", []),
            "confidence": llm_result.get("confidence", 0.0),
            "reasoning": llm_result.get("reasoning", ""),
            "status": "pending"
        }
        
        return result


class AnalysisWorker(QThread):
    """Worker thread for running analysis without freezing the GUI."""
    
    progress = pyqtSignal(int, int, dict)      # current, total, result
    file_done = pyqtSignal(dict)               # one file result
    all_done = pyqtSignal(list)                # all results
    error = pyqtSignal(str)                    # error message
    token_update = pyqtSignal(int, int)        # prompt_tokens, completion_tokens
    
    def __init__(self, analyzer: MediaAnalyzer, directory: Path):
        """
        Initialize the worker thread.
        
        Args:
            analyzer: MediaAnalyzer instance to use for analysis
            directory: Path to directory containing media files
        """
        super().__init__()
        self.analyzer = analyzer
        self.directory = directory
        self._cancelled = False
    
    def run(self):
        """Run the analysis in the background thread."""
        try:
            results = self.analyzer.analyze_directory(
                directory=self.directory,
                progress_callback=self._on_progress,
                file_done_callback=self._on_file_done,
                token_callback=self._on_token_update,
                should_cancel=lambda: self._cancelled
            )
            self.all_done.emit(results)
        except Exception as e:
            logger.exception("Analysis failed")
            self.error.emit(str(e))
    
    def _on_progress(self, current: int, total: int, result: Dict):
        """Handle progress updates from the analyzer."""
        self.progress.emit(current, total, result)
    
    def _on_file_done(self, result: Dict):
        """Handle file completion from the analyzer."""
        self.file_done.emit(result)
    
    def _on_token_update(self, prompt_tokens: int, completion_tokens: int):
        """Handle token usage updates from the analyzer."""
        self.token_update.emit(prompt_tokens, completion_tokens)
    
    def cancel(self):
        """Request cancellation of the analysis."""
        self._cancelled = True
