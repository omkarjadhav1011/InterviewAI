import os
import re
import logging
import threading
from typing import Dict, List, Optional, Tuple
from collections import Counter

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)

# Regex patterns
EMAIL_RE = r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}"
PHONE_RE = r"\+?\d[\d\-\s()]{8,}\d"
LINKEDIN_RE = r"(https?://(www\.)?linkedin\.com/in/[A-Za-z0-9_-]+/?)"

# Skill database — expanded with common modern skills
SKILLS_DB = [
    "python", "java", "c++", "html", "css", "javascript", "sql", "flask",
    "django", "react", "node", "pytorch", "tensorflow", "keras", "aws",
    "azure", "docker", "kubernetes", "git", "linux", "postgresql", "mysql",
    "data science", "machine learning", "deep learning", "typescript",
    "mongodb", "redis", "graphql", "rest api", "spring", "angular", "vue",
    "express", "fastapi", "numpy", "pandas", "scikit-learn", "opencv", "nlp",
    "natural language processing", "computer vision", "devops", "ci/cd",
    "jenkins", "terraform", "ansible", "kafka", "rabbitmq", "elasticsearch",
    "rust", "go", "golang", "swift", "kotlin", "flutter", "dart", "ruby",
    "rails", "php", "laravel", ".net", "c#",
    # Added entries
    "gcp", "android", "ios", "spring boot", "bash", "shell",
    "junit", "maven", "gradle",
]

# Alias map: variant spellings / abbreviations → canonical SKILLS_DB name
SKILL_ALIASES: Dict[str, str] = {
    # JavaScript
    "js":               "javascript",
    "es6":              "javascript",
    "ecmascript":       "javascript",
    # Node.js
    "nodejs":           "node",
    "node.js":          "node",
    "node js":          "node",
    # TypeScript
    "ts":               "typescript",
    # Python
    "py":               "python",
    # ML / AI
    "ml":               "machine learning",
    "ai":               "machine learning",
    # Deep learning
    "dl":               "deep learning",
    # NLP
    "nlp":              "natural language processing",
    # Computer vision
    "cv":               "computer vision",
    # Data science
    "ds":               "data science",
    # Databases
    "postgres":         "postgresql",
    "pg":               "postgresql",
    "mongo":            "mongodb",
    # Kubernetes
    "k8s":              "kubernetes",
    "k8":               "kubernetes",
    # Docker
    "containerization": "docker",
    "containers":       "docker",
    # .NET
    "dotnet":           ".net",
    "dot net":          ".net",
    # C#
    "csharp":           "c#",
    # C++
    "cplusplus":        "c++",
    "c plus plus":      "c++",
    # REST
    "rest":             "rest api",
    "restful":          "rest api",
    "restful api":      "rest api",
    # Vue
    "vue.js":           "vue",
    "vuejs":            "vue",
    # React
    "react.js":         "react",
    "reactjs":          "react",
    # Angular
    "angularjs":        "angular",
    # Express
    "express.js":       "express",
    "expressjs":        "express",
    # Spring Boot
    "spring boot":      "spring",
    # Kafka
    "apache kafka":     "kafka",
    # Elasticsearch
    "elastic":          "elasticsearch",
    "elk":              "elasticsearch",
    # Git
    "github":           "git",
    "gitlab":           "git",
    "bitbucket":        "git",
    # Linux
    "unix":             "linux",
    "ubuntu":           "linux",
    "centos":           "linux",
    "debian":           "linux",
    # Scikit-learn
    "sklearn":          "scikit-learn",
    "scikit learn":     "scikit-learn",
    # FastAPI
    "fast api":         "fastapi",
    # GraphQL
    "gql":              "graphql",
    # Terraform
    "iac":              "terraform",
    # Golang
    "go lang":          "golang",
    # Rails
    "ror":              "rails",
    # HTML/CSS
    "html5":            "html",
    "css3":             "css",
    # CI/CD
    "cicd":             "ci/cd",
    "ci cd":            "ci/cd",
    # Flask / Django variants
    "flask api":        "flask",
    "django rest":      "django",
    # GCP
    "google cloud":     "gcp",
    "google cloud platform": "gcp",
}

