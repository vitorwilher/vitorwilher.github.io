import pandas as pd
from pathlib import Path
from datetime import date, datetime
import os

CACHE_DIR = Path(__file__).parent
CACHE_MAX_HOURS = 6


def _cache_path(name: str) -> Path:
    return CACHE_DIR / f"{name}.parquet"


def _is_fresh(name: str) -> bool:
    path = _cache_path(name)
    if not path.exists():
        return False
    age_hours = (datetime.now().timestamp() - path.stat().st_mtime) / 3600
    return age_hours < CACHE_MAX_HOURS


def load_pagarme(force: bool = False) -> pd.DataFrame:
    if not force and _is_fresh("pagarme"):
        return pd.read_parquet(_cache_path("pagarme"))

    from connectors.pagarme import PagarmeConnector
    print("Buscando Pagarme...")
    df = PagarmeConnector(os.getenv("PAGARME_SECRET_KEY")).to_dataframe(
        date(2024, 1, 1), date.today()
    )
    df.to_parquet(_cache_path("pagarme"))
    return df


def load_meta(force: bool = False) -> pd.DataFrame:
    if not force and _is_fresh("meta"):
        return pd.read_parquet(_cache_path("meta"))

    from connectors.meta_ads import MetaAdsConnector
    print("Buscando Meta Ads...")
    df = MetaAdsConnector(
        os.getenv("META_ACCESS_TOKEN"), os.getenv("META_AD_ACCOUNT_ID")
    ).get_campaign_insights(date(2024, 1, 1), date.today())
    if not df.empty:
        df.to_parquet(_cache_path("meta"))
    return df


def load_ga4(force: bool = False) -> pd.DataFrame:
    if not force and _is_fresh("ga4"):
        return pd.read_parquet(_cache_path("ga4"))

    from connectors.ga4 import GA4Connector
    print("Buscando GA4...")
    df = GA4Connector("312087335", "ga4_credentials.json").get_traffic(
        date(2024, 1, 1), date.today()
    )
    df.to_parquet(_cache_path("ga4"))
    return df


def load_payables(force: bool = False) -> pd.DataFrame:
    if not force and _is_fresh("payables"):
        return pd.read_parquet(_cache_path("payables"))

    from connectors.pagarme import PagarmeConnector
    print("Buscando Payables Pagarme...")
    df = PagarmeConnector(os.getenv("PAGARME_SECRET_KEY")).get_payables(
        date(2024, 1, 1), date.today()
    )
    if not df.empty:
        df.to_parquet(_cache_path("payables"))
    return df


def load_woo(force: bool = False) -> pd.DataFrame:
    if not force and _is_fresh("woo"):
        return pd.read_parquet(_cache_path("woo"))

    from connectors.woocommerce import WooCommerceConnector
    print("Buscando WooCommerce...")
    df = WooCommerceConnector(
        os.getenv("WC_URL"), os.getenv("WC_CONSUMER_KEY"), os.getenv("WC_CONSUMER_SECRET")
    ).orders_to_dataframe(date(2019, 1, 1), date.today())
    if not df.empty:
        df.to_parquet(_cache_path("woo"))
    return df


def load_woo_items(force: bool = False) -> pd.DataFrame:
    if not force and _is_fresh("woo_items"):
        return pd.read_parquet(_cache_path("woo_items"))

    from connectors.woocommerce import WooCommerceConnector
    print("Buscando itens WooCommerce...")
    df = WooCommerceConnector(
        os.getenv("WC_URL"), os.getenv("WC_CONSUMER_KEY"), os.getenv("WC_CONSUMER_SECRET")
    ).items_to_dataframe(date(2019, 1, 1), date.today())
    if not df.empty:
        df.to_parquet(_cache_path("woo_items"))
    return df


def load_kommo(force: bool = False) -> pd.DataFrame:
    if not force and _is_fresh("kommo"):
        return pd.read_parquet(_cache_path("kommo"))

    from connectors.kommo import KommoConnector
    print("Buscando Kommo CRM...")
    df = KommoConnector(
        os.getenv("KOMMO_SUBDOMAIN"),
        os.getenv("KOMMO_LONG_TOKEN"),
    ).get_leads()
    if not df.empty:
        df.to_parquet(_cache_path("kommo"))
    return df


def load_convertkit(force: bool = False) -> pd.DataFrame:
    if not force and _is_fresh("convertkit"):
        return pd.read_parquet(_cache_path("convertkit"))

    from connectors.convertkit import ConvertKitConnector
    print("Buscando ConvertKit...")
    df = ConvertKitConnector(
        os.getenv("CONVERTKIT_API_KEY"),
        os.getenv("CONVERTKIT_API_SECRET"),
    ).get_broadcasts()
    if not df.empty:
        df.to_parquet(_cache_path("convertkit"))
    return df


def load_ga4_pages(force: bool = False) -> pd.DataFrame:
    if not force and _is_fresh("ga4_pages"):
        return pd.read_parquet(_cache_path("ga4_pages"))

    from connectors.ga4 import GA4Connector
    print("Buscando GA4 Landing Pages...")
    df = GA4Connector("312087335", "ga4_credentials.json").get_landing_pages(
        date(2024, 1, 1), date.today()
    )
    if not df.empty:
        df.to_parquet(_cache_path("ga4_pages"))
    return df


def load_all(force: bool = False):
    return (
        load_pagarme(force), load_meta(force), load_ga4(force),
        load_payables(force), load_woo(force), load_woo_items(force),
        load_ga4_pages(force), load_convertkit(force), load_kommo(force),
    )
