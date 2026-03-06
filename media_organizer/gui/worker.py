"""Worker thread for running media analysis without freezing the GUI."""

import logging
from pathlib import Path
from typing import Callable, List, Dict, Optional
from dataclasses import dataclass

from PyQt5.QtCore import QThread, pyqtSignal

from ..core.llm_client import LLMClient, Settings, APIKeyError, APICallError
from ..core.extractor import preprocess_image, extract_keyframes, extract_audio, file_hash, ExtractionError
from ..core.local_processor import LocalProcessor
from ..core.cache_manager import CacheManager
from ..core.organizer import OrganizerError

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
    error_type: Optional[str] = None
    retryable: bool = False
    error_message: Optional[str] = None


class AnalysisError(Exception):
    """Custom exception for analysis errors with context."""
    def __init__(self, message: str, error_type: str = "error", retryable: bool = False):
        super().__init__(message)
        self.error_type = error_type
        self.retryable = retryable


class MediaAnalyzer:
    """Analyzes media files using LLM and local processing."""
    
    def __init__(self, settings: Settings, cache_manager: Optional[CacheManager] = None):
        """
        Initialize the analyzer with settings.
        
        Args:
            settings: Settings instance containing API configuration
            cache_manager: Optional CacheManager instance for caching results
            
        Raises:
            APIKeyError: If API key is not configured
        """
        self.settings = settings
        self.llm_client = LLMClient(settings)
        self.local_processor: Optional[LocalProcessor] = None
        self.cache_manager = cache_manager or CacheManager()
        self._gpu_fallback_notified = False
        
        if settings.use_local_whisper:
            try:
                self.local_processor = LocalProcessor(settings.whisper_model)
                # Check if we fell back to CPU
                if self.local_processor and not self.local_processor.is_using_gpu():
                    device_info = self.local_processor.get_device_info()
                    if device_info.get("fallback_reason"):
                        logger.warning(device_info["fallback_reason"])
            except ImportError:
                logger.warning("Local whisper not available, audio transcription disabled")
            except Exception as e:
                logger.error(f"Failed to initialize local processor: {e}")
                self.local_processor = None
    
    def _create_error_result(
        self, 
        file_path: Path, 
        error_msg: str, 
        error_type: str = "error",
        retryable: bool = False
    ) -> Dict:
        """Create a standardized error result dict."""
        return {
            "source": str(file_path),
            "category": "misc",
            "subcategory": None,
            "descriptive_name": file_path.stem,
            "tags": [],
            "confidence": 0.0,
            "reasoning": error_msg,
            "status": "error",
            "error_type": error_type,
            "retryable": retryable,
            "error_message": error_msg
        }
    
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
                
            except ExtractionError as e:
                # Handle corrupt/unreadable files
                logger.warning(f"Extraction error for {file_path}: {e}")
                error_result = self._create_error_result(
                    file_path, 
                    str(e), 
                    error_type=e.status,
                    retryable=False
                )
                results.append(error_result)
                progress_callback(i + 1, total, error_result)
                file_done_callback(error_result)
                
            except APIKeyError as e:
                # API key not configured - fatal error
                logger.error(f"API key error: {e}")
                error_result = self._create_error_result(
                    file_path,
                    "API key not configured. Go to Settings.",
                    error_type="api_key",
                    retryable=False
                )
                results.append(error_result)
                progress_callback(i + 1, total, error_result)
                file_done_callback(error_result)
                # Stop processing further files
                break
                
            except APICallError as e:
                # API call failed after retries
                logger.error(f"API call error for {file_path}: {e}")
                error_result = self._create_error_result(
                    file_path,
                    str(e),
                    error_type=e.status,
                    retryable=True
                )
                results.append(error_result)
                progress_callback(i + 1, total, error_result)
                file_done_callback(error_result)
                
            except Exception as e:
                logger.error(f"Failed to analyze {file_path}: {e}")
                error_result = self._create_error_result(
                    file_path,
                    f"Unexpected error: {str(e)}",
                    error_type="error",
                    retryable=True
                )
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
            
        Raises:
            ExtractionError: If video/image is corrupt/unreadable
            APIKeyError: If API key is not configured
            APICallError: If API call fails
        """
        file_path = Path(file_path)
        is_video = file_path.suffix.lower() in [".mp4", ".mov", ".avi"]
        
        # Check GPU fallback once per analysis session
        if (self.local_processor and not self.local_processor.is_using_gpu() 
            and not self._gpu_fallback_notified):
            device_info = self.local_processor.get_device_info()
            if device_info.get("fallback_reason"):
                self._gpu_fallback_notified = True
                # Return a special result to notify about GPU fallback
                gpu_result = self._create_error_result(
                    file_path,
                    device_info["fallback_reason"],
                    error_type="gpu_fallback",
                    retryable=False
                )
                # Continue with actual analysis after this notification
                # The GUI will show this as a status message
        
        # Prepare image frames
        if is_video:
            frames = extract_keyframes(file_path, self.settings.keyframes_per_video)
        else:
            frames = [preprocess_image(file_path, self.settings.max_image_size_px)]
        
        # Get transcript for videos (proceed without audio if none exists)
        transcript = ""
        if is_video and self.local_processor:
            import tempfile
            with tempfile.TemporaryDirectory() as tmp_dir:
                try:
                    audio_path = extract_audio(file_path, Path(tmp_dir))
                    if audio_path:
                        transcript = self.local_processor.transcribe_audio(audio_path)
                    # If audio_path is None, video has no audio - proceed with keyframes only
                except ExtractionError:
                    # Video is corrupt, will be handled below
                    raise
                except Exception as e:
                    logger.warning(f"Audio extraction/transcription failed for {file_path}: {e}")
                    # Continue without transcript
        
        # Get OCR hint for images
        ocr_hint = ""
        if not is_video and self.local_processor and frames:
            try:
                ocr_hint = self.local_processor.get_image_ocr_hint(frames[0])
            except Exception as e:
                logger.warning(f"OCR failed for {file_path}: {e}")
                # Continue without OCR hint
        
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
            "status": "pending",
            "error_type": None,
            "retryable": False
        }
        
        # If we had a GPU fallback notification, include it
        if hasattr(self, '_gpu_fallback_notified') and self._gpu_fallback_notified:
            device_info = self.local_processor.get_device_info()
            if device_info.get("fallback_reason"):
                result["_gpu_fallback_notice"] = device_info["fallback_reason"]
        
        return result


class AnalysisWorker(QThread):
    """Worker thread for running analysis without freezing the GUI."""
    
    progress = pyqtSignal(int, int, dict)           # current, total, result
    file_done = pyqtSignal(dict)                    # one file result
    all_done = pyqtSignal(list)                     # all results
    error = pyqtSignal(str, str)                    # error message, error type
    token_update = pyqtSignal(int, int)             # prompt_tokens, completion_tokens
    gpu_fallback = pyqtSignal(str)                  # GPU fallback message
    
    def __init__(self, analyzer: MediaAnalyzer, directory: Path, retry_files: Optional[List[Path]] = None):
        """
        Initialize the worker thread.
        
        Args:
            analyzer: MediaAnalyzer instance to use for analysis
            directory: Path to directory containing media files
            retry_files: Optional list of specific files to retry
        """
        super().__init__()
        self.analyzer = analyzer
        self.directory = directory
        self.retry_files = retry_files
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
        except APIKeyError as e:
            logger.error(f"API key error: {e}")
            self.error.emit(str(e), "api_key")
        except APICallError as e:
            logger.error(f"API call error: {e}")
            self.error.emit(str(e), "api_error")
        except Exception as e:
            logger.exception("Analysis failed")
            self.error.emit(str(e), "error")
    
    def _on_progress(self, current: int, total: int, result: Dict):
        """Handle progress updates from the analyzer."""
        self.progress.emit(current, total, result)
        
        # Check for GPU fallback notification
        if result.get("_gpu_fallback_notice"):
            self.gpu_fallback.emit(result["_gpu_fallback_notice"])
    
    def _on_file_done(self, result: Dict):
        """Handle file completion from the analyzer."""
        self.file_done.emit(result)
        
        # Check for GPU fallback notification
        if result.get("_gpu_fallback_notice"):
            self.gpu_fallback.emit(result["_gpu_fallback_notice"])
    
    def _on_token_update(self, prompt_tokens: int, completion_tokens: int):
        """Handle token usage updates from the analyzer."""
        self.token_update.emit(prompt_tokens, completion_tokens)
    
    def cancel(self):
        """Request cancellation of the analysis."""
        self._cancelled = True
