from ebooklib import epub
from ebooklib import ITEM_DOCUMENT
from bs4 import BeautifulSoup

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
chapters = extract_chapter_snippets("E-Day.epub")
for ch in chapters:
    print(f"{ch['chapter']}: {ch['text']}")