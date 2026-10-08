"""
AI English Conversation Tutor - SQLite persistence layer
Uses only the sqlite3 standard library (no external dependencies)
Opens a new connection each time for safe use from FastAPI async contexts
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

try:
    # Normally use BASE_DIR from config.py
    from config import BASE_DIR
except ImportError:
    # Use this directory if config is unavailable, such as during unit tests
    BASE_DIR = Path(__file__).resolve().parent

# Automatically tag error types (rule-based, no LLM calls)
from error_tagger import tag_correction

# Database file path (db.DB_PATH can be replaced during tests)
DB_PATH = BASE_DIR / "tutor.db"


def _now() -> str:
    """Return the current time in ISO 8601 format (UTC)."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def get_connection():
    """Context manager that opens a new connection each time (thread-safe, auto-commit/close)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Initialize the tables, creating them if they do not exist."""
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS turns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL REFERENCES sessions(id),
                created_at TEXT NOT NULL,
                user_text TEXT NOT NULL,
                reply TEXT NOT NULL,
                natural_expression TEXT,
                encouragement TEXT,
                pronunciation_score INTEGER,
                recognition_confidence INTEGER
            );

            CREATE TABLE IF NOT EXISTS corrections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                turn_id INTEGER NOT NULL REFERENCES turns(id),
                original TEXT,
                corrected TEXT,
                explanation TEXT,
                error_type TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_turns_session ON turns(session_id);
            CREATE INDEX IF NOT EXISTS idx_corrections_turn ON corrections(turn_id);
        """)

        # Backward compatibility: add the error_type column to older tables if missing
        # (Ignore the duplicate column error if it already exists)
        try:
            conn.execute("ALTER TABLE corrections ADD COLUMN error_type TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE turns ADD COLUMN recognition_confidence INTEGER")
        except sqlite3.OperationalError:
            pass

        # Backward compatibility: add columns for review mode (simple SRS)
        # Handle duplicate column errors individually if they already exist
        for column_def in (
            "review_count INTEGER DEFAULT 0",      # Number of reviews
            "correct_streak INTEGER DEFAULT 0",    # Consecutive correct answers (resets after an incorrect answer)
            "next_review_at TEXT",                 # Next scheduled review time (NULL = not yet reviewed)
            "last_reviewed_at TEXT",               # Time of the most recent review
        ):
            try:
                conn.execute(f"ALTER TABLE corrections ADD COLUMN {column_def}")
            except sqlite3.OperationalError:
                pass


def save_turn(session_id: str, user_text: str, ai_response: dict, score: Optional[int]) -> int:
    """
    Save one conversation turn to the database.
    - Create the session if it is not registered
    - Save the turn and its correction list
    - Return the saved turn ID
    """
    now = _now()
    with get_connection() as conn:
        # Register the session if it does not exist
        conn.execute(
            "INSERT OR IGNORE INTO sessions (id, created_at) VALUES (?, ?)",
            (session_id, now),
        )

        cur = conn.execute(
            """
            INSERT INTO turns
                (session_id, created_at, user_text, reply,
                 natural_expression, encouragement, recognition_confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                now,
                user_text,
                ai_response.get("reply", ""),
                ai_response.get("natural_expression"),
                ai_response.get("encouragement", ""),
                score,
            ),
        )
        turn_id = cur.lastrowid

        # Save the correction list (skip invalid entries)
        for correction in ai_response.get("corrections", []) or []:
            if not isinstance(correction, dict):
                continue
            original = correction.get("original", "")
            corrected = correction.get("corrected", "")
            explanation = correction.get("explanation", "")
            # Automatically tag the error type using rules (no LLM calls)
            error_type = tag_correction(original, corrected, explanation)
            conn.execute(
                """
                INSERT INTO corrections
                    (turn_id, original, corrected, explanation, error_type)
                VALUES (?, ?, ?, ?, ?)
                """,
                (turn_id, original, corrected, explanation, error_type),
            )

        return turn_id


def get_history(session_id: str, limit: int = 20) -> list[dict]:
    """
    Return the session conversation history in messages format for the LLM.
    limit is the maximum number of messages (1 turn = 2 messages: user + assistant)
    """
    turn_limit = max(1, limit // 2)
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT user_text, reply FROM turns
            WHERE session_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (session_id, turn_limit),
        ).fetchall()

    messages: list[dict] = []
    # Results were fetched newest first, so restore chronological order
    for row in reversed(rows):
        messages.append({"role": "user", "content": row["user_text"]})
        messages.append({"role": "assistant", "content": row["reply"]})
    return messages


