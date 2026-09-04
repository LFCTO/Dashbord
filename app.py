import calendar
import datetime
import io
import json
import os
import shutil
import tempfile
import time
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import urllib.parse

st.set_page_config(page_title="Analytics MT5 Multi-Comptes", layout="wide")
st.title("📊 Dashboard Quantitatif Avancé Multi-Comptes MT5")

# --- PROTECTION PAR MOT DE PASSE ---
password = st.text_input("Mot de passe requis pour accéder au dashboard :", type="password")

if password != "20032026":  # Tu changes ce texte par le mot de passe de ton choix
    st.warning("Veuillez entrer le mot de passe pour afficher le contenu.")
    st.stop()

# Sur Streamlit Cloud, les fichiers du repo sont dans le dossier courant
COMMON_PATH = "./"

# ------------------------------------------------------------------
# CONFIGURATION DES COMPTES (Dates de début et Capitaux Initiaux)
# ------------------------------------------------------------------
ACCOUNTS_CONFIG = {
    5118904: {
        "start_date": pd.to_datetime("2026-03-20"),
        "initial_balance": 1000.0,
    },
    11642227: {
        "start_date": pd.to_datetime("2026-06-01"),
        "initial_balance": 1174.61,
    },
    11642818: {
        "start_date": pd.to_datetime("2026-06-16"),
        "initial_balance": 300.0,
    },
    5116661: {
        "start_date": pd.to_datetime("2026-07-26"),
        "initial_balance": 1000.0,
    },
}


# ------------------------------------------------------------------
# MODULE : ANALYSE TEMPORELLE ET SAISONNALITÉ DES PROFITS
# ------------------------------------------------------------------
def render_temporal_analysis(df_filtered):
  st.markdown("---")
  st.markdown("## 🦉 Saisonnalité des Heures et des Jours")

  time_ref = st.radio(
      "Sélectionner la référence pour la saisonnalité :",
      options=["Heure de clôture", "Heure d'ouverture"],
      horizontal=True,
      key="selector_temporal_analysis",
  )

  col_time = "time" if time_ref == "Heure de clôture" else "open_time"

  if col_time in df_filtered.columns and "profit" in df_filtered.columns:
    df_filtered["hour"] = pd.to_datetime(df_filtered[col_time]).dt.hour
    hourly_perf = df_filtered.groupby("hour")["profit"].sum().reset_index()
    hourly_perf["color"] = hourly_perf["profit"].apply(
        lambda x: "Profit" if x >= 0 else "Perte"
    )

    days_order = [
        "Lundi",
        "Mardi",
        "Mercredi",
        "Jeudi",
        "Vendredi",
        "Samedi",
        "Dimanche",
    ]
    day_mapping = {
        "Monday": "Lundi",
        "Tuesday": "Mardi",
        "Wednesday": "Mercredi",
        "Thursday": "Jeudi",
        "Friday": "Vendredi",
        "Saturday": "Samedi",
        "Sunday": "Dimanche",
    }
    df_filtered["day_of_week"] = (
        pd.to_datetime(df_filtered[col_time]).dt.day_name().map(day_mapping)
    )

    daily_perf = (
        df_filtered.groupby("day_of_week")["profit"]
        .sum()
        .reindex(days_order)
        .reset_index()
    )
    daily_perf["color"] = daily_perf["profit"].apply(
        lambda x: "Profit" if x >= 0 else "Perte"
    )

    col1, col2 = st.columns(2)

    with col1:
      st.markdown(f"### 📊 Performance par Heure ({time_ref})")
      fig_hour = px.bar(
          hourly_perf,
          x="hour",
          y="profit",
          color="color",
          color_discrete_map={"Profit": "#00CC96", "Perte": "#EF553B"},
          labels={"hour": "Heure", "profit": "Profit Net (€)"},
      )
      fig_hour.update_layout(
          plot_bgcolor="rgba(0,0,0,0)",
          paper_bgcolor="rgba(0,0,0,0)",
          font_color="white",
      )
      st.plotly_chart(fig_hour, use_container_width=True)

    with col2:
      st.markdown(f"### 📊 Performance par Jour de la Semaine ({time_ref})")
      fig_day = px.bar(
          daily_perf,
          x="day_of_week",
          y="profit",
          color="color",
          color_discrete_map={"Profit": "#00CC96", "Perte": "#EF553B"},
          labels={"day_of_week": "Jour", "profit": "Profit Net (€)"},
      )
      fig_day.update_xaxes(categoryorder="array", categoryarray=days_order)
      fig_day.update_layout(
          plot_bgcolor="rgba(0,0,0,0)",
          paper_bgcolor="rgba(0,0,0,0)",
          font_color="white",
      )
      st.plotly_chart(fig_day, use_container_width=True)
  else:
    st.warning(
        f"Les colonnes nécessaires (`{col_time}` ou `profit`) sont introuvables"
        " dans le DataFrame."
    )


# ------------------------------------------------------------------
def get_num(dictionary: dict, possible_keys: list) -> float:
  if not isinstance(dictionary, dict):
    return 0.0

  dict_lower = {str(k).lower(): v for k, v in dictionary.items()}
  for key in possible_keys:
    key_lower = key.lower()
    if key_lower in dict_lower and dict_lower[key_lower] is not None:
      try:
        val = float(dict_lower[key_lower])
        if not np.isnan(val):
          return val
      except (ValueError, TypeError):
        continue
  return 0.0


@st.cache_data(ttl=5)
def load_all_accounts():
  accounts = []
  if not os.path.exists(COMMON_PATH):
    return accounts

  temp_dir = tempfile.gettempdir()

  for file_name in os.listdir(COMMON_PATH):
    if file_name.startswith("account_") and file_name.endswith(".json"):
      full_path = os.path.join(COMMON_PATH, file_name)
      temp_path = os.path.join(temp_dir, f"tmp_{file_name}")
      data = None

      for attempt in range(5):
        try:
          shutil.copy2(full_path, temp_path)
          for encoding in ["utf-16", "utf-8", "cp1252"]:
            try:
              with open(temp_path, "r", encoding=encoding) as f:
                content = f.read()
                if content.strip():
                  parsed = json.loads(content)
                  if isinstance(parsed, dict) and "login" in parsed:
                    data = parsed
                    break
            except (json.JSONDecodeError, UnicodeDecodeError):
              continue

          if data is not None:
            break
        except (PermissionError, OSError):
          pass

        time.sleep(0.1)

      if os.path.exists(temp_path):
        try:
          os.remove(temp_path)
        except Exception:
          pass

      if data:
        accounts.append(data)

  return accounts


if st.sidebar.button("🔄 Rafraîchir les données"):
  st.cache_data.clear()
  st.rerun()

data = load_all_accounts()

if not data:
  st.warning("Aucune donnée détectée dans le dossier partagé MT5.")
  st.stop()

# --- BARRE LATÉRALE DE FILTRAGE ---
st.sidebar.header("🎯 Navigation & Filtres")

account_logins = [str(acc["login"]) for acc in data]
selected_account = st.sidebar.selectbox(
    "Choisir un compte à analyser :", ["Tous les comptes"] + account_logins
)

if selected_account == "Tous les comptes":
  active_accounts = data
else:
  active_accounts = [
      acc for acc in data if str(acc["login"]) == selected_account
  ]

current_balance = sum(acc.get("balance", 0.0) for acc in active_accounts)
current_equity = sum(acc.get("equity", 0.0) for acc in active_accounts)
current_profit = sum(acc.get("profit", 0.0) for acc in active_accounts)
currency = (
    active_accounts[0].get("currency", "EUR") if active_accounts else "EUR"
)

if selected_account == "Tous les comptes":
  total_initial_capital = sum(
      cfg["initial_balance"] for cfg in ACCOUNTS_CONFIG.values()
  )
else:
  sel_id = int(selected_account)
  total_initial_capital = ACCOUNTS_CONFIG.get(sel_id, {}).get(
      "initial_balance", 1000.0
  )