# Common stopwords to filter out from keywords
STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will", "would",
    "shall", "should", "may", "might", "can", "could", "this", "that",
    "these", "those", "i", "me", "my", "we", "our", "you", "your", "he",
    "she", "it", "they", "them", "his", "her", "its", "their", "who",
    "whom", "which", "what", "where", "when", "how", "all", "each",
    "every", "both", "few", "more", "most", "other", "some", "such", "no",
    "not", "only", "same", "so", "than", "too", "very", "also", "just",
    "about", "above", "after", "before", "between", "into", "through",
    "during", "out", "over", "under", "up", "down", "then", "once",
    "here", "there", "any", "new", "work", "use", "used", "using",
    "based", "well", "good", "like",
}

# Resume-specific noise words (generic verbs, nouns, adjectives found in every resume)
RESUME_NOISE: set = {
    # generic resume verbs
    "develop", "developed", "developing",
    "implement", "implemented", "implementing",
    "build", "built", "building",
    "design", "designed", "designing",
    "create", "created", "creating",
    "manage", "managed", "managing",
    "maintain", "maintained", "maintaining",
    "deploy", "deployed", "deploying",
    "optimize", "optimized", "optimizing",
    "test", "tested", "testing",
    "integrate", "integrated", "integrating",
    "contribute", "contributed", "contributing",
    "collaborate", "collaborated",
    "analyze", "analyzed", "analyzing",
    "review", "reviewed", "reviewing",
    "lead", "led", "leading",
    "deliver", "delivered", "delivering",
    "responsible", "ensure", "ensured",
    "provide", "provided", "providing",
    "handle", "handled", "handling",
    "perform", "performed", "performing",
    "define", "defined",
    "configure", "configured",
    "automate", "automated",
    "execute", "executed",
    "resolve", "resolved", "resolving",
    "identify", "identified",
    "reduce", "reduced",
    "improve", "improved", "improving",
    "enhance", "enhanced", "enhancing",
    "support", "supported", "supporting",
    "monitor", "monitored", "monitoring",
    "migrate", "migrated", "migrating",
    "coordinate", "coordinated",
    # generic nouns
    "application", "applications",
    "system", "systems",
    "project", "projects",
    "team", "teams",
    "process", "processes",
    "service", "services",
    "feature", "features",
    "solution", "solutions",
    "environment", "environments",
    "component", "components",
    "module", "modules",
    "platform", "platforms",
    "framework", "frameworks",
    "interface", "interfaces",
    "database", "databases",
    "server", "servers",
    "client", "clients",
    "code", "codebase",
    "function", "functions",
    "method", "methods",
    "model", "models",
    "file", "files",
    "tool", "tools",
    "task", "tasks",
    "issue", "issues",
    "error", "errors",
    "request", "requests",
    "response", "responses",
    "version", "versions",
    "release", "releases",
    "update", "updates",
    "change", "changes",
    "result", "results",
    "report", "reports",
    "pipeline", "pipelines",
    "workflow", "workflows",
    "dataset", "datasets",
    # generic adjectives / adverbs
    "scalable", "efficient", "reliable", "robust", "flexible", "complex",
    "simple", "multiple", "various", "different", "large", "small",
    "high", "low", "real", "full", "stack", "cross", "end", "side",
    # calendar noise
    "january", "february", "march", "april", "june", "july", "august",
    "september", "october", "november", "december",
    "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "oct", "nov", "dec",
    # number words
    "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
    # education / role noise
    "university", "college", "bachelor", "master", "degree", "gpa", "cgpa",
    "intern", "internship", "engineer", "developer", "senior", "junior",
    "associate", "analyst", "manager", "director", "architect",
    "software", "hardware", "technology", "technologies",
}

# Combined noise set used throughout keyword extraction
ALL_NOISE: set = STOPWORDS | RESUME_NOISE

# Short tokens that are also common English words — require section context to count
AMBIGUOUS_SKILLS: set = {"go", "r", "c"}

