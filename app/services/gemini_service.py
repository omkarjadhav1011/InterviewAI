import os
import random
import time
from typing import Any, Dict, List, Optional
import logging

# Optional Google Generative AI client import
try:
    import google.generativeai as genai
except Exception:
    genai = None

from ..utils.gemini_runtime import call_gemini_with_timeout, parse_json_response

# --- Configuration ---
# Model name can be overridden via env. Default is the most-cost-efficient model
# that has separate free-tier quota from the older 2.0-flash. When a model is
# unavailable (404 / 403 leaked-key / 429 quota) we fall through the candidates
# in `_MODEL_CANDIDATES` until one responds.
_DEFAULT_MODEL = "models/gemini-2.5-flash"
_MODEL_CANDIDATES = (
    os.getenv("GEMINI_MODEL_NAME") or _DEFAULT_MODEL,
    "models/gemini-2.5-flash",
    "models/gemini-2.5-flash-lite",
    "models/gemini-2.0-flash",
    "models/gemini-2.0-flash-lite",
)

# Timeout default if Flask app context is unavailable (e.g. tools/ scripts)
_DEFAULT_GEMINI_TIMEOUT = 15

# --- Logging setup ---
logger = logging.getLogger(__name__)


def _gemini_api_key() -> str:
    """Read the API key fresh on each call so dotenv reloads / test fixtures work."""
    return (os.getenv("GEMINI_API_KEY") or "").strip()


if genai is None:
    logger.warning("Google Generative AI client not installed. Using fallback.")
else:
    logger.info("Google Generative AI client is available.")


def _gemini_timeout() -> int:
    """Read GEMINI_TIMEOUT from current Flask app config when available."""
    try:
        from flask import current_app
        return int(current_app.config.get("GEMINI_TIMEOUT", _DEFAULT_GEMINI_TIMEOUT))
    except Exception:
        return _DEFAULT_GEMINI_TIMEOUT


# Skill-driven question templates, one per question type. Each template uses
# `{skill}` and may use `{seniority}`, `{title}`, or `{years}` for personalization.
# The fallback generator substitutes the candidate's actual profile (cycled if needed).
_QUESTION_TEMPLATES_BY_TYPE = {
    "technical_depth": [
        "In simple words, what is {skill} and what is it commonly used for?",
        "Can you explain one important concept in {skill} that you've learned, in your own words?",
        "What do you like about {skill}, and when would you choose to use it?",
    ],
    "practical_application": [
        "Tell me about a small project or assignment where you used {skill}. What did you build?",
        "How have you used {skill} in a project, even a learning project? Walk me through what you did.",
        "Describe one feature you built with {skill}. Keep it simple — just the basics of what you did.",
    ],
    "problem_solving": [
        "Have you ever run into a bug or error while working with {skill}? How did you figure out the fix?",
        "If a beginner asked you for one tip when starting with {skill}, what would you tell them?",
        "What's one common mistake people make when using {skill}, and how can it be avoided?",
    ],
    "behavioural_technical": [
        "Tell me about something new you learned recently about {skill}. How did you learn it?",
        "Describe a time you helped a teammate or classmate with {skill}. What did you explain?",
        "What's been the most fun thing about working with {skill} so far?",
    ],
    "innovation": [
        "If you had time to explore {skill} more, what would you want to learn next?",
        "What's one small improvement you'd like to try in a project that uses {skill}?",
        "What's one thing about {skill} you'd like to understand better?",
    ],
}

# Order matters: matches the 5 question-type slots requested by the Gemini prompt.
_QUESTION_TYPE_ORDER = (
    "technical_depth",
    "practical_application",
    "problem_solving",
    "behavioural_technical",
    "innovation",
)


def _seniority_from_years(experience_years: Optional[int]) -> str:
    """Map years of experience to a seniority bucket used for prompt tailoring."""
    if experience_years is None:
        return "intermediate"
    if experience_years < 2:
        return "junior"
    if experience_years < 5:
        return "mid-level"
    if experience_years < 10:
        return "senior"
    return "staff"


def _normalize_profile(profile: Optional[Dict[str, Any]],
                      skills: Optional[List[str]] = None) -> Dict[str, Any]:
    """Merge an explicit profile dict with a fallback skill list into a canonical form."""
    profile = profile or {}
    out_skills = [s for s in (profile.get("skills") or skills or []) if isinstance(s, str) and s.strip()]
    titles = [t for t in (profile.get("job_titles") or []) if isinstance(t, str) and t.strip()]
    education = [e for e in (profile.get("education") or []) if isinstance(e, str) and e.strip()]
    years = profile.get("experience_years")
    try:
        years = int(years) if years is not None else None
    except (TypeError, ValueError):
        years = None
    summary = profile.get("summary") or ""
    name = profile.get("name") or ""
    return {
        "skills": out_skills,
        "job_titles": titles,
        "education": education,
        "experience_years": years,
        "seniority": _seniority_from_years(years),
        "summary": summary.strip() if isinstance(summary, str) else "",
        "name": name.strip() if isinstance(name, str) else "",
    }


