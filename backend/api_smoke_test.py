import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


def run_smoke_test() -> dict:
    health = client.get("/api/health")
    dashboard = client.get("/api/dashboard")
    exposures = client.get("/api/exposures")
    policies = client.get("/api/policies")
    memories = client.get("/api/memories")
    audit = client.get("/api/audit")

    return {
        "health_status": health.status_code,
        "dashboard_status": dashboard.status_code,
        "exposures_status": exposures.status_code,
        "policies_status": policies.status_code,
        "memories_status": memories.status_code,
        "audit_status": audit.status_code,
        "market_source": dashboard.json().get("market", {}).get("source") if dashboard.status_code == 200 else None,
        "exposure_count": len(exposures.json()) if exposures.status_code == 200 else None,
        "policy_count": len(policies.json()) if policies.status_code == 200 else None,
        "memory_count": len(memories.json()) if memories.status_code == 200 else None,
    }


if __name__ == "__main__":
    print(run_smoke_test())
