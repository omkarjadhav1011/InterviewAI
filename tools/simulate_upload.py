"""
Simple local script to simulate a resume upload without needing the web UI or login.
It calls the resume parser functions on a sample text and then calls the Gemini
service to generate questions. This demonstrates the console prints and logging
added to `gemini_service.py` and the route-like debug prints.

Run: py tools\simulate_upload.py
"""
import traceback

# Importing these modules will trigger the debug prints in gemini_service
from app.services import gemini_service
from app.services.resume_parser import extract_skills, extract_keywords

print('\n--- simulate_upload.py starting ---')

sample_text = (
    "Experienced software engineer with hands-on work in Python, Flask, Docker, "
    "REST API development, Machine Learning, TensorFlow, and AWS. Worked on several "
    "projects involving backend services and data pipelines."
)

try:
    skills = extract_skills(sample_text)
    keywords = extract_keywords(sample_text)
    merged = []
    for s in skills + keywords:
        if s and isinstance(s, str):
            normalized = ' '.join([w.capitalize() for w in s.strip().split()])
            if normalized not in merged:
                merged.append(normalized)
    print(f"Simulated parsing: extracted {len(merged)} skills/keywords. Sample: {merged[:10]}")

    # Generate questions using the gemini service (may use fallback)
    questions = gemini_service.generate_questions(merged, count=5)
    print('\nGenerated questions:')
    for i, q in enumerate(questions, 1):
        print(f"{i}. {q}")

except Exception as e:
    print('Error during simulation:')
    traceback.print_exc()

print('\n--- simulate_upload.py finished ---')
