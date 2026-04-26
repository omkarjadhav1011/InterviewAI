import os
from typing import List, Optional
import logging

# Optional Google Generative AI client import
try:
    import google.generativeai as genai
except Exception:
    genai = None

from ..utils.gemini_runtime import call_gemini_with_timeout, parse_json_response

# --- Configuration ---
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
GEMINI_MODEL_NAME = "models/gemini-2.0-flash"

# Timeout default if Flask app context is unavailable (e.g. tools/ scripts)
_DEFAULT_GEMINI_TIMEOUT = 15

# --- Logging setup ---
logger = logging.getLogger(__name__)

if genai is None:
    logger.warning("Google Generative AI client not installed. Using fallback.")
else:
    logger.info("Google Generative AI client is available.")

if GEMINI_API_KEY:
    logger.info("GEMINI_API_KEY found in environment.")
else:
    logger.warning("GEMINI_API_KEY not set. Gemini calls will be skipped.")


def _gemini_timeout() -> int:
    """Read GEMINI_TIMEOUT from current Flask app config when available."""
    try:
        from flask import current_app
        return int(current_app.config.get("GEMINI_TIMEOUT", _DEFAULT_GEMINI_TIMEOUT))
    except Exception:
        return _DEFAULT_GEMINI_TIMEOUT


