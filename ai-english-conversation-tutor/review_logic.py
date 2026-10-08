import difflib
import re

# Threshold for "close" judgment (similarity of normalized text)
CLOSE_RATIO_THRESHOLD = 0.85


def normalize_review_text(text: str) -> str:
    """
    Normalize text for comparison.
    - Convert to lowercase
    - Strip leading/trailing whitespace
    - Compress consecutive spaces into one
    - Ignore trailing punctuation (. , ! ? ; :)
    """
    t = (text or "").lower().strip()
    t = re.sub(r"\s+", " ", t)
    # Remove trailing punctuation (even if repeated), then strip remaining trailing spaces
    t = re.sub(r"[.,!?;:]+$", "", t).rstrip()
    return t


def judge_review_answer(answer_text: str, corrected: str) -> dict:
    """
    Compare answer text with the correct text after normalization.
    - Exact match: correct=True
    - If not exact but similarity >= CLOSE_RATIO_THRESHOLD → close=True ("almost correct")
    Returns: {"correct": bool, "close": bool, "ratio": float}
    """
    answer = normalize_review_text(answer_text)
    target = normalize_review_text(corrected)

    # If either is empty, treat as incorrect
    if not answer or not target:
        return {"correct": False, "close": False, "ratio": 0.0}

    if answer == target:
        return {"correct": True, "close": False, "ratio": 1.0}

    ratio = difflib.SequenceMatcher(None, answer, target).ratio()
    return {
        "correct": False,
        "close": ratio >= CLOSE_RATIO_THRESHOLD,
        "ratio": round(ratio, 3),
    }
