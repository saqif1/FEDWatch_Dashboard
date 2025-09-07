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

# Create sidebar for controls
st.sidebar.header("Dashboard Controls")

# FRED API key input
api_key = st.sidebar.text_input("FRED API Key", type="password", 
                               help="Get your API key from https://research.stlouisfed.org/docs/api/api_key.html")

# Check if API key is provided FIRST
if not api_key or api_key.strip() == "":
    st.warning("🔑 Please enter your FRED API key in the sidebar to load data")
    st.stop()

# Date range selector (only show if API key is provided)
end_date = datetime.now()
start_date = st.sidebar.date_input(
    "Start Date",
    value=end_date - timedelta(days=365*3),
    max_value=end_date
)

# Correct FRED series mapping based on the documentation
FRED_SERIES = {
    "Total Assets": "WALCL",  # Assets: Total Assets: Total Assets (Less Eliminations from Consolidation): Wednesday Level
    "Treasury Securities": "TREAST",  # Assets: Securities Held Outright: U.S. Treasury Securities: All: Wednesday Level
    "Mortgage-Backed Securities": "SWPT",  # Assets: Securities Held Outright: Mortgage-Backed Securities: Wednesday Level
    "Bank Reserves": "WRESBAL",  # Liabilities: Reserve Balances with Federal Reserve Banks: Wednesday Level
    "Reverse Repo Foreign": "WLRRAFOIAL",  # Liabilities: Reverse Repurchase Agreements: Foreign Official and International Accounts: Wednesday Level
    "Central Bank Liquidity Swaps": "SWPT",  # Assets: Central Bank Liquidity Swaps: Wednesday Level
    "Loans": "WLCFLL",  # Assets: Liquidity and Credit Facilities: Loans: Wednesday Level
    "Securities in Custody": "WFCDA",  # Securities held in custody for foreign official and international accounts
}

# Asset selection
selected_assets = st.sidebar.multiselect(
    "Select Balance Sheet Components",
    list(FRED_SERIES.keys()),
    default=["Total Assets", "Treasury Securities", "Mortgage-Backed Securities", "Bank Reserves", "Loans", "Reverse Repo Foreign"]
)

# Function to fetch data from FRED
def fetch_fred_data(series_id, api_key, start_date):
    """Fetch data from FRED API"""
    if not api_key or api_key.strip() == "":
        return None
        
    url = f"https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "observation_start": start_date.strftime("%Y-%m-%d"),
        "frequency": "w",  # Weekly data
        "units": "lin"
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        observations = data.get('observations', [])
        if not observations:
            st.error(f"No data found for series {series_id}")
            return None
            
        # Convert to DataFrame
        df = pd.DataFrame(observations)
        df['value'] = pd.to_numeric(df['value'], errors='coerce')
        df['date'] = pd.to_datetime(df['date'])
        df = df.dropna(subset=['value'])
        
        if len(df) == 0:
            return None
            
        return df[['date', 'value']].rename(columns={'value': series_id})
        
    except requests.exceptions.HTTPError as e:
        if response.status_code == 403:
            st.error("Invalid API key. Please check your FRED API key.")
        else:
            st.error(f"HTTP Error: {str(e)}")
        return None
    except Exception as e:
        st.error(f"Error fetching data for {series_id}: {str(e)}")
        return None

# Fetch data when API key is provided
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
    
    # Check if any data was successfully fetched
    if successful_fetches == 0:
        st.error("❌ Could not fetch any data. Please check your API key and try again.")
        st.stop()
    
    # Merge all dataframes
    fed_data = all_data[0]
    for df in all_data[1:]:
        fed_data = pd.merge(fed_data, df, on='date', how='outer')
    
    fed_data = fed_data.sort_values('date').ffill()
    
    # Convert from millions to billions for display
    display_data = fed_data.copy()
    for col in display_data.columns:
        if col != 'date':
            display_data[col] = display_data[col] / 1000  # Convert to billions
    
    # Create user-friendly column names
    reverse_series_mapping = {v: k for k, v in FRED_SERIES.items()}
    display_data = display_data.rename(columns=reverse_series_mapping)

# Display success message
st.success(f"✅ Successfully loaded data for {successful_fetches} out of {len(selected_assets)} selected series")

# Main dashboard layout
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("Fed Balance Sheet Components")
    
    # Create interactive chart
    fig = go.Figure()
    
    for asset in selected_assets:
        if asset in display_data.columns:
            fig.add_trace(go.Scatter(
                x=display_data['date'],
                y=display_data[asset],
                name=asset,
                mode='lines',
                hovertemplate='<b>%{x}</b><br>%{y:,.0f} billion<extra></extra>'
            ))
    
    fig.update_layout(
        height=500,
        title="Federal Reserve Balance Sheet Components",
        xaxis_title="Date",
        yaxis_title="Amount (Billions of USD)",
        hovermode='x unified',
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("Key Metrics")
    
    # Latest values
    if len(display_data) > 1:
        latest = display_data.iloc[-1]
        prev = display_data.iloc[-2]
        
        for asset in selected_assets:
            if asset in display_data.columns:
                current_val = latest[asset]
                prev_val = prev[asset]
                change = current_val - prev_val
                change_pct = (change / prev_val * 100) if prev_val != 0 else 0
                
                st.metric(
                    label=asset,
                    value=f"${current_val:,.0f}B",
                    delta=f"{change:+.1f}B ({change_pct:+.1f}%)"
                )
    else:
        st.warning("Insufficient data for metrics comparison")
    
    st.subheader("Market Insights")
    st.info("""
    - **Expanding balance sheet**: Accommodative monetary policy
    - **High credit facilities usage**: Market stress indicator  
    - **Declining foreign repo**: Possible Treasury selling for FX intervention
    - **Rising liquidity swaps**: Offshore dollar funding stress
    """)

# Additional analysis tabs
st.subheader("Detailed Analysis")

tab1, tab2, tab3, tab4 = st.tabs(["Composition", "Growth Rates", "Stress Indicators", "Foreign Sector"])

with tab1:
    st.write("**Balance Sheet Composition Over Time**")
    
    if 'Total Assets' in display_data.columns:
        # Calculate percentages
        comp_data = display_data.copy()
        for col in comp_data.columns:
            if col != 'date' and col != 'Total Assets':
                comp_data[f'{col}_pct'] = (comp_data[col] / comp_data['Total Assets']) * 100
        
        # Composition chart
        comp_cols = [col for col in comp_data.columns if '_pct' in col]
        comp_names = [col.replace('_pct', '') for col in comp_cols]
        
        if comp_cols:
            fig_comp = px.area(
                comp_data, 
                x='date', 
                y=comp_cols,
                title="Balance Sheet Composition (%)",
                labels={'value': 'Percentage', 'variable': 'Component'}
            )
            st.plotly_chart(fig_comp, use_container_width=True)
        else:
            st.warning("No composition data available")
    else:
        st.warning("Total Assets data needed for composition analysis")

with tab2:
    st.write("**Weekly and Annual Growth Rates**")
    
    growth_data = display_data.copy()
    for col in growth_data.columns:
        if col != 'date':
            growth_data[f'{col}_weekly_growth'] = growth_data[col].pct_change() * 100
            growth_data[f'{col}_annual_growth'] = growth_data[col].pct_change(52) * 100
    
    # Growth chart
    available_assets = [asset for asset in selected_assets if asset in display_data.columns]
    if available_assets:
        growth_col = st.selectbox("Select series for growth analysis", available_assets)
        
        if growth_col in display_data.columns:
            fig_growth = make_subplots(specs=[[{"secondary_y": False}]])
            
            fig_growth.add_trace(go.Scatter(
                x=growth_data['date'],
                y=growth_data[f'{growth_col}_weekly_growth'],
                name="Weekly Growth (%)",
                line=dict(color='blue')
            ))
            
            fig_growth.add_trace(go.Scatter(
                x=growth_data['date'],
                y=growth_data[f'{growth_col}_annual_growth'],
                name="Annual Growth (%)",
                line=dict(color='red')
            ))
            
            fig_growth.update_layout(
                title=f"{growth_col} Growth Rates",
                xaxis_title="Date",
                yaxis_title="Growth Rate (%)"
            )
            
            st.plotly_chart(fig_growth, use_container_width=True)
    else:
        st.warning("No data available for growth analysis")

with tab3:
    st.write("**Market Stress Indicators**")
    
    stress_indicators = []
    if 'Central Bank Liquidity Swaps' in display_data.columns:
        stress_indicators.append('Central Bank Liquidity Swaps')
    if 'Loans' in display_data.columns:
        stress_indicators.append('Loans')
    
    if stress_indicators:
        col1, col2 = st.columns(2)
        
        if 'Central Bank Liquidity Swaps' in stress_indicators:
            with col1:
                # Liquidity swaps as stress indicator
                fig_swaps = px.line(
                    display_data, 
                    x='date', 
                    y='Central Bank Liquidity Swaps',
                    title="Central Bank Liquidity Swaps",
                    labels={'Central Bank Liquidity Swaps': 'Billions USD'}
                )
                st.plotly_chart(fig_swaps, use_container_width=True)
                st.caption("High values indicate offshore dollar funding stress")
        
        if 'Loans' in stress_indicators:
            with col2:
                # Loans as stress indicator
                fig_loans = px.line(
                    display_data, 
                    x='date', 
                    y='Loans',
                    title="Credit Facility Loans",
                    labels={'Loans': 'Billions USD'}
                )
                st.plotly_chart(fig_loans, use_container_width=True)
                st.caption("High values indicate domestic market stress")
    else:
        st.warning("Select 'Central Bank Liquidity Swaps' and/or 'Loans' to view stress indicators")

with tab4:
    st.write("**Foreign Sector Activity**")
    
    foreign_metrics = []
    if 'Reverse Repo Foreign' in display_data.columns:
        foreign_metrics.append('Reverse Repo Foreign')
    if 'Securities in Custody' in display_data.columns:
        foreign_metrics.append('Securities in Custody')
    
    if foreign_metrics:
        fig_foreign = px.line(
            display_data, 
            x='date', 
            y=foreign_metrics,
            title="Foreign Official Sector Activity",
            labels={'value': 'Billions USD'}
        )
        st.plotly_chart(fig_foreign, use_container_width=True)
        
        st.info("""
        **Foreign Sector Insights**:
        - Declining Reverse Repo Foreign: Foreign central banks may be selling Treasuries
        - Declining Securities in Custody: Reduction in foreign official dollar reserves
        - Both can indicate FX intervention or diversification away from USD
        """)
    else:
        st.warning("Select foreign sector metrics to view this analysis")

# Data source and documentation
st.markdown("---")
st.subheader("Data Documentation")

with st.expander("FRED Series Reference"):
    st.markdown("""
    | Series Name | FRED ID | Description |
    |-------------|---------|-------------|
    | Total Assets | WALCL | Assets: Total Assets: Total Assets (Less Eliminations from Consolidation): Wednesday Level |
    | Treasury Securities | TREAST | Assets: Securities Held Outright: U.S. Treasury Securities: All: Wednesday Level |
    | Mortgage-Backed Securities | SWPT | Assets: Securities Held Outright: Mortgage-Backed Securities: Wednesday Level |
    | Bank Reserves | WRESBAL | Liabilities: Reserve Balances with Federal Reserve Banks: Wednesday Level |
    | Reverse Repo Foreign | WLRRAFOIAL | Liabilities: Reverse Repurchase Agreements: Foreign Official and International Accounts: Wednesday Level |
    | Central Bank Liquidity Swaps | SWPT | Assets: Central Bank Liquidity Swaps: Wednesday Level |
    | Loans | WLCFLL | Assets: Liquidity and Credit Facilities: Loans: Wednesday Level |
    | Securities in Custody | WFCDA | Securities held in custody for foreign official and international accounts |
    """)

st.caption("""
**Data Source**: Federal Reserve Economic Data (FRED) - Federal Reserve Bank of St. Louis  
**Last Updated**: Weekly (Thursday afternoons) via H.4.1 report  
**Note**: All values converted to billions of USD for display
""")