import base64
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from openai import OpenAI, APIError, APITimeoutError

logger = logging.getLogger(__name__)


class APIKeyError(Exception):
    """Raised when API key is not configured."""
    pass


class APICallError(Exception):
    """Raised when API call fails after retries."""
    def __init__(self, message: str, status: str = "api_error"):
        super().__init__(message)
        self.status = status


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
            
        Raises:
            APIKeyError: If API key is not configured
        """
        self.settings = settings
        self.model_name = settings.model_name
        
        # Validate API key
        if not settings.api_key or settings.api_key.strip() == "":
            raise APIKeyError("API key is not configured")
        
        self.client = OpenAI(
            api_key=settings.api_key,
            base_url=settings.api_base_url
        )
        self._prompt_tokens = 0
        self._completion_tokens = 0
        
    def is_api_key_configured(self) -> bool:
        """Check if API key is properly configured."""
        return bool(self.settings.api_key and self.settings.api_key.strip())

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
            
        Raises:
            APICallError: If API call fails after all retries
        """
        # Check API key first
        if not self.is_api_key_configured():
            raise APIKeyError("API key is not configured. Go to Settings.")
        
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
        
        # Stricter prompt for retry
        strict_messages = [
            {"role": "system", "content": "You are a media file analyzer. You MUST respond with valid JSON only. No markdown, no explanations outside JSON."},
            {"role": "user", "content": content + [{"type": "text", "text": "\n\nIMPORTANT: Return ONLY valid JSON. Do not wrap in markdown code blocks."}]}
        ]
        
        # Try API call with retry logic
        max_attempts = 2
        last_error = None
        
        for attempt in range(max_attempts):
            try:
                # Use stricter prompt on retry
                current_messages = strict_messages if attempt > 0 else messages
                
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=current_messages,
                    max_tokens=500,
                    timeout=60  # 60 second timeout
                )
                
                # Track token usage
                if response.usage:
                    self._prompt_tokens += response.usage.prompt_tokens
                    self._completion_tokens += response.usage.completion_tokens
                    logger.info(f"Token usage: prompt={response.usage.prompt_tokens}, completion={response.usage.completion_tokens}")
                
                # Parse JSON response
                result_text = response.choices[0].message.content.strip()
                
                # Clean up markdown code blocks if present
                if result_text.startswith("```json"):
                    result_text = result_text[7:]
                elif result_text.startswith("```"):
                    result_text = result_text[3:]
                if result_text.endswith("```"):
                    result_text = result_text[:-3]
                result_text = result_text.strip()
                
                result = json.loads(result_text)
                
                # Validate required fields
                required_fields = ["category", "descriptive_name", "tags", "confidence", "reasoning"]
                for field in required_fields:
                    if field not in result:
                        raise ValueError(f"Missing required field: {field}")
                
                return result
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM response as JSON (attempt {attempt + 1}/{max_attempts}): {e}")
                last_error = e
                if attempt < max_attempts - 1:
                    logger.info("Retrying with stricter prompt...")
                    time.sleep(2)
                    continue
                # Return fallback after all retries
                return self._fallback_result()
                
            except (APIError, APITimeoutError) as e:
                logger.error(f"API error (attempt {attempt + 1}/{max_attempts}): {e}")
                last_error = e
                if attempt < max_attempts - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                    continue
                raise APICallError(f"API call failed after {max_attempts} attempts: {e}", status="api_error")
                
            except Exception as e:
                logger.error(f"Unexpected error (attempt {attempt + 1}/{max_attempts}): {e}")
                last_error = e
                if attempt < max_attempts - 1:
                    time.sleep(2)
                    continue
                raise APICallError(f"API call failed: {e}", status="api_error")
        
        # If we get here, all attempts failed
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
