import logging
from pathlib import Path
from typing import Optional
import torch

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
    def __init__(self, whisper_model: str = "base", device: str = "cuda"):
        """
        - Load faster-whisper WhisperModel
        - device: "cuda" if torch.cuda.is_available() else "cpu"
        - compute_type: "float16" for CUDA (980 Ti supports fp16), "int8" for CPU
        - Log which device is being used
        """
        if WhisperModel is None:
            raise ImportError("faster-whisper is not installed")

        self.device = device if torch.cuda.is_available() else "cpu"
        compute_type = "float16" if self.device == "cuda" else "int8"

        logger.info(f"Loading WhisperModel '{whisper_model}' on device '{self.device}' with compute_type '{compute_type}'")
        self.model = WhisperModel(whisper_model, device=self.device, compute_type=compute_type)
        logger.info("WhisperModel loaded successfully")

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