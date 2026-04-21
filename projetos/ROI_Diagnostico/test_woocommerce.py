from dotenv import load_dotenv
import os
from connectors.woocommerce import WooCommerceConnector
from datetime import date

load_dotenv()

wc = WooCommerceConnector(
    url=os.getenv("WC_URL"),
    consumer_key=os.getenv("WC_CONSUMER_KEY"),
    consumer_secret=os.getenv("WC_CONSUMER_SECRET"),
)

df_orders = wc.orders_to_dataframe(
    start_date=date(2026, 1, 1),
    end_date=date(2026, 4, 21),
)

print(f"Total de pedidos: {len(df_orders)}")
print(f"Receita total: R$ {df_orders['total'].sum():,.2f}")
print(df_orders.head())

print("\n--- Produtos ---")
df_products = wc.get_products()
print(f"Total de produtos: {len(df_products)}")
print(df_products.head())