def _generate_skill_based_questions(
    skills: List[str],
    count: int = 5,
    profile: Optional[Dict[str, Any]] = None,
    seed: Optional[int] = None,
) -> List[str]:
    """Deterministically generate `count` distinct, skill-grounded questions.

    Personalizes templates using the candidate's profile (titles, seniority,
    years) when available, varies the question type across the slot order, and
    uses a per-session seed to vary wording across reruns of the same profile.
    """
    norm = _normalize_profile(profile, skills)
    skills = norm["skills"] or ["your strongest technical area"]
    title = (norm["job_titles"][0] if norm["job_titles"] else "software engineer")
    seniority = norm["seniority"]
    years = norm["experience_years"] if norm["experience_years"] is not None else 3

    rng = random.Random(seed if seed is not None else int(time.time()))

    questions: List[str] = []
    for i in range(count):
        qtype = _QUESTION_TYPE_ORDER[i % len(_QUESTION_TYPE_ORDER)]
        templates = _QUESTION_TEMPLATES_BY_TYPE[qtype]
        skill = skills[i % len(skills)]
        template = rng.choice(templates)
        text = template.replace("{skill}", skill)
        # Keep the formatter forgiving in case any template still references
        # title/seniority/years (templates are intentionally beginner-friendly
        # now and ignore those, but stay defensive).
        try:
            text = text.format(title=title, seniority=seniority, years=years)
        except (KeyError, IndexError, ValueError):
            pass
        questions.append(text)
    return questions


_model = None
_model_name_used = None
# Track candidates that failed permanently in this process so we don't retry them
# on every request (e.g. 403 leaked-key, 404 model-not-found).
_model_blacklist: set = set()


def _is_permanent_error(exc: Exception) -> bool:
    """403 (leaked / forbidden) and 404 (model not found) are not retry-worthy."""
    name = type(exc).__name__
    msg = str(exc)
    if name in ("PermissionDenied", "NotFound", "Unauthenticated"):
        return True
    return "403" in msg or "404" in msg or "leaked" in msg.lower()


def _get_model():
    """Configure and return a genai model instance, or None if unavailable.

    Tries each model in `_MODEL_CANDIDATES` until one is reachable.  Caches the
    first working model for the rest of the process.  On transient failure
    (e.g. 429 quota) the next request will try again from the top of the list.
    """
    global _model, _model_name_used

    if _model is not None:
        return _model

    if not genai:
        return None

    api_key = _gemini_api_key()
    if not api_key:
        logger.warning(
            "GEMINI_API_KEY not set. All Gemini calls will use the heuristic fallback. "
            "Add GEMINI_API_KEY=... to your .env to enable AI evaluation."
        )
        return None
    if len(api_key) < 20:
        logger.error("GEMINI_API_KEY looks invalid (length %d).", len(api_key))
        return None

    try:
        genai.configure(api_key=api_key)
    except Exception:
        logger.exception("genai.configure() failed")
        return None

    seen = set()
    for name in _MODEL_CANDIDATES:
        if not name or name in seen or name in _model_blacklist:
            continue
        seen.add(name)
        try:
            model = genai.GenerativeModel(name)
            # Cheap probe so we don't hand back a model that 429s on first real call
            model.generate_content(
                "ok",
                generation_config={"max_output_tokens": 4},
                request_options={"timeout": 10},
            )
            _model = model
            _model_name_used = name
            logger.info("Gemini model ready: %s", name)
            return _model
        except Exception as e:
            if _is_permanent_error(e):
                _model_blacklist.add(name)
                logger.error(
                    "Gemini model %s permanently unavailable: %s: %s",
                    name, type(e).__name__, str(e)[:200],
                )
            else:
                logger.warning(
                    "Gemini model %s probe failed (will retry next request): %s: %s",
                    name, type(e).__name__, str(e)[:200],
                )

    logger.warning(
        "No Gemini model is reachable right now. Using heuristic fallback. "
        "Common causes: API key flagged as leaked (rotate it), free-tier daily "
        "quota exceeded, or no quota for the configured model."
    )
    return None


def _classify_gemini_error(e: Exception) -> Optional[str]:
    """Tag common Gemini failure modes for clearer server-side ops logs.

    Returns one of "quota", "auth", or None. The result is for logging only —
    it must never be surfaced to the user-facing response payload.
    """
    msg = (str(e) or "").lower()
    if "quota" in msg or "429" in msg or "resource_exhausted" in msg or "rate limit" in msg:
        return "quota"
    if "api_key" in msg or "api key" in msg or "401" in msg or "403" in msg or "permission" in msg:
        return "auth"
    return None


def _log_gemini_failure(context: str, e: Exception) -> None:
    """Emit a clearly tagged ops log when Gemini fails. User-facing path stays clean."""
    kind = _classify_gemini_error(e)
    if kind == "quota":
        logger.error(
            "[GEMINI:QUOTA] %s — daily/free-tier quota exhausted. "
            "Check https://aistudio.google.com/app/apikey or rotate GEMINI_API_KEY. "
            "Falling back to heuristic scoring for this request.",
            context,
        )
    elif kind == "auth":
        logger.error(
            "[GEMINI:AUTH] %s — API key rejected (invalid / leaked / lacks permission). "
            "Verify GEMINI_API_KEY in .env. Falling back to heuristic scoring.",
            context,
        )
    else:
        logger.exception("[GEMINI:UNKNOWN] %s — falling back to heuristic scoring.", context)


def _reset_model_for_retry():
    """Clear the cached model so the next call retries from the top of the list."""
    global _model, _model_name_used
    _model = None
    _model_name_used = None


def _format_profile_block(profile: Dict[str, Any]) -> str:
    """Render a normalized profile dict as a human-readable prompt block."""
    parts: List[str] = []
    if profile.get("name"):
        parts.append(f"Name: {profile['name']}")
    if profile.get("job_titles"):
        parts.append("Recent job titles: " + ", ".join(profile["job_titles"][:5]))
    years = profile.get("experience_years")
    seniority = profile.get("seniority", "intermediate")
    if years is not None:
        parts.append(f"Total experience: {years} years ({seniority})")
    else:
        parts.append(f"Inferred seniority: {seniority}")
    if profile.get("education"):
        parts.append("Education: " + "; ".join(profile["education"][:3]))
    if profile.get("skills"):
        parts.append("Skills (in order of resume emphasis): " + ", ".join(profile["skills"][:15]))
    if profile.get("summary"):
        parts.append("Resume summary: " + profile["summary"][:400])
    return "\n".join(parts) if parts else "No profile data available."


def _format_history_block(previous_qa: Optional[List[Dict[str, str]]]) -> str:
    """Render prior Q&A so the LLM can build follow-ups instead of repeating."""
    if not previous_qa:
        return "(no questions asked yet — this is the first question of the interview)"
    out: List[str] = []
    for i, item in enumerate(previous_qa, 1):
        q = (item.get("question") or "").strip()
        a = (item.get("answer") or "").strip()
        if not q:
            continue
        a_excerpt = (a[:300] + "…") if len(a) > 300 else a
        out.append(f"Q{i}: {q}\nA{i}: {a_excerpt or '(no answer captured)'}")
    return "\n\n".join(out) if out else "(none)"


# -------------------------------------------------------------------
# FUNCTION: Generate Questions
# -------------------------------------------------------------------
def generate_questions(skills: List[str], count: int = 5,
                       experience_level: str = "intermediate",
                       previous_topics: Optional[List[str]] = None,
                       profile: Optional[Dict[str, Any]] = None,
                       previous_qa: Optional[List[Dict[str, str]]] = None,
                       session_seed: Optional[int] = None) -> List[str]:
    """
    Generate distinct interview questions covering different question types.

    Profile-aware: when a `profile` dict is supplied (skills, experience_years,
    job_titles, education, summary, name), the LLM tailors each question to the
    candidate's seniority, role, and combination of skills — not just one skill.
    `previous_qa` lets the model build on or contrast with earlier answers.
    `session_seed` salts the prompt so reruns over the same profile produce
    different wording and angles.

    Returns a list of plain-string question texts (length == count) so the existing
    `interview.js` flow that iterates session['interview_questions'] keeps working.
    """
    norm = _normalize_profile(profile, skills)
    if not norm["skills"]:
        norm["skills"] = ["software engineering experience", "projects", "team collaboration"]
    if session_seed is None:
        session_seed = int(time.time() * 1000) & 0xFFFF

    model = _get_model()
    if model is None:
        logger.info("Using fallback question generator (no Gemini).")
        return _generate_skill_based_questions(norm["skills"], count, profile=norm, seed=session_seed)

    profile_block = _format_profile_block(norm)
    history_block = _format_history_block(previous_qa)
    seniority = norm["seniority"]
    avoid_topics = ", ".join(previous_topics or []) or "none"

    prompt = f"""You are a friendly interviewer running an introductory, BEGINNER-FRIENDLY interview.
Generate exactly {count} interview questions tailored to the candidate below.

CANDIDATE PROFILE
-----------------
{profile_block}

PRIOR INTERVIEW HISTORY
-----------------------
{history_block}

TOPICS TO AVOID REPEATING
-------------------------
{avoid_topics}

DIVERSITY SALT (use to vary wording / angle across reruns): {session_seed}

DIFFICULTY — this is the most important rule:
- All questions MUST be EASY enough that a complete beginner with only basic familiarity could answer.
- NO advanced topics: no system design, no production trade-offs, no scaling, no architecture, no incident response, no zero-downtime migration, no performance tuning, no concurrency edge cases.
- NO jargon-heavy phrasing. Prefer plain English, short sentences, and conversational tone.
- It's fine to reference the candidate's specific skills and one or two profile details (skill name, project, or topic), but DO NOT calibrate to "senior" or "staff" depth even if the resume suggests seniority — keep it gentle and approachable for everyone.
- A good rule of thumb: if a first-year student or self-taught beginner couldn't reasonably answer in 1-2 minutes, the question is too hard.

PERSONALIZATION:
- Reference at least one specific named skill from the candidate's profile in each question (so it doesn't feel generic), but keep the depth simple.
- Where prior Q&A exists, each new question should naturally follow up on something the candidate already said — but stay easy.

VARIETY across the {count} questions (truncate if count<5):
   - Q1: Concept check — "in simple words, what is X" or "what does X do".
   - Q2: Practical use — "tell me about a small project where you used X".
   - Q3: Light problem-solving — "have you run into an error with X, how did you fix it" or "one tip for a beginner with X".
   - Q4: Reflective/behavioural — "what did you learn about X" or "how did you help someone with X".
   - Q5: Curiosity — "what would you like to learn next about X".

OTHER RULES:
- Each question must be answerable in 60-120 seconds of spoken response.
- Do NOT use these forbidden openers: "Tell me about yourself", "What are your strengths", "Walk me through your resume".
- Do NOT ask about salary, location, availability, or non-technical biographical info.

Return ONLY a JSON array — no markdown fences, no commentary:
[
  {{"id": 1, "question": "...", "skill_focus": "...", "question_type": "technical_depth", "rationale": "<why this question fits this candidate at a beginner level>"}},
  ...
]"""

    try:
        raw = call_gemini_with_timeout(model, prompt, timeout=_gemini_timeout())
        parsed = parse_json_response(raw)
    except (TimeoutError, ValueError):
        logger.exception("Gemini question generation failed; using fallback")
        _reset_model_for_retry()
        return _generate_skill_based_questions(norm["skills"], count, profile=norm, seed=session_seed)
    except Exception as e:
        logger.exception("Unexpected error in generate_questions; using fallback")
        if not _is_permanent_error(e):
            _reset_model_for_retry()
        return _generate_skill_based_questions(norm["skills"], count, profile=norm, seed=session_seed)

    if not isinstance(parsed, list):
        logger.error("Gemini returned non-array for questions; using fallback")
        return _generate_skill_based_questions(norm["skills"], count, profile=norm, seed=session_seed)

    questions: List[str] = []
    for item in parsed:
        if isinstance(item, dict) and item.get("question"):
            questions.append(str(item["question"]).strip())
        elif isinstance(item, str) and item.strip():
            questions.append(item.strip())

    if not questions:
        return _generate_skill_based_questions(norm["skills"], count, profile=norm, seed=session_seed)

    # Pad or truncate to caller's requested count, using profile-aware fallback templates
    if len(questions) < count:
        pad = _generate_skill_based_questions(
            norm["skills"], count - len(questions), profile=norm, seed=session_seed,
        )
        questions.extend(pad)
    return questions[:count]


