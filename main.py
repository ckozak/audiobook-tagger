import re
from ebooklib import epub
from ebooklib import ITEM_DOCUMENT
from bs4 import BeautifulSoup
import sys
import json
from rapidfuzz import process, fuzz
import math

import re

def normalize(txt):
    txt = txt.lower()
    txt = re.sub(r'[^a-z0-9\s]', ' ', txt)
    txt = re.sub(r'\b(um|uh|you know|like)\b', ' ', txt)
    txt = re.sub(r'\s+', ' ', txt).strip()
    return txt

def format_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

def extract_chapter_snippets(epub_path):
    book = epub.read_epub(epub_path)
    chapters = []

    for item in book.get_items():
        if item.get_type() == ITEM_DOCUMENT:
            soup = BeautifulSoup(item.content, 'html.parser')
            
            # Find all heading tags that might mark chapters
            for heading in soup.find_all(['h1', 'h2', 'h3']):
                chapter_title = heading.get_text(strip=True)

                # Find the first paragraph AFTER the heading
                next_paragraph = heading.find_next_sibling()
                while next_paragraph and next_paragraph.name != 'p':
                    next_paragraph = next_paragraph.find_next_sibling()

                if next_paragraph and next_paragraph.name == 'p':
                    paragraph_text = next_paragraph.get_text(strip=True)
                    chapters.append({
                        "chapter": chapter_title,
                        "text": paragraph_text
                    })

    return chapters

# Example usage:

if __name__ == "__main__":
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print("Usage: python main.py <ebook.epub> [<transcript.json>]")
        sys.exit(1)

    epub_path = sys.argv[1]
    if len(sys.argv) == 2:
        # Only extract chapters from EPUB
        chapters = extract_chapter_snippets(epub_path)
        for ch in chapters:
            print(f"{ch['chapter']}: {ch['text']}")
        sys.exit(0)
    transcript_path = sys.argv[2]

    # Extract chapters and their first-paragraph snippets
    chapters = extract_chapter_snippets(epub_path)

    # Load the transcript JSON (list of segments with 'text', 'start', 'end')
    with open(transcript_path, "r", encoding="utf-8") as f:
        transcript = json.load(f)

    # Precompute normalized text for each segment
    for seg in transcript:
        seg['norm_text'] = normalize(seg['text'])

    # Compute average length of normalized transcript segments for dynamic window sizing
    total_norm_len = sum(len(seg["norm_text"]) for seg in transcript)
    avg_seg_len = total_norm_len / len(transcript) if transcript else 1

    last_end = -1.0

    for ch in chapters:
        snippet = ch["text"]
        snippet_norm = normalize(snippet)
        snippet_len = len(snippet_norm)
        # Determine dynamic window size based on snippet length
        window_size = max(1, math.ceil(snippet_len / avg_seg_len))
        best_score = 0
        best_start_idx = None
        best_end_idx = None

        # Search through transcript segments
        for i, seg in enumerate(transcript):
            start_time = seg["start"]
            if start_time < last_end:
                continue

            combined_norm = ""
            # Try combining up to window_size segments
            for j in range(i, min(i + window_size, len(transcript))):
                combined_norm += transcript[j]["norm_text"] + " "
                score = fuzz.partial_ratio(snippet_norm, combined_norm)
                if score > best_score:
                    best_score = score
                    best_start_idx = i
                    best_end_idx = j

        # Print results
        print(f"Chapter: {ch['chapter']}")
        if best_start_idx is not None:
            start_ts = transcript[best_start_idx]["start"]
            end_ts = transcript[best_end_idx]["end"]
            print(f"  Confidence: {best_score}")
            print(f"  Start time: {format_time(start_ts)}")
            print(f"  End time:   {format_time(end_ts)}\n")
            # Show matched and source snippets for debugging
            epub_snippet = snippet.strip()
            matched_raw = " ".join(seg["text"] for seg in transcript[best_start_idx:best_end_idx+1]).strip()
            print(f"  EPUB paragraph snippet: {epub_snippet}")
            print(f"  Matched transcript snippet: {matched_raw}\n")
            last_end = end_ts
        else:
            print("  No suitable match found.\n")