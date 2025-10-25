import re
import fitz  # PyMuPDF
import spacy
from typing import Dict, List
from collections import Counter

# Load SpaCy NLP model
nlp = spacy.load("en_core_web_sm")

# Regex patterns
EMAIL_RE = r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}"
PHONE_RE = r"\+?\d[\d\-\s()]{8,}\d"
LINKEDIN_RE = r"(https?://(www\.)?linkedin\.com/in/[A-Za-z0-9_-]+/?)"

# Skill database
SKILLS_DB = [
    "python","java","c++","html","css","javascript","sql","flask","django","react",
    "node","pytorch","tensorflow","keras","aws","azure","docker","kubernetes",
    "git","linux","postgresql","mysql","data science","machine learning","deep learning"
]

# ------------------ PDF Text Extraction ------------------
def extract_text_from_pdf(pdf_path: str) -> str:
    text = ""
    with fitz.open(pdf_path) as doc:
        for page in doc:
            text += page.get_text("text") + "\n"
    return text

# ------------------ Contact Info Extraction ------------------
def extract_contact_info(text: str) -> Dict[str, List[str]]:
    emails = re.findall(EMAIL_RE, text, flags=re.I)
    phones = re.findall(PHONE_RE, text)
    linkedin = re.findall(LINKEDIN_RE, text, flags=re.I)
    return {
        "emails": list(set(emails)),
        "phones": list(set(phones)),
        "linkedin": list(set(linkedin))
    }

# ------------------ Name Extraction ------------------
def extract_name(text: str) -> str:
    doc = nlp(text[:300])
    for ent in doc.ents:
        if ent.label_ == "PERSON":
            return ent.text.strip()
    first_line = text.split("\n")[0]
    if len(first_line.split()) <= 5:
        return first_line.strip()
    return "Not found"

# ------------------ Skills Extraction ------------------
def extract_skills(text: str) -> List[str]:
    text_lower = text.lower()
    found = [s for s in SKILLS_DB if s.lower() in text_lower]
    return sorted(set(found))

# ------------------ Section-based Extraction ------------------
def extract_sections(text: str) -> Dict[str, str]:
    sections = {"experience": "", "projects": ""}
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    header_re = re.compile(r"^(PROJECTS?|EXPERIENCE|WORK EXPERIENCE|INTERNSHIP|EDUCATION|SKILLS?)[:\-]?$", flags=re.I)
    current_section = None
    buffer = {key: [] for key in sections}

    for line in lines:
        if header_re.match(line):
            header = header_re.match(line).group(1).lower()
            if "project" in header:
                current_section = "projects"
            elif "experience" in header or "internship" in header:
                current_section = "experience"
            else:
                current_section = None
            continue
        if current_section:
            buffer[current_section].append(line)

    sections["projects"] = "\n".join(buffer["projects"]).strip()
    sections["experience"] = "\n".join(buffer["experience"]).strip()
    return sections

# ------------------ Keyword Extraction (Improved) ------------------
def extract_keywords(text: str, top_n: int = 15) -> List[str]:
    """
    Extracts more accurate keywords from resume text using:
    - spaCy noun chunks
    - proper nouns
    - named entities
    - predefined skill list
    """
    doc = nlp(text.lower())
    keywords = []

    # Add skills from predefined database if present
    for skill in SKILLS_DB:
        if skill.lower() in text.lower():
            keywords.append(skill.lower())

    # Add noun chunks longer than 2 characters
    for chunk in doc.noun_chunks:
        phrase = chunk.text.strip()
        if len(phrase) > 2:
            keywords.append(phrase.lower())

    # Add named entities (except common types)
    for ent in doc.ents:
        if ent.label_ not in ["DATE", "TIME", "MONEY", "PERCENT"]:
            keywords.append(ent.text.strip().lower())

    # Remove stopwords, punctuation, short words
    keywords = [k for k in keywords if len(k) > 2 and not k.isdigit()]

    # Count frequency
    freq = Counter(keywords)

    # Return top N keywords
    top_keywords = [k for k, _ in freq.most_common(top_n)]
    return top_keywords

# ------------------ Main Parsing ------------------
def parse_resume(pdf_path: str) -> Dict:
    text = extract_text_from_pdf(pdf_path)
    name = extract_name(text)
    contact = extract_contact_info(text)
    skills = extract_skills(text)
    sections = extract_sections(text)
    keywords = extract_keywords(text)

    return {
        "name": name,
        "email": contact.get("emails", []),
        "phone": contact.get("phones", []),
        "linkedin": contact.get("linkedin", []),
        "skills": skills,
        "experience": sections["experience"] or "Not found",
        "projects": sections["projects"] or "Not found",
        "keywords": keywords
    }


def parse_resume_to_skills(file_path: str) -> List[str]:
    """
    Convenience wrapper for routes: given a resume file path, return a
    normalized list of skills suitable for downstream usage (e.g. prompting an
    LLM). It combines explicit SKILLS_DB matches with the top keywords and
    returns a de-duplicated, title-cased list of skills.
    """
    data = parse_resume(file_path)
    skills = data.get('skills', []) or []
    keywords = data.get('keywords', []) or []

    # Merge and normalize, prefer explicit skills first
    merged = []
    for s in skills + keywords:
        if not s or not isinstance(s, str):
            continue
        normalized = s.strip()
        # Title case common multi-word skills (e.g., 'machine learning')
        normalized = ' '.join([w.capitalize() for w in normalized.split()])
        if normalized not in merged:
            merged.append(normalized)

    # Limit to reasonable number
    return merged[:30]
