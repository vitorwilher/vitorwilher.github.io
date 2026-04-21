import requests
import pandas as pd
from datetime import datetime


class ConvertKitConnector:
    BASE = "https://api.convertkit.com/v3"

    def __init__(self, api_key: str, api_secret: str = None):
        self.api_key = api_key
        self.api_secret = api_secret

    def _get(self, endpoint: str, params: dict = None, use_secret: bool = False) -> dict:
        p = dict(params or {})
        p["api_secret" if use_secret else "api_key"] = self.api_secret if use_secret else self.api_key
        r = requests.get(f"{self.BASE}/{endpoint}", params=p)
        r.raise_for_status()
        return r.json()

    def get_subscriber_count(self) -> int:
        """Retorna o total real de assinantes ativos via API Secret."""
        d = self._get("subscribers", use_secret=True)
        return d.get("total_subscribers", 0)

    def get_broadcasts(self, include_subscriber_count: bool = True) -> pd.DataFrame:
        """Retorna todos os broadcasts com suas métricas."""
        broadcasts = self._get("broadcasts", {"per_page": 50}).get("broadcasts", [])
        if not broadcasts:
            return pd.DataFrame()

        rows = []
        for b in broadcasts:
            stats = self._get(f"broadcasts/{b['id']}/stats").get("broadcast", {}).get("stats", {})
            rows.append({
                "id":               b["id"],
                "date":             pd.to_datetime(b["created_at"]).date(),
                "subject":          b.get("subject", ""),
                "recipients":       stats.get("recipients", 0),
                "emails_opened":    stats.get("emails_opened", 0),
                "open_rate":        stats.get("open_rate", 0.0),
                "click_rate":       stats.get("click_rate", 0.0),
                "total_clicks":     stats.get("total_clicks", 0),
                "unsubscribes":     stats.get("unsubscribes", 0),
                "status":           stats.get("status", ""),
            })

        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"])
        if include_subscriber_count and self.api_secret:
            df["total_subscribers"] = self.get_subscriber_count()
        else:
            df["total_subscribers"] = 0
        return df.sort_values("date")
