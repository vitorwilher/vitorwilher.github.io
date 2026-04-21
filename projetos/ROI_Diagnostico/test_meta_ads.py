from dotenv import load_dotenv
import os
from connectors.meta_ads import MetaAdsConnector
from datetime import date

load_dotenv()

meta = MetaAdsConnector(
    access_token=os.getenv("META_ACCESS_TOKEN"),
    ad_account_id=os.getenv("META_AD_ACCOUNT_ID"),
)

df = meta.get_campaign_insights(
    start_date=date(2025, 1, 1),
    end_date=date(2025, 12, 31),
)

print(f"Total de linhas: {len(df)}")
print(f"Gasto total: R$ {df['spend'].sum():,.2f}")
print(f"ROAS médio: {df['roas'].mean():.2f}")
print(df[["date", "campaign", "spend", "purchases", "purchase_value", "roas"]].head(10))
