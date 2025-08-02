import sys
import json
import re
import argparse
from ebooklib import epub
from ebooklib import ITEM_DOCUMENT
from bs4 import BeautifulSoup
import torch
from sentence_transformers import SentenceTransformer, util

# Configuration
MIN_SNIPPET_CHARS = 200
MAX_SNIPPET_PARAS = 3
CONFIDENCE_THRESHOLD = 65.0 # Minimum similarity score to consider a match

def normalize(txt):
    txt = txt.lower()
    txt = re.sub(r'[^a-z0-9\s]', ' ', txt)
    txt = re.sub(r'\s+', ' ', txt).strip()
    return txt

def extract_chapter_snippets(epub_path, max_paras=MAX_SNIPPET_PARAS):
    book = epub.read_epub(epub_path)
    chapters = []
    for item in book.get_items():
        if item.get_type() == ITEM_DOCUMENT:
            soup = BeautifulSoup(item.content, 'html.parser')
            for heading in soup.find_all(['h1', 'h2', 'h3']):
                chapter_title = heading.get_text(strip=True)
                
                # Collect all paragraphs following the heading
                paras = []
                node = heading.find_next_sibling()
                while node and node.name != 'h1' and node.name != 'h2' and node.name != 'h3':
                    if node.name == 'p':
                        text = node.get_text(strip=True)
                        if text: # Ensure paragraph is not empty
                            paras.append(text)
                    node = node.find_next_sibling()

                if not paras:
                    continue

                # Create multiple candidate snippets
                snippets = []
                # Snippet 1: First paragraph only
                snippets.append(paras[0])
                # Snippet 2: Second paragraph only (if it exists)
                if len(paras) > 1:
                    snippets.append(paras[1])
                # Snippet 3: First two paragraphs combined
                if len(paras) > 1:
                    snippets.append(' '.join(paras[:2]))
                
                # Add up to `max_paras` as a single snippet
                if len(paras) > 2:
                    snippets.append(' '.join(paras[:max_paras]))

                chapters.append({'chapter': chapter_title, 'snippets': snippets})
    return chapters

def format_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

def find_chapters(epub_path, transcript_path, start_chapter=1):
    """
    Finds chapter timestamps by aligning an EPUB with a transcript.
    Returns a list of chapter dictionaries.
    """
    # Extract chapters
    chapters = extract_chapter_snippets(epub_path)

    # Filter chapters based on start_chapter argument
    if start_chapter > 1:
        start_index = -1
        for i, ch in enumerate(chapters):
            if f"— {start_chapter} —" in ch['chapter'] or ch['chapter'].strip() == str(start_chapter):
                start_index = i
                break
        if start_index != -1:
            print(f"Starting scan from Chapter {start_chapter}...")
            chapters = chapters[start_index:]
        else:
            print(f"Warning: Could not find start chapter {start_chapter}. Starting from the beginning.")

    # Load transcript
    with open(transcript_path, 'r', encoding='utf-8') as f:
        transcript = json.load(f)

    # Normalize transcript text
    for seg in transcript:
        seg['norm_text'] = normalize(seg['text'])

    # Load embedding model
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    embed_model = SentenceTransformer('all-MiniLM-L6-v2', device=device)

    # Create rolling windows of transcript segments
    window_size = 5
    transcript_windows = []
    for i in range(len(transcript) - window_size + 1):
        text_window = ' '.join([transcript[j]['norm_text'] for j in range(i, i + window_size)])
        transcript_windows.append({
            'text': text_window,
            'start_segment': i,
            'end_segment': i + window_size - 1,
        })

    # Compute transcript embeddings
    print(f"Computing embeddings for {len(transcript_windows)} transcript windows...")
    texts = [win['text'] for win in transcript_windows]
    transcript_embs = embed_model.encode(texts, convert_to_tensor=True)

    found_chapters = []
    last_match_window_idx = -1
    for ch in chapters:
        best_overall_score = -1
        best_match_info = {}

        search_start_idx = last_match_window_idx + 1
        if search_start_idx >= len(transcript_windows):
            print(f"Chapter: {ch['chapter']} - No more transcript windows to search.")
            continue
        
        search_embs = transcript_embs[search_start_idx:]

        for snippet in ch['snippets']:
            snippet_norm = normalize(snippet)
            snippet_emb = embed_model.encode(snippet_norm, convert_to_tensor=True)
            sims = util.cos_sim(snippet_emb, search_embs)[0]
            best_local_idx = int(torch.argmax(sims).item())
            best_score = float(sims[best_local_idx].item() * 100)

            if best_score > best_overall_score:
                best_overall_score = best_score
                best_global_idx = search_start_idx + best_local_idx
                best_window = transcript_windows[best_global_idx]
                start_segment_idx = best_window['start_segment']
                end_segment_idx = best_window['end_segment']
                
                best_match_info = {
                    'title': ch['chapter'],
                    'score': best_score,
                    'start_time': transcript[start_segment_idx]['start'],
                    'end_time': transcript[end_segment_idx]['end'],
                    'epub_snippet': snippet,
                    'matched_transcript': ' '.join([transcript[i]['text'] for i in range(start_segment_idx, end_segment_idx + 1)]),
                    'best_window_idx': best_global_idx
                }

        if not best_match_info or best_match_info['score'] < CONFIDENCE_THRESHOLD:
            print(f"Chapter: {ch['chapter']} - No suitable match found above threshold {CONFIDENCE_THRESHOLD}. Stopping.")
            break
            
        last_match_window_idx = best_match_info['best_window_idx']
        found_chapters.append(best_match_info)
        
        # Print progress
        print(f"Found Chapter: {best_match_info['title']} @ {format_time(best_match_info['start_time'])} (Confidence: {best_match_info['score']:.1f}%)")

    return found_chapters

def main():
    parser = argparse.ArgumentParser(description="Align audiobook chapters with an ebook text and print the results.")
    parser.add_argument("ebook", help="Path to the EPUB file.")
    parser.add_argument("transcript", help="Path to the transcript JSON file.")
    parser.add_argument("--start-chapter", type=int, default=1, help="The chapter number to start matching from.")
    args = parser.parse_args()

    found_chapters = find_chapters(args.ebook, args.transcript, args.start_chapter)

    print("\n--- Match Results ---")
    for ch_info in found_chapters:
        print(f"Chapter: {ch_info['title']}")
        print(f"  Semantic confidence: {ch_info['score']:.1f}")
        print(f"  Start time: {format_time(ch_info['start_time'])}")
        print(f"  End time:   {format_time(ch_info['end_time'])}")
        print(f"  EPUB snippet: {ch_info['epub_snippet'].strip()}")
        print(f"  Matched transcript: {ch_info['matched_transcript'].strip()}\n")

if __name__ == '__main__':
    main()