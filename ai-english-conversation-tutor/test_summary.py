"""
Tests for the session summary (today's learning report).
- Unit tests for db.get_session_summary_data
- FastAPI TestClient tests for GET /api/summary/{session_id} (LLM is mocked)
Run with: python test_summary.py (no pytest required; uses standard assert)
"""

import json
import os
import tempfile
from pathlib import Path

# Set the temporary test database before importing db
TMP_DIR = tempfile.mkdtemp(prefix="summary_test_")
TEST_DB_PATH = Path(TMP_DIR) / "test_tutor.db"

import db
db.DB_PATH = TEST_DB_PATH

import server
from fastapi.testclient import TestClient

PASSED = []


def check(name: str, condition: bool, detail: str = ""):
    """Simple assertion helper (raises immediately on failure)."""
    assert condition, f"FAILED: {name} {detail}"
    PASSED.append(name)
    print(f"  ok - {name}")


def make_session_data():
    """Insert two turns of session data for testing."""
    db.init_db()
    session_id = "sess_test_1"
    db.save_turn(
        session_id,
        "I go to school yesterday",
        {
            "reply": "What did you do at school?",
            "corrections": [
                {"original": "I go to school yesterday",
                 "corrected": "I went to school yesterday",
                 "explanation": "Use past tense 'went' with 'yesterday'"},
            ],
            "natural_expression": "I went to school yesterday.",
            "encouragement": "Nice try!",
        },
        72,
    )
    db.save_turn(
        session_id,
        "I had a great time at the party",
        {
            "reply": "That sounds fun! What was the best part?",
            "corrections": [],
            "natural_expression": None,
            "encouragement": "Great!",
        },
        90,
    )
    return session_id


# ============================================================
# 1. Unit tests for db.get_session_summary_data
# ============================================================
def test_db_get_session_summary_data():
    print("[1] db.get_session_summary_data")
    session_id = make_session_data()

    data = db.get_session_summary_data(session_id)
    check("turn count", data is not None and len(data["turns"]) == 2)
    check("turns are oldest first", data["turns"][0]["user_text"] == "I go to school yesterday")
    check("turn includes reply", data["turns"][0]["reply"] == "What did you do at school?")
    check("turn includes score",
          [t["pronunciation_score"] for t in data["turns"]] == [72, 90])
    check("includes natural_expression",
          data["turns"][0]["natural_expression"] == "I went to school yesterday.")
    check("correction count", len(data["corrections"]) == 1)
    c = data["corrections"][0]
    check("correction contents",
          c["original"] == "I go to school yesterday"
          and c["corrected"] == "I went to school yesterday"
          and c["explanation"].startswith("Use past tense"))
    # error_tagger should tag this as a tense error
    check("error_type is assigned", c["error_type"] == "tense", f"got {c['error_type']}")

    # A session with no turns returns None
    check("nonexistent session returns None", db.get_session_summary_data("no_such_session") is None)


# ============================================================
# 2. Unit tests for parse_summary_llm_json
# ============================================================
def test_parse_summary_llm_json():
    print("[2] server.parse_summary_llm_json")

    # Extract JSON even with a code block and introductory text
    raw = ('Here is your report!\n```json\n'
           '{"highlights": ["Good tense usage", "Nice vocabulary"], '
           '"focus_areas": ["Articles", "Prepositions"], '
           '"phrase_to_remember": "I went to school yesterday.", '
           '"message": "Keep it up!"}\n```')
    fb = server.parse_summary_llm_json(raw)
    check("extracts after removing code block", fb["highlights"] == ["Good tense usage", "Nice vocabulary"])
    check("extracts focus_areas", fb["focus_areas"] == ["Articles", "Prepositions"])
    check("extracts phrase", fb["phrase_to_remember"] == "I went to school yesterday.")
    check("extracts message", fb["message"] == "Keep it up!")

    # Malformed responses fall back to empty highlights, etc.
    fb2 = server.parse_summary_llm_json("sorry, I can't do that {broken json")
    check("malformed JSON falls back",
          fb2 == {"highlights": [], "focus_areas": [],
                  "phrase_to_remember": None, "message": ""})

    # Empty strings also fall back
    fb3 = server.parse_summary_llm_json("")
    check("empty response falls back", fb3["highlights"] == [] and fb3["phrase_to_remember"] is None)

    # Fields with invalid types are normalized (highlights is str, phrase is numeric)
    fb4 = server.parse_summary_llm_json(
        '{"highlights": "only one", "focus_areas": [1, "two"], '
        '"phrase_to_remember": 123, "message": null}')
    check("normalizes invalid types",
          fb4["highlights"] == ["only one"]
          and fb4["focus_areas"] == ["1", "two"]
          and fb4["phrase_to_remember"] is None
          and fb4["message"] == "")


# ============================================================
# 3. API tests for GET /api/summary/{session_id} (mock LLM)
# ============================================================
def test_api_summary():
    print("[3] GET /api/summary/{session_id}")
    session_id = "sess_test_1"  # Already inserted by test_db
    original_get_llm_response = server.get_llm_response

    client = TestClient(server.app)

    # ---- Case 1: LLM succeeds (returns JSON with a code block) ----
    async def mock_llm_ok(messages):
        # Also confirm the prompt includes the conversation and corrections
        joined = json.dumps(messages, ensure_ascii=False)
        assert "I go to school yesterday" in joined
        assert "I went to school yesterday" in joined
        return ('```json\n{"highlights": ["h1", "h2"], "focus_areas": ["f1", "f2"], '
                '"phrase_to_remember": "I went to school yesterday.", '
                '"message": "Great job today!"}\n```')

    server.get_llm_response = mock_llm_ok
    try:
        resp = client.get(f"/api/summary/{session_id}")
        check("200 on success", resp.status_code == 200)
        body = resp.json()
        st = body["stats"]
        check("turn_count", st["turn_count"] == 2)
        check("avg_score", st["avg_score"] == 81.0, f"got {st['avg_score']}")
        check("max/min_score", st["max_score"] == 90 and st["min_score"] == 72)
        check("correction_count", st["correction_count"] == 1)
        check("error type breakdown", st["error_types"] == [{"error_type": "tense", "count": 1}])
        check("natural_expressions",
              st["natural_expressions"] == ["I went to school yesterday."])
        fb = body["feedback"]
        check("returns LLM feedback",
              fb["highlights"] == ["h1", "h2"] and fb["focus_areas"] == ["f1", "f2"]
              and fb["phrase_to_remember"] == "I went to school yesterday."
              and fb["message"] == "Great job today!")

        # ---- Case 2: LLM fails → 200 with stats only, feedback is null ----
        async def mock_llm_fail(messages):
            raise RuntimeError("LLM connection error (simulated)")

        server.get_llm_response = mock_llm_fail
        resp2 = client.get(f"/api/summary/{session_id}")
        check("200 even if LLM fails", resp2.status_code == 200)
        body2 = resp2.json()
        check("feedback is null when LLM fails", body2["feedback"] is None)
        check("stats are returned even if LLM fails", body2["stats"]["turn_count"] == 2)

        # ---- Case 3: session with no turns returns 404 (LLM is not called) ----
        llm_called = []

        async def mock_llm_spy(messages):
            llm_called.append(True)
            return "{}"

        server.get_llm_response = mock_llm_spy
        resp3 = client.get("/api/summary/no_such_session")
        check("unknown session returns 404", resp3.status_code == 404)
        check("LLM is not called for 404", llm_called == [])

        # ---- Case 4: LLM returns malformed JSON → 200 with fallback feedback ----
        async def mock_llm_garbage(messages):
            return "I am sorry, I cannot produce JSON today."

        server.get_llm_response = mock_llm_garbage
        resp4 = client.get(f"/api/summary/{session_id}")
        check("200 even with malformed JSON", resp4.status_code == 200)
        fb4 = resp4.json()["feedback"]
        check("malformed JSON produces empty fallback feedback",
              fb4 is not None and fb4["highlights"] == [] and fb4["message"] == "")
    finally:
        server.get_llm_response = original_get_llm_response


if __name__ == "__main__":
    test_db_get_session_summary_data()
    test_parse_summary_llm_json()
    test_api_summary()
    print(f"\nAll {len(PASSED)} checks passed.")
