from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class PortfolioDataService:
    """Persistent store for user-entered portfolio inputs and live assessments."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS exposures (
                    id TEXT PRIMARY KEY,
                    entity TEXT NOT NULL,
                    currency TEXT NOT NULL,
                    amount TEXT NOT NULL,
                    maturity_days INTEGER NOT NULL,
                    hedged_pct TEXT NOT NULL,
                    source TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS policies (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    threshold TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    require_human_escalation INTEGER NOT NULL,
                    description TEXT,
                    source TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS assessments (
                    id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    @staticmethod
    def _exposure(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "entity": row["entity"],
            "currency": row["currency"],
            "amount": row["amount"],
            "maturity_days": row["maturity_days"],
            "hedged_pct": row["hedged_pct"],
            "source": row["source"],
            "created_at": row["created_at"],
        }

    @staticmethod
    def _policy(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "name": row["name"],
            "category": row["category"],
            "threshold": row["threshold"],
            "severity": row["severity"],
            "require_human_escalation": bool(row["require_human_escalation"]),
            "description": row["description"],
            "source": row["source"],
            "created_at": row["created_at"],
        }

    def list_exposures(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM exposures ORDER BY created_at, id").fetchall()
        return [self._exposure(row) for row in rows]

    def add_exposure(self, value: dict[str, Any]) -> dict[str, Any]:
        record = {
            "id": str(uuid4()),
            "entity": value["entity"],
            "currency": value["currency"].upper(),
            "amount": str(Decimal(str(value["amount"]))),
            "maturity_days": int(value["maturity_days"]),
            "hedged_pct": str(Decimal(str(value["hedged_pct"]))),
            "source": "user_entered",
            "created_at": _utc_now(),
        }
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO exposures VALUES (:id, :entity, :currency, :amount, :maturity_days, :hedged_pct, :source, :created_at)",
                record,
            )
        return record

    def list_policies(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM policies ORDER BY created_at, id").fetchall()
        return [self._policy(row) for row in rows]

    def add_policy(self, value: dict[str, Any]) -> dict[str, Any]:
        record = {
            "id": str(uuid4()),
            "name": value["name"],
            "category": value["category"],
            "threshold": str(Decimal(str(value["threshold"]))),
            "severity": value["severity"],
            "require_human_escalation": int(value["require_human_escalation"]),
            "description": value.get("description"),
            "source": "user_entered",
            "created_at": _utc_now(),
        }
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO policies VALUES (:id, :name, :category, :threshold, :severity, :require_human_escalation, :description, :source, :created_at)",
                record,
            )
        return self._policy_from_dict(record)

    @staticmethod
    def _policy_from_dict(value: dict[str, Any]) -> dict[str, Any]:
        return value | {
            "threshold": value["threshold"],
            "require_human_escalation": bool(value["require_human_escalation"]),
        }

    def save_assessment(self, assessment_id: str, payload: dict[str, Any]) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO assessments (id, payload, created_at) VALUES (?, ?, ?)",
                (assessment_id, json.dumps(payload, ensure_ascii=True), _utc_now()),
            )

    def get_assessment(self, assessment_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT payload FROM assessments WHERE id = ?", (assessment_id,)).fetchone()
        return json.loads(row["payload"]) if row else None

    def list_assessment_records(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, payload, created_at FROM assessments ORDER BY created_at DESC, id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        records = []
        for row in rows:
            assessment = json.loads(row["payload"])
            market = assessment.get("market", {})
            shock = assessment.get("shock", {})
            decision = assessment.get("human_decision")
            action = assessment.get("simulated_action")
            records.append({
                "record_id": row["id"],
                "timestamp": row["created_at"],
                "event": shock.get("scenario"),
                "currency": market.get("currency_pair") or shock.get("currency_pair"),
                "market_move_pct": market.get("market_move_pct", shock.get("market_move_pct")),
                "risk_level": assessment.get("risk_level"),
                "decision": decision.get("decision") if decision else None,
                "action": action.get("action") if action else None,
                "agent_action": (assessment.get("proposed_actions") or [None])[0],
                "outcome": action.get("outcome") if action else None,
                "hindsight_recall_status": assessment.get("hindsight_recall_status"),
                "hindsight_retention_status": (
                    action.get("hindsight_retention_status") if action else
                    decision.get("hindsight_retention_status") if decision else
                    assessment.get("hindsight_retention_status")
                ),
            })
        return records

    def record_decision(self, assessment_id: str, decision: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        timestamp = _utc_now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT payload FROM assessments WHERE id = ?", (assessment_id,)).fetchone()
            if row is None:
                raise KeyError(f"Assessment {assessment_id} was not found.")
            assessment = json.loads(row["payload"])
            existing = assessment.get("human_decision")
            if existing:
                if any(existing.get(key) != decision.get(key) for key in ("decision", "rationale", "notes")):
                    raise ValueError("A different human decision is already recorded for this assessment.")
                return existing, False

            decision_record = dict(decision)
            decision_record["timestamp"] = timestamp
            cursor = connection.execute(
                "INSERT INTO audit_events (event, payload, created_at) VALUES (?, ?, ?)",
                ("human_decision", json.dumps(decision_record, ensure_ascii=True), timestamp),
            )
            decision_record["audit_id"] = cursor.lastrowid
            assessment["human_decision"] = decision_record
            connection.execute(
                "UPDATE assessments SET payload = ? WHERE id = ?",
                (json.dumps(assessment, ensure_ascii=True), assessment_id),
            )
            connection.execute(
                "UPDATE audit_events SET payload = ? WHERE id = ?",
                (json.dumps(decision_record, ensure_ascii=True), cursor.lastrowid),
            )
        return decision_record, True

    def update_decision_retention(self, assessment_id: str, status: str, reference: dict[str, Any] | None) -> None:
        with self._connect() as connection:
            row = connection.execute("SELECT payload FROM assessments WHERE id = ?", (assessment_id,)).fetchone()
            if row is None:
                raise KeyError(f"Assessment {assessment_id} was not found.")
            assessment = json.loads(row["payload"])
            decision = assessment["human_decision"]
            decision["hindsight_retention_status"] = status
            decision["hindsight_retention"] = status
            decision["hindsight_reference"] = reference
            audit_id = decision["audit_id"]
            connection.execute(
                "UPDATE assessments SET payload = ? WHERE id = ?",
                (json.dumps(assessment, ensure_ascii=True), assessment_id),
            )
            connection.execute(
                "UPDATE audit_events SET payload = ? WHERE id = ?",
                (json.dumps(decision, ensure_ascii=True), audit_id),
            )

    def record_simulated_action(self, assessment_id: str, action: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        timestamp = _utc_now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT payload FROM assessments WHERE id = ?", (assessment_id,)).fetchone()
            if row is None:
                raise KeyError(f"Assessment {assessment_id} was not found.")
            assessment = json.loads(row["payload"])
            existing = assessment.get("simulated_action")
            if existing:
                if existing.get("action") != action.get("action"):
                    raise ValueError("A different simulated action is already recorded for this assessment.")
                return existing, False
            action_record = dict(action)
            action_record["timestamp"] = timestamp
            cursor = connection.execute(
                "INSERT INTO audit_events (event, payload, created_at) VALUES (?, ?, ?)",
                ("simulated_action", json.dumps(action_record, ensure_ascii=True), timestamp),
            )
            action_record["audit_id"] = cursor.lastrowid
            assessment["simulated_action"] = action_record
            connection.execute(
                "UPDATE assessments SET payload = ? WHERE id = ?",
                (json.dumps(assessment, ensure_ascii=True), assessment_id),
            )
            connection.execute(
                "UPDATE audit_events SET payload = ? WHERE id = ?",
                (json.dumps(action_record, ensure_ascii=True), cursor.lastrowid),
            )
        return action_record, True

    def update_action_retention(self, assessment_id: str, status: str, reference: dict[str, Any] | None) -> None:
        with self._connect() as connection:
            row = connection.execute("SELECT payload FROM assessments WHERE id = ?", (assessment_id,)).fetchone()
            if row is None:
                raise KeyError(f"Assessment {assessment_id} was not found.")
            assessment = json.loads(row["payload"])
            action = assessment["simulated_action"]
            action["hindsight_retention_status"] = status
            action["hindsight_reference"] = reference
            audit_id = action["audit_id"]
            connection.execute(
                "UPDATE assessments SET payload = ? WHERE id = ?",
                (json.dumps(assessment, ensure_ascii=True), assessment_id),
            )
            connection.execute(
                "UPDATE audit_events SET payload = ? WHERE id = ?",
                (json.dumps(action, ensure_ascii=True), audit_id),
            )

    def append_audit_event(self, event: str, payload: dict[str, Any]) -> dict[str, Any]:
        created_at = _utc_now()
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO audit_events (event, payload, created_at) VALUES (?, ?, ?)",
                (event, json.dumps(payload, ensure_ascii=True), created_at),
            )
            event_id = cursor.lastrowid
        return {"id": event_id, "event": event, "payload": payload, "timestamp": created_at}

    def update_audit_event_payload(self, event_id: int, payload: dict[str, Any]) -> None:
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE audit_events SET payload = ? WHERE id = ?",
                (json.dumps(payload, ensure_ascii=True), event_id),
            )
            if cursor.rowcount != 1:
                raise KeyError(f"Audit event {event_id} was not found.")

    def list_audit_events(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, event, payload, created_at FROM audit_events ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "id": row["id"],
                "event": row["event"],
                "payload": json.loads(row["payload"]),
                "timestamp": row["created_at"],
            }
            for row in reversed(rows)
        ]


portfolio_data_service: PortfolioDataService | None = None


def configure_portfolio_data_service(database_path: str | Path) -> PortfolioDataService:
    global portfolio_data_service
    portfolio_data_service = PortfolioDataService(database_path)
    return portfolio_data_service