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

def main():
    parser = argparse.ArgumentParser(description="Align audiobook chapters with an ebook text.")
    parser.add_argument("ebook", help="Path to the EPUB file.")
    parser.add_argument("transcript", help="Path to the transcript JSON file.")
    parser.add_argument("--start-chapter", type=int, default=1, help="The chapter number to start matching from.")
    args = parser.parse_args()

    # Extract chapters
    chapters = extract_chapter_snippets(args.ebook)

    # Filter chapters based on start_chapter argument
    if args.start_chapter > 1:
        start_index = -1
        # Find the index of the chapter to start from.
        # This is a bit naive and assumes chapter titles contain the number.
        for i, ch in enumerate(chapters):
            if f"— {args.start_chapter} —" in ch['chapter'] or ch['chapter'].strip() == str(args.start_chapter):
                start_index = i
                break
        
        if start_index != -1:
            print(f"Starting scan from Chapter {args.start_chapter}...")
            chapters = chapters[start_index:]
        else:
            print(f"Warning: Could not find start chapter {args.start_chapter}. Starting from the beginning.")


    # Load transcript
    with open(args.transcript, 'r', encoding='utf-8') as f:
        transcript = json.load(f)

    # Normalize transcript text
    for seg in transcript:
        seg['norm_text'] = normalize(seg['text'])

    # Load embedding model on GPU if available
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    embed_model = SentenceTransformer('all-MiniLM-L6-v2', device=device)

    # Create rolling windows of transcript segments
    # This helps match longer epub snippets to multiple transcript segments
    window_size = 5 # Number of transcript segments to combine
    transcript_windows = []
    for i in range(len(transcript) - window_size + 1):
        text_window = ' '.join([transcript[j]['norm_text'] for j in range(i, i + window_size)])
        transcript_windows.append({
            'text': text_window,
            'start_segment': i,
            'end_segment': i + window_size - 1,
        })

    # Compute transcript embeddings for windows
    print(f"Computing embeddings for {len(transcript_windows)} transcript windows...")
    texts = [win['text'] for win in transcript_windows]
    transcript_embs = embed_model.encode(texts, convert_to_tensor=True)

    # Semantic-only matching
    last_match_window_idx = -1
    for ch in chapters:
        best_overall_score = -1
        best_match_info = {}

        # To enforce sequential order, we search starting after the last match
        search_start_idx = last_match_window_idx + 1
        if search_start_idx >= len(transcript_windows):
            print(f"Chapter: {ch['chapter']}")
            print("  No more transcript windows to search.")
            continue
        
        search_embs = transcript_embs[search_start_idx:]

        for snippet in ch['snippets']:
            snippet_norm = normalize(snippet)
            snippet_emb = embed_model.encode(snippet_norm, convert_to_tensor=True)

            # Cosine similarity
            sims = util.cos_sim(snippet_emb, search_embs)[0]
            best_local_idx = int(torch.argmax(sims).item())
            best_score = float(sims[best_local_idx].item() * 100)

            if best_score > best_overall_score:
                best_overall_score = best_score
                
                # Convert local index back to global index
                best_global_idx = search_start_idx + best_local_idx
                
                best_window = transcript_windows[best_global_idx]
                start_segment_idx = best_window['start_segment']
                end_segment_idx = best_window['end_segment']
                
                matched_raw = ' '.join([transcript[i]['text'] for i in range(start_segment_idx, end_segment_idx + 1)])

                best_match_info = {
                    'score': best_score,
                    'start_ts': transcript[start_segment_idx]['start'],
                    'end_ts': transcript[end_segment_idx]['end'],
                    'epub_snippet': snippet,
                    'matched_transcript': matched_raw,
                    'best_window_idx': best_global_idx
                }

        if not best_match_info or best_match_info['score'] < CONFIDENCE_THRESHOLD:
            print(f"Chapter: {ch['chapter']}")
            print(f"  --> No suitable match found above threshold {CONFIDENCE_THRESHOLD}. Stopping.")
            break # Stop processing further chapters
            
        # Update the last match index to continue the search from here
        last_match_window_idx = best_match_info['best_window_idx']

        print(f"Chapter: {ch['chapter']}")
        print(f"  Semantic confidence: {best_match_info['score']:.1f}")
        print(f"  Start time: {format_time(best_match_info['start_ts'])}")
        print(f"  End time:   {format_time(best_match_info['end_ts'])}")
        print(f"  EPUB snippet: {best_match_info['epub_snippet'].strip()}")
        print(f"  Matched transcript: {best_match_info['matched_transcript'].strip()}\n")

if __name__ == '__main__':
    main()
