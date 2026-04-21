import pandas as pd
from datetime import date
from typing import Optional


MARGIN = 0.30


def build_revenue(df_pagarme: pd.DataFrame) -> pd.DataFrame:
    df = df_pagarme.copy()
    df["gross_profit"] = df["amount"] * MARGIN
    return df[["date", "order_id", "amount", "gross_profit", "payment_method"]]


def build_roas(df_meta: pd.DataFrame) -> pd.DataFrame:
    df = df_meta.groupby("campaign").agg(
        spend=("spend", "sum"),
        purchase_value=("purchase_value", "sum"),
        impressions=("impressions", "sum"),
        clicks=("clicks", "sum"),
        purchases=("purchases", "sum"),
    ).reset_index()

    df["roas"] = df.apply(
        lambda r: r["purchase_value"] / r["spend"] if r["spend"] > 0 else 0, axis=1
    )
    df["cpc"] = df.apply(
        lambda r: r["spend"] / r["clicks"] if r["clicks"] > 0 else 0, axis=1
    )
    df["cpa"] = df.apply(
        lambda r: r["spend"] / r["purchases"] if r["purchases"] > 0 else 0, axis=1
    )
    return df.sort_values("spend", ascending=False)


def build_roi(
    df_woo: pd.DataFrame,
    df_meta: pd.DataFrame,
    df_payables: pd.DataFrame = None,
) -> pd.DataFrame:
    if df_woo.empty:
        return pd.DataFrame(columns=["date","revenue","gross_profit","ad_spend",
                                      "pagarme_fee","anticipation_fee","net_revenue","roi","profit_after_ads"])

    revenue = df_woo.groupby("date").agg(revenue=("total","sum")).reset_index()
    revenue["gross_profit"] = revenue["revenue"] * MARGIN

    if not df_meta.empty and "spend" in df_meta.columns:
        spend = df_meta.groupby("date").agg(ad_spend=("spend","sum")).reset_index()
        df = revenue.merge(spend, on="date", how="left")
    else:
        df = revenue.copy()
        df["ad_spend"] = 0.0

    if df_payables is not None and not df_payables.empty:
        df_payables = df_payables.copy()
        df_payables["date"] = pd.to_datetime(df_payables["date"]).dt.date
        fees = df_payables.groupby("date").agg(
            pagarme_fee=("fee","sum"),
            anticipation_fee=("anticipation_fee","sum"),
        ).reset_index()
        df = df.merge(fees, on="date", how="left")
    else:
        df["pagarme_fee"] = 0.0
        df["anticipation_fee"] = 0.0

    df = df.fillna(0)
    df["total_fees"] = df["pagarme_fee"] + df["anticipation_fee"]
    df["net_revenue"] = df["revenue"] - df["total_fees"]
    df["net_profit"] = df["net_revenue"] * MARGIN - df["ad_spend"]
    df["roi"] = df.apply(
        lambda r: (r["net_profit"] / r["ad_spend"] * 100) if r["ad_spend"] > 0 else None,
        axis=1,
    )
    df["profit_after_ads"] = df["gross_profit"] - df["ad_spend"]
    return df.sort_values("date")


def build_channel_summary(df_ga4: pd.DataFrame) -> pd.DataFrame:
    return (
        df_ga4.groupby("channel")
        .agg(
            sessions=("sessions", "sum"),
            new_users=("new_users", "sum"),
            conversions=("conversions", "sum"),
            revenue=("revenue", "sum"),
        )
        .reset_index()
        .sort_values("revenue", ascending=False)
    )


def build_summary(
    df_woo: pd.DataFrame,
    df_meta: pd.DataFrame,
    df_ga4: pd.DataFrame,
    df_payables: pd.DataFrame = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> dict:
    if df_payables is not None and not df_payables.empty:
        df_payables = df_payables.copy()
        df_payables["date"] = pd.to_datetime(df_payables["date"]).dt.date

    if start_date:
        df_woo  = df_woo[df_woo["date"] >= start_date]
        df_meta = df_meta[df_meta["date"] >= start_date]
        df_ga4  = df_ga4[df_ga4["date"] >= start_date]
        if df_payables is not None and not df_payables.empty:
            df_payables = df_payables[df_payables["date"] >= start_date]
    if end_date:
        df_woo  = df_woo[df_woo["date"] <= end_date]
        df_meta = df_meta[df_meta["date"] <= end_date]
        df_ga4  = df_ga4[df_ga4["date"] <= end_date]
        if df_payables is not None and not df_payables.empty:
            df_payables = df_payables[df_payables["date"] <= end_date]

    total_revenue  = df_woo["total"].sum() if not df_woo.empty else 0
    pagarme_fee    = df_payables["fee"].sum() if df_payables is not None and not df_payables.empty else 0
    antecip_fee    = df_payables["anticipation_fee"].sum() if df_payables is not None and not df_payables.empty else 0
    total_fees     = pagarme_fee + antecip_fee
    net_revenue    = total_revenue - total_fees
    gross_profit   = net_revenue * MARGIN
    total_spend    = df_meta["spend"].sum() if not df_meta.empty else 0
    net_profit     = gross_profit - total_spend
    roi            = (net_profit / total_spend * 100) if total_spend > 0 else None
    roas           = df_meta["purchase_value"].sum() / total_spend if total_spend > 0 else None

    return {
        "total_revenue":    total_revenue,
        "pagarme_fee":      pagarme_fee,
        "anticipation_fee": antecip_fee,
        "total_fees":       total_fees,
        "net_revenue":      net_revenue,
        "gross_profit":     gross_profit,
        "total_ad_spend":   total_spend,
        "net_profit":       net_profit,
        "roi_pct":          roi,
        "roas":             roas,
        "total_orders":     len(df_woo),
        "total_sessions":   int(df_ga4["sessions"].sum()),
        "total_conversions":df_ga4["conversions"].sum(),
    }
