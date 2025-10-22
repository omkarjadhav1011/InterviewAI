import PyPDF2
import spacy

try:
    nlp = spacy.load('en_core_web_sm')
except Exception:
    nlp = None


def extract_text_from_pdf(path):
    text = ''
    with open(path, 'rb') as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            text += page.extract_text() or ''
    return text


def extract_keywords(text, top_n=10):
    if nlp:
        doc = nlp(text)
        freq = {}
        for token in doc:
            if token.pos_ in ('NOUN', 'PROPN') and not token.is_stop and token.is_alpha:
                key = token.lemma_.lower()
                freq[key] = freq.get(key, 0) + 1
        items = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        return [k for k, _ in items[:top_n]]
    words = [w.lower() for w in text.split() if w.isalpha()]
    freq = {}
    for w in words:
        if w in ('the', 'and', 'a', 'to', 'of', 'in'):
            continue
        freq[w] = freq.get(w, 0) + 1
    items = sorted(freq.items(), key=lambda x: x[1], reverse=True)
    return [k for k, _ in items[:top_n]]
