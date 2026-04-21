import pandas as pd
from datetime import date
from typing import Optional
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    RunReportRequest,
)
from google.oauth2 import service_account


class GA4Connector:
    def __init__(self, property_id: str, credentials_path: str):
        self.property_id = f"properties/{property_id}"
        credentials = service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=["https://www.googleapis.com/auth/analytics.readonly"],
        )
        self.client = BetaAnalyticsDataClient(credentials=credentials)

    def get_traffic(
        self,
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame:
        request = RunReportRequest(
            property=self.property_id,
            dimensions=[
                Dimension(name="date"),
                Dimension(name="sessionDefaultChannelGroup"),
                Dimension(name="sessionCampaignName"),
            ],
            metrics=[
                Metric(name="sessions"),
                Metric(name="totalUsers"),
                Metric(name="newUsers"),
                Metric(name="bounceRate"),
                Metric(name="conversions"),
                Metric(name="purchaseRevenue"),
            ],
            date_ranges=[DateRange(
                start_date=start_date.strftime("%Y-%m-%d"),
                end_date=end_date.strftime("%Y-%m-%d"),
            )],
        )

        response = self.client.run_report(request)

        rows = []
        for row in response.rows:
            rows.append({
                "date": row.dimension_values[0].value,
                "channel": row.dimension_values[1].value,
                "campaign": row.dimension_values[2].value,
                "sessions": int(row.metric_values[0].value),
                "total_users": int(row.metric_values[1].value),
                "new_users": int(row.metric_values[2].value),
                "bounce_rate": float(row.metric_values[3].value),
                "conversions": float(row.metric_values[4].value),
                "revenue": float(row.metric_values[5].value),
            })

        df = pd.DataFrame(rows)
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"]).dt.date
        return df

    def get_landing_pages(self, start_date: date, end_date: date) -> pd.DataFrame:
        request = RunReportRequest(
            property=self.property_id,
            dimensions=[Dimension(name="landingPagePlusQueryString")],
            metrics=[
                Metric(name="sessions"),
                Metric(name="newUsers"),
                Metric(name="conversions"),
                Metric(name="purchaseRevenue"),
            ],
            date_ranges=[DateRange(
                start_date=start_date.strftime("%Y-%m-%d"),
                end_date=end_date.strftime("%Y-%m-%d"),
            )],
        )
        response = self.client.run_report(request)
        rows = []
        for row in response.rows:
            rows.append({
                "landing_page": row.dimension_values[0].value,
                "sessions":     int(row.metric_values[0].value),
                "new_users":    int(row.metric_values[1].value),
                "conversions":  float(row.metric_values[2].value),
                "revenue":      float(row.metric_values[3].value),
            })
        return pd.DataFrame(rows) if rows else pd.DataFrame(
            columns=["landing_page", "sessions", "new_users", "conversions", "revenue"]
        )
