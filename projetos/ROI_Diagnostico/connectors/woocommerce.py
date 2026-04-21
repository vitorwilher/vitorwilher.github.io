import requests
import pandas as pd
from datetime import datetime, date
from typing import Optional


class WooCommerceConnector:
    def __init__(self, url: str, consumer_key: str, consumer_secret: str):
        self.base_url = url.rstrip("/") + "/wp-json/wc/v3"
        self.auth = (consumer_key, consumer_secret)

    def _get(self, endpoint: str, params: dict = None) -> list:
        url = f"{self.base_url}/{endpoint}"
        p = dict(params or {})
        p["consumer_key"] = self.auth[0]
        p["consumer_secret"] = self.auth[1]
        response = requests.get(url, params=p)
        response.raise_for_status()
        return response.json()

    def get_all_orders(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        status: str = "completed",
    ) -> list[dict]:
        all_orders = []
        page = 1

        params = {"status": status, "per_page": 100}
        if start_date:
            params["after"] = datetime.combine(start_date, datetime.min.time()).isoformat()
        if end_date:
            params["before"] = datetime.combine(end_date, datetime.max.time()).isoformat()

        while True:
            params["page"] = page
            orders = self._get("orders", params)
            if not orders:
                break
            all_orders.extend(orders)
            page += 1

        return all_orders

    def orders_to_dataframe(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        status: str = "completed",
    ) -> pd.DataFrame:
        orders = self.get_all_orders(start_date, end_date, status)

        if not orders:
            return pd.DataFrame()

        rows = []
        for order in orders:
            rows.append({
                "order_id": order.get("id"),
                "status": order.get("status"),
                "created_at": order.get("date_created"),
                "total": float(order.get("total", 0)),
                "subtotal": float(order.get("cart_tax", 0)) + sum(
                    float(i.get("subtotal", 0)) for i in order.get("line_items", [])
                ),
                "discount_total": float(order.get("discount_total", 0)),
                "shipping_total": float(order.get("shipping_total", 0)),
                "payment_method": order.get("payment_method_title"),
                "items_count": len(order.get("line_items", [])),
                "customer_id": order.get("customer_id"),
                "customer_email": order.get("billing", {}).get("email"),
                "billing_phone": order.get("billing", {}).get("phone", ""),
                "billing_first_name": order.get("billing", {}).get("first_name", ""),
                "billing_last_name": order.get("billing", {}).get("last_name", ""),
            })

        df = pd.DataFrame(rows)
        df["created_at"] = pd.to_datetime(df["created_at"])
        df["date"] = df["created_at"].dt.date
        return df

    def items_to_dataframe(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        status: str = "completed",
    ) -> pd.DataFrame:
        orders = self.get_all_orders(start_date, end_date, status)
        if not orders:
            return pd.DataFrame()

        rows = []
        for order in orders:
            order_date = pd.to_datetime(order.get("date_created")).date()
            for item in order.get("line_items", []):
                rows.append({
                    "order_id":     order.get("id"),
                    "date":         order_date,
                    "product_id":   item.get("product_id"),
                    "product_name": item.get("name"),
                    "quantity":     int(item.get("quantity", 0)),
                    "subtotal":     float(item.get("subtotal", 0)),
                    "total":        float(item.get("total", 0)),
                })
        return pd.DataFrame(rows)

    def get_products(self) -> pd.DataFrame:
        all_products = []
        page = 1

        while True:
            products = self._get("products", {"per_page": 100, "page": page})
            if not products:
                break
            all_products.extend(products)
            page += 1

        rows = []
        for p in all_products:
            rows.append({
                "product_id": p.get("id"),
                "name": p.get("name"),
                "sku": p.get("sku"),
                "price": float(p.get("price") or 0),
                "regular_price": float(p.get("regular_price") or 0),
                "sale_price": float(p.get("sale_price") or 0),
                "stock_quantity": p.get("stock_quantity"),
                "categories": ", ".join(c["name"] for c in p.get("categories", [])),
            })

        return pd.DataFrame(rows)
