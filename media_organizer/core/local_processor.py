import logging
from pathlib import Path
from typing import Optional, Tuple
import torch
import warnings

try:
    from faster_whisper import WhisperModel
except ImportError:
    WhisperModel = None

try:
    import pytesseract
    from PIL import Image
    import io
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

logger = logging.getLogger(__name__)


class LocalProcessor:
    """Local processor for audio transcription and OCR."""
    
    def __init__(self, whisper_model: str = "base", device: Optional[str] = None):
        """
        Load faster-whisper WhisperModel with automatic device fallback.
        
        Args:
            whisper_model: Name of the whisper model to use (e.g., "base", "small")
            device: Preferred device ("cuda" or "cpu"). If None, auto-detects.
                   Falls back to CPU if CUDA is not available or fails.
        """
        if WhisperModel is None:
            raise ImportError("faster-whisper is not installed")

        # Determine device with fallback
        requested_device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.device, self.compute_type, self.fallback_reason = self._determine_device(
            requested_device, whisper_model
        )
        
        if self.fallback_reason:
            logger.warning(self.fallback_reason)
        
        logger.info(f"Loading WhisperModel '{whisper_model}' on device '{self.device}' with compute_type '{self.compute_type}'")
        
        try:
            self.model = WhisperModel(whisper_model, device=self.device, compute_type=self.compute_type)
            logger.info("WhisperModel loaded successfully")
        except RuntimeError as e:
            if "CUDA" in str(e) and self.device == "cuda":
                logger.warning(f"CUDA initialization failed: {e}. Falling back to CPU.")
                self.device = "cpu"
                self.compute_type = "int8"
                self.fallback_reason = f"GPU not available: {e}. Using CPU."
                self.model = WhisperModel(whisper_model, device=self.device, compute_type=self.compute_type)
                logger.info("WhisperModel loaded successfully on CPU")
            else:
                raise
    
    def _determine_device(self, requested_device: str, model_name: str) -> Tuple[str, str, Optional[str]]:
        """
        Determine the best device and compute type with fallback logic.
        
        Returns:
            Tuple of (device, compute_type, fallback_reason or None)
        """
        fallback_reason = None
        
        if requested_device == "cuda":
            if not torch.cuda.is_available():
                fallback_reason = "GPU not available (CUDA not detected). Using CPU."
                return "cpu", "int8", fallback_reason
            
            # Check GPU memory (rough estimate)
            try:
                gpu_memory = torch.cuda.get_device_properties(0).total_memory / (1024**3)  # GB
                if gpu_memory < 2.0:  # Less than 2GB VRAM
                    fallback_reason = f"GPU has insufficient memory ({gpu_memory:.1f}GB). Using CPU."
                    return "cpu", "int8", fallback_reason
            except Exception as e:
                logger.warning(f"Could not check GPU memory: {e}")
            
            # CUDA is available and seems sufficient
            return "cuda", "float16", None
        
        # CPU requested or fallback
        return "cpu", "int8", fallback_reason
    
    def is_using_gpu(self) -> bool:
        """Check if currently using GPU acceleration."""
        return self.device == "cuda"
    
    def get_device_info(self) -> dict:
        """Get information about the current device configuration."""
        return {
            "device": self.device,
            "compute_type": self.compute_type,
            "using_gpu": self.is_using_gpu(),
            "fallback_reason": self.fallback_reason
        }

    def transcribe_audio(self, wav_path: Path) -> str:
        """
        - Transcribe WAV file
        - Join all segment texts
        - Truncate to 500 words max (sufficient for context, saves tokens)
        - Return empty string on failure
        """
        try:
            segments, info = self.model.transcribe(str(wav_path))
            text = " ".join([segment.text for segment in segments])
            words = text.split()
            if len(words) > 500:
                text = " ".join(words[:500])
            return text
        except Exception as e:
            logger.error(f"Transcription failed for {wav_path}: {e}")
            return ""

    def get_image_ocr_hint(self, image_bytes: bytes) -> str:
        """
        - OPTIONAL: Use pytesseract if installed to extract any visible text
        - Return empty string if tesseract not available
        - This is a bonus hint, not required
        """
        if not TESSERACT_AVAILABLE:
            return ""
        try:
            image = Image.open(io.BytesIO(image_bytes))
            text = pytesseract.image_to_string(image)
            return text.strip()
        except Exception as e:
            logger.error(f"OCR failed: {e}")
            return ""