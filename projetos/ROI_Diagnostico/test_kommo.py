from dotenv import load_dotenv
import os
from connectors.kommo import KommoConnector
from datetime import date

load_dotenv()

kommo = KommoConnector(
    subdomain=os.getenv("KOMMO_SUBDOMAIN"),
    long_token=os.getenv("KOMMO_LONG_TOKEN"),
)

df = kommo.to_dataframe(
    start_date=date(2025, 1, 1),
    end_date=date(2025, 12, 31),
)

print(f"Total de leads: {len(df)}")
print(f"Valor total: R$ {df['value'].sum():,.2f}")
print(df.head())