# -------------------------------------------------------------------
# FUNCTION: Regenerate Next Question (adaptive, mid-interview)
# -------------------------------------------------------------------
def regenerate_next_question(
    profile: Optional[Dict[str, Any]],
    skills: List[str],
    previous_qa: List[Dict[str, str]],
    next_index: int,
    total_questions: int,
    fallback_question: Optional[str] = None,
) -> str:
    """Produce a single follow-up question that builds on what the candidate just said.

    Used between turns of the interview: after answer N is evaluated, this
    regenerates question N+1 so it adapts to the candidate's prior answer
    instead of being a static, pre-generated string. Falls back to the
    pre-generated question (or a profile-aware template) if Gemini is unavailable.
    """
    norm = _normalize_profile(profile, skills)
    seed = int(time.time() * 1000) & 0xFFFF

    if not norm["skills"]:
        return fallback_question or "Tell me about a challenging technical problem you've solved recently."

    model = _get_model()
    if model is None:
        # Fall through to a profile-aware template at the right slot
        return fallback_question or _generate_skill_based_questions(
            norm["skills"], total_questions, profile=norm, seed=seed,
        )[min(next_index, total_questions - 1)]

    # Map the slot index to a question type so the arc still varies
    slot_type = _QUESTION_TYPE_ORDER[next_index % len(_QUESTION_TYPE_ORDER)]
    profile_block = _format_profile_block(norm)
    history_block = _format_history_block(previous_qa)

    prompt = f"""You are a friendly interviewer continuing a BEGINNER-FRIENDLY interview.
Generate exactly ONE follow-up question (question #{next_index + 1} of {total_questions}).

CANDIDATE PROFILE
-----------------
{profile_block}

INTERVIEW SO FAR
----------------
{history_block}

DIFFICULTY — most important rule:
- The question MUST be EASY enough that a complete beginner could answer. Plain English, short, conversational.
- NO advanced topics (no system design, scaling, architecture, production trade-offs, incident response, performance tuning, concurrency edge cases, zero-downtime migrations).
- Even if the candidate sounds experienced, keep this question gentle and approachable.
- A first-year student or self-taught beginner should be able to answer in 1-2 minutes.

REQUIREMENTS for question #{next_index + 1}:
- The question's style should be: {slot_type.replace('_', ' ')}, but rendered in a beginner-friendly form (e.g. "in simple words, what is X" instead of "design a production-ready X service").
- It should build on something the candidate just said in the most recent answer (a topic, a tool they mentioned, a small detail). Do not repeat any topic already covered above.
- Reference at least one specific named skill from the candidate's profile so it doesn't feel generic.
- Answerable in 60-120 seconds of spoken response.
- Do NOT use generic openers like "Tell me about yourself" or "What's your favourite technology".

Return ONLY a JSON object — no markdown fences, no commentary:
{{"question": "...", "skill_focus": "...", "rationale": "<why this beginner-friendly question follows naturally from what they said>"}}"""

    try:
        raw = call_gemini_with_timeout(model, prompt, timeout=_gemini_timeout())
        parsed = parse_json_response(raw)
    except (TimeoutError, ValueError):
        logger.exception("Gemini next-question regen failed; using fallback")
        parsed = None
    except Exception:
        logger.exception("Unexpected next-question regen error; using fallback")
        parsed = None

    if isinstance(parsed, dict) and isinstance(parsed.get("question"), str):
        text = parsed["question"].strip()
        if text:
            return text

    if fallback_question:
        return fallback_question
    return _generate_skill_based_questions(
        norm["skills"], total_questions, profile=norm, seed=seed,
    )[min(next_index, total_questions - 1)]


