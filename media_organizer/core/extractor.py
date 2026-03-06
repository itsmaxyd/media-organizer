import cv2
from PIL import Image
import ffmpeg
import hashlib
from pathlib import Path
import logging
from io import BytesIO

logger = logging.getLogger(__name__)

class ExtractionError(Exception):
    """Custom exception for extraction errors with status."""
    def __init__(self, message: str, status: str = "error"):
        super().__init__(message)
        self.status = status


def preprocess_image(path: Path, max_size: int = 512) -> bytes:
    """
    - Open image with Pillow
    - Resize so longest side = max_size (preserve aspect ratio)
    - Convert to RGB if needed (handle RGBA, palette modes)
    - Return as JPEG bytes (quality=85)
    - DO NOT modify original file
    - Raises ExtractionError if image is corrupt/unreadable
    """
    try:
        with Image.open(path) as img:
            # Verify the image is valid by loading it
            img.verify()
        
        # Re-open after verify (verify closes the file)
        with Image.open(path) as img:
            img = img.convert('RGB')
            if img.width > img.height:
                new_width = max_size
                new_height = int(img.height * max_size / img.width)
            else:
                new_height = max_size
                new_width = int(img.width * max_size / img.height)
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            buffer = BytesIO()
            img.save(buffer, format='JPEG', quality=85)
            return buffer.getvalue()
    except (IOError, OSError, Image.UnidentifiedImageError) as e:
        logger.warning(f"Corrupt or unreadable image {path}: {e}")
        raise ExtractionError(f"Corrupt or unreadable image: {e}", status="unreadable")
    except Exception as e:
        logger.error(f"Failed to preprocess image {path}: {e}")
        raise ExtractionError(f"Failed to preprocess image: {e}", status="error")

def extract_keyframes(video_path: Path, n_frames: int = 8) -> list[bytes]:
    """
    - Use OpenCV (cv2) to open video
    - Get total frame count and FPS
    - Evenly sample n_frames timestamps across duration
    - Skip first 2% and last 2% of video (avoid black frames)
    - For each timestamp: seek, grab frame, convert BGR→RGB
    - Resize each frame to max 512px longest side
    - Return list of JPEG bytes
    - Raises ExtractionError for corrupt/unreadable videos
    """
    cap = None
    try:
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise ExtractionError(f"Cannot open video file: {video_path}", status="unreadable")
        
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        
        if fps == 0 or total_frames == 0:
            raise ExtractionError(f"Video has no frames or invalid FPS: {video_path}", status="unreadable")
        
        duration = total_frames / fps
        start_time = duration * 0.02
        end_time = duration * 0.98
        
        if n_frames == 1:
            timestamps = [start_time + (end_time - start_time) / 2]
        else:
            timestamps = [start_time + i * (end_time - start_time) / (n_frames - 1) for i in range(n_frames)]
        
        frames = []
        for ts in timestamps:
            frame_num = int(ts * fps)
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
            ret, frame = cap.read()
            if ret:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w = frame.shape[:2]
                if w > h:
                    new_w = 512
                    new_h = int(h * 512 / w)
                else:
                    new_h = 512
                    new_w = int(w * 512 / h)
                frame = cv2.resize(frame, (new_w, new_h))
                _, buffer = cv2.imencode('.jpg', cv2.cvtColor(frame, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 85])
                frames.append(buffer.tobytes())
        
        if not frames:
            raise ExtractionError(f"Could not extract any frames from video: {video_path}", status="unreadable")
        
        return frames
        
    except ExtractionError:
        raise
    except Exception as e:
        logger.error(f"Failed to extract keyframes from {video_path}: {e}")
        raise ExtractionError(f"Failed to extract keyframes: {e}", status="unreadable")
    finally:
        if cap is not None:
            cap.release()

def extract_audio(video_path: Path, tmp_dir: Path) -> Path | None:
    """
    - Use ffmpeg-python to extract audio track to tmp WAV (16kHz mono)
    - If video has no audio stream, return None (not an error)
    - Store in tmp_dir with hashed filename
    - Return path to WAV file or None
    - Raises ExtractionError for corrupt/unreadable videos
    """
    try:
        probe = ffmpeg.probe(str(video_path))
        audio_streams = [s for s in probe['streams'] if s['codec_type'] == 'audio']
        
        if not audio_streams:
            logger.info(f"Video has no audio stream: {video_path}")
            return None
        
        hash_name = file_hash(video_path)[:16] + '.wav'
        output_path = tmp_dir / hash_name
        
        try:
            ffmpeg.input(str(video_path)).output(str(output_path), ac=1, ar=16000, f='wav').run(quiet=True, overwrite_output=True)
            return output_path
        except ffmpeg.Error as e:
            stderr = e.stderr.decode('utf-8') if e.stderr else str(e)
            if "No such file" in stderr or "Invalid data" in stderr:
                raise ExtractionError(f"Corrupt video file: {stderr}", status="unreadable")
            # Audio extraction failed but video might still be valid
            logger.warning(f"Audio extraction failed for {video_path}: {stderr}")
            return None
            
    except ExtractionError:
        raise
    except ffmpeg.Error as e:
        stderr = e.stderr.decode('utf-8') if e.stderr else str(e)
        logger.error(f"FFmpeg error processing {video_path}: {stderr}")
        raise ExtractionError(f"Video file unreadable: {stderr}", status="unreadable")
    except Exception as e:
        logger.error(f"Failed to extract audio from {video_path}: {e}")
        return None  # Audio extraction failure is not fatal

def file_hash(path: Path) -> str:
    """SHA256 of first 1MB + file size — fast fingerprint for caching"""
    hash_obj = hashlib.sha256()
    with open(path, 'rb') as f:
        chunk = f.read(1024 * 1024)  # 1MB
        hash_obj.update(chunk)
        size = path.stat().st_size
        hash_obj.update(str(size).encode())
    return hash_obj.hexdigest()