# --- EXTRACTION ET DÉDUPLICATION DE TOUS LES COMPTES ---
global_history = []
for acc in data:
  acc_login = int(acc["login"])
  account_start_date = (
      pd.to_datetime(ACCOUNTS_CONFIG[acc_login]["start_date"])
      if acc_login in ACCOUNTS_CONFIG
      else pd.to_datetime("2026-01-01")
  )

  for deal in acc.get("history", []):
    if str(deal.get("type", "")).lower() == "balance" or deal.get("type") == 2:
      continue

    entry_str = str(deal.get("entry", "")).lower()

    if entry_str not in ["out", "out_by", "1", "2"]:
      continue

    profit_val = get_num(deal, ["profit", "pnl", "deal_profit"])
    swap_val = get_num(
        deal, ["swap", "swaps", "storage", "deal_swap", "rollover"]
    )
    comm_val = get_num(
        deal,
        [
            "commission",
            "commissions",
            "comm",
            "fee",
            "fees",
            "deal_commission",
            "charge",
        ],
    )

    # MISE À JOUR COMMISSIONS IC MARKETS (Comptes commençant par '11')
    if str(acc_login).startswith("11"):
      comm_val = comm_val * 2.0

    volume_val = get_num(deal, ["volume", "lots", "size"])

    total_trade_profit = profit_val + swap_val + comm_val

    t_close = deal.get("time")
    if t_close is None:
      continue

    try:
      close_time = (
          pd.to_datetime(int(t_close), unit="s")
          if str(t_close).isdigit()
          else pd.to_datetime(t_close)
      )
    except Exception:
      continue

    if close_time < account_start_date:
      continue

    t_open = deal.get("open_time", t_close)
    try:
      open_time = (
          pd.to_datetime(int(t_open), unit="s")
          if str(t_open).isdigit()
          else pd.to_datetime(t_open)
      )
    except Exception:
      open_time = close_time

    deal_copy = deal.copy()
    deal_copy["time"] = close_time
    deal_copy["open_time"] = open_time
    deal_copy["login"] = acc_login
    deal_copy["raw_profit"] = profit_val
    deal_copy["profit"] = total_trade_profit
    deal_copy["swap"] = swap_val
    deal_copy["commission"] = comm_val
    deal_copy["volume"] = volume_val

    global_history.append(deal_copy)

df_global = pd.DataFrame(global_history)
if not df_global.empty:
  df_global["time"] = pd.to_datetime(df_global["time"], errors="coerce")
  df_global["open_time"] = pd.to_datetime(df_global["open_time"], errors="coerce")
  df_global = df_global.dropna(subset=["time", "open_time"])
  if "ticket" in df_global.columns:
    df_global = df_global.drop_duplicates(subset=["ticket"])

if selected_account == "Tous les comptes":
  df_hist = df_global.copy() if not df_global.empty else pd.DataFrame()
else:
  df_hist = (
      df_global[df_global["login"] == int(selected_account)].copy()
      if not df_global.empty
      else pd.DataFrame()
  )

if not df_hist.empty:
  df_hist = df_hist.sort_values(by="time")
  df_hist["cum_profit"] = df_hist["profit"].cumsum()
  df_hist["peak"] = df_hist["cum_profit"].cummax()
  df_hist["drawdown"] = df_hist["cum_profit"] - df_hist["peak"]
  df_hist["peak_capital"] = (
      total_initial_capital + df_hist["cum_profit"]
  ).cummax()
  df_hist["drawdown_pct"] = (
      abs(df_hist["drawdown"]) / df_hist["peak_capital"]
  ) * 100
  df_hist["cum_profit_pct"] = (
      df_hist["cum_profit"] / total_initial_capital
  ) * 100
  df_hist["date_only"] = df_hist["time"].dt.date

real_net_profit = df_hist["profit"].sum() if not df_hist.empty else 0.0

# ===================================================================
# ORDRE D'AFFICHAGE DES MODULES (1 à 10)
# ===================================================================

# --- 1. MODULE ANALYSE (Résumé des métriques et capitaux) ---
st.subheader(f"📌 Analyse : {selected_account}")

balance_pct = (
    ((current_balance - total_initial_capital) / total_initial_capital * 100)
    if total_initial_capital > 0
    else 0.0
)
equity_pct = (
    ((current_equity - total_initial_capital) / total_initial_capital * 100)
    if total_initial_capital > 0
    else 0.0
)
net_profit_pct = (
    (real_net_profit / total_initial_capital * 100)
    if total_initial_capital > 0
    else 0.0
)
latent_pct = (
    (current_profit / total_initial_capital * 100)
    if total_initial_capital > 0
    else 0.0
)

c1, c2, c3, c4 = st.columns(4)
c1.metric(
    "💰 Solde Actuel (Balance)",
    f"{current_balance:,.2f} {currency}".replace(",", " "),
    f"{balance_pct:+.2f}% / Init",
)
c2.metric(
    "📈 Capital Actuel (Équité)",
    f"{current_equity:,.2f} {currency}".replace(",", " "),
    f"{equity_pct:+.2f}% / Init",
)
c3.metric(
    "✨ Profit Net Réalisé",
    f"{real_net_profit:,.2f} {currency}".replace(",", " "),
    f"{net_profit_pct:+.2f}%",
)
c4.metric(
    "⚡ Profit Latent En Cours",
    f"{current_profit:,.2f} {currency}".replace(",", " "),
    f"{latent_pct:+.2f}%",
)

st.markdown("---")

if not df_hist.empty:
  df_daily = df_hist.groupby("date_only")["profit"].sum().reset_index()

  # --- 2. HEATMAP CALENDAIRE ---
  st.markdown("### 📅 Calendrier & Heatmap des Gains Journaliers")
  if not df_daily.empty:
    hm_col1, hm_col2 = st.columns(2)

    granularity = hm_col1.selectbox(
        "🔍 Vue de la Heatmap :",
        [
            "Tous les jours du mois",
            "Tous les mois de l'année",
            "Toutes les années (Global)",
        ],
        index=0,
        key="heatmap_granularity",
    )

    df_cal = df_daily.copy()
    df_cal["date_dt"] = pd.to_datetime(df_cal["date_only"])
    df_cal["Annee"] = df_cal["date_dt"].dt.year
    df_cal["Mois"] = df_cal["date_dt"].dt.month
    available_years = sorted(df_cal["Annee"].unique(), reverse=True)

    if granularity == "Tous les jours du mois":
      sel_year = hm_col2.selectbox(
          "Choisir l'année :", available_years, key="hm_sel_year"
      )
      months_in_year = sorted(
          df_cal[df_cal["Annee"] == sel_year]["Mois"].unique()
      )
      month_names = {
          1: "Janvier",
          2: "Février",
          3: "Mars",
          4: "Avril",
          5: "Mai",
          6: "Juin",
          7: "Juillet",
          8: "Août",
          9: "Septembre",
          10: "Octobre",
          11: "Novembre",
          12: "Décembre",
      }
      sel_month = st.selectbox(
          "Choisir le mois :",
          months_in_year,
          format_func=lambda x: month_names.get(x, str(x)),
          key="hm_sel_month",
      )

      _, last_day_num = calendar.monthrange(sel_year, sel_month)
      start_date = pd.Timestamp(sel_year, sel_month, 1)
      end_date = pd.Timestamp(sel_year, sel_month, last_day_num)
      full_range = pd.date_range(start=start_date, end=end_date, freq="D")
      df_full = pd.DataFrame({"date_dt": full_range})
      df_full["date_only"] = df_full["date_dt"].dt.date

      df_cal["date_only"] = pd.to_datetime(df_cal["date_only"]).dt.date
      df_month_data = df_cal[
          (df_cal["Annee"] == sel_year) & (df_cal["Mois"] == sel_month)
      ].copy()

      df_cal_month = pd.merge(
          df_full,
          df_month_data,
          on=["date_only"],
          how="left",
          suffixes=("", "_dup"),
      )
      if "date_dt_dup" in df_cal_month.columns:
        df_cal_month = df_cal_month.drop(columns=["date_dt_dup"])
      df_cal_month["profit"] = df_cal_month["profit"].fillna(0.0)

      base_cap_approx = total_initial_capital + df_cal[
          df_cal["date_dt"] < start_date
      ]["profit"].sum()
      if base_cap_approx <= 0:
        base_cap_approx = total_initial_capital

      df_cal_month["cum_before_day"] = (
          base_cap_approx + df_cal_month["profit"].cumsum().shift(1).fillna(0)
      )
      df_cal_month["return_pct"] = np.where(
          df_cal_month["cum_before_day"] > 0,
          (df_cal_month["profit"] / df_cal_month["cum_before_day"]) * 100,
          0.0,
      )

      df_cal_month["weekday"] = df_cal_month["date_dt"].dt.weekday
      df_cal_month["week_row"] = df_cal_month.apply(
          lambda row: (row["date_dt"].day + start_date.weekday() - 1) // 7,
          axis=1,
      )


      def make_calendar_text(row):
        d = row["date_dt"].day
        p = row["profit"]
        if p == 0:
          return f"<b>{d}</b><br>-"
        else:
          pct = row["return_pct"]
          return f"<b>{d}</b><br>{p:+.1f}€<br>({pct:+.2f}%)"


      df_cal_month["cell_text"] = df_cal_month.apply(
          make_calendar_text, axis=1
      )
      df_cal_month["z_val"] = df_cal_month["profit"]

      pivot_vals = df_cal_month.pivot_table(
          index="week_row", columns="weekday", values="z_val", fill_value=np.nan
      )
      pivot_text = df_cal_month.pivot_table(
          index="week_row",
          columns="weekday",
          values="cell_text",
          aggfunc="first",
          fill_value="",
      )

      for i in range(7):
        if i not in pivot_vals.columns:
          pivot_vals[i] = np.nan
          pivot_text[i] = ""
      pivot_vals = pivot_vals[sorted(pivot_vals.columns)]
      pivot_text = pivot_text[sorted(pivot_text.columns)]

      pivot_vals.columns = [
          "Lundi",
          "Mardi",
          "Mercredi",
          "Jeudi",
          "Vendredi",
          "Samedi",
          "Dimanche",
      ]
      pivot_text.columns = [
          "Lundi",
          "Mardi",
          "Mercredi",
          "Jeudi",
          "Vendredi",
          "Samedi",
          "Dimanche",
      ]

      fig_hm = go.Figure(
          data=go.Heatmap(
              z=pivot_vals.values,
              x=list(pivot_vals.columns),
              y=[f"Semaine {i+1}" for i in range(len(pivot_vals))],
              text=pivot_text.values,
              texttemplate="%{text}",
              textfont={"size": 13, "color": "white"},
              colorscale=[
                  [0.0, "#C62828"],
                  [0.49, "#E57373"],
                  [0.5, "#30363D"],
                  [0.51, "#81C784"],
                  [1.0, "#2E7D32"],
              ],
              zmid=0,
              hoverinfo="x+y+text",
              xgap=3,
              ygap=3,
          )
      )
     fig_hm.update_layout(
    title=(
        "Calendrier Journalier -"
        f" {month_names.get(sel_month, sel_month)} {sel_year}"
    ),
    xaxis_title="Jours de la semaine",
    yaxis_title="",
    yaxis=dict(autorange="reversed"),
    height=480,
    plot_bgcolor="#161616",
    paper_bgcolor="#0E1117",
)

