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

            # ✅ Updated model name
            model = genai.GenerativeModel("models/gemini-2.0-flash")

            prompt = (
                f"Generate {count} concise, varied technical interview questions "
                f"for a candidate skilled in {', '.join(skills)}. "
                "Return only the questions, one per line, no numbering or extra text."
            )

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
            print(f"⚠️ Gemini API call failed ({type(e).__name__}): {e}")

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
    Lightweight evaluator for candidate answers.
    Returns mock scores and summary.
    """
    words = len(answer.split()) if answer else 0
    confidence = min(100, 40 + words)
    technical = min(100, 30 + (10 if "python" in answer.lower() else 0) + min(words, 20))
    communication = min(100, 35 + min(words, 20))

    summary = "Auto-evaluated: emphasize quantitative results and technical clarity."

    return {
        "confidence": confidence,
        "technical": technical,
        "communication": communication,
        "summary": summary,
    }

