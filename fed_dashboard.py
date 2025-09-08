import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from plotly.subplots import make_subplots
import requests

# Set up the page
st.set_page_config(page_title="Fed Balance Sheet Dashboard", layout="wide")

# Title and description
st.title("Federal Reserve Balance Sheet Dashboard")
st.markdown("""
This dashboard visualizes key components of the Federal Reserve's balance sheet based on the H.4.1 report published weekly.
Data is retrieved from the FRED API (Federal Reserve Economic Data).
""")

# Educational expander at the top
with st.expander("📚 Quick Guide: Understanding the Fed's Balance Sheet", expanded=False):
    st.markdown("""
    **What is the Fed's Balance Sheet?**
    - The Fed's balance sheet shows all the assets it owns and liabilities it owes
    - **Assets**: Mostly Treasury bonds and Mortgage-Backed Securities (MBS) the Fed has purchased
    - **Liabilities**: Mostly bank reserves and currency in circulation
    
    **Why It Matters:**
    - 🎯 **Expanding balance sheet** = More money in economy = Lower interest rates = Good for stocks
    - 🎯 **Shrinking balance sheet** = Less money in economy = Higher interest rates = Can be bad for stocks
    - 🎯 **Stress indicators** show where financial markets are struggling
    """)

# Sidebar controls
st.sidebar.header("Dashboard Controls")
api_key = st.sidebar.text_input("FRED API Key", type="password", 
                               help="Get your API key from https://research.stlouisfed.org/docs/api/api_key.html")

if not api_key or api_key.strip() == "":
    st.warning("🔑 Please enter your FRED API key in the sidebar to load data")
    st.stop()

end_date = datetime.now()
start_date = st.sidebar.date_input("Start Date", value=end_date - timedelta(days=365*10), max_value=end_date)

# FRED series mapping
FRED_SERIES = {
    "Total Assets": "WALCL",
    "Treasury Securities": "TREAST",
    "Mortgage-Backed Securities": "WSHOMCB",
    "Bank Reserves": "WRBWFRBL",
    "Reverse Repo Foreign": "WLRRAFOIAL",
    "Central Bank Liquidity Swaps": "SWPT",
    "Loans": "WLCFLL",
    "Securities in Custody": "WFCDA",
    "Repo Operations": "WORAL",
    "Other Assets": "WAOAL",
}

st.sidebar.markdown("**Select Components to Display:**")
selected_assets = st.sidebar.multiselect(
    "Balance Sheet Components",
    list(FRED_SERIES.keys()),
    default=["Total Assets", "Treasury Securities", "Mortgage-Backed Securities", "Bank Reserves", 
             "Reverse Repo Foreign", "Central Bank Liquidity Swaps", "Loans", "Securities in Custody"]
)

# Fetch FRED data
def fetch_fred_data(series_id, api_key, start_date):
    url = f"https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "observation_start": start_date.strftime("%Y-%m-%d"),
        "frequency": "w",
        "units": "lin"
    }
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        observations = data.get('observations', [])
        if not observations:
            return None
        df = pd.DataFrame(observations)
        df['value'] = pd.to_numeric(df['value'], errors='coerce')
        df['date'] = pd.to_datetime(df['date'])
        df = df.dropna(subset=['value'])
        if len(df) == 0:
            return None
        return df[['date', 'value']].rename(columns={'value': series_id})
    except:
        return None

with st.spinner("Fetching data from FRED..."):
    all_data = []
    successful_fetches = 0
    for asset_name in selected_assets:
        series_id = FRED_SERIES[asset_name]
        df = fetch_fred_data(series_id, api_key, start_date)
        if df is not None and not df.empty:
            all_data.append(df)
            successful_fetches += 1
        else:
            st.warning(f"Could not fetch data for {asset_name} (series: {series_id})")
    if successful_fetches == 0:
        st.error("❌ Could not fetch any data. Please check your API key and try again.")
        st.stop()
    fed_data = all_data[0]
    for df in all_data[1:]:
        fed_data = pd.merge(fed_data, df, on='date', how='outer')
    fed_data = fed_data.sort_values('date').ffill()
    display_data = fed_data.copy()
    for col in display_data.columns:
        if col != 'date':
            display_data[col] = display_data[col] / 1000
    reverse_series_mapping = {v: k for k, v in FRED_SERIES.items()}
    display_data = display_data.rename(columns=reverse_series_mapping)

st.success(f"✅ Successfully loaded data for {successful_fetches} out of {len(selected_assets)} selected series")

# ✅ Highlight periods (COVID, SVB, Liberation Day)
highlight_periods = [
    {"name": "COVID-19", "start": "2020-03-01", "end": "2020-06-30", "color": "rgba(255,0,0,0.1)"},
    {"name": "SVB Collapse", "start": "2023-03-01", "end": "2023-04-15", "color": "rgba(0,0,255,0.1)"},
    {"name": "Liberation Day 2025", "start": "2025-05-01", "end": "2025-05-15", "color": "rgba(0,255,0,0.1)"}
]