# On applique les modifications hors du bloc update_layout
fig_hm.update_layout(showlegend=False)
fig_hm.update_coloraxes(showscale=False)  # Enlève la barre de couleur verticale à droite

st.plotly_chart(fig_hm, use_container_width=True)

    elif granularity == "Tous les mois de l'année":
      sel_year = hm_col2.selectbox(
          "Choisir l'année :", available_years, key="hm_sel_year_annual"
      )
      df_filtered_hm = (
          df_cal[df_cal["Annee"] == sel_year].sort_values("date_dt").copy()
      )
      if not df_filtered_hm.empty:
        monthly_aggregates = []
        prev_profits = df_cal[
            df_cal["date_dt"] < pd.Timestamp(sel_year, 1, 1)
        ]["profit"].sum()
        current_running_cap = total_initial_capital + prev_profits
        if current_running_cap <= 0:
          current_running_cap = total_initial_capital

        for m in sorted(df_filtered_hm["Mois"].unique()):
          df_m_data = df_filtered_hm[df_filtered_hm["Mois"] == m]
          m_profit = df_m_data["profit"].sum()
          m_return_pct = (
              (m_profit / current_running_cap) * 100
              if current_running_cap > 0
              else 0.0
          )
          month_names_dict = {
              1: "Jan",
              2: "Fév",
              3: "Mar",
              4: "Avr",
              5: "Mai",
              6: "Juin",
              7: "Juil",
              8: "Août",
              9: "Sep",
              10: "Oct",
              11: "Nov",
              12: "Déc",
          }
          monthly_aggregates.append({
              "Mois": m,
              "MoisNom": month_names_dict.get(m, str(m)),
              "profit": m_profit,
              "return_pct": m_return_pct,
          })
          current_running_cap += m_profit

        df_monthly_bar = pd.DataFrame(monthly_aggregates)
        df_monthly_bar["text_label"] = df_monthly_bar.apply(
            lambda r: f"{r['profit']:+.2f} €<br>({r['return_pct']:+.2f}%)", axis=1
        )

        fig_hm = px.bar(
            df_monthly_bar,
            x="MoisNom",
            y="profit",
            color="profit",
            color_continuous_scale=[
                [0.0, "#C62828"],
                [0.49, "#E57373"],
                [0.5, "#30363D"],
                [0.51, "#81C784"],
                [1.0, "#2E7D32"],
            ],
            color_continuous_midpoint=0,
            title=(
                f"Performance Mensuelle de l'Année {sel_year} (en % du capital"
                " en début de mois)"
            ),
        )
        fig_hm.update_traces(
            text=df_monthly_bar["text_label"], textposition="outside"
        )
        fig_hm.update_layout(
            xaxis_title="Mois", yaxis_title="Profit (€)", height=400
        )
        st.plotly_chart(fig_hm, use_container_width=True)
    else:
      hm_col2.empty()
      df_yearly = df_cal.groupby("Annee")["profit"].sum().reset_index()
      if not df_yearly.empty:
        df_yearly["return_pct"] = (
            df_yearly["profit"] / total_initial_capital
        ) * 100
        df_yearly["text_label"] = df_yearly.apply(
            lambda r: f"{r['profit']:+.2f} €<br>({r['return_pct']:+.2f}%)", axis=1
        )
        fig_hm = px.bar(
            df_yearly,
            x="Annee",
            y="profit",
            color="profit",
            color_continuous_scale=[
                [0.0, "#C62828"],
                [0.49, "#E57373"],
                [0.5, "#30363D"],
                [0.51, "#81C784"],
                [1.0, "#2E7D32"],
            ],
            color_continuous_midpoint=0,
            title="Performance Annuelle Globale (€)",
        )
        fig_hm.update_traces(
            text=df_yearly["text_label"], textposition="outside"
        )
        fig_hm.update_layout(
            xaxis=dict(tickmode="linear", dtick=1),
            xaxis_title="Année",
            yaxis_title="Profit (€)",
            height=400,
        )
        st.plotly_chart(fig_hm, use_container_width=True)

  st.markdown("---")

  # --- 3. PERFORMANCES & STATISTIQUES MENSUELLES ---
  st.markdown("### 📅 Performances & Statistiques Mensuelles")
  df_hist["Annee"] = df_hist["time"].dt.year
  df_hist["Mois"] = df_hist["time"].dt.month
  df_hist["AnneeMois"] = df_hist["time"].dt.strftime("%b %Y")

  df_monthly = (
      df_hist.groupby(["Annee", "Mois", "AnneeMois"])["profit"]
      .sum()
      .reset_index()
  )
  df_monthly = df_monthly.sort_values(["Annee", "Mois"])

  monthly_returns = []
  running_cap = total_initial_capital
  for idx, row in df_monthly.iterrows():
    m_profit = row["profit"]
    m_return_pct = (m_profit / running_cap) * 100 if running_cap > 0 else 0.0
    monthly_returns.append(m_return_pct)
    running_cap += m_profit
  df_monthly["return_pct"] = monthly_returns

  df_monthly["text_profit"] = df_monthly["profit"].apply(
      lambda x: f"<b>{x:,.2f} €</b>".replace(",", " ")
  )
  df_monthly["text_return"] = df_monthly["return_pct"].apply(
      lambda x: f"<b>{x:+.2f}%</b>"
  )

  avg_monthly_profit = (
      df_monthly["profit"].mean() if not df_monthly.empty else 0.0
  )
  avg_monthly_pct = (
      df_monthly["return_pct"].mean() if not df_monthly.empty else 0.0
  )
  median_monthly_profit = (
      df_monthly["profit"].median() if not df_monthly.empty else 0.0
  )
  median_monthly_pct = (
      df_monthly["return_pct"].median() if not df_monthly.empty else 0.0
  )

  col_m1, col_m2 = st.columns(2)
  col_m1.metric(
      "📅 Moyenne Mensuelle",
      f"{avg_monthly_profit:,.2f} €".replace(",", " "),
      f"{avg_monthly_pct:+.2f}%",
  )
  col_m2.metric(
      "📊 Médiane Mensuelle",
      f"{median_monthly_profit:,.2f} €".replace(",", " "),
      f"{median_monthly_pct:+.2f}%",
  )

  fig_col1, fig_col2 = st.columns(2)
  with fig_col1:
    fig_pm = px.bar(
        df_monthly,
        x="AnneeMois",
        y="profit",
        text="text_profit",
        color="profit",
        color_continuous_scale=[
            [0.0, "#C62828"],
            [0.49, "#E57373"],
            [0.5, "#30363D"],
            [0.51, "#81C784"],
            [1.0, "#2E7D32"],
        ],
        color_continuous_midpoint=0,
        title="Profit Mensuel (€)",
    )
    fig_pm.update_traces(textposition="outside", textfont_size=12)
    fig_pm.update_layout(
        xaxis_title="Mois", yaxis_title="Profit (€)", height=380, showlegend=False
    )
    st.plotly_chart(fig_pm, use_container_width=True)

  with fig_col2:
    fig_rm = px.bar(
        df_monthly,
        x="AnneeMois",
        y="return_pct",
        text="text_return",
        color="return_pct",
        color_continuous_scale=[
            [0.0, "#C62828"],
            [0.49, "#E57373"],
            [0.5, "#30363D"],
            [0.51, "#81C784"],
            [1.0, "#2E7D32"],
        ],
        color_continuous_midpoint=0,
        title="Rendement Mensuel (%)",
    )
    fig_rm.update_traces(textposition="outside", textfont_size=12)
    fig_rm.update_layout(
        xaxis_title="Mois",
        yaxis_title="Rendement (%)",
        height=380,
        showlegend=False,
    )
    st.plotly_chart(fig_rm, use_container_width=True)

  st.markdown("---")

  # --- 4. COURBES DE GAIN CUMULÉ & DRAWDOWN ---
  st.markdown("### 📈 Courbe de Gain Cumulé & Évolution du Drawdown")
  chart_col1, chart_col2 = st.columns(2)

  with chart_col1:
    st.markdown("##### Courbe de Gain Cumulé")
    gain_mode = st.radio(
        "Unité (Gain Cumulé) :",
        ["Euros (€)", "Pourcentage (%)"],
        index=1,
        horizontal=True,
        key="gain_curve_mode",
    )
    y_col = (
        "cum_profit" if "Euros" in gain_mode else "cum_profit_pct"
    )
    y_label = "Profit Cumulé (€)" if "Euros" in gain_mode else "Profit Cumulé (%)"
    unit_symbol_gain = "€" if "Euros" in gain_mode else "%"

    fig_gain = go.Figure()
    fig_gain.add_trace(
        go.Scatter(
            x=df_hist["time"],
            y=df_hist[y_col],
            mode="lines",
            name="Gain Cumulé",
            line=dict(color="#00C853", width=2),
            hovertemplate=(
                "<b>%{x|%b %d, %Y}</b><br>Gain: %{y:.2f}"
                f" {unit_symbol_gain}<extra></extra>"
            ),
        )
    )
    fig_gain.update_layout(
        title=dict(text="Profit Cumulé", font=dict(size=13, color="#A0A0A0")),
        xaxis_title="",
        yaxis_title=y_label,
        height=380,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=False, color="#8c939d"),
        yaxis=dict(showgrid=True, gridcolor="#22262b", color="#8c939d"),
        margin=dict(l=10, r=10, t=30, b=10),
    )
    st.plotly_chart(fig_gain, use_container_width=True)

  with chart_col2:
    st.markdown("##### Évolution du Drawdown")
    dd_mode = st.radio(
        "Unité (Drawdown) :",
        ["Euros (€)", "Pourcentage (%)"],
        index=1,
        horizontal=True,
        key="dd_curve_mode",
    )
    y_col_dd = (
        df_hist["drawdown"].abs()
        if "Euros" in dd_mode
        else df_hist["drawdown_pct"]
    )
    y_label_dd = "Drawdown (€)" if "Euros" in dd_mode else "Drawdown (%)"
    unit_symbol_dd = "€" if "Euros" in dd_mode else "%"

    fig_dd = go.Figure()
    fig_dd.add_trace(
        go.Scatter(
            x=df_hist["time"],
            y=y_col_dd,
            mode="lines",
            name="Drawdown",
            line=dict(color="#FF5722", width=1.8),
            fill="tozeroy",
            fillcolor="rgba(255, 87, 34, 0.25)",
            hovertemplate=(
                "<b>%{x|%b %d, %Y}</b><br>Drawdown: %{y:.2f}"
                f" {unit_symbol_dd}<extra></extra>"
            ),
        )
    )
    fig_dd.update_layout(
        title=dict(text="Série de Drawdown", font=dict(size=13, color="#A0A0A0")),
        xaxis_title="",
        yaxis_title=y_label_dd,
        height=380,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=False, color="#8c939d"),
        yaxis=dict(
            autorange="reversed",
            showgrid=True,
            gridcolor="#22262b",
            color="#8c939d",
        ),
        margin=dict(l=10, r=10, t=30, b=10),
    )
    st.plotly_chart(fig_dd, use_container_width=True)

  st.markdown("---")

  # --- 5. HISTORIQUE DÉTAILLÉ DES TRANSACTIONS ---
  st.subheader("📋 Historique Détaillé et Filtré des Trades & Frais")
  min_date_hist = df_hist["time"].min().date()
  max_date_hist = df_hist["time"].max().date()
  today = datetime.date.today()

  col_period, col_custom = st.columns([1, 1.5])
  with col_period:
    selected_period = st.selectbox(
        "📅 Choisir la période (Style MT5) :",
        [
            "Toutes les données",
            "Aujourd'hui",
            "Derniers 7 jours",
            "Dernier mois calendaire",
            "Dernier mois glissant",
            "Dernier trimestre calendaire",
            "Période personnalisée",
        ],
        index=0,
        key="mt5_period_select",
    )

  if selected_period == "Aujourd'hui":
    start_filter = today
    end_filter = today
  elif selected_period == "Derniers 7 jours":
    start_filter = today - datetime.timedelta(days=7)
    end_filter = today
  elif selected_period == "Dernier mois glissant":
    start_filter = today - datetime.timedelta(days=30)
    end_filter = today
  elif selected_period == "Dernier mois calendaire":
    first_day_current_month = today.replace(day=1)
    last_day_last_month = first_day_current_month - datetime.timedelta(days=1)
    first_day_last_month = last_day_last_month.replace(day=1)
    start_filter = first_day_last_month
    end_filter = last_day_last_month
  elif selected_period == "Dernier trimestre calendaire":
    current_quarter = (today.month - 1) // 3 + 1
    if current_quarter == 1:
      last_quarter_year = today.year - 1
      last_quarter_months = (10, 12)
    else:
      last_quarter_year = today.year
      last_quarter_months = (
          (current_quarter - 2) * 3 + 1,
          (current_quarter - 1) * 3,
      )
    start_filter = datetime.date(last_quarter_year, last_quarter_months[0], 1)
    if last_quarter_months[1] in [4, 6, 9, 11]:
      last_day = 30
    elif last_quarter_months[1] == 2:
      last_day = (
          29
          if (
              last_quarter_year % 4 == 0
              and (last_quarter_year % 100 != 0 or last_quarter_year % 400 == 0)
          )
          else 28
      )
    else:
      last_day = 31
    end_filter = datetime.date(
        last_quarter_year, last_quarter_months[1], last_day
    )
  elif selected_period == "Période personnalisée":
    with col_custom:
      c_start, c_end = st.columns(2)
      start_filter = c_start.date_input(
          "Du :",
          value=min_date_hist,
          min_value=min_date_hist,
          max_value=max_date_hist,
          key="custom_start",
      )
      end_filter = c_end.date_input(
          "Au :",
          value=max_date_hist,
          min_value=min_date_hist,
          max_value=max_date_hist,
          key="custom_end",
      )
  else:
    start_filter = min_date_hist
    end_filter = max_date_hist

  df_filtered = df_hist[
      (df_hist["time"].dt.date >= start_filter)
      & (df_hist["time"].dt.date <= end_filter)
  ].copy()

  filtered_raw_profit = (
      df_filtered["raw_profit"].sum()
      if "raw_profit" in df_filtered.columns
      else 0.0
  )
  filtered_swaps = (
      df_filtered["swap"].sum() if "swap" in df_filtered.columns else 0.0
  )
  filtered_commisions = (
      df_filtered["commission"].sum()
      if "commission" in df_filtered.columns
      else 0.0
  )
  filtered_net_profit = (
      df_filtered["profit"].sum() if "profit" in df_filtered.columns else 0.0
  )

  col_f1, col_f2, col_f3, col_f4 = st.columns(4)
  col_f1.metric(
      "💵 Profit Réalisé (Brut)",
      f"{filtered_raw_profit:,.2f} €".replace(",", " "),
  )
  col_f2.metric("📉 Swaps Totaux", f"{filtered_swaps:,.2f} €".replace(",", " "))
  col_f3.metric(
      "💸 Commissions Totales",
      f"{filtered_commisions:,.2f} €".replace(",", " "),
  )
  col_f4.metric(
      "✨ Profit Net (Période)",
      f"{filtered_net_profit:,.2f} €".replace(",", " "),
  )

  st.markdown("<br>", unsafe_allow_html=True)

  display_cols = [
      col
      for col in [
          "login",
          "time",
          "open_time",
          "ticket",
          "symbol",
          "type",
          "volume",
          "price",
          "raw_profit",
          "swap",
          "commission",
          "profit",
      ]
      if col in df_filtered.columns
  ]

  if not df_filtered.empty:
    st.dataframe(
        df_filtered[display_cols].sort_values(by="time", ascending=False),
        use_container_width=True,
    )
  else:
    st.info("Aucun historique de trade valide trouvé pour cette sélection.")

  st.markdown("---")

  # --- 6. STATISTIQUES & RECORDS JOURNALIERS ---
  best_day_eur = 0.0
  worst_day_eur = 0.0
  best_day_pct = 0.0
  worst_day_pct = 0.0
  avg_day_eur = 0.0
  avg_day_pct = 0.0

  if not df_daily.empty:
    df_daily_sorted = df_daily.sort_values("date_only").copy()
    df_daily_sorted["cum_profit_day"] = df_daily_sorted["profit"].cumsum()
    df_daily_sorted["capital_before"] = total_initial_capital + df_daily_sorted[
        "cum_profit_day"
    ].shift(1).fillna(0)
    df_daily_sorted["return_pct"] = (
        df_daily_sorted["profit"] / df_daily_sorted["capital_before"]
    ) * 100

    best_day_eur = df_daily_sorted["profit"].max()
    worst_day_eur = df_daily_sorted["profit"].min()
    best_day_pct = df_daily_sorted["return_pct"].max()
    worst_day_pct = df_daily_sorted["return_pct"].min()
    avg_day_eur = df_daily_sorted["profit"].mean()
    avg_day_pct = df_daily_sorted["return_pct"].mean()

  st.markdown("### 🏆 Statistiques & Records Journaliers")
  col_j1, col_j2, col_j3 = st.columns(3)
  col_j1.metric(
      "🔥 Meilleure Journée",
      f"{best_day_eur:,.2f} €".replace(",", " "),
      f"+{best_day_pct:.2f}%",
  )
  col_j2.metric(
      "💧 Pire Journée",
      f"{worst_day_eur:,.2f} €".replace(",", " "),
      f"{worst_day_pct:.2f}%",
  )
  col_j3.metric(
      "⚖️ Moyenne Journalière",
      f"{avg_day_eur:,.2f} €".replace(",", " "),
      f"{avg_day_pct:+.2f}%",
  )

  st.markdown("---")

  # --- 7. INDICATEURS & RATIOS QUANTITATIFS AVANCÉS ---


  def calculate_advanced_metrics(df, initial_cap):
    default_metrics = {
        "Total Trades": 0,
        "Win Rate (%)": "0.00%",
        "Profit Factor": "0.00",
        "Expectancy (€)": "0.00 €",
        "Risk/Reward": "0.00",
        "Max Drawdown (€)": "0.00 €",
        "Max Drawdown (%)": "0.00%",
        "Drawdown Moyen (€)": "0.00 €",
        "Drawdown Moyen (%)": "0.00%",
        "Recovery Factor": "0.00",
        "Plus Haut (Profit) (€)": "0.00 €",
        "Plus Haut (Solde) (€)": f"{initial_cap:,.2f} €",
        "Max Gains d'Affilée": 0,
        "Max Pertes d'Affilée": 0,
        "Ratio Sharpe": "0.00",
        "Ratio Sortino": "0.00",
        "Gain Moyen": "0.00 €",
        "Perte Moyenne": "0.00 €",
    }

    if df.empty or "profit" not in df.columns:
      return default_metrics

    profits = df["profit"]
    total_trades = len(profits)
    winning_trades = profits[profits > 0]
    losing_trades = profits[profits < 0]

    win_rate = (
        (len(winning_trades) / total_trades * 100) if total_trades > 0 else 0
    )
    gross_profit = winning_trades.sum()
    gross_loss = abs(losing_trades.sum())

    profit_factor = (
        (gross_profit / gross_loss)
        if gross_loss > 0
        else (gross_profit if gross_profit > 0 else 0)
    )

    avg_win = winning_trades.mean() if len(winning_trades) > 0 else 0
    avg_loss = abs(losing_trades.mean()) if len(losing_trades) > 0 else 0
    risk_reward = (avg_win / avg_loss) if avg_loss > 0 else 0
    expectancy = (win_rate / 100 * avg_win) - ((1 - win_rate / 100) * avg_loss)

    max_drawdown_eur = df["drawdown"].min() if not df["drawdown"].empty else 0
    max_drawdown_pct = (
        df["drawdown_pct"].max() if not df["drawdown_pct"].empty else 0
    )
    avg_drawdown_eur = (
        df["drawdown"][df["drawdown"] < 0].mean()
        if not df["drawdown"][df["drawdown"] < 0].empty
        else 0
    )
    avg_drawdown_pct = (
        df["drawdown_pct"][df["drawdown_pct"] > 0].mean()
        if not df["drawdown_pct"][df["drawdown_pct"] > 0].empty
        else 0
    )

    peak_profit = df["cum_profit"].max() if not df["cum_profit"].empty else 0
    peak_balance = initial_cap + peak_profit
    net_profit_val = profits.sum()
    recovery_factor = (
        (net_profit_val / abs(max_drawdown_eur)) if max_drawdown_eur < 0 else 0.0
    )

    is_win = profits > 0
    is_loss = profits < 0
    max_consec_wins = (
        is_win.astype(int)
        .groupby((is_win != is_win.shift()).cumsum())
        .sum()
        .max()
        if total_trades > 0
        else 0
    )
    max_consec_losses = (
        is_loss.astype(int)
        .groupby((is_loss != is_loss.shift()).cumsum())
        .sum()
        .max()
        if total_trades > 0
        else 0
    )

    returns = profits
    mean_ret = returns.mean()
    std_ret = returns.std()
    downside_std = returns[returns < 0].std()

    sharpe_ratio = (
        (mean_ret / std_ret * np.sqrt(total_trades))
        if pd.notna(std_ret) and std_ret > 0
        else 0.0
    )
    sortino_ratio = (
        (mean_ret / downside_std * np.sqrt(total_trades))
        if pd.notna(downside_std) and downside_std > 0
        else 0.0
    )

    return {
        "Total Trades": total_trades,
        "Win Rate (%)": f"{win_rate:.2f}%",
        "Profit Factor": f"{profit_factor:.2f}",
        "Expectancy (€)": f"{expectancy:.2f} €".replace(",", " "),
        "Risk/Reward": f"{risk_reward:.2f}",
        "Max Drawdown (€)": f"{max_drawdown_eur:.2f} €".replace(",", " "),
        "Max Drawdown (%)": f"{max_drawdown_pct:.2f}%",
        "Drawdown Moyen (€)": f"{avg_drawdown_eur:.2f} €".replace(",", " "),
        "Drawdown Moyen (%)": f"{avg_drawdown_pct:.2f}%",
        "Recovery Factor": f"{recovery_factor:.2f}",
        "Plus Haut (Profit) (€)": f"{peak_profit:.2f} €".replace(",", " "),
        "Plus Haut (Solde) (€)": f"{peak_balance:,.2f} €",
        "Max Gains d'Affilée": int(max_consec_wins),
        "Max Pertes d'Affilée": int(max_consec_losses),
        "Ratio Sharpe": f"{sharpe_ratio:.2f}",
        "Ratio Sortino": f"{sortino_ratio:.2f}",
        "Gain Moyen": f"{avg_win:.2f} €".replace(",", " "),
        "Perte Moyenne": f"{avg_loss:.2f} €".replace(",", " "),
    }


  metrics = calculate_advanced_metrics(df_hist, total_initial_capital)

  st.markdown("### 📊 Indicateurs & Ratios Quantitatifs Avancés")
  col1, col2, col3, col4, col5, col6 = st.columns(6)
  col1.metric("Trades Clôturés", metrics["Total Trades"])
  col2.metric("🎯 Win Rate Réel", metrics["Win Rate (%)"])
  col3.metric("⚖️ Risk / Reward", metrics["Risk/Reward"])
  col4.metric("Profit Factor", metrics["Profit Factor"])
  col5.metric("Recovery Factor", metrics["Recovery Factor"])
  col6.metric("Ratio Sharpe", metrics["Ratio Sharpe"])

  col7, col8, col9, col10, col11 = st.columns(5)
  with col7:
    st.markdown(
        f"""
            <div style="background-color: transparent; padding: 4px 0px;">
                <div style="font-size: 14px; color: #959595; margin-bottom: 2px;">Max DD (€ / %)</div>
                <div style="font-size: 20px; font-weight: 600; color: #FFFFFF;">
                    {metrics['Max Drawdown (€)']} <span style="font-size: 13px; color: #A0A0A0; font-weight: normal;">({metrics['Max Drawdown (%)']})</span>
                </div>
            </div>
            """,
        unsafe_allow_html=True,
    )
  with col8:
    st.markdown(
        f"""
            <div style="background-color: transparent; padding: 4px 0px;">
                <div style="font-size: 14px; color: #959595; margin-bottom: 2px;">DD Moyen (€ / %)</div>
                <div style="font-size: 20px; font-weight: 600; color: #FFFFFF;">
                    {metrics['Drawdown Moyen (€)']} <span style="font-size: 13px; color: #A0A0A0; font-weight: normal;">({metrics['Drawdown Moyen (%)']})</span>
                </div>
            </div>
            """,
        unsafe_allow_html=True,
    )
  col9.metric("Peak Solde Historique", metrics["Plus Haut (Solde) (€)"])
  col10.metric("Ratio Sortino", metrics["Ratio Sortino"])
  col11.metric("Espérance / Trade", metrics["Expectancy (€)"])

  col12, col13, col14, col15, col16 = st.columns(5)
  col12.metric("Peak Profit Net", metrics["Plus Haut (Profit) (€)"])
  col13.metric("Gain Moyen", metrics["Gain Moyen"])
  col14.metric("Perte Moyenne", metrics["Perte Moyenne"])
  col15.metric("Max Gains d'Affilée", metrics["Max Gains d'Affilée"])
  col16.metric("Max Pertes d'Affilée", metrics["Max Pertes d'Affilée"])

  st.markdown("---")

  # --- 8. SAISONNALITÉ DES HEURES ET DES JOURS ---
  render_temporal_analysis(df_hist)

  st.markdown("---")

  # --- 9. CORRÉLATION & DÉPENDANCE INTER-COMPTES ---
  if not df_global.empty and len(df_global["login"].unique()) > 1:
    st.markdown("### 🔗 Corrélation & Dépendance Inter-Comptes")
    df_global["date_only"] = df_global["time"].dt.date
    df_daily_pivot = (
        df_global.groupby(["date_only", "login"])["profit"]
        .sum()
        .unstack(fill_value=0.0)
    )
    corr_matrix = df_daily_pivot.corr()

    upper_triangle = np.triu(np.ones(corr_matrix.shape), k=1).astype(bool)
    unique_correlations = corr_matrix.values[upper_triangle]
    avg_portfolio_corr = (
        unique_correlations.mean() if len(unique_correlations) > 0 else 0.0
    )

    col_corr1, col_corr2 = st.columns([1.2, 1])
    with col_corr1:
      labels_str = [f"Compte {col}" for col in corr_matrix.columns]
      fig_corr = px.imshow(
          corr_matrix.values,
          x=labels_str,
          y=labels_str,
          text_auto=".2f",
          color_continuous_scale="RdBu_r",
          zmin=-1,
          zmax=1,
          title="Matrice de Corrélation des Gains Journaliers (Pearson r)",
      )
      fig_corr.update_layout(height=400)
      st.plotly_chart(fig_corr, use_container_width=True)

    with col_corr2:
      st.metric(
          "🌐 Corrélation Moyenne du Portefeuille",
          f"{avg_portfolio_corr:+.2f}",
          f"{avg_portfolio_corr * 100:+.1f}%",
      )
      st.markdown("##### 💡 Interprétation des Ratios")
      st.write("""
              * **+0.80 à +1.00 :** Corrélation forte. Stratégies quasi identiques.
              * **-0.20 à +0.20 :** Indépendance élevée. Excellente diversification.
              * **-1.00 à -0.80 :** Stratégies opposées (effet couverture).
              """)

    st.markdown("---")