# -------------------------------------------------------------------
# FUNCTION: Evaluate Answer (single Gemini call, all 3 dimensions)
# -------------------------------------------------------------------
def evaluate_answer(question: str, answer: str, skills: Optional[List[str]] = None) -> dict:
    """
    Evaluate a single answer across confidence/technical/communication using one Gemini call.
    Returns dict with: confidence, technical, communication, summary, feedback,
    strengths, areas_to_improve, key_strength, key_gap.
    Falls back to a heuristic evaluator on Gemini failure.
    """
    question = (question or '')[:1000]
    answer = (answer or '')[:5000]
    skills_str = ", ".join(skills) if skills else "general technical skills"

    model = _get_model()
    if model is None:
        logger.warning("Gemini unavailable; using fallback evaluator")
        return _fallback_evaluation(question, answer)

    prompt = f"""You are a senior technical interviewer. Evaluate the candidate's answer across three independent dimensions.

Question: {question}
Candidate skills: {skills_str}
Answer: {answer}

DIMENSION 1 - Confidence (0-100): assertiveness, ownership, specificity.
  [+] direct "I built/designed/chose"; concrete examples with numbers/names; structured problem->action->result.
  [-] hedging "I think maybe"; vague generalizations; passive voice without agent; very short answers (<20 words).

DIMENSION 2 - Technical (0-100): correctness, depth, relevance, practical knowledge.
  [+] accurate facts and terminology; goes beyond surface ("why" not just "what"); addresses the technical content; shows real-world experience.
  [-] textbook-only; missing key concepts; factual errors; off-topic.

DIMENSION 3 - Communication (0-100): grammar, clarity, structure, vocabulary, conciseness.
  [+] clear topic sentence + supporting details; professional vocabulary; logical transitions; concise.
  [-] run-ons; frequent grammar errors; excessive filler ("like", "um", "basically"); circular or contradictory.

Score bands (apply per dimension): 90-100 exceptional - 75-89 strong - 55-74 mixed - 35-54 weak - 15-34 poor - 0-14 empty/incoherent.

Edge cases:
- If answer is <=2 words: all three scores must be <=20 and note "answer too short".
- If answer is empty: all three scores = 0.

Return ONLY a JSON object - no markdown fences, no commentary:
{{
  "confidence": <0-100>,
  "technical": <0-100>,
  "communication": <0-100>,
  "summary": "<1-2 sentence overall summary>",
  "feedback": "<actionable, constructive improvement tip in 1-2 sentences>",
  "strengths": ["<key strength 1>", "<key strength 2>"],
  "areas_to_improve": ["<area 1>", "<area 2>"],
  "key_strength": "<the single strongest thing about the answer>",
  "key_gap": "<the single most important thing missing or wrong>"
}}"""

    try:
        raw = call_gemini_with_timeout(model, prompt, timeout=_gemini_timeout())
        evaluation = parse_json_response(raw)
        if not isinstance(evaluation, dict):
            raise ValueError("evaluation response was not a JSON object")
        # Coerce score fields to ints
        for k in ("confidence", "technical", "communication"):
            try:
                evaluation[k] = int(round(float(evaluation.get(k, 0))))
            except (TypeError, ValueError):
                evaluation[k] = 0
            evaluation[k] = max(0, min(100, evaluation[k]))
        # Ensure list fields exist
        evaluation.setdefault("strengths", [])
        evaluation.setdefault("areas_to_improve", [])
        evaluation.setdefault("summary", "")
        evaluation.setdefault("feedback", "")
        evaluation.setdefault("key_strength", "")
        evaluation.setdefault("key_gap", "")
        logger.info("Gemini evaluation parsed successfully")
        return evaluation
    except (TimeoutError, ValueError):
        logger.exception("Gemini evaluation failed; using fallback")
        _reset_model_for_retry()
        return _fallback_evaluation(question, answer)
    except Exception as e:
        _log_gemini_failure("evaluate_answer", e)
        if not _is_permanent_error(e):
            _reset_model_for_retry()
        return _fallback_evaluation(question, answer)


