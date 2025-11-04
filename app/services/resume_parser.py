import re
import fitz  # PyMuPDF
from typing import Dict, List
from collections import Counter

# Regex patterns
EMAIL_RE = r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}"
PHONE_RE = r"\+?\d[\d\-\s()]{8,}\d"
LINKEDIN_RE = r"(https?://(www\.)?linkedin\.com/in/[A-Za-z0-9_-]+/?)"

# Skill database
SKILLS_DB = [
    "python","java","c++","html","css","javascript","sql","flask","django","react",
    "node","pytorch","tensorflow","keras","aws","azure","docker","kubernetes",
    "git","linux","postgresql","mysql","data science","machine learning","deep learning",
    "typescript","mongodb","redis","graphql","rest api","spring","angular","vue",
    "express","fastapi","numpy","pandas","scikit-learn","opencv","nlp",
    "natural language processing","computer vision","devops","ci/cd","jenkins",
    "terraform","ansible","kafka","rabbitmq","elasticsearch","rust","go","golang",
    "swift","kotlin","flutter","dart","ruby","rails","php","laravel",".net","c#",
]

# Common stopwords to filter out from keywords
STOPWORDS = {
    "the","a","an","and","or","but","in","on","at","to","for","of","with","by",
    "from","is","are","was","were","be","been","being","have","has","had","do",
    "does","did","will","would","shall","should","may","might","can","could",
    "this","that","these","those","i","me","my","we","our","you","your","he",
    "she","it","they","them","his","her","its","their","who","whom","which",
    "what","where","when","how","all","each","every","both","few","more","most",
    "other","some","such","no","not","only","same","so","than","too","very",
    "also","just","about","above","after","before","between","into","through",
    "during","out","over","under","up","down","then","once","here","there",
    "any","new","work","use","used","using","based","well","good","like",
}

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
    # Heuristic: the name is usually on the first non-empty line
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        # Skip lines that look like emails, phone numbers, or URLs
        if re.search(EMAIL_RE, line, re.I) or re.search(PHONE_RE, line) or re.search(r"https?://", line):
            continue
        # A name line is typically short (2-5 words) and mostly alphabetic
        words = line.split()
        if 1 <= len(words) <= 5 and all(re.match(r"^[A-Za-z.\-']+$", w) for w in words):
            return line
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

# ------------------ Keyword Extraction ------------------
def extract_keywords(text: str, top_n: int = 15) -> List[str]:
    """
    Extracts keywords from resume text using:
    - predefined skill list
    - significant multi-word phrases
    - capitalized terms (likely proper nouns / technologies)
    """
    text_lower = text.lower()
    keywords = []

    # Add skills from predefined database if present
    for skill in SKILLS_DB:
        if skill.lower() in text_lower:
            keywords.append(skill.lower())

    # Extract capitalized words/phrases that look like technologies or proper nouns
    # e.g., "React", "Node.js", "AWS Lambda"
    tech_pattern = re.compile(r'\b[A-Z][a-zA-Z+#.]*(?:\s+[A-Z][a-zA-Z+#.]*)*\b')
    for match in tech_pattern.findall(text):
        term = match.strip().lower()
        if len(term) > 2 and term not in STOPWORDS:
            keywords.append(term)

    # Extract meaningful words (3+ chars, not stopwords, not pure numbers)
    word_pattern = re.compile(r'\b[a-zA-Z]{3,}\b')
    for match in word_pattern.findall(text_lower):
        if match not in STOPWORDS and not match.isdigit():
            keywords.append(match)

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
