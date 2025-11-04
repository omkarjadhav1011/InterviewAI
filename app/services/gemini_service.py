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
You are an AI Interview Assistant designed to conduct realistic, beginner-level job interviews.

Your goal is to simulate a professional yet approachable interview experience, ask relevant and clear questions, and remember details from the candidate's previous responses to create a natural and adaptive conversation flow.

**Guidelines:**
1. Maintain a professional but friendly and encouraging tone to make the candidate comfortable.
2. Ask **one clear, concise question at a time**.
3. Focus on **basic and intermediate-level** questions that assess **core concepts, understanding, and practical thinking**.
4. Include both **technical** and **behavioral** aspects relevant to the candidate's role.
5. Keep responses and questions under **3 sentences**, unless deeper exploration is required.

    Generate {count} concise, varied **basic or intermediate-level** technical interview questions
    for a candidate skilled in {', '.join(skills)}.
    Focus on testing **practical understanding** and **core concepts**.
    Return only the questions, **one per line**, with **no numbering or extra text**.

Your overall goal is to assess the candidate's **foundational knowledge, communication skills, and reasoning ability** while maintaining a conversational, encouraging tone.
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
As an expert technical interviewer, evaluate the following interview response.
Consider clarity, technical accuracy, and communication skills.

Question: {question}
Answer: {answer}

Provide evaluation in the following JSON format:
{{
    "confidence": <score 0-100>,
    "technical": <score 0-100>,
    "communication": <score 0-100>,
    "summary": "<brief evaluation summary>",
    "feedback": "<constructive feedback>",
    "strengths": ["<key strength 1>", "<key strength 2>"],
    "areas_to_improve": ["<area 1>", "<area 2>"]
}}

Base the scores on:
- Confidence: Answer structure, certainty in statements
- Technical: Accuracy, depth of knowledge, proper terminology
- Communication: Clarity, organization, example usage
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
