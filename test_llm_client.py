#!/usr/bin/env python3
"""Test script for LLMClient with testing_mode=True, limit=1 file."""

import os
import sys
from pathlib import Path

# Add media_organizer to path
sys.path.insert(0, str(Path(__file__).parent))

from media_organizer.core.llm_client import LLMClient, Settings


def main():
    # Check for API key
    api_key = os.environ.get("OPENAI_API_KEY", "")
    
    if not api_key:
        print("WARNING: OPENAI_API_KEY environment variable is not set.")
        print("Skipping API test. Set the API key and run again.")
        return
    
    # Create settings with testing mode
    settings = Settings(
        api_key=api_key,
        testing_mode=True,
        testing_limit=1
    )
    
    # Initialize client
    client = LLMClient(settings)
    
    # Create a simple test image using PIL
    from PIL import Image
    import io
    
    img = Image.new('RGB', (100, 100), color='red')
    buffer = io.BytesIO()
    img.save(buffer, format='JPEG')
    image_bytes = buffer.getvalue()
    
    print(f"Created test image: {len(image_bytes)} bytes")
    
    # Send to API
    print("\nSending image to API...")
    result = client.describe_media(
        image_frames=[image_bytes],
        transcript="",
        ocr_hint="",
        media_type="image"
    )
    
    # Print result
    print("\n=== API Response ===")
    print(f"Category: {result.get('category')}")
    print(f"Subcategory: {result.get('subcategory')}")
    print(f"Descriptive name: {result.get('descriptive_name')}")
    print(f"Tags: {result.get('tags')}")
    print(f"Confidence: {result.get('confidence')}")
    print(f"Reasoning: {result.get('reasoning')}")
    
    # Print token usage
    usage = client.get_token_usage()
    print("\n=== Token Usage ===")
    print(f"Prompt tokens: {usage['prompt_tokens']}")
    print(f"Completion tokens: {usage['completion_tokens']}")
    print(f"Total tokens: {usage['total_tokens']}")


if __name__ == "__main__":
    main()
