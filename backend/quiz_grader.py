# backend/quiz_grader.py
"""Lightweight LLM‑based grader for the final quiz.

Returns per‑question scores (0‒1) and an overall average.
No persistence; everything lives in memory until the wrap phase.
"""

from __future__ import annotations

import json
from typing import List, Tuple

from langchain_openai import ChatOpenAI
from utils.config import load_api_key

# single shared client
_llm_grader = ChatOpenAI(
    model_name="gpt-4o-mini",
    temperature=0,           # deterministic scoring
    openai_api_key=load_api_key(),
)

_GRADER_SYSTEM_PROMPT = (
    "You are a strict but fair examiner. "
    "Read the question and the learner's answer, then reply with *only* a JSON "
    "object on a single line in the form {\"score\": <float 0-1>, \"feedback\": <str>} . "
    "Score 1.0 means fully correct; 0.5 partially correct; 0.0 incorrect or blank."
)

_JSON_TAG = "```json"  # guard against code‑block wrapping

def _grade_one(llm: ChatOpenAI, question: str, answer: str) -> Tuple[float, str]:
    """Grade a single Q/A pair. Returns (score, feedback)."""
    user_prompt = f"Question:\n{question}\n\nLearner answer:\n{answer}"
    resp = llm([
        {"role": "system", "content": _GRADER_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]).content.strip()

    # tolerate code‑block fences
    if resp.startswith(_JSON_TAG):
        resp = resp.removeprefix(_JSON_TAG).rstrip("`").strip()
    try:
        data = json.loads(resp)
        return float(data.get("score", 0.0)), str(data.get("feedback", ""))
    except Exception:
        return 0.0, "Could not parse grader output"


def grade_test(llm: ChatOpenAI, questions: List[str], answers: List[str]) -> Tuple[List[float], float]:
    """Grade aligned lists of questions & answers. Missing answers → score 0."""
    scores: List[float] = []
    for q, a in zip(questions, answers + [""] * (len(questions) - len(answers))):
        score, _ = _grade_one(llm, q, a)
        scores.append(score)
    overall = sum(scores) / len(scores) if scores else 0.0
    return scores, overall
