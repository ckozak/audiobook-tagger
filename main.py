import sys
import json
import re
from ebooklib import epub
from ebooklib import ITEM_DOCUMENT
from bs4 import BeautifulSoup
import torch
from sentence_transformers import SentenceTransformer, util

# Configuration
MIN_SNIPPET_CHARS = 200
MAX_SNIPPET_PARAS = 3

def normalize(txt):
    txt = txt.lower()
    txt = re.sub(r'[^a-z0-9\s]', ' ', txt)
    txt = re.sub(r'\s+', ' ', txt).strip()
    return txt

def extract_chapter_snippets(epub_path, min_chars=MIN_SNIPPET_CHARS, max_paras=MAX_SNIPPET_PARAS):
    book = epub.read_epub(epub_path)
    chapters = []
    for item in book.get_items():
        if item.get_type() == ITEM_DOCUMENT:
            soup = BeautifulSoup(item.content, 'html.parser')
            for heading in soup.find_all(['h1','h2','h3']):
                chapter_title = heading.get_text(strip=True)
                paras, char_count, node = [], 0, heading.find_next_sibling()
                while node and len(paras) < max_paras:
                    if node.name == 'p':
                        text = node.get_text(strip=True)
                        paras.append(text)
                        char_count += len(text)
                        if char_count >= min_chars:
                            break
                    node = node.find_next_sibling()
                if paras:
                    snippet = ' '.join(paras)
                    chapters.append({'chapter': chapter_title, 'text': snippet})
    return chapters

def format_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

def main():
    if len(sys.argv) != 3:
        print("Usage: python main.py <ebook.epub> <transcript.json>")
        sys.exit(1)
    epub_path, transcript_path = sys.argv[1], sys.argv[2]

    # Extract chapters
    chapters = extract_chapter_snippets(epub_path)

    # Load transcript
    with open(transcript_path, 'r', encoding='utf-8') as f:
        transcript = json.load(f)

    # Normalize transcript text
    for seg in transcript:
        seg['norm_text'] = normalize(seg['text'])

    # Load embedding model on GPU if available
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    embed_model = SentenceTransformer('all-MiniLM-L6-v2', device=device)

    # Compute transcript embeddings
    texts = [seg['norm_text'] for seg in transcript]
    transcript_embs = embed_model.encode(texts, convert_to_tensor=True)

    # Semantic-only matching
    for ch in chapters:
        snippet, snippet_norm = ch['text'], normalize(ch['text'])
        snippet_emb = embed_model.encode(snippet_norm, convert_to_tensor=True)

        # Cosine similarity
        sims = util.cos_sim(snippet_emb, transcript_embs)[0]
        best_idx = int(torch.argmax(sims).item())
        best_score = float(sims[best_idx].item() * 100)

        start_ts = transcript[best_idx]['start']
        end_ts   = transcript[best_idx]['end']
        matched_raw = transcript[best_idx]['text']

        print(f"Chapter: {ch['chapter']}")
        print(f"  Semantic confidence: {best_score:.1f}")
        print(f"  Start time: {format_time(start_ts)}")
        print(f"  End time:   {format_time(end_ts)}")
        print(f"  EPUB snippet: {snippet.strip()}")
        print(f"  Matched transcript: {matched_raw.strip()}\n")

if __name__ == '__main__':
    main()