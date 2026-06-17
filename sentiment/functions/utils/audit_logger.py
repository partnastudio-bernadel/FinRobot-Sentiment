import json
import os
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Audit Logger
# ---------------------------------------------------------------------------
# Writes scheduler telemetry metadata to a structured JSONL file.
# Each line is a self-contained JSON object representing one scheduler event.
#
# Future: replace _write_to_db() stub with a real audit_db / intent_chains
# table insert via the backend schema database connector.
# ---------------------------------------------------------------------------

# Default log file path (relative to the sentiment/ directory)
_DEFAULT_LOG_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),  # utils/
    "..", "..",                                   # -> sentiment/
    "logs"
)
_DEFAULT_LOG_PATH = os.path.join(_DEFAULT_LOG_DIR, "scheduler_audit.jsonl")


def log_scheduler_event(
    metadata: dict,
    log_path: str = _DEFAULT_LOG_PATH
) -> None:
    """
    Writes a scheduler audit event to the local JSONL log file.

    The metadata dict is expected to be the '_scheduler' block extracted from
    a MacroScheduler fallback payload, optionally enriched with the event_name.

    Args:
        metadata:  Dict containing scheduler state, source, timing, and flags.
        log_path:  Absolute path to the JSONL log file. Defaults to
                   sentiment/logs/scheduler_audit.jsonl.
    """
    entry = {
        "logged_at": datetime.now(timezone.utc).isoformat(),
        **metadata
    }

    # Ensure the logs directory exists
    os.makedirs(os.path.dirname(log_path), exist_ok=True)

    # Append the entry to the JSONL file
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

    print(f"[AuditLogger] Scheduler event written to: {os.path.abspath(log_path)}")

    # Stub for future database write
    _write_to_db(entry)


def extract_scheduler_block(payload: dict) -> tuple:
    """
    Separates the '_scheduler' audit metadata block from a payload dict.

    Args:
        payload: The full macro report dict, potentially containing '_scheduler'.

    Returns:
        Tuple[dict, dict | None]:
            - Clean payload (without '_scheduler' key).
            - The '_scheduler' block, or None if not present.
    """
    scheduler_meta = payload.pop("_scheduler", None)
    return payload, scheduler_meta


def _write_to_db(entry: dict) -> None:
    """
    Stub for future audit_db / intent_chains table insert.

    TODO: Replace this stub with a real database connector call, e.g.:
        from functions.utils.db_handler import get_db_connection
        conn = get_db_connection("audit_db")
        conn.execute(
            "INSERT INTO intent_chains (event, state, source, triggered_at, outage_ms) "
            "VALUES (?, ?, ?, ?, ?)",
            [entry.get("event_name"), entry.get("state"), entry.get("source"),
             entry.get("fallback_triggered_at"), entry.get("outage_duration_ms")]
        )
        conn.commit()
    """
    pass  # TODO: wire to audit_db intent_chains table (backend schema sprint)
