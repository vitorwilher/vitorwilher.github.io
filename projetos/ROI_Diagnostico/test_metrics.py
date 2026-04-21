from dotenv import load_dotenv
import os
from datetime import date

from connectors.pagarme import PagarmeConnector
from connectors.meta_ads import MetaAdsConnector
from connectors.ga4 import GA4Connector
from metrics.calculator import build_summary, build_roas, build_roi, build_channel_summary

load_dotenv()

START = date(2025, 1, 1)
END = date(2025, 12, 31)

print("Carregando dados...")

df_pagarme = PagarmeConnector(os.getenv("PAGARME_SECRET_KEY")).to_dataframe(START, END)
df_meta = MetaAdsConnector(os.getenv("META_ACCESS_TOKEN"), os.getenv("META_AD_ACCOUNT_ID")).get_campaign_insights(START, END)
df_ga4 = GA4Connector("312087335", "ga4_credentials.json").get_traffic(START, END)

print("\n=== RESUMO GERAL ===")
summary = build_summary(df_pagarme, df_meta, df_ga4)
for k, v in summary.items():
    if isinstance(v, float):
        print(f"  {k}: {v:,.2f}")
    else:
        print(f"  {k}: {v}")

print("\n=== ROAS POR CAMPANHA ===")
print(build_roas(df_meta)[["campaign", "spend", "roas", "cpa"]].to_string(index=False))

print("\n=== ROI MENSAL ===")
df_roi = build_roi(df_pagarme, df_meta)
df_roi["month"] = df_roi["date"].astype(str).str[:7]
print(df_roi.groupby("month")[["revenue", "gross_profit", "ad_spend", "roi"]].mean().round(2))