# -------------------------------------------------------------------
# FUNCTION: Evaluate Full Interview (batch, post-interview)
# -------------------------------------------------------------------
def evaluate_full_interview(skills: list, questions: list, answers: list) -> dict:
    """
    Comprehensive post-interview evaluation. Returns the existing rich shape
    (questions_review, answer_evaluation, skill_summary, overall_evaluation)
    that result.html consumes. Falls back gracefully when Gemini is unavailable.
    """
    pairs = list(zip(questions, answers or []))
    transcript_block = "\n\n".join(
        f"Q{i+1}: {q}\nA{i+1}: {a}" for i, (q, a) in enumerate(pairs)
    )
    skills_csv = ", ".join(skills) if skills else "general technical skills"

    model = _get_model()
    if model is None:
        logger.warning("Gemini not available; using fallback full-interview evaluation.")
        return _fallback_full_evaluation(skills, questions, answers)

    prompt = f"""You are an expert technical interviewer and evaluator.

You are given:
1. Skills extracted from the candidate's resume: {skills_csv}
2. Questions and Candidate Answers (combined from speech + typed input):

CANDIDATE ANSWERS:
{transcript_block}

---
PART 1 - QUESTION EVALUATION & IMPROVEMENT
For each question: identify issues (too generic, repetitive, vague) and rewrite it to be more specific, skill-focused, and diverse in style (conceptual / practical / scenario-based / experience-based).
Assign a difficulty: Basic | Intermediate | Advanced.

PART 2 - STRICT ANSWER EVALUATION
The answers may be a combination of spoken transcripts and manually typed text. Evaluate based on the overall quality, correctness, and completeness of the combined answer.
Score each answer strictly 0-100:
  0       = completely wrong, irrelevant, or no answer
  10-30   = very weak, shallow, mostly incorrect
  40-60   = partial understanding, lacks depth
  70-85   = good, mostly correct with minor gaps
  90-100  = excellent, precise, in-depth, well-articulated

CRITICAL:
- If the answer is vague, generic, or unsatisfying -> score MUST be 0
- No partial credit for non-answers
- Be strict and evidence-based

PART 3 - SKILL SUMMARY
Aggregate performance per skill. Label each as Strong | Medium | Weak.

PART 4 - OVERALL EVALUATION
Compute a final score (0-100) reflecting strict scoring.
Assign a verdict: Strong Hire | Hire | Weak Hire | Reject.

Return ONLY valid JSON - no commentary, no markdown fences:
{{
  "questions_review": [
    {{
      "skill": "<skill name>",
      "original_question": "<original>",
      "issues": ["<issue1>", "<issue2>"],
      "improved_question": "<rewritten question>",
      "difficulty": "<Basic|Intermediate|Advanced>"
    }}
  ],
  "answer_evaluation": [
    {{
      "question": "<question text>",
      "answer_summary": "<short summary of candidate answer>",
      "issues": ["<issue1>"],
      "score": <0-100>,
      "justification": "<reason for score>"
    }}
  ],
  "skill_summary": [
    {{
      "skill": "<skill>",
      "average_score": <0-100>,
      "strength": "<Strong|Medium|Weak>",
      "insight": "<brief explanation>"
    }}
  ],
  "overall_evaluation": {{
    "final_score": <0-100>,
    "verdict": "<Strong Hire|Hire|Weak Hire|Reject>",
    "summary": "<concise honest evaluation>"
  }}
}}"""

    try:
        raw = call_gemini_with_timeout(model, prompt, timeout=_gemini_timeout() * 2)
        parsed = parse_json_response(raw)
        if isinstance(parsed, dict):
            return parsed
        logger.error("Full-interview evaluation returned non-object; using fallback")
    except (TimeoutError, ValueError):
        logger.exception("evaluate_full_interview Gemini call failed")
        _reset_model_for_retry()
    except Exception as e:
        _log_gemini_failure("evaluate_full_interview", e)
        if not _is_permanent_error(e):
            _reset_model_for_retry()

    return _fallback_full_evaluation(skills, questions, answers)


