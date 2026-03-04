import base64
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from openai import OpenAI

logger = logging.getLogger(__name__)


@dataclass
class Settings:
    """Settings configuration for the LLM client."""
    api_key: str = ""
    api_base_url: str = "https://frogapi.app/v1"
    model_name: str = "gpt-5-nano"
    source_dir: str = ""
    output_dir: str = ""
    testing_mode: bool = True
    testing_limit: int = 3
    keyframes_per_video: int = 8
    max_image_size_px: int = 512
    use_local_whisper: bool = True
    whisper_model: str = "base"
    dry_run: bool = True
    naming_template: str = "{category}/{descriptive_name}{ext}"


class LLMClient:
    """Thin wrapper around OpenAI SDK with custom endpoint."""

    def __init__(self, settings: Settings):
        """
        Initialize OpenAI client with custom endpoint.
        
        Args:
            settings: Settings instance containing API configuration
        """
        self.settings = settings
        self.model_name = settings.model_name
        self.client = OpenAI(
            api_key=settings.api_key,
            base_url=settings.api_base_url
        )
        self._prompt_tokens = 0
        self._completion_tokens = 0

    def describe_media(
        self,
        image_frames: list[bytes],
        transcript: str = "",
        ocr_hint: str = "",
        media_type: str = "image",
    ) -> dict:
        """
        Send media to LLM for analysis and categorization.
        
        Args:
            image_frames: List of JPEG bytes (1 image OR keyframes)
            transcript: Audio transcript from whisper or empty string
            ocr_hint: OCR text detected in image
            media_type: "image" or "video"
            
        Returns:
            dict with keys: category, subcategory, descriptive_name, tags, confidence, reasoning
        """
        # Build context block
        context_lines = [f"Analyze this {media_type}."]
        
        if transcript:
            context_lines.append(f"Audio transcript: {transcript[:500]}")
        
        if ocr_hint:
            context_lines.append(f"Visible text detected: {ocr_hint}")
        
        context_lines.append("")
        context_lines.append("""Return JSON with these exact keys:
{
  "category": "<single folder name, lowercase, no spaces, e.g. nature, food, receipts, people, pets, travel, gaming, documents, misc>",
  "subcategory": "<optional second level, or null>",
  "descriptive_name": "<2-4 word snake_case description, e.g. sunset_beach_waves>",
  "tags": ["tag1", "tag2"],
  "confidence": <0.0 to 1.0>,
  "reasoning": "<one sentence>"
}""")
        
        context_block = "\n".join(context_lines)
        
        # Build message content
        content = [{"type": "text", "text": context_block}]
        
        # Add image frames as base64
        for frame_bytes in image_frames:
            b64_data = base64.b64encode(frame_bytes).decode("utf-8")
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{b64_data}"
                }
            })
        
        messages = [
            {"role": "system", "content": "You are a media file analyzer. Respond ONLY in valid JSON."},
            {"role": "user", "content": content}
        ]
        
        # Try API call with one retry
        max_attempts = 2
        for attempt in range(max_attempts):
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    max_tokens=500
                )
                
                # Track token usage
                if response.usage:
                    self._prompt_tokens += response.usage.prompt_tokens
                    self._completion_tokens += response.usage.completion_tokens
                    logger.info(f"Token usage: prompt={response.usage.prompt_tokens}, completion={response.usage.completion_tokens}")
                
                # Parse JSON response
                result_text = response.choices[0].message.content
                result = json.loads(result_text)
                return result
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM response as JSON: {e}")
                if attempt < max_attempts - 1:
                    time.sleep(2)
                    continue
                return self._fallback_result()
                
            except Exception as e:
                logger.error(f"API error (attempt {attempt + 1}/{max_attempts}): {e}")
                if attempt < max_attempts - 1:
                    time.sleep(2)
                    continue
                return self._fallback_result()
        
        return self._fallback_result()

    def _fallback_result(self) -> dict:
        """Return fallback result when API fails."""
        return {
            "category": "misc",
            "subcategory": None,
            "descriptive_name": "unknown_file",
            "tags": [],
            "confidence": 0.0,
            "reasoning": "API call failed, using fallback categorization"
        }

    def get_token_usage(self) -> dict:
        """
        Return cumulative token counts for this session.
        
        Returns:
            dict with prompt_tokens and completion_tokens
        """
        return {
            "prompt_tokens": self._prompt_tokens,
            "completion_tokens": self._completion_tokens,
            "total_tokens": self._prompt_tokens + self._completion_tokens
        }