# Context patterns that precede a skill mention, indicating explicit usage
_CONTEXT_PATTERNS = [
    re.compile(r'\b(?:built|written|developed|implemented)\s+(?:in|with|using)\s+', re.IGNORECASE),
    re.compile(r'\b(?:using|leveraging|via)\s+', re.IGNORECASE),
    re.compile(r'\b(?:experience|expertise|proficiency|knowledge|proficient|skilled)\s+(?:in|with)\s+', re.IGNORECASE),
    re.compile(r'\b(?:worked|familiar)\s+with\s+', re.IGNORECASE),
    re.compile(r'\b(?:proficient|experienced|expert)\s+in\s+', re.IGNORECASE),
]


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _resolve_alias(term: str) -> str:
    """Return the canonical SKILLS_DB name for a term (or the term itself)."""
    return SKILL_ALIASES.get(term.lower(), term.lower())


def _make_pattern(term: str) -> re.Pattern:
    """
    Compile a word-boundary-aware regex for a skill term.
    Handles special characters in '.net', 'c++', 'c#', 'ci/cd' correctly.
    """
    escaped = re.escape(term)
    # Use lookbehind/lookahead instead of \b when the term starts/ends with non-word chars
    left  = r'(?<!\w)' if not term[0].isalnum()  else r'\b'
    right = r'(?!\w)'  if not term[-1].isalnum() else r'\b'
    return re.compile(left + escaped + right, re.IGNORECASE)


def _build_skill_patterns() -> List[tuple]:
    """
    Pre-compile one regex pattern per SKILLS_DB entry plus each alias key.
    Returns a list of (compiled_pattern, canonical_name) tuples.
    """
    skills_db_lower = {s.lower() for s in SKILLS_DB}
    seen_canonicals: Dict[str, re.Pattern] = {}  # canonical → pattern (avoid duplicates)

    # Build from SKILLS_DB entries
    for term in SKILLS_DB:
        canonical = term.lower()
        if canonical not in seen_canonicals:
            seen_canonicals[canonical] = _make_pattern(canonical)

    # Build from alias keys (map to their canonical)
    for alias_key, canonical in SKILL_ALIASES.items():
        if canonical not in skills_db_lower:
            continue  # skip aliases pointing outside SKILLS_DB
        # Store alias pattern → canonical (may add multiple patterns per canonical)
        seen_canonicals[alias_key] = (canonical, _make_pattern(alias_key))

    # Flatten into list of (pattern, canonical_name)
    result = []
    for key, val in seen_canonicals.items():
        if isinstance(val, tuple):
            canonical, pat = val
            result.append((pat, canonical))
        else:
            # val is a pattern for a SKILLS_DB entry; canonical == key
            result.append((val, key))
    return result


# Build once at module load — O(n_skills) upfront cost, negligible at runtime
_SKILL_PATTERNS: List[tuple] = _build_skill_patterns()


def _has_context(text: str, match_start: int) -> bool:
    """
    Return True if a context prefix (e.g. 'using', 'built with') appears
    in the 60 characters immediately before match_start.
    """
    prefix = text[max(0, match_start - 60): match_start]
    return any(cp.search(prefix) for cp in _CONTEXT_PATTERNS)


def _extract_skills_with_scores(text: str, sections: Dict[str, str]) -> List[Dict]:
    """
    Score each recognized skill based on:
    - Frequency in the dedicated skills section  (weight 3.0)
    - Frequency in experience / projects sections (weight 1.5 each)
    - Frequency in full text                      (weight 1.0)
    - Context-pattern bonus per hit               (+2.0 per hit, capped at 3)

    Ambiguous short tokens ('go', 'c', 'r') are only counted in sections,
    not in the general text, to reduce false positives.

    Returns: [{"name": str, "score": float}, ...]
    """
    skills_section = sections.get("skills", "")
    experience_sec = sections.get("experience", "")
    projects_sec   = sections.get("projects", "")

    scores: Dict[str, float] = {}

    for pat, canonical in _SKILL_PATTERNS:
        full_hits = len(pat.findall(text))
        if full_hits == 0:
            continue

        # Cap individual hit counts to prevent keyword-stuffing inflation
        full_hits    = min(full_hits, 5)
        skills_hits  = min(len(pat.findall(skills_section)), 5)
        exp_hits     = min(len(pat.findall(experience_sec)), 5)
        proj_hits    = min(len(pat.findall(projects_sec)), 5)

        # Ambiguous skills: don't count general-text hits, only section hits
        if canonical in AMBIGUOUS_SKILLS:
            full_hits = 0

        # Context bonus: flat +2.0 per contextual match, capped at 3 occurrences
        context_bonus = 0.0
        ctx_count = 0
        for m in pat.finditer(text):
            if _has_context(text, m.start()):
                context_bonus += 2.0
                ctx_count += 1
                if ctx_count >= 3:
                    break

        score = (
            skills_hits * 3.0
            + exp_hits   * 1.5
            + proj_hits  * 1.5
            + full_hits  * 1.0
            + context_bonus
        )

        # Merge: if canonical already seen via another alias, keep highest score
        if canonical in scores:
            scores[canonical] = max(scores[canonical], score)
        else:
            scores[canonical] = score

    return [{"name": k, "score": v} for k, v in scores.items()]