def get_session_summary_data(session_id: str) -> dict | None:
    """
    Return data for the session summary (today's learning report).
    - turns: user_text / reply / pronunciation_score / natural_expression (oldest first)
    - corrections: original / corrected / explanation / error_type (oldest first)
    Return None if the session has no turns.
    """
    with get_connection() as conn:
        turn_rows = conn.execute(
            """
            SELECT user_text, reply,
                   recognition_confidence AS pronunciation_score,
                   natural_expression
            FROM turns
            WHERE session_id = ?
            ORDER BY id ASC
            """,
            (session_id,),
        ).fetchall()

        # Exclude sessions with no turns (unused or nonexistent IDs) from summaries
        if not turn_rows:
            return None

        correction_rows = conn.execute(
            """
            SELECT c.original, c.corrected, c.explanation, c.error_type
            FROM corrections c
            JOIN turns t ON t.id = c.turn_id
            WHERE t.session_id = ?
            ORDER BY c.id ASC
            """,
            (session_id,),
        ).fetchall()

    return {
        "turns": [
            {
                "user_text": row["user_text"],
                "reply": row["reply"],
                "pronunciation_score": row["pronunciation_score"],
                "natural_expression": row["natural_expression"],
            }
            for row in turn_rows
        ],
        "corrections": [
            {
                "original": row["original"],
                "corrected": row["corrected"],
                "explanation": row["explanation"],
                "error_type": row["error_type"],
            }
            for row in correction_rows
        ],
    }


