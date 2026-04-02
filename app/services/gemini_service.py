import os
from typing import List
import logging

# Optional Google Generative AI client import
try:
    import google.generativeai as genai
except Exception:
    genai = None

# --- Configuration ---
GEMINI_API_KEY = "AIzaSyBbiV0V5Q_9Sb8dbZNa4hvdli3BNgVo-qo"


# --- Logging setup ---
logger = logging.getLogger(__name__)

# Informational output
if genai is None:
    logger.warning("Google Generative AI client not installed. Using fallback.")
    print("Gemini client not installed; using fallback question generator.")
else:
    logger.info("Google Generative AI client is available.")
    print("Gemini client available.")

if GEMINI_API_KEY:
    logger.info("GEMINI_API_KEY found in environment.")
    print("Gemini API key loaded from environment.")
else:
    logger.warning("GEMINI_API_KEY not set.")
    print("Gemini API key is NOT set. Gemini calls will be skipped.")


# -------------------------------------------------------------------
# FUNCTION: Generate Questions
# -------------------------------------------------------------------
def generate_questions(skills: List[str], count: int = 7) -> List[str]:
    """
    Generate interview questions using Google Gemini 2.0 if available.
    Falls back to a simple generator if unavailable.
    """
    skills = [s for s in (skills or []) if isinstance(s, str) and s.strip()]
    if not skills:
        skills = ["experience", "projects", "team"]

    # --- Use Gemini API if available ---
    if genai and GEMINI_API_KEY:
        try:
            genai.configure(api_key=GEMINI_API_KEY)

            model = genai.GenerativeModel("models/gemini-2.0-flash")

            prompt = f"""
You are an AI Interview Assistant. Generate interview questions that are **strictly based on the candidate's resume skills**.

Skills extracted from resume: {', '.join(skills)}

Requirements:
- Generate exactly {count} questions.
- Each question must map to one or more of the listed skills; do NOT use skills outside the list.
- Mix question types: core concept, applied scenario, debugging/troubleshooting, and one behavioral question tied to a skill.
- Target beginner-to-intermediate level; avoid advanced theory unless a skill clearly implies it.
- Ask one clear question at a time, under 2 sentences.
- Keep the tone professional and encouraging.
- Do not mention the resume or the skill list explicitly.

Output format:
- Return only the questions, one per line.
- No numbering, no bullets, no extra text.
"""

            print("Gemini: Sending API request...")
            response = model.generate_content(prompt)
            print("Gemini: Response received.")

            if hasattr(response, "text") and response.text.strip():
                text = response.text.strip()
                questions = [line.strip("0123456789. )-").strip() for line in text.splitlines() if line.strip()]
                logger.info("Gemini returned %d questions.", len(questions))
                print(f"Gemini: returned {len(questions)} generated questions.")
                return questions[:count]

        except Exception as e:
            logger.exception("Gemini API call failed; using fallback generator.")
            print(f"Gemini API call failed ({type(e).__name__}): {e}")

    # --- Fallback question generator ---
    logger.info("Using fallback question generator.")
    print("Using fallback question generator.")
    return [
        f"Explain your experience with {kw}. Provide an example project and technical details."
        for kw in (skills * (count // len(skills) + 1))[:count]
    ]


# -------------------------------------------------------------------
# FUNCTION: Evaluate Answer
# -------------------------------------------------------------------
def evaluate_answer(question: str, answer: str) -> dict:
    """
    Evaluates the candidate's answer using Gemini API.
    Returns detailed feedback and scores.
    """
    if not genai or not GEMINI_API_KEY:
        logger.warning("Gemini API not available; using fallback evaluator")
        return _fallback_evaluation(question, answer)

    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("models/gemini-2.0-flash")

        prompt = f"""
You are an expert technical interviewer. Evaluate the candidate's response based only on the content of the answer/transcript.

Question: {question}
Answer/Transcript: {answer}

Scoring rubric (0-100 each):
- Confidence: structure, specificity, and decisiveness; penalize excessive hedging or vagueness.
- Technical: correctness, depth, and appropriate terminology; penalize inaccuracies or irrelevant content.
- Communication: clarity, organization, and helpful examples; penalize rambling or disorganized delivery.

Rules:
- If the answer is empty or nearly empty, give low scores and note missing content.
- If the answer is off-topic, reduce technical and communication scores.
- Favor concise, correct, well-structured answers with concrete examples.

Return ONLY valid JSON in this exact schema (no extra keys, no commentary):
{{
  "confidence": <score 0-100>,
  "technical": <score 0-100>,
  "communication": <score 0-100>,
  "summary": "<1-2 sentence evaluation summary>",
  "feedback": "<actionable, constructive feedback in 1-2 sentences>",
  "strengths": ["<key strength 1>", "<key strength 2>"],
  "areas_to_improve": ["<area 1>", "<area 2>"]
}}
"""

        response = model.generate_content(prompt)
        if hasattr(response, "text") and response.text.strip():
            import json, re
            text = response.text.strip()
            # Try direct JSON parse first
            try:
                evaluation = json.loads(text)
                logger.info("Generated evaluation for answer (direct JSON parse)")
                return evaluation
            except Exception:
                # Try to extract a JSON-like substring between the first { and the last }
                start = text.find('{')
                end = text.rfind('}')
                if start != -1 and end != -1 and end > start:
                    candidate = text[start:end+1]
                    try:
                        evaluation = json.loads(candidate)
                        logger.info("Generated evaluation for answer (extracted JSON substring)")
                        return evaluation
                    except Exception:
                        logger.debug('Failed to parse extracted JSON candidate')

                # Some models emit single quotes or minor formatting issues; try a loose fallback
                try:
                    candidate2 = text.replace("'", '"')
                    evaluation = json.loads(candidate2)
                    logger.info("Generated evaluation for answer (replaced single quotes)")
                    return evaluation
                except Exception:
                    logger.debug('Single-quote replacement parsing failed')

                # Last resort: log the raw response for debugging and use fallback
                logger.error("Failed to parse Gemini evaluation response; raw text:\n%s", text[:2000])
                return _fallback_evaluation(question, answer)

        return _fallback_evaluation(question, answer)

    except Exception as e:
        logger.exception("Gemini evaluation failed")
        return _fallback_evaluation(question, answer)

# -------------------------------------------------------------------
# FUNCTION: Evaluate Full Interview (batch, post-interview)
# -------------------------------------------------------------------
def evaluate_full_interview(skills: list, questions: list, answers: list) -> dict:
    """
    Runs a comprehensive post-interview evaluation using the full transcript.
    Returns question reviews, strict per-answer scores, skill summaries, and a hire verdict.
    Falls back gracefully if Gemini is unavailable.
    """
    import json

    # Build transcript block
    pairs = list(zip(questions, answers))
    transcript_block = "\n\n".join(
        f"Q{i+1}: {q}\nA{i+1}: {a}" for i, (q, a) in enumerate(pairs)
    )
    skills_csv = ", ".join(skills) if skills else "general technical skills"

    if not genai or not GEMINI_API_KEY:
        logger.warning("Gemini not available; using fallback full-interview evaluation.")
        return _fallback_full_evaluation(skills, questions, answers)

    prompt = f"""You are an expert technical interviewer and evaluator.

You are given:
1. Skills extracted from the candidate's resume: {skills_csv}
2. A full interview transcript with questions and candidate answers.

TRANSCRIPT:
{transcript_block}

---
PART 1 — QUESTION EVALUATION & IMPROVEMENT
For each question: identify issues (too generic, repetitive, vague) and rewrite it to be more specific, skill-focused, and diverse in style (conceptual / practical / scenario-based / experience-based).
Assign a difficulty: Basic | Intermediate | Advanced.

PART 2 — STRICT ANSWER EVALUATION
Score each answer strictly 0–100:
  0          = completely wrong, irrelevant, or no answer
  10–30      = very weak, shallow, mostly incorrect
  40–60      = partial understanding, lacks depth
  70–85      = good, mostly correct with minor gaps
  90–100     = excellent, precise, in-depth, well-articulated

CRITICAL:
- If the answer is vague, generic, or unsatisfying → score MUST be 0
- No partial credit for non-answers
- Be strict and evidence-based

PART 3 — SKILL SUMMARY
Aggregate performance per skill. Label each as Strong | Medium | Weak.

PART 4 — OVERALL EVALUATION
Compute a final score (0–100) reflecting strict scoring.
Assign a verdict: Strong Hire | Hire | Weak Hire | Reject

Return ONLY valid JSON — no commentary, no markdown fences:
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
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("models/gemini-2.0-flash")
        response = model.generate_content(prompt)

        if hasattr(response, "text") and response.text.strip():
            text = response.text.strip()
            # Strip optional markdown fences
            if text.startswith("```"):
                text = text.split("```", 2)[-1] if text.count("```") >= 2 else text
                text = text.lstrip("json").strip()

            # Try direct parse
            try:
                return json.loads(text)
            except Exception:
                pass

            # Extract first { ... last }
            start, end = text.find("{"), text.rfind("}")
            if start != -1 and end > start:
                try:
                    return json.loads(text[start:end + 1])
                except Exception:
                    pass

            logger.error("Could not parse full-interview evaluation JSON; using fallback.")

    except Exception:
        logger.exception("evaluate_full_interview: Gemini API call failed.")

    return _fallback_full_evaluation(skills, questions, answers)


def _fallback_full_evaluation(skills: list, questions: list, answers: list) -> dict:
    """Minimal fallback when Gemini is unavailable for batch evaluation."""
    n = len(questions)
    answer_evaluation = []
    for i, (q, a) in enumerate(zip(questions, answers)):
        words = len(a.split()) if a else 0
        score = min(60, max(0, words * 3))
        answer_evaluation.append({
            "question": q,
            "answer_summary": a[:100] if a else "",
            "issues": ["Unable to evaluate (AI unavailable)"],
            "score": score,
            "justification": "Evaluated by word count only (Gemini unavailable)."
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
                "difficulty": "Intermediate"
            }
            for i, s in enumerate(skills[:n])
        ],
        "answer_evaluation": answer_evaluation,
        "skill_summary": [
            {
                "skill": s,
                "average_score": avg_score,
                "strength": "Medium",
                "insight": "Detailed evaluation unavailable."
            }
            for s in skills
        ],
        "overall_evaluation": {
            "final_score": avg_score,
            "verdict": verdict,
            "summary": "Automated evaluation was unavailable. Scores are approximate."
        }
    }


def _fallback_evaluation(question: str, answer: str) -> dict:
    """Fallback evaluation when Gemini is unavailable."""
    words = len(answer.split()) if answer else 0
    confidence = min(100, 40 + min(words // 2, 30))
    technical = min(100, 30 + (10 if any(tech in answer.lower() for tech in ["example", "project", "implemented"]) else 0) + min(words // 3, 30))
    communication = min(100, 35 + min(words // 4, 35))

    return {
        "confidence": confidence,
        "technical": technical,
        "communication": communication,
        "summary": "Answer evaluated based on length and keyword usage",
        "feedback": "Consider providing more specific examples and technical details",
        "strengths": ["Attempted to answer the question"],
        "areas_to_improve": ["Add more technical specifics", "Provide concrete examples"]
    }