# --- 10. SIMULATION DE MONTE-CARLO & PROJECTIONS DE RISQUE ---
st.markdown("### 🎲 Simulation de Monte-Carlo & Projections de Risque")

with st.expander("⚙️ Paramètres de la Simulation Monte-Carlo", expanded=False):
  col_mc1, col_mc2, col_mc3, col_mc4 = st.columns(4)

  sim_horizon_type = col_mc1.radio(
      "Horizon de projection :",
      ["Nombre de trades futurs (N)", "Date cible future"],
      index=1,
      key="mc_type",
  )

  today_dt = datetime.date.today()
  latest_trade_date = (
      df_hist["time"].max().date() if not df_hist.empty else today_dt
  )
  base_date = max(today_dt, latest_trade_date)

  if sim_horizon_type == "Nombre de trades futurs (N)":
    horizon_val = col_mc2.number_input(
        "Nombre de trades (N) :",
        min_value=20,
        max_value=2000,
        value=200,
        step=50,
    )
    step_label = "Trade"
  else:
    default_target_date = datetime.date(2027, 3, 18)
    target_date = col_mc2.date_input(
        "Choisir la date cible :",
        value=default_target_date,
        min_value=base_date + datetime.timedelta(days=1),
        key="mc_target_date",
    )

    horizon_val = int(
        np.busday_count(
            base_date.strftime("%Y-%m-%d"), target_date.strftime("%Y-%m-%d")
        )
    )
    horizon_val = max(1, horizon_val)

    st.caption(
        f"🗓️ Projection sur **{horizon_val} jours ouvrés** (hors week-ends)"
        f" jusqu'au {target_date.strftime('%d/%m/%Y')}."
    )
    step_label = "Jour"

  num_simulations = col_mc3.slider(
      "Nombre de simulations :",
      min_value=500,
      max_value=5000,
      value=5000,
      step=500,
  )
  dd_target_pct = col_mc4.number_input(
      "Seuil de Drawdown à tester (%) :",
      min_value=1.0,
      max_value=80.0,
      value=15.0,
      step=1.0,
  )

  calc_mode = st.radio(
      "Modèle de gestion du capital :",
      [
          "Pourcentage / Compound (Taille de position dynamique)",
          "Euros Fixes (Taille de lot constante)",
      ],
      horizontal=True,
      key="mc_mode",
  )

