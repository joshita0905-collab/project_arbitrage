import json
import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from hindsight_client import Hindsight

from backend.config import is_placeholder, settings


class HindsightMemoryService:
    def __init__(self, api_key: str | None = None, base_url: str | None = None, bank_id: str | None = None, timeout: float = 15.0) -> None:
        candidate = api_key if api_key is not None else settings.hindsight_api_key
        self.api_key = candidate if candidate and not is_placeholder(candidate) else ""
        self.base_url = base_url or settings.hindsight_api_url
        self.bank_id = bank_id or settings.hindsight_bank_id
        self.timeout = timeout
        self.client: Hindsight | None = None

    @staticmethod
    def _normalize_for_json(value: Any) -> Any:
        if isinstance(value, dict):
            return {str(key): HindsightMemoryService._normalize_for_json(item) for key, item in value.items()}
        if isinstance(value, list):
            return [HindsightMemoryService._normalize_for_json(item) for item in value]
        if isinstance(value, tuple):
            return [HindsightMemoryService._normalize_for_json(item) for item in value]
        if isinstance(value, set):
            return [HindsightMemoryService._normalize_for_json(item) for item in sorted(value, key=lambda item: str(item))]
        if hasattr(value, "model_dump"):
            return HindsightMemoryService._normalize_for_json(value.model_dump())
        if hasattr(value, "__dict__") and not isinstance(value, (str, bytes, int, float, bool, type(None))):
            return {str(key): HindsightMemoryService._normalize_for_json(val) for key, val in vars(value).items() if not key.startswith("_")}
        return value

    def connect(self) -> Hindsight:
        if not self.api_key:
            raise RuntimeError("HINDSIGHT_API_KEY is missing. Live Hindsight memory is not configured.")
        return Hindsight(base_url=self.base_url, api_key=self.api_key, timeout=self.timeout)

    def _run_with_client(self, operation: Callable[[Hindsight], Awaitable[Any]]) -> Any:
        client = self.connect()

        async def run() -> Any:
            try:
                return await operation(client)
            finally:
                await client.aclose()

        return asyncio.run(run())

    async def _ensure_bank(self, client: Hindsight) -> str:
        try:
            await client.aget_bank_config(self.bank_id)
            return self.bank_id
        except Exception:
            try:
                await client.acreate_bank(
                    bank_id=self.bank_id,
                    name="Project Arbitrage",
                    mission="Treasury decision support using sourced market data, submitted exposure data, policy decisions, and human oversight.",
                    retain_mission="Store sourced market assessments and submitted human decision outcomes with their provenance.",
                )
                return self.bank_id
            except Exception as exc:
                raise RuntimeError(f"Unable to create or access Hindsight bank '{self.bank_id}': {exc}") from exc

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def ensure_bank(self) -> str:
        return self._run_with_client(self._ensure_bank)

    def retain_memory(self, memory: dict[str, Any] | str, *, context: str | None = None, tags: list[str] | None = None, metadata: dict[str, str] | None = None, live_mode: bool = False) -> dict[str, Any]:
        if not self.is_configured():
            raise RuntimeError("HINDSIGHT_API_KEY is missing. Live Hindsight memory is not configured.")

        content = json.dumps(memory, ensure_ascii=True) if isinstance(memory, dict) else memory

        async def retain(client: Hindsight) -> Any:
            await self._ensure_bank(client)
            return await client.aretain(
                bank_id=self.bank_id,
                content=content,
                context=context or "Project Arbitrage treasury event",
                tags=tags or ["project-arbitrage", "treasury"],
                metadata=metadata or {},
            )

        payload = self._run_with_client(retain)
        return payload.model_dump() if hasattr(payload, "model_dump") else dict(payload)

    def recall_memories(self, query: str, limit: int = 5, *, live_mode: bool = False) -> list[dict[str, Any]]:
        if not self.is_configured():
            raise RuntimeError("HINDSIGHT_API_KEY is missing. Live Hindsight memory is not configured.")

        async def recall(client: Hindsight) -> Any:
            await self._ensure_bank(client)
            return await client.arecall(
                bank_id=self.bank_id,
                query=query,
                max_tokens=2000,
                budget="mid",
            )

        response = self._run_with_client(recall)
        results = getattr(response, "results", []) or []
        items: list[dict[str, Any]] = []
        for result in results:
            result_tags = getattr(result, "tags", []) or []
            result_metadata = self._normalize_for_json(getattr(result, "metadata", {})) or {}
            tagged_synthetic = any(str(tag).lower() == "synthetic" for tag in result_tags)
            metadata_synthetic = str(result_metadata.get("synthetic", "")).lower() == "true"
            if tagged_synthetic or metadata_synthetic:
                continue
            items.append({
                "id": getattr(result, "id", "unknown"),
                "text": getattr(result, "text", ""),
                "type": getattr(result, "type", None),
                "context": getattr(result, "context", None),
                "tags": result_tags,
                "scores": self._normalize_for_json(getattr(result, "scores", None)),
                "metadata": result_metadata,
            })
            if len(items) >= limit:
                break
        return items

    def list_memory_records(self, *, limit: int = 1000) -> dict[str, Any]:
        if not self.is_configured():
            raise RuntimeError("HINDSIGHT_API_KEY is missing. Live Hindsight memory is not configured.")

        async def list_records(client: Hindsight) -> dict[str, Any]:
            await self._ensure_bank(client)
            offset = 0
            total_available = 0
            records: list[dict[str, Any]] = []
            while offset < min(limit, total_available or limit):
                response = await client.alist_memories(
                    bank_id=self.bank_id,
                    limit=min(100, limit - offset),
                    offset=offset,
                )
                total_available = response.total
                page = response.items or []
                if not page:
                    break
                for item in page:
                    tags = item.tags or []
                    metadata = self._normalize_for_json(item.metadata or {})
                    if not any(str(tag).lower() == "project-arbitrage" for tag in tags):
                        continue
                    if any(str(tag).lower() == "synthetic" for tag in tags):
                        continue
                    if str(metadata.get("synthetic", "")).lower() == "true":
                        continue
                    records.append({
                        "id": item.id,
                        "text": item.text or "",
                        "context": item.context or "",
                        "timestamp": item.occurred_start or item.mentioned_at or item.updated_at or item.var_date,
                        "fact_type": item.fact_type,
                        "document_id": item.document_id,
                        "tags": tags,
                        "metadata": metadata,
                    })
                offset += len(page)
            records.sort(key=lambda item: item.get("timestamp") or "", reverse=True)
            return {
                "total_units": len(records),
                "returned_units": len(records),
                "fact_type_counts": {
                    fact_type: sum(1 for item in records if item.get("fact_type") == fact_type)
                    for fact_type in sorted({item.get("fact_type") for item in records if item.get("fact_type")})
                },
                "category_counts_available": False,
                "records": records,
            }

        return self._run_with_client(list_records)

    def health_check(self) -> dict[str, Any]:
        if not self.is_configured():
            return {"status": "error", "message": "Hindsight is not configured. Set HINDSIGHT_API_KEY to enable live mode."}
        try:
            self.ensure_bank()
            return {"status": "ok", "bank_id": self.bank_id, "configured": True}
        except Exception as exc:
            return {"status": "error", "bank_id": self.bank_id, "message": str(exc)}


hindsight_memory_service = HindsightMemoryService()
