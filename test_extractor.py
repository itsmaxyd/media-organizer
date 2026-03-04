#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.append('media_organizer')
from core.extractor import preprocess_image, extract_keyframes, extract_audio, file_hash
from core.local_processor import LocalProcessor

def test():
    # Test image
    img_path = Path('../0d188d80-f516-46ed-afae-eb9fa29901b9.png')
    if img_path.exists():
        processed = preprocess_image(img_path)
        print(f"Image processed: {len(processed)} bytes")
    else:
        print("Test image not found")

    # Test video
    video_path = Path('../rapidsave.com_a_girls_life_was_saved_just_in_time_thanks_to_the-hs1y1di8geaf1.mp4')
    if video_path.exists():
        keyframes = extract_keyframes(video_path)
        print(f"Number of keyframes: {len(keyframes)}")
        tmp_dir = Path('tmp')
        tmp_dir.mkdir(exist_ok=True)
        audio_path = extract_audio(video_path, tmp_dir)
        if audio_path:
            print(f"Audio extracted: {audio_path}")
            # Test transcription
            processor = LocalProcessor()
            transcript = processor.transcribe_audio(audio_path)
            print(f"Transcript (first 100 chars): {transcript[:100]}")
        else:
            print("No audio found")
    else:
        print("Test video not found")

if __name__ == '__main__':
    test()