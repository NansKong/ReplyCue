"""Local, source-labelled lexical retrieval. No documents leave this process."""
import math
import re
import zipfile
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree


def extract(path):
    path = Path(path)
    if path.stat().st_size > 20 * 1024 * 1024:
        raise ValueError('Please use a document smaller than 20 MB.')
    extension = path.suffix.lower()
    if extension == '.txt':
        text = path.read_text(encoding='utf-8-sig')
    elif extension == '.docx':
        with zipfile.ZipFile(path) as archive:
            info = archive.getinfo('word/document.xml')
            if info.file_size > 30 * 1024 * 1024:
                raise ValueError('Document content is too large.')
            root = ElementTree.fromstring(archive.read(info))
            ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
            text = '\n'.join(''.join(p.itertext()) for p in root.findall('.//w:p', ns))
    elif extension == '.pdf':
        from pypdf import PdfReader
        reader = PdfReader(path)
        if reader.is_encrypted:
            raise ValueError('Use an unencrypted PDF.')
        text = '\n\n'.join(f'[Page {i+1}]\n{page.extract_text() or ""}' for i, page in enumerate(reader.pages))
        if len(re.sub(r'\[Page \d+\]', '', text).strip()) < 30:
            raise ValueError('No readable PDF text. Scanned PDFs need OCR, which is not connected yet.')
    else:
        raise ValueError('Supported documents: TXT, DOCX and text-based PDF.')
    if not text.strip():
        raise ValueError('The document has no readable text.')
    return text


def tokens(text):
    return re.findall(r'[a-z0-9+#]+', text.lower())


def retrieve(question, documents, limit=5):
    """Rebuild from the current edited documents, preventing stale resume context."""
    chunks = []
    for kind, text in documents.items():
        paragraphs = re.split(r'\n\s*\n', text.strip())
        index = 0
        for paragraph in paragraphs:
            for offset in range(0, len(paragraph), 900):
                part = paragraph[offset:offset+1000].strip()
                if part:
                    index += 1
                    chunks.append((kind, index, part, tokens(part)))
    query = set(tokens(question))
    if not chunks or not query:
        return []
    average = sum(len(c[3]) for c in chunks) / len(chunks)
    document_frequencies = Counter()
    for _, _, _, words in chunks:
        document_frequencies.update(set(words))
    ranked = []
    for kind, index, text, words in chunks:
        frequencies = Counter(words)
        score = 0.0
        for token in query:
            frequency = frequencies[token]
            if not frequency:
                continue
            df = document_frequencies[token]
            idf = math.log(1 + (len(chunks)-df+0.5)/(df+0.5))
            score += idf * frequency * 2.2 / (frequency + 1.2*(0.25+0.75*len(words)/max(1, average)))
        if score:
            ranked.append({'source': kind, 'section': index, 'text': text, 'score': score})
    return sorted(ranked, key=lambda c: c['score'], reverse=True)[:limit]
