import os
import requests

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')


def generate_questions(keywords, count=7):
    # TODO: Replace this placeholder with a Gemini API call using GEMINI_API_KEY
    if not keywords:
        keywords = ['experience', 'projects', 'team']
    questions = []
    for i in range(count):
        kw = keywords[i % len(keywords)]
        questions.append(f'Please describe your experience with {kw}.')
    return questions


def evaluate_answer(question, answer):
    # TODO: Implement Gemini API call to evaluate the answer and return structured feedback
    length = len(answer.split())
    conf = min(100, 40 + length)
    tech = min(100, 30 + (10 if 'python' in answer.lower() else 0) + int(min(length, 20)))
    comm = min(100, 35 + int(min(length, 20)))
    summary = 'Auto-evaluated: focus on measurable achievements and technical depth.'
    return {'confidence': conf, 'technical': tech, 'communication': comm, 'summary': summary}