np.random.seed(42)
start_capital = current_balance

accounts_to_sim = (
    active_accounts
    if selected_account == "Tous les comptes"
    else [acc for acc in active_accounts if str(acc["login"]) == selected_account]
)

all_account_trajectories = np.zeros((num_simulations, horizon_val + 1))
valid_simulation = False

for acc in accounts_to_sim:
  acc_id = int(acc["login"])
  acc_balance = float(acc.get("balance", 0.0))
  acc_init_cap = ACCOUNTS_CONFIG.get(acc_id, {}).get("initial_balance", 1000.0)

  df_acc = (
      df_global[df_global["login"] == acc_id].copy()
      if not df_global.empty
      else pd.DataFrame()
  )

  if df_acc.empty or acc_balance <= 0:
    all_account_trajectories += acc_balance
    continue

  if sim_horizon_type == "Nombre de trades futurs (N)":
    df_acc["cap_before"] = (
        acc_init_cap + df_acc["profit"].cumsum().shift(1).fillna(0)
    )
    df_acc["cap_before"] = np.maximum(df_acc["cap_before"], 1.0)
    sample_pct = (df_acc["profit"] / df_acc["cap_before"]).values
    sample_eur = df_acc["profit"].values
  else:
    df_acc["date_only"] = df_acc["time"].dt.date
    df_acc_daily = df_acc.groupby("date_only")["profit"].sum().reset_index()
    df_acc_daily["cum_profit"] = df_acc_daily["profit"].cumsum()
    df_acc_daily["cap_before"] = (
        acc_init_cap + df_acc_daily["cum_profit"].shift(1).fillna(0)
    )
    df_acc_daily["cap_before"] = np.maximum(df_acc_daily["cap_before"], 1.0)
    df_acc_daily["return_pct"] = (
        df_acc_daily["profit"] / df_acc_daily["cap_before"]
    )
    sample_pct = df_acc_daily["return_pct"].values
    sample_eur = df_acc_daily["profit"].values

  if len(sample_pct) > 2:
    valid_simulation = True
    if "Compound" in calc_mode:
      draws_pct = np.random.choice(
          sample_pct, size=(num_simulations, horizon_val), replace=True
      )
      factors = 1.0 + draws_pct
      cum_factors = np.cumprod(factors, axis=1)
      acc_trajectories = np.hstack([
          np.full((num_simulations, 1), acc_balance),
          acc_balance * cum_factors,
      ])
    else:
      draws_eur = np.random.choice(
          sample_eur, size=(num_simulations, horizon_val), replace=True
      )
      cum_draws = np.cumsum(draws_eur, axis=1)
      acc_trajectories = np.hstack([
          np.full((num_simulations, 1), acc_balance),
          acc_balance + cum_draws,
      ])
  else:
    acc_trajectories = np.full((num_simulations, horizon_val + 1), acc_balance)

  all_account_trajectories += acc_trajectories

