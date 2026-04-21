from dotenv import load_dotenv
import os
from connectors.pagarme import PagarmeConnector
from datetime import date

load_dotenv()

pagarme = PagarmeConnector(secret_key=os.getenv("PAGARME_SECRET_KEY"))

df = pagarme.to_dataframe(
    start_date=date(2026, 1, 1),
    end_date=date(2026, 4, 21),
    status="paid",
)

print(f"Total de pedidos: {len(df)}")
print(f"Receita total: R$ {df['amount'].sum():,.2f}")
print(df.head())
