from connectors.ga4 import GA4Connector
from datetime import date

ga4 = GA4Connector(
    property_id="312087335",
    credentials_path="ga4_credentials.json",
)

df = ga4.get_traffic(
    start_date=date(2025, 1, 1),
    end_date=date(2025, 12, 31),
)

print(f"Total de linhas: {len(df)}")
print(f"Sessões totais: {df['sessions'].sum():,}")
print(f"Receita total: R$ {df['revenue'].sum():,.2f}")
print(df.groupby("channel")[["sessions", "conversions", "revenue"]].sum().sort_values("sessions", ascending=False))
