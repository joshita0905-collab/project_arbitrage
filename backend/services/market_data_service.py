from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from typing import Any


class MarketDataUnavailable(RuntimeError):
    """Raised when the configured public market-data feed cannot supply rates."""


class FrankfurterMarketDataProvider:
    source = "Frankfurter API (ECB reference exchange rates)"

    def __init__(self, base_url: str, timeout: float = 12.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def get_fx_snapshot(self, base_currency: str, quote_currency: str) -> dict[str, Any]:
        base = base_currency.upper()
        quote = quote_currency.upper()
        end_date = date.today()
        start_date = end_date - timedelta(days=45)
        period = f"{start_date.isoformat()}..{end_date.isoformat()}"
        query = urlencode({"base": base, "symbols": quote})
        url = f"{self.base_url}/{period}?{query}"
        request = Request(url, headers={"Accept": "application/json", "User-Agent": "ProjectArbitrage/1.0"})

        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise MarketDataUnavailable(f"Frankfurter returned HTTP {exc.code} for {base}/{quote}.") from exc
        except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise MarketDataUnavailable(f"Frankfurter market-data request failed ({type(exc).__name__}).") from exc

        rates_by_date = payload.get("rates")
        if not isinstance(rates_by_date, dict):
            raise MarketDataUnavailable("Frankfurter response did not contain a dated rate series.")

        observations: list[dict[str, Any]] = []
        for observed_date, rates in sorted(rates_by_date.items()):
            try:
                rate = float(rates[quote])
                date.fromisoformat(observed_date)
            except (KeyError, TypeError, ValueError):
                continue
            if rate > 0:
                observations.append({"date": observed_date, "rate": rate})

        if len(observations) < 2:
            raise MarketDataUnavailable(f"Frankfurter has fewer than two usable {base}/{quote} observations.")

        previous = observations[-2]
        latest = observations[-1]
        daily_changes = [
            {
                "date": current["date"],
                "market_move_pct": round((current["rate"] / previous_item["rate"] - 1) * 100, 6),
            }
            for previous_item, current in zip(observations, observations[1:])
        ]

        return {
            "currency_pair": f"{base}/{quote}",
            "base_currency": base,
            "quote_currency": quote,
            "spot_rate": latest["rate"],
            "market_move_pct": round((latest["rate"] / previous["rate"] - 1) * 100, 6),
            "latest_date": latest["date"],
            "previous_date": previous["date"],
            "previous_rate": previous["rate"],
            "historical_daily_moves": daily_changes[:-1],
            "source": self.source,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }