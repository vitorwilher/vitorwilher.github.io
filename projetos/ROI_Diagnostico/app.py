from shiny import App, ui, render, reactive
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from dotenv import load_dotenv
from datetime import date, timedelta
import pandas as pd
import numpy as np
import os

from data.loader import load_all
from metrics.calculator import build_summary, build_roas, build_roi, build_channel_summary

load_dotenv()

print("Carregando dados...")
df_pagarme, df_meta, df_ga4, df_payables, df_woo, df_items, df_ga4_pages, df_ck, df_kommo = load_all()
print("Dados carregados!")

# Campanhas de e-mail (Google Sheets)
_SHEET_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1FHMkDcjqetl5jt5efaDoxQky96j6zo4Sa7WF-4J3Las"
    "/export?format=csv&gid=406590812"
)
try:
    df_campanhas = pd.read_csv(_SHEET_URL)
    df_campanhas.columns = [c.strip() for c in df_campanhas.columns]
    df_campanhas["inicio"] = pd.to_datetime(df_campanhas["Data Início"], dayfirst=True).dt.date
    df_campanhas["fim"]    = pd.to_datetime(df_campanhas["Data Término"], dayfirst=True).dt.date
    df_campanhas["nome"]   = df_campanhas["Campanha"].str.strip()
    df_campanhas = df_campanhas.dropna(subset=["inicio", "fim"])
except Exception as e:
    print(f"Aviso: não foi possível carregar campanhas de e-mail: {e}")
    df_campanhas = pd.DataFrame(columns=["nome", "inicio", "fim"])

MIN_DATE = df_woo["date"].min() if len(df_woo) else date(2019, 1, 1)
MAX_DATE = df_woo["date"].max() if len(df_woo) else date.today()

# Choices de produtos calculadas uma vez no startup
_items_norm = df_items.copy()
_items_norm["product_name"] = _items_norm["product_name"].str.strip()
PRODUCT_CHOICES = sorted(_items_norm["product_name"].dropna().unique().tolist())
DEFAULT_CURSO = ["Livro Digital Do Zero à Análise de Dados Econômicos e Financeiros usando Python"] if PRODUCT_CHOICES else []

_TODAY   = date.today()
_12M_AGO = date(_TODAY.year - 1, _TODAY.month, _TODAY.day)

BLUE   = "#3498db"
GREEN  = "#2ecc71"
RED    = "#e74c3c"
ORANGE = "#e67e22"
DARK   = "#2c3e50"
PURPLE = "#8e44ad"


def fmt_brl(value):
    return "R$ " + f"{value:,.0f}".replace(",", ".")


def kpi_card(title, value, color=DARK):
    return ui.div(
        ui.div(title, style="font-size:12px;color:#888;margin-bottom:4px;"),
        ui.div(value, style=f"font-size:20px;font-weight:700;color:{color};"),
        style=(
            "background:#fff;border-radius:10px;padding:16px 20px;"
            "box-shadow:0 1px 4px rgba(0,0,0,.08);flex:1;min-width:150px;"
        ),
    )


def empty_meta():
    return pd.DataFrame(columns=["date","campaign","spend","impressions",
                                  "clicks","reach","cpm","cpc","ctr",
                                  "purchases","purchase_value","roas"])


app_ui = ui.page_fluid(
    ui.tags.style("""
        body{background:#f4f6f9;font-family:'Segoe UI',sans-serif;}
        .section-title{font-size:15px;font-weight:600;color:#2c3e50;margin:20px 0 10px;}
        .topbar{background:#fff;border-bottom:2px solid #e0e6ed;padding:10px 24px;
            display:flex;align-items:center;justify-content:space-between;
            box-shadow:0 1px 4px rgba(0,0,0,.05);}
        .filter-bar{background:#fff;border-bottom:1px solid #e8ecf0;
            padding:8px 24px;display:flex;align-items:flex-end;gap:20px;}
        .nav-tabs{background:#fff;padding:0 24px;border-bottom:2px solid #dee2e6;}
        .nav-tabs .nav-link{font-size:14px;font-weight:500;color:#555;padding:10px 16px;border:none;}
        .nav-tabs .nav-link.active{color:#1a3a6b;font-weight:700;
            border-bottom:2px solid #1a3a6b;background:transparent;}
    """),
    ui.div(
        ui.div(
            ui.span("ROI Diagnóstico", style=f"font-weight:800;color:{DARK};font-size:18px;"),
            ui.span(" — Marketing & Vendas", style="color:#888;font-size:13px;margin-left:8px;"),
        ),
        class_="topbar",
    ),
    ui.div(
        ui.input_date("start_date", "Data início", value=max(MIN_DATE, min(_12M_AGO, MAX_DATE)),
                      min=MIN_DATE, max=MAX_DATE),
        ui.input_date("end_date", "Data fim", value=MAX_DATE,
                      min=MIN_DATE, max=MAX_DATE),
        ui.input_action_button("refresh", "Atualizar dados",
                               class_="btn btn-outline-primary btn-sm",
                               style="margin-bottom:1px;"),
        class_="filter-bar",
    ),
    ui.navset_tab(
        ui.nav_panel(
            "Finanças",
            ui.div(
                ui.div("Visão Geral", class_="section-title"),
                ui.output_ui("kpis"),
                ui.div("Receita, Taxas, Lucro e Gasto em Ads (mensal)", class_="section-title"),
                ui.output_plot("chart_roi", height="400px"),
                style="padding:0 24px 40px;",
            ),
        ),
        ui.nav_panel(
            "Produtos",
            ui.div(
                # Bloco 1 — análise por curso
                ui.div("Análise por Curso", class_="section-title"),
                ui.div(
                    ui.input_date("prod_start", "De", value=_12M_AGO,
                                  min=date(2019, 1, 1), max=date.today()),
                    ui.input_date("prod_end", "Até", value=_TODAY,
                                  min=date(2019, 1, 1), max=date.today()),
                    ui.div(
                        ui.input_select("prod_curso", "Curso",
                                        choices=PRODUCT_CHOICES,
                                        selected=DEFAULT_CURSO[0] if DEFAULT_CURSO else None,
                                        multiple=False,
                                        size=1),
                        style="flex:1;min-width:400px;max-width:800px;",
                    ),
                    style="display:flex;gap:16px;align-items:flex-end;flex-wrap:wrap;"
                          "background:#fff;padding:12px 16px;border-radius:8px;"
                          "box-shadow:0 1px 4px rgba(0,0,0,.06);margin-bottom:12px;",
                ),
                ui.output_ui("prod_kpis"),
                ui.output_plot("chart_prod_mensal", height="320px"),
                ui.hr(),
                # Bloco 2 — top/bottom 5
                ui.div("Top 5 e Bottom 5 Produtos", class_="section-title"),
                ui.div(
                    ui.input_date("rank_start", "De", value=_12M_AGO,
                                  min=date(2019, 1, 1), max=date.today()),
                    ui.input_date("rank_end", "Até", value=_TODAY,
                                  min=date(2019, 1, 1), max=date.today()),
                    style="display:flex;gap:16px;align-items:flex-end;flex-wrap:wrap;"
                          "background:#fff;padding:12px 16px;border-radius:8px;"
                          "box-shadow:0 1px 4px rgba(0,0,0,.06);margin-bottom:12px;",
                ),
                ui.div(
                    ui.div(
                        ui.div("Top 5 — Mais Vendidos", class_="section-title"),
                        ui.output_plot("chart_top5", height="260px"),
                        style="flex:1;",
                    ),
                    ui.div(
                        ui.div("Bottom 5 — Menos Vendidos", class_="section-title"),
                        ui.output_plot("chart_bottom5", height="260px"),
                        style="flex:1;",
                    ),
                    style="display:flex;gap:20px;",
                ),
                ui.hr(),
                # Bloco 3 — área acumulada top 10
                ui.div("Evolução Mensal — Top 10 Cursos", class_="section-title"),
                ui.div(
                    ui.input_date("area_start", "De", value=date(2019, 1, 1),
                                  min=date(2019, 1, 1), max=date.today()),
                    ui.input_date("area_end", "Até", value=date.today(),
                                  min=date(2019, 1, 1), max=date.today()),
                    style="display:flex;gap:16px;align-items:flex-end;flex-wrap:wrap;"
                          "background:#fff;padding:12px 16px;border-radius:8px;"
                          "box-shadow:0 1px 4px rgba(0,0,0,.06);margin-bottom:12px;",
                ),
                ui.output_plot("chart_area_top10", height="400px"),
                style="padding:0 24px 40px;",
            ),
        ),
        ui.nav_panel(
            "Marketing",
            ui.div(
                ui.output_ui("marketing_kpis"),
                ui.hr(),
                ui.navset_pill(
                    # ── Google Analytics ──────────────────────────────────
                    ui.nav_panel(
                        "Google Analytics",
                        ui.div(
                            ui.input_date("ga_start", "De", value=_12M_AGO,
                                          min=date(2024,1,1), max=date.today()),
                            ui.input_date("ga_end",   "Até", value=_TODAY,
                                          min=date(2024,1,1), max=date.today()),
                            style="display:flex;gap:16px;align-items:flex-end;padding:12px 0;",
                        ),
                        ui.div(
                            ui.div(
                                ui.div("Sessões por Canal", class_="section-title"),
                                ui.output_plot("chart_channels", height="320px"),
                                style="flex:1;",
                            ),
                            ui.div(
                                ui.div("Top 10 Páginas de Destino", class_="section-title"),
                                ui.output_plot("chart_landing_pages", height="320px"),
                                style="flex:1;",
                            ),
                            style="display:flex;gap:20px;",
                        ),
                    ),
                    # ── Tráfego Pago ──────────────────────────────────────
                    ui.nav_panel(
                        "Tráfego Pago",
                        ui.div("Todas as Campanhas de Tráfego Ativas", class_="section-title"),
                        ui.output_ui("table_campanhas_tp"),
                        ui.hr(),
                        ui.div(
                            ui.input_date("tp_start", "De", value=_12M_AGO,
                                          min=date(2024,1,1), max=date.today()),
                            ui.input_date("tp_end",   "Até", value=_TODAY,
                                          min=date(2024,1,1), max=date.today()),
                            style="display:flex;gap:16px;align-items:flex-end;padding:12px 0;",
                        ),
                        ui.div(
                            ui.div(
                                ui.div("Dispersão: Gasto em Ads × Receita Líquida", class_="section-title"),
                                ui.output_plot("chart_ads_scatter", height="340px"),
                                style="flex:1;",
                            ),
                            ui.div(
                                ui.div("Série Temporal: Ads vs Receita Líquida", class_="section-title"),
                                ui.output_plot("chart_ads_line", height="340px"),
                                style="flex:1;",
                            ),
                            style="display:flex;gap:20px;",
                        ),
                        ui.hr(),
                        ui.div("Top 15 Campanhas — Maior ROAS", class_="section-title"),
                        ui.output_plot("chart_roas_top", height="360px"),
                        ui.div("Top 15 Campanhas — Menor ROAS", class_="section-title"),
                        ui.output_plot("chart_roas_bottom", height="360px"),
                    ),
                    # ── E-mail ────────────────────────────────────────────
                    ui.nav_panel(
                        "E-mail",
                        ui.div(
                            ui.input_date("em_start", "De", value=_12M_AGO,
                                          min=date(2024,1,1), max=date.today()),
                            ui.input_date("em_end",   "Até", value=_TODAY,
                                          min=date(2024,1,1), max=date.today()),
                            style="display:flex;gap:16px;align-items:flex-end;padding:12px 0;",
                        ),
                        ui.div(
                            ui.div(
                                ui.div("Top 5 Campanhas — Maior Receita no Período", class_="section-title"),
                                ui.output_plot("chart_email_top5", height="280px"),
                                style="flex:1;",
                            ),
                            ui.div(
                                ui.div("Bottom 5 Campanhas — Menor Receita no Período", class_="section-title"),
                                ui.output_plot("chart_email_bottom5", height="280px"),
                                style="flex:1;",
                            ),
                            style="display:flex;gap:20px;",
                        ),
                    ),
                ),
                style="padding:0 24px 40px;",
            ),
        ),
        ui.nav_panel(
            "Comercial",
            ui.div(
                ui.output_ui("comercial_kpis"),
                ui.div(
                    ui.input_date("crm_start", "De", value=_12M_AGO,
                                  min=date(2024,1,1), max=date.today()),
                    ui.input_date("crm_end",   "Até", value=_TODAY,
                                  min=date(2024,1,1), max=date.today()),
                    style="display:flex;gap:16px;align-items:flex-end;padding:12px 0 4px;",
                ),
                ui.div(
                    ui.div(
                        ui.div("Novos Leads por Mês", class_="section-title"),
                        ui.output_plot("chart_leads_mensal", height="300px"),
                        style="flex:1;",
                    ),
                    ui.div(
                        ui.div("Funil de Vendas (Estágio Atual)", class_="section-title"),
                        ui.output_plot("chart_funil", height="300px"),
                        style="flex:1;",
                    ),
                    style="display:flex;gap:20px;",
                ),
                ui.hr(),
                ui.div("Cruzamento CRM × WooCommerce — Leads Convertidos", class_="section-title"),
                ui.output_ui("crm_woo_kpis"),
                ui.div(
                    ui.div(
                        ui.div("Receita WooCommerce por Faixa de LTV", class_="section-title"),
                        ui.output_plot("chart_ltv_dist", height="280px"),
                        style="flex:1;",
                    ),
                    ui.div(
                        ui.div("Top 10 Clientes por Receita WooCommerce", class_="section-title"),
                        ui.output_plot("chart_top_clientes", height="280px"),
                        style="flex:1;",
                    ),
                    style="display:flex;gap:20px;",
                ),
                style="padding:0 24px 40px;",
            ),
        ),
        ui.nav_panel(
            "Clientes",
            ui.div(
                ui.div("Busca de Aluno", class_="section-title"),
                ui.div(
                    ui.input_text("cliente_email", "E-mail do aluno",
                                  placeholder="exemplo@email.com",
                                  width="400px"),
                    ui.input_action_button("buscar_cliente", "Buscar",
                                           class_="btn btn-primary btn-sm",
                                           style="margin-bottom:1px;"),
                    style="display:flex;gap:12px;align-items:flex-end;"
                          "background:#fff;padding:16px;border-radius:8px;"
                          "box-shadow:0 1px 4px rgba(0,0,0,.07);margin-bottom:16px;",
                ),
                ui.output_ui("cliente_perfil"),
                style="padding:0 24px 40px;",
            ),
        ),
    ),
)