# Skill-driven question templates, one per question type. Each template MUST contain
# `{skill}` exactly once; the fallback generator substitutes the candidate's actual
# skills (cycled if fewer skills than question types).
_QUESTION_TEMPLATES_BY_TYPE = {
    "technical_depth": [
        "Walk me through how you would design a production-ready service using {skill}, including the key trade-offs you'd weigh.",
        "Explain the {skill} concept you find most often misunderstood by engineers, and why it matters in production.",
    ],
    "practical_application": [
        "Describe a concrete project where you applied {skill} to solve a real problem. What was the outcome and what did you measure?",
        "How have you used {skill} in a production setting, and what specific challenge did it address?",
    ],
    "problem_solving": [
        "A service built around {skill} is failing intermittently under load and the logs are unhelpful. Walk me through how you diagnose and resolve it.",
        "You've been asked to migrate a critical component that relies on {skill} with zero downtime. What's your plan and where do you see the biggest risks?",
    ],
    "behavioural_technical": [
        "Tell me about a time you made a difficult technical decision involving {skill}. What was the trade-off and what would you do differently today?",
        "Describe a project that used {skill} where things went wrong. What did you learn, and how did it change how you work?",
    ],
    "innovation": [
        "If you could redesign one common pattern in how {skill} is used today, what would it be and why?",
        "What's the most impactful improvement you'd make to a {skill}-based system you've worked on if you had one more month?",
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


def _generate_skill_based_questions(skills: List[str], count: int = 5) -> List[str]:
    """Deterministically generate `count` distinct, skill-grounded questions.

    Uses the candidate's actual skills (cycled if fewer than `count`) and varies
    the question type across the slot order. Each question references at least
    one specific skill — never a generic placeholder.
    """
    skills = [s for s in (skills or []) if isinstance(s, str) and s.strip()]
    if not skills:
        # Final-tier fallback: still skill-shaped, just generic-domain
        skills = ["your strongest technical area"]

    # Per-template-list rotating index so different runs over the same skill set
    # don't produce identical wording. We use len(skill_index) as a cheap salt.
    questions: List[str] = []
    for i in range(count):
        qtype = _QUESTION_TYPE_ORDER[i % len(_QUESTION_TYPE_ORDER)]
        templates = _QUESTION_TEMPLATES_BY_TYPE[qtype]
        skill = skills[i % len(skills)]
        template = templates[i % len(templates)]
        questions.append(template.format(skill=skill))
    return questions


def _get_model():
    """Configure and return a genai model instance, or None if unavailable."""
    if not genai or not GEMINI_API_KEY:
        return None
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        return genai.GenerativeModel(GEMINI_MODEL_NAME)
    except Exception:
        logger.exception("Failed to configure Gemini model")
        return None


# -------------------------------------------------------------------
# FUNCTION: Generate Questions
# -------------------------------------------------------------------
def generate_questions(skills: List[str], count: int = 5,
                       experience_level: str = "intermediate",
                       previous_topics: Optional[List[str]] = None) -> List[str]:
    """
    Generate distinct interview questions covering different question types.

    Returns a list of plain-string question texts (length == count) so the existing
    `interview.js` flow that iterates session['interview_questions'] keeps working.
    """
    skills = [s for s in (skills or []) if isinstance(s, str) and s.strip()]
    if not skills:
        skills = ["software engineering experience", "projects", "team collaboration"]

    model = _get_model()
    if model is None:
        logger.info("Using fallback question generator (no Gemini).")
        return _generate_skill_based_questions(skills, count)

    prompt = f"""You are a senior technical interviewer at a top-tier technology company.
Generate exactly 5 interview questions for a candidate with the following profile.

Candidate skills: {', '.join(skills)}
Role level: {experience_level}
Previously asked topics (do NOT repeat these): {', '.join(previous_topics or []) or 'none'}

Requirements for each question:
1. Cover a DIFFERENT skill or dimension than every other question in this set
2. Vary the question TYPE across the 5 questions using this exact distribution:
   - Q1: Technical depth (explain a concept or design decision)
   - Q2: Practical application (a real scenario solvable with their skills)
   - Q3: Problem-solving under constraints (a challenge with limited resources or time)
   - Q4: Behavioural + technical hybrid (a past experience showing technical judgment)
   - Q5: Open-ended innovation (an improvement or future build)
3. Each question must be answerable in 90-120 seconds of spoken response.
4. Avoid generic prompts like "Tell me about yourself" or "What are your strengths".
5. Make each question specific to the listed skills - name the technology or domain.

Return ONLY a JSON array - no markdown fences, no commentary:
[
  {{"id": 1, "question": "...", "skill_focus": "...", "question_type": "technical_depth"}},
  {{"id": 2, "question": "...", "skill_focus": "...", "question_type": "practical_application"}},
  {{"id": 3, "question": "...", "skill_focus": "...", "question_type": "problem_solving"}},
  {{"id": 4, "question": "...", "skill_focus": "...", "question_type": "behavioural_technical"}},
  {{"id": 5, "question": "...", "skill_focus": "...", "question_type": "innovation"}}
]"""

    try:
        raw = call_gemini_with_timeout(model, prompt, timeout=_gemini_timeout())
        parsed = parse_json_response(raw)
    except (TimeoutError, ValueError):
        logger.exception("Gemini question generation failed; using fallback")
        return _generate_skill_based_questions(skills, count)
    except Exception:
        logger.exception("Unexpected error in generate_questions; using fallback")
        return _generate_skill_based_questions(skills, count)

    if not isinstance(parsed, list):
        logger.error("Gemini returned non-array for questions; using fallback")
        return _generate_skill_based_questions(skills, count)

    questions: List[str] = []
    for item in parsed:
        if isinstance(item, dict) and item.get("question"):
            questions.append(str(item["question"]).strip())
        elif isinstance(item, str) and item.strip():
            questions.append(item.strip())

    if not questions:
        return _generate_skill_based_questions(skills, count)

    # Pad or truncate to caller's requested count, using skill-based templates
    if len(questions) < count:
        pad = _generate_skill_based_questions(skills, count - len(questions))
        questions.extend(pad)
    return questions[:count]


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
        return _fallback_evaluation(question, answer)
    except Exception:
        logger.exception("Unexpected evaluation error; using fallback")
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
    pairs = list(zip(questions, answers))
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
    except Exception:
        logger.exception("Unexpected full-interview evaluation error")

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
    """Minimal fallback when Gemini is unavailable for batch evaluation."""
    n = len(questions)
    answer_evaluation = []
    for i, (q, a) in enumerate(zip(questions, answers)):
        words = len((a or "").split()) if a else 0
        score = min(60, max(0, words * 3))
        answer_evaluation.append({
            "question": q,
            "answer_summary": (a or "")[:100],
            "issues": ["Unable to evaluate (AI unavailable)"],
            "score": score,
            "justification": "Evaluated by word count only (Gemini unavailable).",
        })

    avg_score = int(sum(e["score"] for e in answer_evaluation) / n) if n else 0
    if avg_score >= 75:
        verdict = "Hire"
    elif avg_score >= 45:
        verdict = "Weak Hire"
    else:
        verdict = "Reject"

    return {
        "questions_review": [
            {
                "skill": s,
                "original_question": questions[i] if i < len(questions) else "",
                "issues": ["Evaluation unavailable"],
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
                "strength": "Medium",
                "insight": "Detailed evaluation unavailable.",
            }
            for s in skills
        ],
        "overall_evaluation": {
            "final_score": avg_score,
            "verdict": verdict,
            "summary": "Automated evaluation was unavailable. Scores are approximate.",
        },
    }


def _fallback_evaluation(question: str, answer: str) -> dict:
    """Fallback evaluation when Gemini is unavailable."""
    words = len(answer.split()) if answer else 0
    if words == 0:
        confidence = technical = communication = 0
    elif words <= 2:
        confidence = technical = communication = 15
    else:
        confidence = min(100, 40 + min(words // 2, 30))
        technical = min(
            100,
            30
            + (10 if any(tech in answer.lower() for tech in ["example", "project", "implemented"]) else 0)
            + min(words // 3, 30),
        )
        communication = min(100, 35 + min(words // 4, 35))

    return {
        "confidence": confidence,
        "technical": technical,
        "communication": communication,
        "summary": "Answer evaluated by length and keyword heuristic (Gemini unavailable).",
        "feedback": "Provide more specific examples and technical details.",
        "strengths": ["Attempted to answer the question"] if words else [],
        "areas_to_improve": ["Add more technical specifics", "Provide concrete examples"],
        "key_strength": "" if not words else "engaged with the question",
        "key_gap": "Limited evaluation - automated scoring fallback in use.",
    }