trajectories = all_account_trajectories

if valid_simulation:
  equities_p5 = np.percentile(trajectories, 5, axis=0)
  equities_p50 = np.percentile(trajectories, 50, axis=0)
  equities_p95 = np.percentile(trajectories, 95, axis=0)

  final_equities = trajectories[:, -1]
  p1_final = np.percentile(final_equities, 1)
  p5_final = np.percentile(final_equities, 5)
  p50_final = np.percentile(final_equities, 50)

  median_profit_eur = p50_final - start_capital
  median_return_pct = (
      ((p50_final - start_capital) / start_capital) * 100
      if start_capital > 0
      else 0.0
  )

  step_profits = np.diff(trajectories, axis=1)
  wins_mask = step_profits > 0
  losses_mask = step_profits < 0

  win_counts = np.sum(wins_mask, axis=1)
  loss_counts = np.sum(losses_mask, axis=1)

  sim_win_rates = (win_counts / horizon_val) * 100
  median_sim_win_rate = np.median(sim_win_rates)

  sum_wins = np.sum(np.maximum(step_profits, 0), axis=1)
  sum_losses = np.sum(np.abs(np.minimum(step_profits, 0)), axis=1)

  avg_wins = np.divide(
      sum_wins,
      win_counts,
      out=np.zeros_like(sum_wins, dtype=float),
      where=win_counts > 0,
  )
  avg_losses = np.divide(
      sum_losses,
      loss_counts,
      out=np.ones_like(sum_losses, dtype=float),
      where=loss_counts > 0,
  )

  sim_rr_ratios = np.divide(
      avg_wins,
      avg_losses,
      out=np.zeros_like(avg_wins, dtype=float),
      where=avg_losses > 0,
  )
  median_sim_rr = np.median(sim_rr_ratios)

  var_95_eur = max(0.0, start_capital - p5_final)
  var_99_eur = max(0.0, start_capital - p1_final)
  var_95_pct = (var_95_eur / start_capital) * 100 if start_capital > 0 else 0.0
  var_99_pct = (var_99_eur / start_capital) * 100 if start_capital > 0 else 0.0

  running_peaks = np.maximum.accumulate(trajectories, axis=1)
  drawdowns_eur = trajectories - running_peaks
  drawdowns_pct = (abs(drawdowns_eur) / np.maximum(running_peaks, 1.0)) * 100
  max_dd_per_sim = np.max(drawdowns_pct, axis=1)

  prob_dd_exceeded = (
      np.sum(max_dd_per_sim >= dd_target_pct) / num_simulations
  ) * 100

  median_delta_str = (
      f"{median_profit_eur:+,.2f} €"
      f" ({median_return_pct:+.2f}%)".replace(",", " ")
  )

  col_mcm1, col_mcm2, col_mcm3, col_mcm4 = st.columns(4)
  col_mcm1.metric(
      "💵 Capital de Base", f"{start_capital:,.2f} €".replace(",", " ")
  )
  col_mcm2.metric(
      "🎯 Capital & Profit Médian",
      f"{p50_final:,.2f} €".replace(",", " "),
      median_delta_str,
  )
  col_mcm3.metric(
      "🛡️ Capital Résiduel (VaR 95% - P5)",
      f"{p5_final:,.2f} €".replace(",", " "),
      f"-{var_95_eur:,.2f} € (-{var_95_pct:.2f}%)",
  )
  col_mcm4.metric(
      "🚨 Capital Résiduel (VaR 99% - P1)",
      f"{p1_final:,.2f} €".replace(",", " "),
      f"-{var_99_eur:,.2f} € (-{var_99_pct:.2f}%)",
  )

  col_mcm5, col_mcm6, col_mcm7 = st.columns(3)
  col_mcm5.metric(
      f"🎯 Win Rate Projeté ({step_label})", f"{median_sim_win_rate:.2f}%"
  )
  col_mcm6.metric(
      f"⚖️ Risk / Reward Projeté ({step_label})", f"{median_sim_rr:.2f}"
  )
  col_mcm7.metric(
      f"⚠️ Risque DD > {dd_target_pct:.0f}%", f"{prob_dd_exceeded:.1f}%"
  )

  steps = np.arange(0, horizon_val + 1)
  fig_mc = go.Figure()

  sample_size = min(80, num_simulations)
  for i in range(sample_size):
    fig_mc.add_trace(
        go.Scatter(
            x=steps,
            y=trajectories[i],
            mode="lines",
            line=dict(width=0.5, color="rgba(150, 150, 150, 0.15)"),
            showlegend=False,
            hoverinfo="skip",
        )
    )

  fig_mc.add_trace(
      go.Scatter(
          x=steps,
          y=equities_p95,
          mode="lines",
          name="Optimiste (Percentile 95%)",
          line=dict(color="#2E7D32", width=2.5),
      )
  )
  fig_mc.add_trace(
      go.Scatter(
          x=steps,
          y=equities_p50,
          mode="lines",
          name="Médian (Percentile 50%)",
          line=dict(color="#00B0FF", width=2.5),
      )
  )
  fig_mc.add_trace(
      go.Scatter(
          x=steps,
          y=equities_p5,
          mode="lines",
          name="Pessimiste (Percentile 5%)",
          line=dict(color="#C62828", width=2.5),
      )
  )

  fig_mc.update_layout(
      title=(
          f"Cône de Probabilité d'Équité ({num_simulations} simulations sur"
          f" {horizon_val} {step_label}s - Mode: {calc_mode.split(' ')[0]})"
      ),
      xaxis_title=f"Nombre de {step_label}s futurs",
      yaxis_title="Capital (€)",
      height=450,
      hovermode="x unified",
  )
  st.plotly_chart(fig_mc, use_container_width=True)