def add_highlight_shapes(fig, periods):
    for period in periods:
        fig.add_vrect(
            x0=period["start"], x1=period["end"],
            fillcolor=period["color"], opacity=0.3,
            layer="below", line_width=0,
            annotation_text=period["name"], annotation_position="top left"
        )
    return fig

# ✅ Main chart
fig = go.Figure()
for asset in selected_assets:
    if asset in display_data.columns:
        fig.add_trace(go.Scatter(
            x=display_data['date'], y=display_data[asset],
            name=asset, mode='lines',
            hovertemplate='<b>%{x}</b><br>%{y:,.0f} billion<extra></extra>'
        ))
fig = add_highlight_shapes(fig, highlight_periods)
fig.update_layout(height=500, title="Federal Reserve Balance Sheet Components",
                  xaxis_title="Date", yaxis_title="Amount (Billions of USD)",
                  hovermode='x unified', legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
st.plotly_chart(fig, use_container_width=True)

# ✅ Tabs
tab1, tab2, tab3, tab4 = st.tabs(["📊 Composition", "📈 Growth Rates", "⚡ Stress Indicators", "🌍 Foreign Sector"])

# Composition chart
with tab1:
    if 'Total Assets' in display_data.columns:
        comp_data = display_data.copy()
        for col in comp_data.columns:
            if col != 'date' and col != 'Total Assets':
                comp_data[f'{col}_pct'] = (comp_data[col] / comp_data['Total Assets']) * 100
        comp_cols = [col for col in comp_data.columns if '_pct' in col]
        if comp_cols:
            fig_comp = px.area(comp_data, x='date', y=comp_cols, title="Balance Sheet Composition (%)")
            fig_comp = add_highlight_shapes(fig_comp, highlight_periods)
            st.plotly_chart(fig_comp, use_container_width=True)
        else:
            st.warning("No composition data available")

# Growth chart
with tab2:
    growth_data = display_data.copy()
    for col in growth_data.columns:
        if col != 'date':
            growth_data[f'{col}_weekly_growth'] = growth_data[col].pct_change() * 100
            growth_data[f'{col}_annual_growth'] = growth_data[col].pct_change(52) * 100
    available_assets = [asset for asset in selected_assets if asset in display_data.columns]
    if available_assets:
        growth_col = st.selectbox("Select series for growth analysis", available_assets)
        fig_growth = make_subplots(specs=[[{"secondary_y": False}]])
        fig_growth.add_trace(go.Scatter(x=growth_data['date'], y=growth_data[f'{growth_col}_weekly_growth'],
                                        name="Weekly Growth (%)", line=dict(color='blue')))
        fig_growth.add_trace(go.Scatter(x=growth_data['date'], y=growth_data[f'{growth_col}_annual_growth'],
                                        name="Annual Growth (%)", line=dict(color='red')))
        fig_growth = add_highlight_shapes(fig_growth, highlight_periods)
        fig_growth.update_layout(title=f"{growth_col} Growth Rates", xaxis_title="Date", yaxis_title="Growth Rate (%)")
        st.plotly_chart(fig_growth, use_container_width=True)

# Stress indicators
with tab3:
    if 'Central Bank Liquidity Swaps' in display_data.columns:
        fig_swaps = px.line(display_data, x='date', y='Central Bank Liquidity Swaps',
                            title="Offshore Dollar Stress (Liquidity Swaps)")
        fig_swaps.add_hline(y=100, line_dash="dash", line_color="red", annotation_text="Stress Threshold")
        fig_swaps = add_highlight_shapes(fig_swaps, highlight_periods)
        st.plotly_chart(fig_swaps, use_container_width=True)
    if 'Loans' in display_data.columns:
        fig_loans = px.line(display_data, x='date', y='Loans', title="Domestic Credit Stress (Loans)")
        fig_loans.add_hline(y=50, line_dash="dash", line_color="red", annotation_text="Stress Threshold")
        fig_loans = add_highlight_shapes(fig_loans, highlight_periods)
        st.plotly_chart(fig_loans, use_container_width=True)

# Foreign sector
with tab4:
    foreign_metrics = [m for m in ['Reverse Repo Foreign', 'Securities in Custody'] if m in display_data.columns]
    if foreign_metrics:
        fig_foreign = px.line(display_data, x='date', y=foreign_metrics, title="Foreign Official Sector Activity")
        fig_foreign = add_highlight_shapes(fig_foreign, highlight_periods)
        st.plotly_chart(fig_foreign, use_container_width=True)