# -------------------------------------------------------------------
# FUNCTION: Compute final_scores aggregation block for interview_runs
# -------------------------------------------------------------------
def compute_final_scores(per_question_results: list, full_evaluation: Optional[dict] = None) -> dict:
    """
    Aggregate per-question dimension scores into the final_scores block stored
    on each interview_runs document. Pure-Python (no Gemini call) so it always works.

    Inputs:
      per_question_results: list of dicts shaped like the session_results entries
                            (each has .result.{confidence, technical, communication}
                            and .answer / .questionNumber).
      full_evaluation: optional dict from evaluate_full_interview() — used to
                       lift verdict and overall_feedback when available.

    Output keys:
      overall_score (1-10), confidence_avg, technical_avg, communication_avg,
      hire_recommendation (strong_yes|yes|maybe|no), overall_feedback,
      strengths (list), areas_for_improvement (list).

    Floor rules apply on the 0-100 weighted average BEFORE division by 10
    (the spec's "weighted_avg / 10" then ">=75" comparison was unit-inconsistent).
    """
    if not per_question_results:
        return {
            "overall_score": 1.0,
            "confidence_avg": 0,
            "technical_avg": 0,
            "communication_avg": 0,
            "hire_recommendation": "no",
            "overall_feedback": "No answers were recorded.",
            "strengths": [],
            "areas_for_improvement": ["Provide answers to receive an evaluation"],
        }

    confs, techs, comms = [], [], []
    capped_indices = []
    for i, r in enumerate(per_question_results):
        result = (r or {}).get("result") or {}
        ans = ((r or {}).get("answer") or "").strip()
        words = len(ans.split()) if ans else 0
        try:
            c = float(result.get("confidence", 0))
            t = float(result.get("technical", 0))
            m = float(result.get("communication", 0))
        except (TypeError, ValueError):
            c = t = m = 0.0
        if words == 0:
            c = t = m = 0.0
            capped_indices.append(i)
        elif words <= 2:
            c = min(c, 20.0)
            t = min(t, 20.0)
            m = min(m, 20.0)
            capped_indices.append(i)
        confs.append(c)
        techs.append(t)
        comms.append(m)

    n = len(per_question_results)
    confidence_avg = round(sum(confs) / n, 1)
    technical_avg = round(sum(techs) / n, 1)
    communication_avg = round(sum(comms) / n, 1)

    weighted_100 = (technical_avg * 0.5
                    + confidence_avg * 0.25
                    + communication_avg * 0.25)
    if weighted_100 >= 75:
        overall_10 = max(weighted_100 / 10.0, 8.0)
    elif weighted_100 >= 45:
        overall_10 = max(weighted_100 / 10.0, 5.0)
    else:
        overall_10 = weighted_100 / 10.0
    overall_10 = round(max(1.0, min(10.0, overall_10)), 1)

    if weighted_100 >= 80:
        recommendation = "strong_yes"
    elif weighted_100 >= 65:
        recommendation = "yes"
    elif weighted_100 >= 45:
        recommendation = "maybe"
    else:
        recommendation = "no"

    # Pull feedback from full_evaluation when available; build a generic one otherwise
    overall_feedback = ""
    if isinstance(full_evaluation, dict):
        overall_eval = full_evaluation.get("overall_evaluation") or {}
        overall_feedback = overall_eval.get("summary") or ""

    if not overall_feedback:
        overall_feedback = (
            f"Average scores - confidence {confidence_avg:.0f}, technical {technical_avg:.0f}, "
            f"communication {communication_avg:.0f}. Weighted overall {overall_10:.1f}/10."
        )

    # Aggregate strengths / improvements from per-question evaluations
    strengths_set = []
    improvements_set = []
    for r in per_question_results:
        res = (r or {}).get("result") or {}
        for s in (res.get("strengths") or []):
            if s and s not in strengths_set:
                strengths_set.append(s)
        for s in (res.get("areas_to_improve") or []):
            if s and s not in improvements_set:
                improvements_set.append(s)

    return {
        "overall_score": overall_10,
        "confidence_avg": confidence_avg,
        "technical_avg": technical_avg,
        "communication_avg": communication_avg,
        "hire_recommendation": recommendation,
        "overall_feedback": overall_feedback,
        "strengths": strengths_set[:5],
        "areas_for_improvement": improvements_set[:5],
        "capped_questions": capped_indices,
    }


