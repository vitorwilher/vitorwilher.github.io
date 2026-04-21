import requests
import pandas as pd
from datetime import datetime, date
from typing import Optional
import base64


class PagarmeConnector:
    BASE_URL = "https://api.pagar.me/core/v5"

    def __init__(self, secret_key: str):
        token = base64.b64encode(f"{secret_key}:".encode()).decode()
        self.headers = {
            "Authorization": f"Basic {token}",
            "Content-Type": "application/json",
        }

    def _get(self, endpoint: str, params: dict = None) -> dict:
        url = f"{self.BASE_URL}/{endpoint}"
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json()

    def get_orders(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        status: str = "paid",
        page: int = 1,
        size: int = 100,
    ) -> list[dict]:
        params = {"page": page, "size": size, "status": status}

        if start_date:
            params["created_since"] = datetime.combine(start_date, datetime.min.time()).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
        if end_date:
            params["created_until"] = datetime.combine(end_date, datetime.max.time()).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )

        result = self._get("orders", params)
        return result.get("data", [])

    def get_all_orders(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        status: str = "paid",
    ) -> list[dict]:
        all_orders = []
        page = 1

        while True:
            orders = self.get_orders(start_date, end_date, status, page=page, size=100)
            if not orders:
                break
            all_orders.extend(orders)
            page += 1

        return all_orders

    def get_payables(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> pd.DataFrame:
        all_payables = []
        page = 1

        while True:
            params = {"page": page, "size": 100}
            if start_date:
                params["accrual_at_since"] = datetime.combine(start_date, datetime.min.time()).strftime("%Y-%m-%dT%H:%M:%SZ")
            if end_date:
                params["accrual_at_until"] = datetime.combine(end_date, datetime.max.time()).strftime("%Y-%m-%dT%H:%M:%SZ")

            result = self._get("payables", params)
            data = result.get("data", [])
            if not data:
                break
            all_payables.extend(data)
            page += 1

        if not all_payables:
            return pd.DataFrame()

        rows = []
        for p in all_payables:
            rows.append({
                "charge_id":          p.get("charge_id"),
                "payment_method":     p.get("payment_method"),
                "payment_date":       p.get("payment_date"),
                "amount":             p.get("amount", 0) / 100,
                "fee":                p.get("fee", 0) / 100,
                "anticipation_fee":   p.get("anticipation_fee", 0) / 100,
                "fraud_coverage_fee": p.get("fraud_coverage_fee", 0) / 100,
                "installment":        p.get("installment"),
                "status":             p.get("status"),
            })

        df = pd.DataFrame(rows)
        df["payment_date"] = pd.to_datetime(df["payment_date"])
        df["accrual_at"] = pd.to_datetime([p.get("accrual_at") for p in all_payables])
        df["date"] = df["accrual_at"].dt.date
        df["net_amount"] = df["amount"] - df["fee"] - df["anticipation_fee"] - df["fraud_coverage_fee"]
        df["total_fees"] = df["fee"] + df["anticipation_fee"] + df["fraud_coverage_fee"]
        return df

    def to_dataframe(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        status: str = "paid",
    ) -> pd.DataFrame:
        orders = self.get_all_orders(start_date, end_date, status)

        if not orders:
            return pd.DataFrame()

        rows = []
        for order in orders:
            rows.append({
                "order_id": order.get("id"),
                "status": order.get("status"),
                "created_at": order.get("created_at"),
                "amount": order.get("amount", 0) / 100,  # centavos → reais
                "currency": order.get("currency"),
                "customer_id": order.get("customer", {}).get("id"),
                "customer_email": order.get("customer", {}).get("email"),
                "payment_method": _extract_payment_method(order),
                "items_count": len(order.get("items", [])),
            })

        df = pd.DataFrame(rows)
        df["created_at"] = pd.to_datetime(df["created_at"])
        df["date"] = df["created_at"].dt.date
        return df


def _extract_payment_method(order: dict) -> Optional[str]:
    charges = order.get("charges", [])
    if not charges:
        return None
    return charges[0].get("payment_method")