# ---------------------------------------------------------------------------
# PDF Text Extraction
# ---------------------------------------------------------------------------

def _extract_pdf_text_inner(file_bytes: bytes, max_pages: int, result: dict) -> None:
    """Worker that runs in a thread so we can enforce a wall-clock timeout."""
    try:
        with fitz.open(stream=file_bytes, filetype="pdf") as doc:
            if doc.page_count == 0:
                result["error"] = "PDF has no pages"
                return
            pages_to_read = min(doc.page_count, max_pages)
            parts: List[str] = []
            for i in range(pages_to_read):
                try:
                    page_text = doc[i].get_text("text").strip()
                except Exception:
                    logger.exception("Failed to read PDF page %s", i)
                    continue
                if page_text:
                    parts.append(page_text)
            result["text"] = "\n\n".join(parts)
            if not result["text"].strip():
                result["error"] = "PDF appears to be image-only (no extractable text)"
    except fitz.FileDataError as e:
        result["error"] = f"Corrupted or invalid PDF: {e}"
    except Exception as e:
        result["error"] = f"Unexpected PDF extraction error: {e}"


def extract_text_from_pdf_bytes(
    file_bytes: bytes,
    max_pages: int = 10,
    timeout_seconds: int = 20,
) -> Tuple[str, Optional[str]]:
    """Extract text from raw PDF bytes with a wall-clock timeout and page cap.

    Returns (text, error). `error` is None on success; populated for empty PDFs,
    image-only PDFs, corrupted PDFs, or extractor timeouts. The function never raises.
    """
    if not file_bytes:
        return "", "empty file"
    result: Dict[str, Optional[str]] = {"text": "", "error": None}
    t = threading.Thread(target=_extract_pdf_text_inner,
                         args=(file_bytes, max_pages, result), daemon=True)
    t.start()
    t.join(timeout=timeout_seconds)
    if t.is_alive():
        return "", f"PDF extraction timed out after {timeout_seconds}s"
    return (result.get("text") or "", result.get("error"))


def extract_text_from_pdf(pdf_path: str) -> str:
    """Backward-compatible path-based wrapper (used by parse_resume / tools/).

    Reads the file into bytes, then delegates to the hardened bytes extractor.
    Falls back to a quiet empty string on read errors so existing callers don't crash.
    """
    try:
        with open(pdf_path, "rb") as f:
            data = f.read()
    except Exception:
        logger.exception("Failed to read PDF file at %s", pdf_path)
        return ""
    text, err = extract_text_from_pdf_bytes(data)
    if err:
        logger.warning("PDF extraction warning for %s: %s", pdf_path, err)
    return text


# ---------------------------------------------------------------------------
# Structured profile extraction (Gemini-backed, with skill-scorer fallback)
# ---------------------------------------------------------------------------