# -------------------------------------------------------------------
# Fallbacks (offline path when GEMINI_API_KEY is missing or Gemini fails)
# -------------------------------------------------------------------
def _fallback_full_evaluation(skills: list, questions: list, answers: list) -> dict:
    """Heuristic fallback when Gemini is unavailable for batch evaluation.

    Uses the same per-answer heuristic as `_fallback_evaluation` so each
    question card gets meaningful issues / justification instead of a generic
    "Unable to evaluate" placeholder.
    """
    answers = answers or []
    n = len(questions)
    answer_evaluation = []
    per_q_scores = []

    for i, q in enumerate(questions):
        a = answers[i] if i < len(answers) else ""
        ev = _fallback_evaluation(q, a)
        # Map the three 0-100 dimension scores into one strict 0-100 score
        avg_pct = (ev.get("confidence", 0) + ev.get("technical", 0) + ev.get("communication", 0)) / 3
        score = int(round(avg_pct))
        per_q_scores.append(score)

        issues = list(ev.get("areas_to_improve") or [])
        if not a or not str(a).strip():
            issues = ["No answer recorded"]

        answer_evaluation.append({
            "question": q,
            "answer_summary": (a or "")[:160],
            "issues": issues[:3],
            "score": score,
            "justification": ev.get("summary") or "Scored heuristically (AI evaluation unavailable).",
        })

    avg_score = int(sum(per_q_scores) / n) if n else 0
    if avg_score >= 75:
        verdict = "Hire"
        summary = (
            "Solid performance across the board. You demonstrated good technical "
            "understanding and communicated your thought process clearly. A few "
            "areas to sharpen before a real interview."
        )
    elif avg_score >= 45:
        verdict = "Weak Hire"
        summary = (
            "You showed potential but left gaps in technical depth or clarity. "
            "Focus on structuring answers more precisely and backing them with "
            "concrete examples and measurable outcomes."
        )
    else:
        verdict = "Reject"
        summary = (
            "Your answers need more depth and structure. Practise giving specific, "
            "example-driven responses and review the core concepts in your skill "
            "areas before your next interview."
        )

    logger.info(
        "Heuristic full-evaluation generated (avg_score=%d, verdict=%s) — "
        "AI evaluator was not used for this run.",
        avg_score, verdict,
    )

    return {
        "questions_review": [
            {
                "skill": s,
                "original_question": questions[i] if i < len(questions) else "",
                "issues": [],
                "improved_question": questions[i] if i < len(questions) else "",
                "difficulty": "Intermediate",
            }
            for i, s in enumerate(skills[:n])
        ],
        "answer_evaluation": answer_evaluation,
        "skill_summary": [
            {
                "skill": s,
                "average_score": avg_score,
                "strength": "Strong" if avg_score >= 75 else "Medium" if avg_score >= 45 else "Weak",
                "insight": (
                    "Strong demonstration of this skill across your answers."
                    if avg_score >= 75 else
                    "Some signal here — back it up with concrete examples and outcomes."
                    if avg_score >= 45 else
                    "Limited evidence — practise this area with project-grounded answers."
                ),
            }
            for s in skills
        ],
        "overall_evaluation": {
            "final_score": avg_score,
            "verdict": verdict,
            "summary": summary,
            "ai_evaluated": False,
        },
    }


def _fallback_evaluation(question: str, answer: str) -> dict:
    """Heuristic evaluation when Gemini is unavailable.

    Produces structured `strengths`, `areas_to_improve`, `feedback`, and
    `key_strength` / `key_gap` so the UI remains informative even with no AI.
    Marks itself with `ai_unavailable: True` so the frontend can surface a
    "scored heuristically" badge if it wants to.
    """
    answer = answer or ""
    words = len(answer.split())
    text = answer.lower()

    has_example = any(tok in text for tok in ("example", "for instance", "e.g.", "such as"))
    has_specifics = any(tok in text for tok in (
        "project", "built", "implemented", "designed", "deployed", "tested",
        "fixed", "debugged", "optimized", "refactored", "shipped",
    ))
    has_metrics = any(ch.isdigit() for ch in answer)
    has_structure = answer.count(".") >= 2 or "first" in text or "then" in text or "finally" in text
    hedging = sum(text.count(w) for w in ("i think maybe", "i guess", "kind of", "sort of", "probably"))

    if words == 0:
        confidence = technical = communication = 0
    elif words <= 2:
        confidence = technical = communication = 15
    else:
        # Confidence: length + specificity - hedging
        confidence = min(100, 35 + min(words // 2, 30) + (10 if has_specifics else 0) - (5 * hedging))
        # Technical: keyword-driven approximation
        technical = min(100, 25
                        + (15 if has_specifics else 0)
                        + (10 if has_example else 0)
                        + (10 if has_metrics else 0)
                        + min(words // 3, 25))
        # Communication: length-balanced
        communication = min(100, 30 + min(words // 4, 35) + (10 if has_structure else 0))
        confidence = max(0, confidence)

    strengths = []
    areas = []
    if words > 0:
        if has_specifics:
            strengths.append("Mentions concrete actions you took (built / implemented / etc.)")
        if has_example:
            strengths.append("Includes at least one supporting example")
        if has_metrics:
            strengths.append("Backed by numeric specifics")
        if has_structure:
            strengths.append("Answer has clear structure")
        if not strengths:
            strengths.append("Engaged with the question")

        if not has_specifics:
            areas.append("Name the specific tools, projects, or actions you took")
        if not has_example:
            areas.append("Add a concrete example to ground the answer")
        if not has_metrics:
            areas.append("Quantify the impact where possible (numbers, time saved, etc.)")
        if hedging:
            areas.append("Drop hedging language (\"I think maybe\", \"kind of\") — speak with ownership")
        if words < 30:
            areas.append("Expand the answer — aim for 60–120 seconds of spoken detail")
    else:
        areas = ["Provide an answer to receive feedback"]

    if words == 0:
        summary = "No answer was recorded."
        feedback = "Type or speak an answer so it can be evaluated."
    else:
        summary = (
            f"Answer scored heuristically: {words} words, "
            f"{'with' if has_specifics else 'without'} concrete specifics, "
            f"{'with' if has_example else 'no'} example."
        )
        feedback = (
            areas[0] if areas else "Continue practising for fluency and depth."
        )

    return {
        "confidence": confidence,
        "technical": technical,
        "communication": communication,
        "summary": summary,
        "feedback": feedback,
        "strengths": strengths[:3],
        "areas_to_improve": areas[:3],
        "key_strength": strengths[0] if strengths else "",
        "key_gap": areas[0] if areas else "",
        "ai_unavailable": True,
    }
