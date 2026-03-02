#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "youtube-transcript-api>=1.0.0",
# ]
# ///
"""Fetch YouTube video transcript and metadata.
Usage: uv run get_transcript.py <youtube_url_or_id>
"""

import sys
import re
import json


def extract_video_id(url_or_id: str) -> str:
    """Extract video ID from URL or return as-is if already an ID."""
    patterns = [
        r"(?:v=|youtu\.be/|embed/|shorts/)([a-zA-Z0-9_-]{11})",
        r"^([a-zA-Z0-9_-]{11})$",
    ]
    for pattern in patterns:
        match = re.search(pattern, url_or_id)
        if match:
            return match.group(1)
    raise ValueError(f"Could not extract video ID from: {url_or_id}")


def get_transcript(video_id: str) -> dict:
    from youtube_transcript_api import YouTubeTranscriptApi

    api = YouTubeTranscriptApi()

    try:
        try:
            data = api.fetch(video_id, languages=["en", "en-US", "en-GB"])
        except Exception:
            transcript_list = api.list(video_id)
            first = next(iter(transcript_list))
            data = api.fetch(video_id, languages=[first.language_code])

        entries = list(data)
        full_text = " ".join([e.text for e in entries])
        duration_seconds = entries[-1].start + getattr(entries[-1], "duration", 0) if entries else 0

        return {
            "video_id": video_id,
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "duration_minutes": round(duration_seconds / 60, 1),
            "word_count": len(full_text.split()),
            "transcript": full_text,
            "segments": [{"start": e.start, "text": e.text} for e in entries],
        }

    except Exception as e:
        return {
            "video_id": video_id,
            "error": str(e),
        }


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 get_transcript.py <url1> [url2] [url3] ...")
        sys.exit(1)

    inputs = sys.argv[1:]

    results = []
    for input_val in inputs:
        try:
            video_id = extract_video_id(input_val)
            result = get_transcript(video_id)
        except ValueError as e:
            result = {"input": input_val, "error": str(e)}
        results.append(result)

    if len(results) == 1:
        print(json.dumps(results[0], ensure_ascii=False, indent=2))
    else:
        print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
