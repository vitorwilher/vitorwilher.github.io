import requests
import pandas as pd
from datetime import datetime, date
from typing import Optional


PIPELINE_QUALIFICACAO = 10781335

STATUS_MAP = {
    82673927: "Leads de Entrada",
    82673931: "Em Atendimento",
    82673935: "Negociação",
    98070840: "Boletim AM",
    85422723: "Pagamento Feito",
    92316887: "Follow/Nutrição",
    142:      "Fechado - Ganho",
    143:      "Fechado - Perdido",
}

FUNNEL_ORDER = [
    "Leads de Entrada",
    "Em Atendimento",
    "Negociação",
    "Follow/Nutrição",
    "Pagamento Feito",
    "Fechado - Ganho",
]


class KommoConnector:
    def __init__(self, subdomain: str, long_token: str):
        self.base_url = f"https://{subdomain}.kommo.com/api/v4"
        self.headers = {
            "Authorization": f"Bearer {long_token}",
            "Content-Type": "application/json",
        }

    def _get(self, endpoint: str, params: dict = None) -> dict:
        response = requests.get(
            f"{self.base_url}/{endpoint}",
            headers=self.headers,
            params=params or {},
        )
        if response.status_code == 204:
            return {}
        response.raise_for_status()
        return response.json()

    def _get_contact_emails(self, contact_ids: list) -> dict:
        """Retorna dict {contact_id: email} buscando em batches de 50."""
        email_map = {}
        for i in range(0, len(contact_ids), 50):
            batch = contact_ids[i:i+50]
            params = {f"filter[id][{j}]": cid for j, cid in enumerate(batch)}
            params["limit"] = 50
            d = self._get("contacts", params)
            for ct in d.get("_embedded", {}).get("contacts", []):
                for f in (ct.get("custom_fields_values") or []):
                    if f.get("field_code") == "EMAIL":
                        vals = f.get("values", [])
                        if vals:
                            email_map[ct["id"]] = vals[0]["value"].lower().strip()
                            break
        return email_map

    def get_leads(self, pipeline_id: int = PIPELINE_QUALIFICACAO) -> pd.DataFrame:
        all_leads = []
        page = 1
        while True:
            d = self._get("leads", {
                "filter[pipeline_id]": pipeline_id,
                "limit": 250,
                "page": page,
                "with": "contacts",
            })
            batch = d.get("_embedded", {}).get("leads", [])
            if not batch:
                break
            all_leads.extend(batch)
            if len(batch) < 250:
                break
            page += 1

        if not all_leads:
            return pd.DataFrame()

        # Coleta IDs de contatos únicos
        lead_contact = {}
        for l in all_leads:
            contacts = l.get("_embedded", {}).get("contacts", [])
            if contacts:
                lead_contact[l["id"]] = contacts[0]["id"]

        unique_contact_ids = list(set(lead_contact.values()))
        email_map = self._get_contact_emails(unique_contact_ids)

        rows = []
        for l in all_leads:
            contact_id = lead_contact.get(l["id"])
            rows.append({
                "lead_id":    l["id"],
                "contact_id": contact_id,
                "email":      email_map.get(contact_id, ""),
                "status_id":  l["status_id"],
                "status":     STATUS_MAP.get(l["status_id"], str(l["status_id"])),
                "price":      float(l.get("price") or 0),
                "created_at": datetime.fromtimestamp(l["created_at"]),
                "updated_at": datetime.fromtimestamp(l["updated_at"]),
                "closed_at":  datetime.fromtimestamp(l["closed_at"]) if l.get("closed_at") else None,
                "is_won":     l["status_id"] in (142, 85422723),
                "is_lost":    l["status_id"] == 143,
            })

        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["created_at"]).dt.date
        return df.sort_values("created_at")