def parse_resume_to_skills_from_text(text: str) -> List[str]:
    """Run the deterministic skill scorer over already-extracted resume text.

    Mirrors the merge/normalize logic in parse_resume_to_skills() so callers
    that already have text don't need to re-extract.
    """
    if not text or not text.strip():
        return []
    sections = extract_sections(text)
    scored = _extract_skills_with_scores(text, sections)
    scored.sort(key=lambda x: x["score"], reverse=True)
    skills = [item["name"] for item in scored]
    keywords = extract_keywords(text)

    merged: List[str] = []
    for s in skills + keywords:
        if not s or not isinstance(s, str):
            continue
        normalized = " ".join(w.capitalize() for w in s.strip().split())
        if normalized and normalized not in merged:
            merged.append(normalized)
    return merged[:30]


_DEFAULT_PROFILE = {
    "skills": [],
    "experience_years": None,
    "job_titles": [],
    "education": [],
    "name": None,
    "summary": "",
}


def extract_structured_profile(resume_text: str) -> Dict:
    """Extract a structured candidate profile from resume text via Gemini.

    Returns a dict with keys: skills, experience_years, job_titles, education,
    name, summary. On Gemini failure (or missing API key), falls back to the
    deterministic skill scorer for `skills` and a heuristic name extractor.
    The function never raises.
    """
    if not resume_text or not resume_text.strip():
        return dict(_DEFAULT_PROFILE)

    # Lazy import to avoid coupling resume_parser to gemini_service at module load
    try:
        from .gemini_service import _get_model, _gemini_timeout
        from ..utils.gemini_runtime import call_gemini_with_timeout, parse_json_response
    except Exception:
        logger.exception("Could not import Gemini runtime; using fallback profile")
        return _fallback_profile(resume_text)

    model = _get_model()
    if model is None:
        return _fallback_profile(resume_text)

    truncated = resume_text[:8000]
    prompt = f"""You are a professional resume parser. Extract candidate info from the resume text below.

Return ONLY a valid JSON object - no markdown fences, no commentary:
{{
  "skills": ["..."],
  "experience_years": <integer or null>,
  "job_titles": ["..."],
  "education": ["..."],
  "name": "<candidate name or null>",
  "summary": "<2-sentence professional summary>"
}}

Rules:
- skills: 5-20 specific technical and soft skills, deduplicated, normalized capitalization (e.g. "Python", "REST APIs", "Team Leadership").
- If a section is missing from the resume, use null or [].
- Do NOT include markdown code fences in your response.

Resume text:
{truncated}"""

    try:
        raw = call_gemini_with_timeout(model, prompt, timeout=_gemini_timeout())
        parsed = parse_json_response(raw)
    except Exception:
        logger.exception("Gemini profile extraction failed; using fallback")
        return _fallback_profile(resume_text)

    if not isinstance(parsed, dict):
        return _fallback_profile(resume_text)

    # Normalize fields
    skills = parsed.get("skills") or []
    if not isinstance(skills, list):
        skills = []
    skills = [str(s).strip() for s in skills if s][:20]
    if not skills:
        # Backfill from deterministic scorer if Gemini returned nothing
        skills = parse_resume_to_skills_from_text(resume_text)

    job_titles = parsed.get("job_titles") or []
    if not isinstance(job_titles, list):
        job_titles = []
    job_titles = [str(t).strip() for t in job_titles if t][:10]

    education = parsed.get("education") or []
    if not isinstance(education, list):
        education = []
    education = [str(e).strip() for e in education if e][:10]

    name = parsed.get("name")
    if not isinstance(name, str) or not name.strip():
        name = None
    else:
        name = name.strip()

    summary = parsed.get("summary") or ""
    if not isinstance(summary, str):
        summary = ""

    exp_years = parsed.get("experience_years")
    if exp_years is not None:
        try:
            exp_years = int(exp_years)
        except (TypeError, ValueError):
            exp_years = None

    return {
        "skills": skills,
        "experience_years": exp_years,
        "job_titles": job_titles,
        "education": education,
        "name": name,
        "summary": summary.strip(),
    }


def _fallback_profile(resume_text: str) -> Dict:
    """Build a profile dict using only deterministic local extractors."""
    name = extract_name(resume_text)
    return {
        "skills": parse_resume_to_skills_from_text(resume_text),
        "experience_years": None,
        "job_titles": [],
        "education": [],
        "name": name if name and name != "Not found" else None,
        "summary": "",
    }


# ---------------------------------------------------------------------------
# Contact Info Extraction
# ---------------------------------------------------------------------------

def extract_contact_info(text: str) -> Dict[str, List[str]]:
    emails   = re.findall(EMAIL_RE, text, flags=re.I)
    phones   = re.findall(PHONE_RE, text)
    linkedin = re.findall(LINKEDIN_RE, text, flags=re.I)
    return {
        "emails":   list(set(emails)),
        "phones":   list(set(phones)),
        "linkedin": list(set(linkedin)),
    }


# ---------------------------------------------------------------------------
# Name Extraction
# ---------------------------------------------------------------------------

def extract_name(text: str) -> str:
    # Heuristic: the name is usually on the first non-empty line
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        # Skip lines that look like emails, phone numbers, or URLs
        if (re.search(EMAIL_RE, line, re.I)
                or re.search(PHONE_RE, line)
                or re.search(r"https?://", line)):
            continue
        # A name line is typically short (2-5 words) and mostly alphabetic
        words = line.split()
        if 1 <= len(words) <= 5 and all(re.match(r"^[A-Za-z.\-']+$", w) for w in words):
            return line
    return "Not found"


# ---------------------------------------------------------------------------
# Skills Extraction  (public — signature unchanged)
# ---------------------------------------------------------------------------

def extract_skills(text: str) -> List[str]:
    """
    Return a deduplicated list of skills found in text, ordered by relevance
    score (most relevant first).  Uses word-boundary regex matching, alias
    resolution, context-pattern detection, and section-weighted scoring —
    replacing the old naive substring approach.
    """
    sections = extract_sections(text)
    scored = _extract_skills_with_scores(text, sections)
    scored.sort(key=lambda x: x["score"], reverse=True)
    return [item["name"] for item in scored]


# ---------------------------------------------------------------------------
# Section-based Extraction  (public — return structure unchanged, adds "skills")
# ---------------------------------------------------------------------------

def extract_sections(text: str) -> Dict[str, str]:
    """
    Parse common resume section headers and return their content.
    Returns {"experience": str, "projects": str, "skills": str}.
    The "skills" key is new; existing callers only reading "experience" /
    "projects" are unaffected.
    """
    sections = {"experience": "", "projects": "", "skills": ""}
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    # Expanded header regex — catches "Technical Skills", "Professional Experience", etc.
    header_re = re.compile(
        r"^("
        r"PROJECTS?|"
        r"EXPERIENCE|WORK EXPERIENCE|WORK HISTORY|PROFESSIONAL EXPERIENCE|EMPLOYMENT HISTORY|"
        r"INTERNSHIPS?|"
        r"EDUCATION|ACADEMIC BACKGROUND|ACADEMIC QUALIFICATIONS|"
        r"SKILLS?|TECHNICAL SKILLS?|KEY SKILLS?|CORE SKILLS?|SKILLS? SUMMARY|"
        r"CERTIFICATIONS?|ACHIEVEMENTS?|AWARDS?|SUMMARY|OBJECTIVE|PROFILE"
        r")[:\-\s]*$",
        flags=re.I,
    )

    current_section = None
    buffer: Dict[str, List[str]] = {key: [] for key in sections}

    for line in lines:
        m = header_re.match(line)
        if m:
            header = m.group(1).lower()
            if "project" in header:
                current_section = "projects"
            elif any(kw in header for kw in ("experience", "internship", "employment", "work history")):
                current_section = "experience"
            elif any(kw in header for kw in ("skill", "technical", "key skill", "core skill")):
                current_section = "skills"
            else:
                current_section = None
            continue
        if current_section:
            buffer[current_section].append(line)

    sections["projects"]   = "\n".join(buffer["projects"]).strip()
    sections["experience"] = "\n".join(buffer["experience"]).strip()
    sections["skills"]     = "\n".join(buffer["skills"]).strip()
    return sections


# ---------------------------------------------------------------------------
# Keyword Extraction  (public — signature unchanged)
# ---------------------------------------------------------------------------

def extract_keywords(text: str, top_n: int = 15) -> List[str]:
    """
    Extract meaningful technical keywords from resume text.

    Improvements over the original:
    - Uses pre-compiled skill patterns (word-boundary safe) instead of substring
    - Collects capitalized technical-looking tokens (camelCase, acronyms, digit-mixed)
    - Filters with ALL_NOISE (STOPWORDS + RESUME_NOISE)
    - Applies a section boost (1.5×) for terms appearing in skills/exp/projects
    - Returns top_n by weighted frequency
    """
    candidates: List[str] = []

    # 1. All SKILLS_DB / alias hits (word-boundary matched)
    for pat, canonical in _SKILL_PATTERNS:
        if pat.search(text):
            candidates.append(canonical)

    # 2. Capitalized tokens that look like technology names
    #    Accept: has a digit (OAuth2), camelCase (TensorFlow), short ALL-CAPS acronym (AWS)
    cap_token_re = re.compile(r'\b[A-Z][a-zA-Z0-9+#._-]{2,}\b')
    for m in cap_token_re.finditer(text):
        raw = m.group()
        token = raw.lower()
        if token in ALL_NOISE or len(token) <= 2:
            continue
        looks_technical = (
            any(c.isdigit() for c in raw)                              # "OAuth2", "EC2"
            or (raw != raw.lower() and raw != raw.upper() and len(raw) > 3)  # "TensorFlow"
            or (raw.isupper() and 2 <= len(raw) <= 6)                 # "AWS", "SQL", "GCP"
        )
        if looks_technical:
            candidates.append(token)

    # 3. Filter and count frequency
    candidates = [c for c in candidates if c not in ALL_NOISE and len(c) > 2]
    freq = Counter(candidates)

    # 4. Section boost: terms appearing in skills/experience/projects score 1.5×
    sections = extract_sections(text)
    section_text_lower = " ".join([
        sections.get("skills", ""),
        sections.get("experience", ""),
        sections.get("projects", ""),
    ]).lower()

    boosted: Dict[str, float] = {}
    for term, count in freq.items():
        boost = 1.5 if term in section_text_lower else 1.0
        boosted[term] = count * boost

    return sorted(boosted, key=boosted.__getitem__, reverse=True)[:top_n]


# ---------------------------------------------------------------------------
# Main Parsing  (public — signature and return keys unchanged)
# ---------------------------------------------------------------------------

def parse_resume(pdf_path: str) -> Dict:
    """
    Full resume parser. Calls extract_sections once and threads sections into
    the skill scorer to avoid redundant regex work.
    """
    text    = extract_text_from_pdf(pdf_path)
    name    = extract_name(text)
    contact = extract_contact_info(text)
    sections = extract_sections(text)                         # called once

    scored = _extract_skills_with_scores(text, sections)
    scored.sort(key=lambda x: x["score"], reverse=True)
    skills   = [item["name"] for item in scored]
    keywords = extract_keywords(text)

    return {
        "name":       name,
        "email":      contact.get("emails", []),
        "phone":      contact.get("phones", []),
        "linkedin":   contact.get("linkedin", []),
        "skills":     skills,
        "experience": sections["experience"] or "Not found",
        "projects":   sections["projects"]   or "Not found",
        "keywords":   keywords,
    }


# ---------------------------------------------------------------------------
# Convenience Wrapper  (public — unchanged)
# ---------------------------------------------------------------------------

def parse_resume_to_skills(file_path: str) -> List[str]:
    """
    Convenience wrapper for routes: given a resume file path, return a
    normalized list of skills suitable for downstream usage (e.g. prompting an
    LLM). It combines explicit SKILLS_DB matches with the top keywords and
    returns a de-duplicated, title-cased list of skills.
    """
    data     = parse_resume(file_path)
    skills   = data.get("skills",   []) or []
    keywords = data.get("keywords", []) or []

    # Merge and normalize, prefer explicit skills first
    merged = []
    for s in skills + keywords:
        if not s or not isinstance(s, str):
            continue
        normalized = s.strip()
        # Title case common multi-word skills (e.g., 'machine learning')
        normalized = " ".join([w.capitalize() for w in normalized.split()])
        if normalized not in merged:
            merged.append(normalized)

    # Limit to reasonable number
    return merged[:30]
