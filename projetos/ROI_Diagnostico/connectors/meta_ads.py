import requests
import pandas as pd
from datetime import date, timedelta
from calendar import monthrange
from typing import Optional


class MetaAdsConnector:
    BASE_URL = "https://graph.facebook.com/v19.0"

    def __init__(self, access_token: str, ad_account_id: str):
        self.access_token = access_token
        self.ad_account_id = ad_account_id

    def _get(self, endpoint: str, params: dict = None) -> dict:
        url = f"{self.BASE_URL}/{endpoint}"
        p = dict(params or {})
        p["access_token"] = self.access_token
        response = requests.get(url, params=p)
        response.raise_for_status()
        return response.json()

    def _fetch_chunk(self, start: date, end: date, level: str) -> list:
        endpoint = f"{self.ad_account_id}/insights"
        params = {
            "level": level,
            "time_range": f'{{"since":"{start}","until":"{end}"}}',
            "fields": ",".join([
                "campaign_name", "spend", "impressions",
                "clicks", "reach", "frequency", "cpm", "cpc", "ctr",
                "actions", "action_values", "date_start", "date_stop",
            ]),
            "time_increment": 1,
            "limit": 500,
        }
        all_data = []
        while True:
            result = self._get(endpoint, params)
            data = result.get("data", [])
            all_data.extend(data)
            if not result.get("paging", {}).get("next"):
                break
            params["after"] = result["paging"]["cursors"]["after"]
        return all_data

    def get_campaign_insights(
        self,
        start_date: date,
        end_date: date,
        level: str = "campaign",
    ) -> pd.DataFrame:
        all_data = []
        chunk_start = start_date
        while chunk_start <= end_date:
            last_day = monthrange(chunk_start.year, chunk_start.month)[1]
            chunk_end = min(date(chunk_start.year, chunk_start.month, last_day), end_date)
            try:
                all_data.extend(self._fetch_chunk(chunk_start, chunk_end, level))
            except Exception as e:
                print(f"Aviso: erro ao buscar {chunk_start} a {chunk_end}: {e}")
            chunk_start = chunk_end + timedelta(days=1)

        if not all_data:
            return pd.DataFrame()

        rows = []
        for d in all_data:
            purchases = _extract_action(d.get("actions", []), "purchase")
            purchase_value = _extract_action(d.get("action_values", []), "purchase")

            rows.append({
                "date": d.get("date_start"),
                "campaign": d.get("campaign_name"),
                "spend": float(d.get("spend", 0)),
                "impressions": int(d.get("impressions", 0)),
                "clicks": int(d.get("clicks", 0)),
                "reach": int(d.get("reach", 0)),
                "cpm": float(d.get("cpm", 0)),
                "cpc": float(d.get("cpc", 0)),
                "ctr": float(d.get("ctr", 0)),
                "purchases": purchases,
                "purchase_value": purchase_value,
            })

        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"]).dt.date
        df["roas"] = df.apply(
            lambda r: r["purchase_value"] / r["spend"] if r["spend"] > 0 else 0, axis=1
        )
        return df


def _extract_action(actions: list, action_type: str) -> float:
    for a in actions:
        if a.get("action_type") == action_type:
            return float(a.get("value", 0))
    return 0.0