def get_recent_sessions(limit: int = 20) -> list[dict]:
    """Return recent sessions with turn count, average score, and last update."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                s.id,
                s.created_at,
                COUNT(t.id) AS turn_count,
                ROUND(AVG(t.recognition_confidence)) AS avg_score,
                MAX(t.created_at) AS last_active
            FROM sessions s
            LEFT JOIN turns t ON t.session_id = s.id
            GROUP BY s.id
            ORDER BY COALESCE(MAX(t.created_at), s.created_at) DESC,
                     COALESCE(MAX(t.id), 0) DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [
        {
            "id": row["id"],
            "created_at": row["created_at"],
            "turn_count": row["turn_count"],
            "avg_score": row["avg_score"],
            "last_active": row["last_active"],
        }
        for row in rows
    ]


def get_all_corrections(limit: int = 100) -> list[dict]:
    """Return correction history for all sessions, newest first (for the weakness dashboard)."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                c.id,
                c.original,
                c.corrected,
                c.explanation,
                c.error_type,
                t.session_id,
                t.user_text,
                t.created_at
            FROM corrections c
            JOIN turns t ON t.id = c.turn_id
            ORDER BY c.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [
        {
            "id": row["id"],
            "original": row["original"],
            "corrected": row["corrected"],
            "explanation": row["explanation"],
            "error_type": row["error_type"],
            "session_id": row["session_id"],
            "user_text": row["user_text"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def get_error_stats(example_limit: int = 3) -> list[dict]:
    """
    Return counts and recent examples for each error type (for the weakness dashboard).
    Rows without an error_type (older data) are grouped as "other".
    Return: [{error_type, count, examples: [{original, corrected, explanation}]}], ordered by count descending
    """
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                COALESCE(NULLIF(error_type, ''), 'other') AS error_type,
                COUNT(*) AS count
            FROM corrections
            GROUP BY 1
            ORDER BY count DESC, error_type ASC
            """
        ).fetchall()

        stats = []
        for row in rows:
            # Fetch a few recent correction examples for each type
            examples = conn.execute(
                """
                SELECT original, corrected, explanation
                FROM corrections
                WHERE COALESCE(NULLIF(error_type, ''), 'other') = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (row["error_type"], example_limit),
            ).fetchall()
            stats.append({
                "error_type": row["error_type"],
                "count": row["count"],
                "examples": [
                    {
                        "original": ex["original"],
                        "corrected": ex["corrected"],
                        "explanation": ex["explanation"],
                    }
                    for ex in examples
                ],
            })

    return stats


def get_dashboard_stats(score_limit: int = 20) -> dict:
    """
    Return overall statistics for the dashboard.
    - total_turns / total_corrections / avg_score
    - recent_scores: recent speech-recognition confidence scores (oldest first)
    """
    with get_connection() as conn:
        total_turns = conn.execute(
            "SELECT COUNT(*) AS n FROM turns"
        ).fetchone()["n"]
        total_corrections = conn.execute(
            "SELECT COUNT(*) AS n FROM corrections"
        ).fetchone()["n"]
        avg_row = conn.execute(
            "SELECT ROUND(AVG(recognition_confidence), 1) AS avg FROM turns "
            "WHERE recognition_confidence IS NOT NULL"
        ).fetchone()
        # Fetch recent scores newest first, then restore chronological order for display
        score_rows = conn.execute(
            """
            SELECT recognition_confidence AS score, created_at
            FROM turns
            WHERE recognition_confidence IS NOT NULL
            ORDER BY id DESC
            LIMIT ?
            """,
            (score_limit,),
        ).fetchall()

    return {
        "total_turns": total_turns,
        "total_corrections": total_corrections,
        "avg_score": avg_row["avg"],
        "recent_scores": [row["score"] for row in reversed(score_rows)],
    }


# ============================================================
# Review mode (simple SRS: Spaced Repetition System)
# ============================================================
# Review intervals (in days) based on consecutive correct answers.
# 1st correct = 1 day, 2nd = 3 days, 3rd = 7 days, 4th = 14 days, 5th and later = 30 days
SRS_INTERVALS_DAYS = [1, 3, 7, 14, 30]


def get_due_reviews(limit: int = 10) -> list[dict]:
    """
    Return corrections due for review.
    - Include items where next_review_at is NULL (not yet reviewed) or no later than the current time
    - Sort by most frequent error_type across all corrections, then oldest first (ascending ID)
    - Exclude items with an empty corrected value because they cannot be quizzed
    """
    now = _now()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                c.id,
                c.original,
                c.corrected,
                c.explanation,
                c.error_type,
                c.review_count,
                t.user_text
            FROM corrections c
            JOIN turns t ON t.id = c.turn_id
            JOIN (
                -- Frequency per error_type (normalize unset values to 'other')
                SELECT COALESCE(NULLIF(error_type, ''), 'other') AS et,
                       COUNT(*) AS freq
                FROM corrections
                GROUP BY 1
            ) f ON f.et = COALESCE(NULLIF(c.error_type, ''), 'other')
            WHERE (c.next_review_at IS NULL OR c.next_review_at <= ?)
              AND c.corrected IS NOT NULL AND TRIM(c.corrected) != ''
            ORDER BY f.freq DESC, c.id ASC
            LIMIT ?
            """,
            (now, limit),
        ).fetchall()

    return [
        {
            "id": row["id"],
            "original": row["original"],
            "corrected": row["corrected"],
            "explanation": row["explanation"],
            "error_type": row["error_type"],
            "review_count": row["review_count"] or 0,
            "user_text": row["user_text"],
        }
        for row in rows
    ]


def get_correction(correction_id: int) -> dict | None:
    """Get one correction for review answer checking. Return None if it does not exist."""
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, original, corrected, explanation, error_type,
                   review_count, correct_streak, next_review_at, last_reviewed_at
            FROM corrections
            WHERE id = ?
            """,
            (correction_id,),
        ).fetchone()
    return dict(row) if row else None


def record_review_result(correction_id: int, correct: bool) -> dict | None:
    """
    Update the simple SRS state based on the review result.
    - Correct: increment correct_streak. Use the previous streak to select an interval from SRS_INTERVALS_DAYS
      (1st correct = 1 day, 2nd = 3 days, ..., 5th and later = 30 days)
    - Incorrect: reset correct_streak to 0 and schedule another attempt in 1 day
    - Both: increment review_count and update last_reviewed_at
    Return the updated state dict, or None if the item does not exist.
    """
    now_dt = datetime.now(timezone.utc)
    with get_connection() as conn:
        row = conn.execute(
            "SELECT review_count, correct_streak FROM corrections WHERE id = ?",
            (correction_id,),
        ).fetchone()
        if row is None:
            return None

        old_streak = row["correct_streak"] or 0
        if correct:
            new_streak = old_streak + 1
            # Use the previous streak as the index (capped at 30 days)
            interval_days = SRS_INTERVALS_DAYS[min(old_streak, len(SRS_INTERVALS_DAYS) - 1)]
        else:
            new_streak = 0
            interval_days = 1  # Retry the next day after an incorrect answer

        next_review_at = (now_dt + timedelta(days=interval_days)).isoformat(timespec="seconds")
        last_reviewed_at = now_dt.isoformat(timespec="seconds")
        review_count = (row["review_count"] or 0) + 1

        conn.execute(
            """
            UPDATE corrections
            SET review_count = ?, correct_streak = ?,
                next_review_at = ?, last_reviewed_at = ?
            WHERE id = ?
            """,
            (review_count, new_streak, next_review_at, last_reviewed_at, correction_id),
        )

    return {
        "correction_id": correction_id,
        "review_count": review_count,
        "correct_streak": new_streak,
        "interval_days": interval_days,
        "next_review_at": next_review_at,
        "last_reviewed_at": last_reviewed_at,
    }