else:
  st.info("Historique insuffisant pour exécuter la simulation de Monte-Carlo.")

# ===================================================================
# MODULE : EXPORT DE RAPPORTS (CSV, EXCEL, HTML, PDF)
# ===================================================================
st.markdown("---")
st.markdown("### 📥 Module d'Export de Rapports Professionnels")

col_exp1, col_exp2 = st.columns(2)
with col_exp1:
  export_scope = st.radio(
      "Sélectionner le périmètre des données à exporter :",
      ["Historique Filtré (Actuel)", "Historique Global"],
      key="export_scope_radio",
  )

df_to_export = (
    df_filtered if export_scope == "Historique Filtré (Actuel)" else df_hist
)

if df_to_export.empty:
  st.warning("Aucune donnée disponible pour l'exportation.")
else:
  col_b1, col_b2, col_b3, col_b4 = st.columns(4)

  # 1. EXPORT CSV
  csv_data = df_to_export.to_csv(index=False).encode("utf-8")
  col_b1.download_button(
      label="📄 Exporter en CSV",
      data=csv_data,
      file_name="rapport_trading_mt5.csv",
      mime="text/csv",
      use_container_width=True,
  )

  # 2. EXPORT EXCEL
  excel_buffer = io.BytesIO()
  with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
    df_to_export.to_excel(writer, index=False, sheet_name="Trades")
  excel_data = excel_buffer.getvalue()
  col_b2.download_button(
      label="📊 Exporter en Excel",
      data=excel_data,
      file_name="rapport_trading_mt5.xlsx",
      mime=(
          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
      ),
      use_container_width=True,
  )

  # 3. EXPORT HTML STYLISÉ
  html_report = f"""
    <html>
        <head>
            <title>Rapport de Trading MT5</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 30px; background-color: #f8f9fa; color: #333; }}
                h1 {{ color: #007BFF; border-bottom: 2px solid #007BFF; padding-bottom: 10px; }}
                .summary-box {{ background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }}
                table {{ border-collapse: collapse; width: 100%; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                th, td {{ border: 1px solid #dee2e6; padding: 10px 12px; text-align: left; font-size: 13px; }}
                th {{ background-color: #007BFF; color: white; }}
                tr:nth-child(even) {{ background-color: #f1f3f5; }}
            </style>
        </head>
        <body>
            <h1>Rapport d'Analyse - Dashboard MT5</h1>
            <div class="summary-box">
                <p><b>Date d'édition :</b> {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p><b>Compte(s) analysé(s) :</b> {selected_account}</p>
                <p><b>Capital Initial :</b> {total_initial_capital:,.2f} EUR</p>
                <p><b>Solde Actuel :</b> {current_balance:,.2f} EUR</p>
                <p><b>Profit Net Réalisé :</b> {real_net_profit:,.2f} EUR</p>
            </div>
            <h2>Historique Détaillé des Transactions</h2>
            {df_to_export.to_html(index=False, classes='table')}
        </body>
    </html>
    """
  col_b3.download_button(
      label="🌐 Exporter en HTML",
      data=html_report.encode("utf-8"),
      file_name="rapport_trading_mt5.html",
      mime="text/html",
      use_container_width=True,
  )

  # 4. EXPORT PDF NATIF (Propre & Clean via fpdf2)
  try:
    from fpdf import FPDF

    class CleanPDF(FPDF):

      def header(self):
        self.set_font("helvetica", "B", 14)
        self.set_text_color(0, 123, 255)
        self.cell(
            0, 10, "Rapport d'Analyse - Dashboard Trading MT5", 0, 1, "C"
        )
        self.set_font("helvetica", "I", 9)
        self.set_text_color(100, 100, 100)
        self.cell(
            0,
            5,
            (
                "Généré le :"
                f" {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            ),
            0,
            1,
            "C",
        )
        self.ln(5)

      def footer(self):
        self.set_y(-15)
        self.set_font("helvetica", "I", 8)
        self.set_text_color(150, 150, 150)
        self.cell(
            0, 10, f"Page {self.page_no()}", 0, 0, "C"
        )

    pdf = CleanPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # En-tête des métriques globales dans le PDF
    pdf.set_font("helvetica", "B", 11)
    pdf.set_text_color(50, 50, 50)
    pdf.cell(0, 7, f"Compte(s) analysé(s) : {selected_account}", 0, 1)

    pdf.set_font("helvetica", "", 10)
    pdf.cell(0, 6, f"Capital Initial : {total_initial_capital:,.2f} EUR", 0, 1)
    pdf.cell(0, 6, f"Solde Actuel : {current_balance:,.2f} EUR", 0, 1)
    pdf.cell(0, 6, f"Profit Net Réalisé : {real_net_profit:,.2f} EUR", 0, 1)
    pdf.ln(5)

    # Tableau des transactions (limité aux 30 plus récentes pour la propreté de la mise en page)
    pdf.set_font("helvetica", "B", 11)
    pdf.cell(0, 7, "Aperçu des dernières transactions (30 max)", 0, 1)
    pdf.set_font("helvetica", "B", 8)
    pdf.set_fill_color(0, 123, 255)
    pdf.set_text_color(255, 255, 255)

    headers = ["Ticket", "Date", "Symbole", "Type", "Lots", "Profit"]
    widths = [25, 38, 25, 22, 20, 35]

    for i, h in enumerate(headers):
      pdf.cell(widths[i], 6, h, 1, 0, "C", True)
    pdf.ln()

    pdf.set_font("helvetica", "", 8)
    pdf.set_text_color(50, 50, 50)

    for _, row in df_to_export.head(30).iterrows():
      t_str = str(row.get("ticket", ""))
      d_str = (
          str(row.get("time"))[:16] if pd.notna(row.get("time")) else ""
      )
      s_str = str(row.get("symbol", ""))
      type_str = str(row.get("type", ""))
      vol_str = f"{float(row.get('volume', 0)):.2f}"
      prof_str = f"{float(row.get('profit', 0)):.2f} EUR"

      pdf.cell(widths[0], 5, t_str, 1, 0, "C")
      pdf.cell(widths[1], 5, d_str, 1, 0, "C")
      pdf.cell(widths[2], 5, s_str, 1, 0, "C")
      pdf.cell(widths[3], 5, type_str, 1, 0, "C")
      pdf.cell(widths[4], 5, vol_str, 1, 0, "C")
      pdf.cell(widths[5], 5, prof_str, 1, 0, "C")
      pdf.ln()

    pdf_data = bytes(pdf.output())

    col_b4.download_button(
        label="📑 Exporter en PDF",
        data=pdf_data,
        file_name="rapport_trading_mt5.pdf",
        mime="application/pdf",
        use_container_width=True,
    )
  except ImportError:
    col_b4.warning("Installez 'fpdf2' (`pip install fpdf2`) pour activer le PDF.")
    import urllib.parse

st.markdown("### 📤 Partager le rapport")

# Message pré-rempli pour le partage
message_partage = "Salut ! Je te partage mon rapport de trading et mes simulations issues de mon tableau de bord Streamlit."
message_encode = urllib.parse.quote(message_partage)

# Liens universels de partage
url_whatsapp = f"https://wa.me/?text={message_encode}"
url_email = f"mailto:?subject=Rapport%20de%20Trading&body={message_encode}"

# Affichage des boutons de partage en colonnes
col_s1, col_s2 = st.columns(2)

with col_s1:
    st.markdown(
        f'<a href="{url_whatsapp}" target="_blank"><button style="width:100%; background-color:#25D366; color:white; border:none; padding:10px; border-radius:5px; font-weight:bold; cursor:pointer;">💬 Partager sur WhatsApp</button></a>',
        unsafe_allow_html=True
    )

with col_s2:
    st.markdown(
        f'<a href="{url_email}" target="_blank"><button style="width:100%; background-color:#0078D4; color:white; border:none; padding:10px; border-radius:5px; font-weight:bold; cursor:pointer;">✉️ Envoyer par Email</button></a>',
        unsafe_allow_html=True
    )