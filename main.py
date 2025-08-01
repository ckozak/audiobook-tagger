from ebooklib import epub
from ebooklib import ITEM_DOCUMENT
from bs4 import BeautifulSoup
import sys
import json
from rapidfuzz import process, fuzz

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
    if len(sys.argv) != 3:
        print("Usage: python main.py <ebook.epub> <transcript.json>")
        sys.exit(1)

    epub_path = sys.argv[1]
    transcript_path = sys.argv[2]

    # Extract chapters and their first-paragraph snippets
    chapters = extract_chapter_snippets(epub_path)

    # Load the transcript JSON (list of segments with 'text', 'start', 'end')
    with open(transcript_path, "r", encoding="utf-8") as f:
        transcript = json.load(f)

    # Prepare list of transcript texts for matching
    texts = [seg["text"] for seg in transcript]

    # Fuzzy match each chapter snippet to the transcript to find timestamps,
    # combining up to 5 consecutive segments and enforcing increasing timestamps.
    last_end = -1.0
    MAX_WINDOW = 5

    for ch in chapters:
        snippet = ch["text"]
        best_score = 0
        best_start_idx = None
        best_end_idx = None

        # Search through transcript segments
        for i, seg in enumerate(transcript):
            start_time = seg["start"]
            if start_time < last_end:
                continue

            combined = ""
            # Try combining up to MAX_WINDOW segments
            for j in range(i, min(i + MAX_WINDOW, len(transcript))):
                combined += transcript[j]["text"] + " "
                score = fuzz.partial_ratio(snippet, combined)
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
            print(f"  Start time: {start_ts}s")
            print(f"  End time:   {end_ts}s\n")
            last_end = end_ts
        else:
            print("  No suitable match found.\n")