def server(input, output, session):

    data = reactive.value((df_pagarme, df_meta, df_ga4, df_payables, df_woo, df_items, df_ga4_pages, df_ck, df_kommo))

    @reactive.effect
    @reactive.event(input.refresh)
    def _refresh():
        with ui.Progress(min=0, max=7) as p:
            from data.loader import (load_pagarme, load_meta, load_ga4, load_payables,
                                     load_woo, load_woo_items, load_ga4_pages,
                                     load_convertkit, load_kommo)
            p.set(1, message="Buscando WooCommerce...")
            woo   = load_woo(force=True)
            items = load_woo_items(force=True)
            pag   = load_pagarme(force=True)
            pay   = load_payables(force=True)
            p.set(3, message="Buscando Meta Ads...")
            meta  = load_meta(force=True)
            p.set(4, message="Buscando GA4...")
            ga    = load_ga4(force=True)
            pages = load_ga4_pages(force=True)
            p.set(6, message="Buscando ConvertKit e Kommo...")
            ck  = load_convertkit(force=True)
            km  = load_kommo(force=True)
            data.set((pag, meta, ga, pay, woo, items, pages, ck, km))

    @reactive.calc
    def filtered():
        start, end = input.start_date(), input.end_date()
        df_p, df_m, df_g, df_pay, df_w, df_it, _pg, _ck, _km = data()
        df_w   = df_w.copy();   df_w["date"]  = pd.to_datetime(df_w["date"]).dt.date
        df_pay = df_pay.copy(); df_pay["date"] = pd.to_datetime(df_pay["date"]).dt.date
        df_m   = df_m.copy();   df_m["date"]   = pd.to_datetime(df_m["date"]).dt.date
        df_g   = df_g.copy();   df_g["date"]   = pd.to_datetime(df_g["date"]).dt.date
        w   = df_w[(df_w["date"] >= start) & (df_w["date"] <= end)]
        m   = df_m[(df_m["date"] >= start) & (df_m["date"] <= end)] if len(df_m) > 0 else empty_meta()
        g   = df_g[(df_g["date"] >= start) & (df_g["date"] <= end)]
        pay = df_pay[(df_pay["date"] >= start) & (df_pay["date"] <= end)] if len(df_pay) > 0 else pd.DataFrame()
        return w, m, g, pay

    @reactive.calc
    def items_data():
        _, _, _, _, _, df_it, _pg, _ck, _km = data()
        df_it = df_it.copy()
        df_it["date"] = pd.to_datetime(df_it["date"]).dt.date
        return df_it

    @reactive.calc
    def pages_data():
        _, _, _, _, _, _, df_pg, _ck, _km = data()
        return df_pg.copy() if not df_pg.empty else pd.DataFrame(
            columns=["landing_page", "sessions", "new_users", "conversions", "revenue"]
        )

    @reactive.calc
    def ck_data():
        _, _, _, _, _, _, _pg, df_ck, _km = data()
        return df_ck.copy() if not df_ck.empty else pd.DataFrame()

    @reactive.calc
    def kommo_data():
        _, _, _, _, _, _, _, _, df_km = data()
        df = df_km.copy() if not df_km.empty else pd.DataFrame()
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"]).dt.date
        return df

    @reactive.calc
    def kommo_woo_merged():
        """Cruza leads Kommo (convertidos) com pedidos WooCommerce pelo e-mail."""
        km = kommo_data()
        _, _, _, _, df_w, _, _, _, _ = data()
        if km.empty or df_w.empty or "email" not in km.columns:
            return pd.DataFrame()
        df_w = df_w.copy()
        df_w["date"] = pd.to_datetime(df_w["date"]).dt.date
        df_w["email"] = df_w["customer_email"].str.lower().str.strip()
        woo_by_email = df_w.groupby("email").agg(
            woo_orders=("order_id", "count"),
            woo_revenue=("total", "sum"),
            woo_first=("date", "min"),
            woo_last=("date", "max"),
        ).reset_index()
        won = km[km["is_won"] & km["email"].str.len() > 0].copy()
        merged = won.merge(woo_by_email, on="email", how="left")
        merged["woo_revenue"] = merged["woo_revenue"].fillna(0)
        merged["woo_orders"]  = merged["woo_orders"].fillna(0).astype(int)
        return merged

    def _daily_net_revenue(start, end):
        _, _, _, _, df_w, _, _, _, _ = data()
        _, _, _, df_pay, _, _, _, _, _ = data()
        df_w  = df_w.copy();  df_w["date"]  = pd.to_datetime(df_w["date"]).dt.date
        df_pay = df_pay.copy(); df_pay["date"] = pd.to_datetime(df_pay["date"]).dt.date
        w = df_w[(df_w["date"] >= start) & (df_w["date"] <= end)]
        pay = df_pay[(df_pay["date"] >= start) & (df_pay["date"] <= end)]
        rev = w.groupby("date")["total"].sum().reset_index().rename(columns={"total": "revenue"})
        fee = pay.groupby("date").agg(fees=("fee","sum"), antecip=("anticipation_fee","sum")).reset_index()
        fee["total_fees"] = fee["fees"] + fee["antecip"]
        df = rev.merge(fee[["date","total_fees"]], on="date", how="left").fillna(0)
        df["net_revenue"] = df["revenue"] - df["total_fees"]
        return df

    @render.ui
    def kpis():
        w, m, g, pay = filtered()
        s = build_summary(w, m, g, pay)
        roi_val   = (s["roi_pct"] or 0) / 100  # converte % para multiplicador
        roi_str   = f"{roi_val:.1f}x" if s["roi_pct"] else "—"
        roas_str  = f"{s['roas']:.2f}x" if s["roas"] else "—"
        roi_color = GREEN if roi_val > 0 else RED
        ads_note  = "" if s["total_ad_spend"] > 0 else " *"
        return ui.div(
            kpi_card("Receita Bruta",        fmt_brl(s['total_revenue'])),
            kpi_card("Taxa Pagarme",         fmt_brl(s['pagarme_fee']),       RED),
            kpi_card("Taxa Antecipação",     fmt_brl(s['anticipation_fee']),  RED),
            kpi_card("Receita Líquida",      fmt_brl(s['net_revenue']),       BLUE),
            kpi_card("Lucro Bruto (30%)",    fmt_brl(s['gross_profit']),      GREEN),
            kpi_card("Gasto em Ads" + ads_note, fmt_brl(s['total_ad_spend']), ORANGE),
            kpi_card("Lucro Líquido",        fmt_brl(s['net_profit']),        GREEN),
            kpi_card("ROI",  roi_str,  roi_color),
            kpi_card("ROAS", roas_str, PURPLE),
            kpi_card("Pedidos",  f"{s['total_orders']:,}"),
            kpi_card("Sessões",  f"{s['total_sessions']:,}"),
            style="display:flex;gap:10px;flex-wrap:wrap;",
        )

    @render.ui
    def marketing_kpis():
        w, m, g, pay = filtered()
        s = build_summary(w, m, g, pay)
        # sessões e usuários únicos do GA4
        total_sessions = int(g["sessions"].sum()) if not g.empty else 0
        total_users    = int(g["total_users"].sum()) if not g.empty and "total_users" in g.columns else 0
        # gasto total com ads (Meta)
        total_ads = s["total_ad_spend"]
        # receita líquida
        net_rev = s["net_revenue"]
        # assinantes ConvertKit: total real via API Secret
        ck = ck_data()
        subscribers = int(ck["total_subscribers"].iloc[0]) if not ck.empty and "total_subscribers" in ck.columns else 0

        def big_kpi(title, value, sub=None, color=DARK):
            return ui.div(
                ui.div(title, style="font-size:12px;color:#888;text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px;"),
                ui.div(value, style=f"font-size:26px;font-weight:800;color:{color};line-height:1.1;"),
                ui.div(sub or "", style="font-size:11px;color:#aaa;margin-top:4px;"),
                style=(
                    "background:#fff;border-radius:12px;padding:20px 24px;"
                    "box-shadow:0 2px 8px rgba(0,0,0,.07);flex:1;min-width:180px;"
                ),
            )

        return ui.div(
            big_kpi("Sessões no Site",        f"{total_sessions:,}".replace(",","."),
                    f"{total_users:,} usuários únicos".replace(",","."), BLUE),
            big_kpi("Gasto com Tráfego Pago", fmt_brl(total_ads),
                    "Meta Ads no período", ORANGE),
            big_kpi("Assinantes Boletim AM",  f"{subscribers:,}".replace(",","."),
                    "ConvertKit — base ativa", PURPLE),
            big_kpi("Receita Líquida",        fmt_brl(net_rev),
                    "WooCommerce menos taxas", GREEN),
            style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:20px;padding-top:12px;",
        )

    @render.plot
    def chart_roi():
        w, m, _, pay = filtered()
        df = build_roi(w, m, pay)
        if df.empty:
            fig, ax = plt.subplots(); ax.set_visible(False); return fig
        df["month"] = pd.to_datetime(df["date"].astype(str)).dt.to_period("M").astype(str)
        mo = df.groupby("month")[["revenue","pagarme_fee","anticipation_fee","net_revenue","gross_profit","ad_spend"]].sum().reset_index()

        BLUE1 = "#1a3a6b"
        BLUE2 = "#2980b9"
        BLUE3 = "#aed6f1"

        fig, ax = plt.subplots(figsize=(12, 4))
        ax2 = ax.twinx()

        x = list(range(len(mo)))
        bw = 0.18
        ax.bar([i - 2*bw for i in x], mo["revenue"],     bw*2, label="Receita Bruta",   color=BLUE1, alpha=.88)
        ax.bar([i         for i in x], mo["net_revenue"], bw*2, label="Receita Líquida", color=BLUE2, alpha=.88)
        ax.bar([i + 2*bw  for i in x], mo["gross_profit"],bw*2, label="Lucro Bruto",     color=BLUE3, alpha=.88)

        ax2.plot(x, mo["pagarme_fee"],      "s--", color=ORANGE, lw=1.5, markersize=4, label="Taxa Pagarme")
        ax2.plot(x, mo["anticipation_fee"], "^--", color=RED,    lw=1.5, markersize=4, label="Antecipação")
        ax2.plot(x, mo["ad_spend"],         "o-",  color=PURPLE, lw=2,   markersize=5, label="Gasto Ads")

        ax.set_xticks(x); ax.set_xticklabels(mo["month"], rotation=45, ha="right", fontsize=9)
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"R$ {v/1000:.0f}k"))
        ax2.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"R$ {v/1000:.0f}k"))
        ax.set_ylabel("Receita / Lucro", fontsize=8)
        ax2.set_ylabel("Taxas / Ads", fontsize=8)

        lines1, labels1 = ax.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines1 + lines2, labels1 + labels2, fontsize=8, ncol=3)

        ax.set_facecolor("#fafafa"); fig.patch.set_facecolor("#fafafa")
        fig.tight_layout()
        return fig

    def _roas_chart(m, ascending: bool):
        if m.empty or "spend" not in m.columns:
            fig, ax = plt.subplots()
            ax.text(.5, .5, "Sem dados de Meta Ads", ha="center", va="center")
            return fig
        df = build_roas(m).sort_values("roas", ascending=ascending).head(15)
        df = df.sort_values("roas", ascending=not ascending)
        labels = df["campaign"]
        colors = [GREEN if r >= 1 else RED for r in df["roas"]]

        fig, ax = plt.subplots(figsize=(12, max(3, len(df) * 0.35)))
        bars = ax.barh(labels, df["roas"], color=colors, alpha=.85)
        ax.axvline(1, color="gray", lw=1.2, ls="--", label="Break-even (1x)")
        for bar, val in zip(bars, df["roas"]):
            ax.text(bar.get_width() + 0.05, bar.get_y() + bar.get_height() / 2,
                    f"{val:.1f}x", va="center", fontsize=6)
        ax.set_xlabel("ROAS", fontsize=7)
        ax.legend(fontsize=7)
        ax.tick_params(axis="y", labelsize=6)
        ax.set_facecolor("#fafafa"); fig.patch.set_facecolor("#fafafa")
        fig.tight_layout()
        return fig

    # helpers Marketing ────────────────────────────────────────────────
    def _ga_filtered():
        start, end = input.ga_start(), input.ga_end()
        _, _, df_g, _, _, _, _, _, _ = data()
        df_g = df_g.copy(); df_g["date"] = pd.to_datetime(df_g["date"]).dt.date
        return df_g[(df_g["date"] >= start) & (df_g["date"] <= end)]

    def _tp_filtered_meta():
        start, end = input.tp_start(), input.tp_end()
        _, df_m, _, _, _, _, _, _, _ = data()
        df_m = df_m.copy(); df_m["date"] = pd.to_datetime(df_m["date"]).dt.date
        return df_m[(df_m["date"] >= start) & (df_m["date"] <= end)] if len(df_m) > 0 else empty_meta()

    @render.plot
    def chart_roas_top():
        m = _tp_filtered_meta()
        return _roas_chart(m, ascending=False)

    @render.plot
    def chart_roas_bottom():
        m = _tp_filtered_meta()
        return _roas_chart(m, ascending=True)

    @render.ui
    def table_campanhas_tp():
        _, df_m, _, _, _, _, _, _, _ = data()
        if df_m.empty or "spend" not in df_m.columns:
            return ui.p("Sem dados de campanhas.", style="color:#888;")
        df_m = df_m.copy()
        df_m["date"] = pd.to_datetime(df_m["date"]).dt.date
        hoje = date.today()
        mes_atual = df_m[(df_m["date"].apply(lambda d: d.year == hoje.year and d.month == hoje.month))]

        df = (mes_atual.groupby("campaign")
               .agg(spend=("spend","sum"), purchases=("purchases","sum"),
                    purchase_value=("purchase_value","sum"))
               .reset_index())
        df = df[df["spend"] > 0].copy()
        df["cac"]  = df.apply(lambda r: r["spend"] / r["purchases"] if r["purchases"] > 0 else None, axis=1)
        df["roas"] = df.apply(lambda r: r["purchase_value"] / r["spend"] if r["spend"] > 0 else 0, axis=1)
        df = df.sort_values("spend", ascending=False)

        header = ui.tags.tr(
            ui.tags.th("Campanha",      style="text-align:left;"),
            ui.tags.th("Investimento",  style="text-align:right;"),
            ui.tags.th("Vendas",        style="text-align:right;"),
            ui.tags.th("Receita Ads",   style="text-align:right;"),
            ui.tags.th("CAC",           style="text-align:right;"),
            ui.tags.th("ROAS",          style="text-align:right;"),
        )

        def roas_color(v):
            if v >= 3:   return GREEN
            if v >= 1:   return ORANGE
            return RED

        rows = []
        for _, r in df.iterrows():
            cac_str  = fmt_brl(r["cac"]) if r["cac"] is not None else "—"
            roas_val = r["roas"]
            nome     = r["campaign"]
            nome_str = (nome[:60] + "…") if len(nome) > 60 else nome
            rows.append(ui.tags.tr(
                ui.tags.td(nome_str, style="font-size:12px;max-width:360px;word-break:break-word;"),
                ui.tags.td(fmt_brl(r["spend"]),          style="text-align:right;font-size:12px;"),
                ui.tags.td(f"{int(r['purchases']):,}".replace(",","."), style="text-align:right;font-size:12px;"),
                ui.tags.td(fmt_brl(r["purchase_value"]), style="text-align:right;font-size:12px;"),
                ui.tags.td(cac_str,                      style="text-align:right;font-size:12px;"),
                ui.tags.td(f"{roas_val:.2f}x",
                           style=f"text-align:right;font-size:12px;font-weight:700;color:{roas_color(roas_val)};"),
            ))

        totals     = df[["spend","purchases","purchase_value"]].sum()
        total_cac  = totals["spend"] / totals["purchases"] if totals["purchases"] > 0 else None
        total_roas = totals["purchase_value"] / totals["spend"] if totals["spend"] > 0 else 0
        footer = ui.tags.tr(
            ui.tags.td("TOTAL", style="font-weight:700;font-size:12px;"),
            ui.tags.td(fmt_brl(totals["spend"]),          style="text-align:right;font-weight:700;font-size:12px;"),
            ui.tags.td(f"{int(totals['purchases']):,}".replace(",","."), style="text-align:right;font-weight:700;font-size:12px;"),
            ui.tags.td(fmt_brl(totals["purchase_value"]), style="text-align:right;font-weight:700;font-size:12px;"),
            ui.tags.td(fmt_brl(total_cac) if total_cac else "—", style="text-align:right;font-weight:700;font-size:12px;"),
            ui.tags.td(f"{total_roas:.2f}x",
                       style=f"text-align:right;font-weight:700;font-size:12px;color:{roas_color(total_roas)};"),
        )

        return ui.div(
            ui.tags.table(
                ui.tags.thead(header,
                              style="background:#1a3a6b;color:#fff;"),
                ui.tags.tbody(*rows),
                ui.tags.tfoot(footer,
                              style="background:#eaf0fb;border-top:2px solid #1a3a6b;"),
                style=(
                    "width:100%;border-collapse:collapse;"
                    "font-family:'Segoe UI',sans-serif;"
                ),
            ),
            ui.tags.style("""
                tbody tr:nth-child(even){background:#f8f9fa;}
                tbody tr:hover{background:#eaf0fb;}
                th,td{padding:7px 12px;border-bottom:1px solid #e8ecf0;}
            """),
            style="background:#fff;border-radius:10px;padding:16px;box-shadow:0 1px 4px rgba(0,0,0,.07);overflow-x:auto;",
        )

    @render.plot
    def chart_channels():
        g = _ga_filtered()
        df = build_channel_summary(g)
        if df.empty:
            fig, ax = plt.subplots(); ax.text(.5,.5,"Sem dados",ha="center",va="center"); return fig
        fig, ax = plt.subplots(figsize=(6, 3.5))
        bars = ax.bar(df["channel"], df["sessions"], color=BLUE, alpha=.85)
        for bar, val in zip(bars, df["sessions"]):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 20,
                    f"{val:,}", ha="center", fontsize=7)
        ax.set_ylabel("Sessões"); plt.xticks(rotation=30, ha="right", fontsize=8)
        ax.set_facecolor("#fafafa"); fig.patch.set_facecolor("#fafafa")
        fig.tight_layout()
        return fig

    @render.plot
    def chart_landing_pages():
        df = pages_data()
        if df.empty:
            fig, ax = plt.subplots(); ax.text(.5,.5,"Sem dados de landing pages",ha="center",va="center"); return fig
        top10 = df.nlargest(10, "sessions").sort_values("sessions")
        labels = top10["landing_page"].apply(lambda p: (p[:40] + "…") if len(p) > 40 else p)
        fig, ax = plt.subplots(figsize=(6, max(3, len(top10)*0.45)))
        bars = ax.barh(labels, top10["sessions"], color="#2980b9", alpha=.85)
        for bar, val in zip(bars, top10["sessions"]):
            ax.text(bar.get_width()*1.01, bar.get_y()+bar.get_height()/2,
                    f"{val:,}", va="center", fontsize=7)
        ax.set_xlabel("Sessões", fontsize=8)
        ax.tick_params(axis="y", labelsize=7)
        ax.set_facecolor("#fafafa"); fig.patch.set_facecolor("#fafafa")
        fig.tight_layout()
        return fig

    @render.plot
    def chart_ads_scatter():
        start, end = input.tp_start(), input.tp_end()
        m = _tp_filtered_meta()
        net = _daily_net_revenue(start, end)
        if m.empty or net.empty:
            fig, ax = plt.subplots(); ax.text(.5,.5,"Sem dados",ha="center",va="center"); return fig
        spend = m.groupby("date")["spend"].sum().reset_index()
        df = spend.merge(net[["date","net_revenue"]], on="date", how="inner").dropna()
        if len(df) < 3:
            fig, ax = plt.subplots(); ax.text(.5,.5,"Poucos dados",ha="center",va="center"); return fig
        x, y = df["spend"].values, df["net_revenue"].values
        r2 = np.corrcoef(x, y)[0,1]**2
        m_coef, b = np.polyfit(x, y, 1)
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.scatter(x, y, color=BLUE, alpha=.6, s=30)
        xline = np.linspace(x.min(), x.max(), 100)
        ax.plot(xline, m_coef*xline + b, color=RED, lw=1.5, ls="--")
        ax.set_xlabel("Gasto em Ads (R$)", fontsize=8)
        ax.set_ylabel("Receita Líquida (R$)", fontsize=8)
        ax.set_title(f"R² = {r2:.3f}", fontsize=10, fontweight="bold")
        ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v,_: f"R$ {v/1000:.0f}k"))
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v,_: f"R$ {v/1000:.0f}k"))
        ax.set_facecolor("#fafafa"); fig.patch.set_facecolor("#fafafa")
        fig.tight_layout()
        return fig

    @render.plot
    def chart_ads_line():
        start, end = input.tp_start(), input.tp_end()
        m = _tp_filtered_meta()
        net = _daily_net_revenue(start, end)
        if m.empty and net.empty:
            fig, ax = plt.subplots(); ax.text(.5,.5,"Sem dados",ha="center",va="center"); return fig
        spend = m.groupby("date")["spend"].sum().reset_index() if not m.empty else pd.DataFrame(columns=["date","spend"])
        df = net[["date","net_revenue"]].merge(spend, on="date", how="outer").fillna(0).sort_values("date")
        df["month"] = pd.to_datetime(df["date"].astype(str)).dt.to_period("M").astype(str)
        mo = df.groupby("month")[["net_revenue","spend"]].sum().reset_index()
        x = range(len(mo))
        fig, ax = plt.subplots(figsize=(6, 4))
        ax2 = ax.twinx()
        ax.plot(x, mo["net_revenue"], "o-", color=BLUE, lw=2, markersize=4, label="Receita Líquida")
        ax2.plot(x, mo["spend"], "s--", color=ORANGE, lw=1.5, markersize=4, label="Gasto Ads")
        ax.set_xticks(list(x)); ax.set_xticklabels(mo["month"], rotation=45, ha="right", fontsize=7)
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v,_: f"R$ {v/1000:.0f}k"))
        ax2.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v,_: f"R$ {v/1000:.0f}k"))
        ax.set_ylabel("Receita Líquida", fontsize=7)
        ax2.set_ylabel("Gasto Ads", fontsize=7)
        l1,lb1 = ax.get_legend_handles_labels(); l2,lb2 = ax2.get_legend_handles_labels()
        ax.legend(l1+l2, lb1+lb2, fontsize=7)
        ax.set_facecolor("#fafafa"); fig.patch.set_facecolor("#fafafa")
        fig.tight_layout()
        return fig

    def _email_chart(ascending: bool):
        start, end = input.em_start(), input.em_end()
        camps = df_campanhas[
            (df_campanhas["inicio"] >= start) & (df_campanhas["inicio"] <= end)
        ].copy()
        if camps.empty:
            fig, ax = plt.subplots(); ax.text(.5,.5,"Nenhuma campanha no período",ha="center",va="center"); return fig
        rows = []
        for _, row in camps.iterrows():
            net = _daily_net_revenue(row["inicio"], row["fim"])
            rows.append({"nome": row["nome"], "net_revenue": net["net_revenue"].sum()})
        df = pd.DataFrame(rows).sort_values("net_revenue", ascending=ascending).head(5)
        nome_curto = df["nome"].apply(lambda n: (n[:45]+"…") if len(n) > 45 else n)
        color = GREEN if not ascending else RED
        fig, ax = plt.subplots(figsize=(6, max(2.5, len(df)*0.6)))
        bars = ax.barh(nome_curto, df["net_revenue"], color=color, alpha=.85)
        for bar, val in zip(bars, df["net_revenue"]):
            ax.text(bar.get_width()*1.01, bar.get_y()+bar.get_height()/2,
                    fmt_brl(val), va="center", fontsize=7)
        ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v,_: f"R$ {v/1000:.0f}k"))
        ax.tick_params(axis="y", labelsize=7)
        ax.set_facecolor("#fafafa"); fig.patch.set_facecolor("#fafafa")
        fig.tight_layout()
        return fig

    @render.plot
    def chart_email_top5():
        return _email_chart(ascending=False)

    @render.plot
    def chart_email_bottom5():
        return _email_chart(ascending=True)

    @render.ui
    def comercial_kpis():
        w, _, _, _ = filtered()
        if w.empty:
            return ui.p("Sem dados no período.")
        total_alunos  = len(w)
        receita       = w["total"].sum()
        ticket_medio  = receita / total_alunos if total_alunos else 0
        metodos       = w["payment_method"].value_counts()
        metodo_top    = metodos.index[0] if len(metodos) else "—"
        return ui.div(
            kpi_card("Total de Pedidos",  f"{total_alunos:,}"),
            kpi_card("Receita (WooCommerce)", fmt_brl(receita), BLUE),
            kpi_card("Ticket Médio",      fmt_brl(ticket_medio), PURPLE),
            kpi_card("Forma Mais Usada",  metodo_top),
            style="display:flex;gap:10px;flex-wrap:wrap;",
        )

    @render.plot
    def chart_alunos_mensal():
        w, _, _, _ = filtered()
        if w.empty:
            fig, ax = plt.subplots(); ax.text(.5,.5,"Sem dados",ha="center",va="center"); return fig
        w = w.copy()
        w["month"] = pd.to_datetime(w["date"].astype(str)).dt.to_period("M").astype(str)
        mo = w.groupby("month").agg(pedidos=("order_id","count"), receita=("total","sum")).reset_index()

        fig, ax = plt.subplots(figsize=(12, 3.5))
        ax2 = ax.twinx()
        x = list(range(len(mo)))
        ax.bar(x, mo["pedidos"], color="#1a3a6b", alpha=.85, label="Pedidos")
        ax2.plot(x, mo["receita"], "o-", color=ORANGE, lw=2, markersize=5, label="Receita")
        ax.set_xticks(x); ax.set_xticklabels(mo["month"], rotation=45, ha="right", fontsize=9)
        ax.set_ylabel("Pedidos", fontsize=8)
        ax2.set_ylabel("Receita (R$)", fontsize=8)
        ax2.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"R$ {v/1000:.0f}k"))
        lines1, labels1 = ax.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines1 + lines2, labels1 + labels2, fontsize=8)
        ax.set_facecolor("#fafafa"); fig.patch.set_facecolor("#fafafa")
        fig.tight_layout()
        return fig

    @render.plot
    def chart_produtos():
        w, _, _, _ = filtered()
        if w.empty:
            fig, ax = plt.subplots(); ax.text(.5,.5,"Sem dados",ha="center",va="center"); return fig
        w = w.copy()
        prod = w.groupby("payment_method").agg(pedidos=("order_id","count"), receita=("total","sum")).reset_index()
        prod = prod.sort_values("receita", ascending=True)

        fig, ax = plt.subplots(figsize=(10, max(3, len(prod) * 0.5)))
        bars = ax.barh(prod["payment_method"], prod["receita"], color="#2980b9", alpha=.85)
        for bar, val in zip(bars, prod["receita"]):
            ax.text(bar.get_width() + 500, bar.get_y() + bar.get_height()/2,
                    f"R$ {val:,.0f}", va="center", fontsize=9)
        ax.set_xlabel("Receita (R$)", fontsize=8)
        ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"R$ {v/1000:.0f}k"))
        ax.set_facecolor("#fafafa"); fig.patch.set_facecolor("#fafafa")
        fig.tight_layout()
        return fig


    # ── Bloco 1: análise por curso ──────────────────────────────────────
    _cursos_sel = reactive.value(DEFAULT_CURSO)

    @reactive.effect
    def _track_cursos():
        v = input.prod_curso()
        _cursos_sel.set([v] if v else [])

    @reactive.calc
    def prod_filtered():
        it = items_data()
        it = it.copy()
        it["product_name"] = it["product_name"].str.strip()
        start, end = input.prod_start(), input.prod_end()
        df = it[(it["date"] >= start) & (it["date"] <= end)]
        cursos = _cursos_sel()
        if not cursos:
            return pd.DataFrame(columns=it.columns)
        return df[df["product_name"].isin(cursos)]

    @render.ui
    def prod_kpis():
        df = prod_filtered()
        pedidos  = df["order_id"].nunique()
        receita  = df["total"].sum()
        qtd      = df["quantity"].sum()
        ticket   = receita / pedidos if pedidos else 0
        return ui.div(
            kpi_card("Pedidos",      f"{pedidos:,}"),
            kpi_card("Receita",      fmt_brl(receita), BLUE),
            kpi_card("Itens Vendidos", f"{qtd:,}",      PURPLE),
            kpi_card("Ticket Médio", fmt_brl(ticket),   GREEN),
            style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:12px;",
        )

    @render.plot
    def chart_prod_mensal():
        df = prod_filtered()
        if df.empty:
            fig, ax = plt.subplots(); ax.text(.5,.5,"Sem dados",ha="center",va="center"); return fig
        df = df.copy()
        df["month"] = pd.to_datetime(df["date"].astype(str)).dt.to_period("M").astype(str)
        mo = df.groupby("month").agg(pedidos=("order_id","nunique"), receita=("total","sum")).reset_index()
        fig, ax = plt.subplots(figsize=(12, 3.5))
        ax2 = ax.twinx()
        x = list(range(len(mo)))
        ax.bar(x, mo["pedidos"], color="#1a3a6b", alpha=.85, label="Pedidos")
        ax2.plot(x, mo["receita"], "o-", color=ORANGE, lw=2, markersize=5, label="Receita")
        ax.set_xticks(x); ax.set_xticklabels(mo["month"], rotation=45, ha="right", fontsize=9)
        ax.set_ylabel("Pedidos", fontsize=8)
        ax2.set_ylabel("Receita (R$)", fontsize=8)
        ax2.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"R$ {v/1000:.0f}k"))
        l1, lb1 = ax.get_legend_handles_labels()
        l2, lb2 = ax2.get_legend_handles_labels()
        ax.legend(l1+l2, lb1+lb2, fontsize=8)
        ax.set_facecolor("#fafafa"); fig.patch.set_facecolor("#fafafa")
        fig.tight_layout(); return fig

    # ── Bloco 2: top/bottom 5 ───────────────────────────────────────────
    @reactive.calc
    def rank_filtered():
        it = items_data()
        start, end = input.rank_start(), input.rank_end()
        return it[(it["date"] >= start) & (it["date"] <= end)]

    def _rank_chart(df, n=5, ascending=False):
        if df.empty:
            fig, ax = plt.subplots(); ax.text(.5,.5,"Sem dados",ha="center",va="center"); return fig
        rank = (df.groupby("product_name")
                  .agg(pedidos=("order_id","nunique"), receita=("total","sum"))
                  .reset_index()
                  .sort_values("receita", ascending=ascending)
                  .head(n))
        color = GREEN if not ascending else RED
        fig, ax = plt.subplots(figsize=(6, max(2.5, len(rank)*0.55)))
        bars = ax.barh(rank["product_name"], rank["receita"], color=color, alpha=.85)
        for bar, val in zip(bars, rank["receita"]):
            ax.text(bar.get_width()*1.01, bar.get_y()+bar.get_height()/2,
                    f"R${val/1000:.1f}k", va="center", fontsize=7)
        ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v,_: f"R${v/1000:.0f}k"))
        ax.tick_params(axis="y", labelsize=7)
        ax.set_facecolor("#fafafa"); fig.patch.set_facecolor("#fafafa")
        fig.tight_layout(); return fig

    @render.plot
    def chart_top5():
        return _rank_chart(rank_filtered(), ascending=False)

    @render.plot
    def chart_bottom5():
        return _rank_chart(rank_filtered(), ascending=True)

    # ── Bloco 3: área mensal top 10 ─────────────────────────────────────
    @render.plot
    def chart_area_top10():
        it = items_data()
        start, end = input.area_start(), input.area_end()
        df = it[(it["date"] >= start) & (it["date"] <= end)].copy()
        if df.empty:
            fig, ax = plt.subplots(); ax.text(.5,.5,"Sem dados",ha="center",va="center"); return fig

        top10 = (df.groupby("product_name")["total"].sum()
                   .nlargest(10).index.tolist())
        df = df[df["product_name"].isin(top10)]
        df["month"] = pd.to_datetime(df["date"].astype(str)).dt.to_period("M").astype(str)
        pivot = (df.groupby(["month","product_name"])["total"].sum()
                   .unstack(fill_value=0)
                   .reindex(columns=top10))

        pivot_pct = pivot.div(pivot.sum(axis=1), axis=0).fillna(0) * 100

        colors = plt.cm.Blues_r([i/len(top10) for i in range(len(top10))])
        fig, ax = plt.subplots(figsize=(13, 4.5))
        ax.stackplot(range(len(pivot_pct)), pivot_pct.T.values, labels=top10, colors=colors, alpha=.85)
        ax.set_xticks(range(len(pivot_pct)))
        ax.set_xticklabels(pivot_pct.index, rotation=45, ha="right", fontsize=8)
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v,_: f"{v:.0f}%"))
        ax.set_ylim(0, 100)
        ax.legend(loc="upper left", fontsize=7, ncol=1,
                  bbox_to_anchor=(1.01, 1), borderaxespad=0)
        ax.set_facecolor("#fafafa"); fig.patch.set_facecolor("#fafafa")
        fig.tight_layout(); return fig

    # ── Comercial / CRM ─────────────────────────────────────────────────
    @render.ui
    def comercial_kpis():
        df = kommo_data()
        start, end = input.crm_start(), input.crm_end()
        if df.empty:
            return ui.p("Sem dados do CRM.", style="color:#888;")
        # coorte: leads criados no período — status atual
        coorte      = df[(df["date"] >= start) & (df["date"] <= end)]
        total       = len(coorte)
        convertidos = int(coorte["is_won"].sum())
        perdidos    = int(coorte["is_lost"].sum())
        follow      = int((coorte["status"] == "Follow/Nutrição").sum())
        negociacao  = int((coorte["status"] == "Negociação").sum())
        taxa        = convertidos / total * 100 if total else 0
        ticket      = coorte[coorte["is_won"]]["price"].mean() if convertidos else 0

        def big_kpi(title, value, sub=None, color=DARK):
            return ui.div(
                ui.div(title, style="font-size:12px;color:#888;text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px;"),
                ui.div(value, style=f"font-size:26px;font-weight:800;color:{color};line-height:1.1;"),
                ui.div(sub or "", style="font-size:11px;color:#aaa;margin-top:4px;"),
                style="background:#fff;border-radius:12px;padding:20px 24px;box-shadow:0 2px 8px rgba(0,0,0,.07);flex:1;min-width:160px;",
            )

        return ui.div(
            big_kpi("Novos Leads",      f"{total:,}".replace(",","."), "no período selecionado", BLUE),
            big_kpi("Convertidos",      f"{convertidos:,}".replace(",","."), "Pagamento feito / ganho", GREEN),
            big_kpi("Perdidos",         f"{perdidos:,}".replace(",","."), "fechado como perdido", RED),
            big_kpi("Taxa de Conversão",f"{taxa:.1f}%", "convertidos / (conv. + perdidos)", PURPLE),
            big_kpi("Ticket Médio CRM", fmt_brl(ticket), "valor médio dos convertidos", ORANGE),
            style="display:flex;gap:16px;flex-wrap:wrap;padding-top:12px;margin-bottom:8px;",
        )

    @render.plot
    def chart_leads_mensal():
        df = kommo_data()
        start, end = input.crm_start(), input.crm_end()
        if df.empty:
            fig, ax = plt.subplots(); ax.text(.5,.5,"Sem dados",ha="center",va="center"); return fig

        # coorte: todos os leads criados no período, agrupados por mês de criação
        coorte = df[(df["date"] >= start) & (df["date"] <= end)].copy()
        coorte["month"] = pd.to_datetime(coorte["date"].astype(str)).dt.to_period("M").astype(str)

        mo_total  = coorte.groupby("month")["lead_id"].count().rename("leads")
        mo_conv   = coorte[coorte["is_won"]].groupby("month")["lead_id"].count().rename("convertidos")
        mo_perd   = coorte[coorte["is_lost"]].groupby("month")["lead_id"].count().rename("perdidos")
        mo_follow = coorte[coorte["status"] == "Follow/Nutrição"].groupby("month")["lead_id"].count().rename("follow")
        mo_neg    = coorte[coorte["status"] == "Negociação"].groupby("month")["lead_id"].count().rename("negociacao")

        mo = pd.concat([mo_total, mo_conv, mo_perd, mo_follow, mo_neg], axis=1).fillna(0).reset_index()
        mo = mo.sort_values("month")

        if mo.empty:
            fig, ax = plt.subplots(); ax.text(.5,.5,"Sem leads no período",ha="center",va="center"); return fig

        x = list(range(len(mo)))
        fig, ax = plt.subplots(figsize=(7, 3.5))
        ax2 = ax.twinx()
        ax.bar(x, mo["leads"], color="#1a3a6b", alpha=.8, label="Novos Leads")
        ax2.plot(x, mo["convertidos"], "o-",  color=GREEN,  lw=2, markersize=5, label="Convertidos")
        ax2.plot(x, mo["perdidos"],    "s--", color=RED,    lw=2, markersize=5, label="Perdidos")
        ax2.plot(x, mo["follow"],      "^:",  color=PURPLE, lw=1.5, markersize=4, label="Follow")
        ax2.plot(x, mo["negociacao"],  "D:",  color=ORANGE, lw=1.5, markersize=4, label="Negociação")
        ax.set_xticks(x); ax.set_xticklabels(mo["month"], rotation=45, ha="right", fontsize=8)
        ax.set_ylabel("Novos Leads (por mês de criação)", fontsize=8)
        ax2.set_ylabel("Status atual da coorte", fontsize=8)
        l1,lb1 = ax.get_legend_handles_labels(); l2,lb2 = ax2.get_legend_handles_labels()
        ax.legend(l1+l2, lb1+lb2, fontsize=7, ncol=3)
        ax.set_facecolor("#fafafa"); fig.patch.set_facecolor("#fafafa")
        fig.tight_layout(); return fig

    @render.plot
    def chart_funil():
        df     = kommo_data()
        merged = kommo_woo_merged()
        start, end = input.crm_start(), input.crm_end()
        if df.empty:
            fig, ax = plt.subplots(); ax.text(.5,.5,"Sem dados",ha="center",va="center"); return fig

        # coorte: todos os leads criados no período
        coorte = df[(df["date"] >= start) & (df["date"] <= end)]
        total = len(coorte)
        if total == 0:
            fig, ax = plt.subplots(); ax.text(.5,.5,"Sem leads no período",ha="center",va="center"); return fig

        convertidos = int(coorte["is_won"].sum())
        perdidos    = int(coorte["is_lost"].sum())
        follow      = int((coorte["status"] == "Follow/Nutrição").sum())
        negociacao  = int((coorte["status"] == "Negociação").sum())
        em_aberto   = total - convertidos - perdidos - follow - negociacao

        labels = ["Em Aberto", "Negociação", "Follow/Nutrição", "Perdidos", "Convertidos"]
        values = [em_aberto, negociacao, follow, perdidos, convertidos]
        bar_colors = ["#95a5a6", ORANGE, PURPLE, RED, GREEN]

        fig, ax = plt.subplots(figsize=(6, 3.5))
        bars = ax.barh(labels, values, color=bar_colors, alpha=.88)
        max_val = max(values) if max(values) > 0 else 1
        for bar, val in zip(bars, values):
            pct = val / total * 100
            ax.text(bar.get_width() + max_val * 0.01,
                    bar.get_y() + bar.get_height() / 2,
                    f"{val:,}  ({pct:.0f}%)".replace(",", "."),
                    va="center", fontsize=8)
        ax.set_xlabel("Leads da coorte", fontsize=8)
        ax.set_title(f"Coorte: {total} leads criados no período", fontsize=9, color="#555")
        ax.set_xlim(0, max_val * 1.35)
        ax.set_facecolor("#fafafa"); fig.patch.set_facecolor("#fafafa")
        fig.tight_layout(); return fig


    # ── CRM × WooCommerce ───────────────────────────────────────────────
    @render.ui
    def crm_woo_kpis():
        df = kommo_woo_merged()
        if df.empty:
            return ui.p("Sem dados cruzados ainda — aguarde o carregamento do Kommo.", style="color:#888;")
        total_won      = len(df)
        com_woo        = int((df["woo_revenue"] > 0).sum())
        sem_woo        = total_won - com_woo
        ltv_medio      = df[df["woo_revenue"] > 0]["woo_revenue"].mean()
        receita_total  = df["woo_revenue"].sum()
        match_pct      = com_woo / total_won * 100 if total_won else 0

        def big_kpi(title, value, sub=None, color=DARK):
            return ui.div(
                ui.div(title, style="font-size:12px;color:#888;text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px;"),
                ui.div(value, style=f"font-size:24px;font-weight:800;color:{color};line-height:1.1;"),
                ui.div(sub or "", style="font-size:11px;color:#aaa;margin-top:4px;"),
                style="background:#fff;border-radius:12px;padding:18px 22px;box-shadow:0 2px 8px rgba(0,0,0,.07);flex:1;min-width:150px;",
            )

        return ui.div(
            big_kpi("Leads Convertidos", f"{total_won:,}".replace(",","."), "com e-mail no CRM", BLUE),
            big_kpi("Match WooCommerce", f"{com_woo:,}".replace(",","."), f"{match_pct:.0f}% dos convertidos", GREEN),
            big_kpi("Sem Histórico Woo", f"{sem_woo:,}".replace(",","."), "não compraram no site", ORANGE),
            big_kpi("LTV Médio",         fmt_brl(ltv_medio), "receita média por cliente", PURPLE),
            big_kpi("Receita Total CRM", fmt_brl(receita_total), "WooCommerce atribuível ao CRM", DARK),
            style="display:flex;gap:14px;flex-wrap:wrap;margin-bottom:12px;",
        )

    @render.plot
    def chart_ltv_dist():
        df = kommo_woo_merged()
        if df.empty or (df["woo_revenue"] > 0).sum() == 0:
            fig, ax = plt.subplots(); ax.text(.5,.5,"Sem dados",ha="center",va="center"); return fig
        vals = df[df["woo_revenue"] > 0]["woo_revenue"]
        bins = [0, 200, 500, 1000, 2000, 5000, float("inf")]
        labels = ["até R$200", "R$200–500", "R$500–1k", "R$1k–2k", "R$2k–5k", "acima R$5k"]
        counts = pd.cut(vals, bins=bins, labels=labels).value_counts().reindex(labels)
        fig, ax = plt.subplots(figsize=(6, 3.5))
        bars = ax.bar(labels, counts, color=BLUE, alpha=.85)
        for bar, val in zip(bars, counts):
            ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+1,
                    f"{int(val)}", ha="center", fontsize=8)
        ax.set_ylabel("Clientes", fontsize=8)
        plt.xticks(rotation=20, ha="right", fontsize=8)
        ax.set_facecolor("#fafafa"); fig.patch.set_facecolor("#fafafa")
        fig.tight_layout(); return fig

    @render.plot
    def chart_top_clientes():
        df = kommo_woo_merged()
        if df.empty:
            fig, ax = plt.subplots(); ax.text(.5,.5,"Sem dados",ha="center",va="center"); return fig
        top = df[df["woo_revenue"] > 0].nlargest(10, "woo_revenue")[["email","woo_revenue","woo_orders"]].copy()
        top["label"] = top["email"].apply(lambda e: e[:28]+"…" if len(e) > 28 else e)
        fig, ax = plt.subplots(figsize=(6, max(3, len(top)*0.5)))
        bars = ax.barh(top["label"], top["woo_revenue"], color=GREEN, alpha=.85)
        for bar, val in zip(bars, top["woo_revenue"]):
            ax.text(bar.get_width()*1.01, bar.get_y()+bar.get_height()/2,
                    fmt_brl(val), va="center", fontsize=7)
        ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v,_: f"R$ {v/1000:.0f}k"))
        ax.tick_params(axis="y", labelsize=7)
        ax.set_facecolor("#fafafa"); fig.patch.set_facecolor("#fafafa")
        fig.tight_layout(); return fig


    # ── Clientes ────────────────────────────────────────────────────────
    @render.ui
    @reactive.event(input.buscar_cliente)
    def cliente_perfil():
        email = input.cliente_email().strip().lower()
        if not email:
            return ui.p("Digite um e-mail e clique em Buscar.", style="color:#888;")

        _, _, _, _, df_w, df_it, _, _, _ = data()
        df_w  = df_w.copy()
        df_it = df_it.copy()

        df_w["email_norm"] = df_w["customer_email"].str.lower().str.strip()
        pedidos = df_w[df_w["email_norm"] == email].sort_values("date", ascending=False)

        if pedidos.empty:
            return ui.p(f"Nenhum pedido encontrado para '{email}'.", style="color:#e74c3c;font-weight:600;")

        # métricas
        ltv         = pedidos["total"].sum()
        n_pedidos   = len(pedidos)
        ticket_med  = ltv / n_pedidos

        if ltv >= 10_000:
            classe, classe_color, classe_bg = "Aluno Premium",  "#fff",    "#f39c12"
        elif ltv >= 2_000:
            classe, classe_color, classe_bg = "Aluno Mediano",  "#fff",    "#2980b9"
        else:
            classe, classe_color, classe_bg = "Aluno Iniciante","#555",    "#dfe6e9"

        # dados do primeiro pedido (nome e telefone)
        primeiro = pedidos.iloc[-1]
        nome_col  = [c for c in ["billing_first_name","billing_last_name"] if c in pedidos.columns]
        if nome_col:
            nome = (str(primeiro.get("billing_first_name","")) + " " +
                    str(primeiro.get("billing_last_name",""))).strip()
        else:
            nome = "—"
        telefone = primeiro.get("billing_phone", "") if "billing_phone" in pedidos.columns else ""
        telefone = telefone if telefone else "—"

        # cursos por pedido
        itens = df_it[df_it["order_id"].isin(pedidos["order_id"])].copy()
        itens = itens.merge(
            pedidos[["order_id","date"]].rename(columns={"date":"order_date"}),
            on="order_id", how="left"
        ).sort_values("order_date", ascending=False)

        def kpi(title, value, color=DARK):
            return ui.div(
                ui.div(title, style="font-size:11px;color:#888;text-transform:uppercase;letter-spacing:.5px;margin-bottom:5px;"),
                ui.div(value, style=f"font-size:22px;font-weight:800;color:{color};"),
                style="background:#fff;border-radius:10px;padding:16px 20px;"
                      "box-shadow:0 1px 4px rgba(0,0,0,.08);flex:1;min-width:140px;",
            )

        # tabela de cursos
        if itens.empty:
            tabela_cursos = ui.p("Sem detalhes de itens disponíveis.", style="color:#aaa;font-size:13px;")
        else:
            header = ui.tags.tr(
                ui.tags.th("Data",    style="text-align:left;width:110px;"),
                ui.tags.th("Curso",   style="text-align:left;"),
                ui.tags.th("Valor",   style="text-align:right;width:120px;"),
            )
            rows_html = []
            for _, r in itens.iterrows():
                nome_curso = str(r["product_name"])
                nome_curso = (nome_curso[:70] + "…") if len(nome_curso) > 70 else nome_curso
                rows_html.append(ui.tags.tr(
                    ui.tags.td(str(r["order_date"]), style="font-size:12px;color:#666;"),
                    ui.tags.td(nome_curso,           style="font-size:12px;"),
                    ui.tags.td(fmt_brl(r["total"]),  style="text-align:right;font-size:12px;"),
                ))
            tabela_cursos = ui.div(
                ui.tags.table(
                    ui.tags.thead(header, style="background:#1a3a6b;color:#fff;"),
                    ui.tags.tbody(*rows_html),
                    style="width:100%;border-collapse:collapse;font-family:'Segoe UI',sans-serif;",
                ),
                ui.tags.style("tbody tr:nth-child(even){background:#f8f9fa;}"
                              "th,td{padding:7px 12px;border-bottom:1px solid #e8ecf0;}"),
                style="background:#fff;border-radius:10px;padding:16px;"
                      "box-shadow:0 1px 4px rgba(0,0,0,.07);overflow-x:auto;",
            )

        return ui.div(
            # cabeçalho do perfil
            ui.div(
                ui.div(
                    ui.div(nome if nome != "—" else email,
                           style="font-size:18px;font-weight:800;color:#2c3e50;"),
                    ui.div(email, style="font-size:12px;color:#888;margin-top:2px;"),
                    ui.div(f"WhatsApp: {telefone}",
                           style="font-size:12px;color:#555;margin-top:4px;"),
                    style="flex:1;",
                ),
                ui.div(
                    classe,
                    style=(f"background:{classe_bg};color:{classe_color};"
                           "font-size:13px;font-weight:700;padding:8px 18px;"
                           "border-radius:20px;align-self:center;"),
                ),
                style="display:flex;justify-content:space-between;align-items:flex-start;"
                      "background:#fff;padding:20px 24px;border-radius:12px;"
                      "box-shadow:0 2px 8px rgba(0,0,0,.08);margin-bottom:16px;",
            ),
            # KPIs
            ui.div(
                kpi("LTV Total",     fmt_brl(ltv),         BLUE),
                kpi("Ticket Médio",  fmt_brl(ticket_med),  PURPLE),
                kpi("Pedidos",       str(n_pedidos),       DARK),
                style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px;",
            ),
            # tabela de cursos
            ui.div("Histórico de Compras", class_="section-title"),
            tabela_cursos,
        )


app = App(app_ui, server)
