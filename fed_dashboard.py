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
    value=end_date - timedelta(days=365*10),
    max_value=end_date
)

# CORRECT FRED series mapping with ALL indicators
FRED_SERIES = {
    "Total Assets": "WALCL",  # Assets: Total Assets: Total Assets (Less Eliminations from Consolidation): Wednesday Level
    "Treasury Securities": "TREAST",  # Assets: Securities Held Outright: U.S. Treasury Securities: All: Wednesday Level
    "Mortgage-Backed Securities": "WSHOMCB",  # Assets: Securities Held Outright: Mortgage-Backed Securities: Wednesday Level
    "Bank Reserves": "WRBWFRBL",  # Liabilities: Reserve Balances with Federal Reserve Banks: Wednesday Level
    "Reverse Repo Foreign": "WLRRAFOIAL",  # Liabilities: Reverse Repurchase Agreements: Foreign Official and International Accounts: Wednesday Level
    "Central Bank Liquidity Swaps": "SWPT",  # Assets: Central Bank Liquidity Swaps: Wednesday Level
    "Loans": "WLCFLL",  # Assets: Liquidity and Credit Facilities: Loans: Wednesday Level
    "Securities in Custody": "WFCDA",  # Assets: Other Factors Supplying Reserve Balances: Foreign Currency Denominated Assets: Wednesday Level
    "Repo Operations": "WORAL",  # Assets: Other: Repurchase Agreements: Wednesday Level
    "Other Assets": "WAOAL",  # Assets: Other: Other Assets, Consolidated Table: Wednesday Level 
}

# Asset selection with tooltips
st.sidebar.markdown("**Select Components to Display:**")
with st.sidebar.expander("ℹ️ What each component means"):
    st.markdown("""
    - **Total Assets**: Overall size of Fed's balance sheet - THE BIG PICTURE
    - **Treasury Securities**: US government bonds owned by Fed - SUPPORTS GOVERNMENT BORROWING
    - **Mortgage-Backed Securities**: Housing market loans packaged as securities - SUPPORTS HOUSING MARKET
    - **Bank Reserves**: Cash banks keep at the Fed - LIQUIDITY IN BANKING SYSTEM
    - **Reverse Repo Foreign**: Foreign central banks parking cash at Fed - FOREIGN DEMAND FOR USD SAFETY
    - **Central Bank Liquidity Swaps**: Emergency USD loans to foreign banks - OFFSHORE DOLLAR STRESS
    - **Loans**: Emergency lending to US institutions - DOMESTIC CREDIT STRESS
    - **Securities in Custody**: Treasuries held for foreign governments - FOREIGN RESERVE HOLDINGS
    - **Repo Operations**: Short-term liquidity operations - MONEY MARKET CONDITIONS
    - **Other Assets**: Miscellaneous Fed assets - WATCH FOR UNUSUAL ITEMS
    """)

selected_assets = st.sidebar.multiselect(
    "Balance Sheet Components",
    list(FRED_SERIES.keys()),
    default=["Total Assets", "Treasury Securities", "Mortgage-Backed Securities", "Bank Reserves", 
             "Reverse Repo Foreign", "Central Bank Liquidity Swaps", "Loans", "Securities in Custody"]
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
        
    except Exception as e:
        return None

# Fetch data
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
    
    # Educational tooltip
    with st.expander("💡 How to interpret this chart", expanded=False):
        st.markdown("""
        - **Rising lines** = Fed is adding liquidity to that area
        - **Falling lines** = Fed is reducing support
        - **Total Assets rising** = Generally bullish for risk assets (QE)
        - **Total Assets falling** = Generally bearish for risk assets (QT)
        - **Stress indicators rising** = Market trouble brewing
        """)
    
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
                
                # Color coding for metrics
                delta_color = "normal"
                if "Assets" in asset or "Securities" in asset or "Reserves" in asset:
                    if change > 0:
                        delta_color = "inverse"  # Green for increasing assets
                elif "Loans" in asset or "Swaps" in asset:
                    if change > 0:
                        delta_color = "off"  # Red for increasing stress indicators
                
                st.metric(
                    label=asset,
                    value=f"${current_val:,.0f}B",
                    delta=f"{change:+.1f}B ({change_pct:+.1f}%)",
                    delta_color=delta_color
                )
    else:
        st.warning("Insufficient data for metrics comparison")
    
    st.subheader("📋 Quick Interpretation Guide")
    with st.expander("What these numbers mean for markets"):
        st.markdown("""
        **🟢 Bullish Signals:**
        - Total Assets increasing (QE)
        - Treasury/MBS purchases rising
        - Bank reserves growing
        - Foreign repo increasing (demand for USD)
        
        **🔴 Bearish Signals:**
        - Total Assets decreasing (QT)
        - Stress indicators rising sharply
        - Foreign sector pulling money out
        - Loans increasing rapidly
        
        **⚠️ Watch Out For:**
        - Liquidity swaps > $100B = Offshore stress
        - Loans > $50B = Domestic credit stress
        - Foreign repo declining sharply = Potential trouble
        """)

# Additional analysis tabs
st.subheader("Detailed Analysis")

tab1, tab2, tab3, tab4 = st.tabs(["📊 Composition", "📈 Growth Rates", "⚡ Stress Indicators", "🌍 Foreign Sector"])

with tab1:
    st.write("**Balance Sheet Composition Over Time**")
    
    with st.expander("🎯 Why composition matters"):
        st.markdown("""
        **Composition tells you WHERE the Fed is focused:**
        - More Treasuries = Supporting government borrowing
        - More MBS = Supporting housing market  
        - More Loans = Emergency market support
        - Changing mix = Shifting policy priorities
        
        **Normal Composition:**
        - 50-60% Treasury Securities
        - 30-40% Mortgage-Backed Securities
        - 5-10% Other assets
        - Stress facilities near ZERO in normal times
        """)
    
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
    
    with st.expander("📖 Reading growth rates"):
        st.markdown("""
        **Growth Rate Interpretation:**
        - **Positive growth** = Expansion in that area
        - **Negative growth** = Contraction in that area  
        - **>10% weekly** = Emergency measures likely
        - **<-5% weekly** = Active tightening
        - Compare weekly vs annual for trend changes
        
        **What to watch:**
        - Treasury growth = QE/QT pace
        - MBS growth = Housing support level
        - Stress indicator growth = Problem severity
        """)
    
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
    
    with st.expander("🚨 Understanding stress indicators"):
        st.markdown("""
        **When to worry:**
        - **Liquidity Swaps > $100B** = Offshore dollar shortage
        - **Loans > $50B** = Domestic credit problems
        - **Rapid increases** = Market panic emerging
        - **Sustained highs** = Structural problems
        
        **Real-world examples:**
        - COVID-19 crisis: Both indicators spiked to $500B+
        - 2008 crisis: Loans spiked to $1.5T
        - Normal times: Both near zero
        
        **Trading implications:**
        - Rising stress = Reduce risk exposure
        - Falling stress = Opportunity to add risk
        """)
    
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
                    title="Offshore Dollar Stress (Central Bank Liquidity Swaps)",
                    labels={'Central Bank Liquidity Swaps': 'Billions USD'}
                )
                # Add stress threshold line
                fig_swaps.add_hline(y=100, line_dash="dash", line_color="red", 
                                  annotation_text="Stress Threshold", annotation_position="bottom right")
                st.plotly_chart(fig_swaps, use_container_width=True)
                st.caption("Values above $100B indicate serious offshore dollar funding stress")
        
        if 'Loans' in stress_indicators:
            with col2:
                # Loans as stress indicator
                fig_loans = px.line(
                    display_data, 
                    x='date', 
                    y='Loans',
                    title="Domestic Credit Stress (Loans)",
                    labels={'Loans': 'Billions USD'}
                )
                # Add stress threshold line
                fig_loans.add_hline(y=50, line_dash="dash", line_color="red",
                                  annotation_text="Stress Threshold", annotation_position="bottom right")
                st.plotly_chart(fig_loans, use_container_width=True)
                st.caption("Values above $50B indicate domestic credit market stress")
    else:
        st.warning("Select 'Central Bank Liquidity Swaps' and/or 'Loans' to view stress indicators")

with tab4:
    st.write("**Foreign Sector Activity**")
    
    with st.expander("🌎 Foreign sector signals"):
        st.markdown("""
        **What foreign activity tells you:**
        - **Reverse Repo falling** = Foreign banks pulling cash = Potential trouble
        - **Securities falling** = Foreign selling Treasuries = USD weakness possible
        - **Both falling** = Global dollar reduction = Risk-off environment
        
        **Trading implications:**
        - Foreign outflow = Watch USD strength
        - Large moves = Potential currency intervention
        - Sustained trends = Structural shifts
        
        **Normal ranges:**
        - Reverse Repo: $100-300B in normal times
        - Securities in Custody: $3-4T typically
        """)
    
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
        
        # Add specific insights based on current data
        if len(display_data) > 0:
            latest = display_data.iloc[-1]
            if 'Reverse Repo Foreign' in latest:
                repo_change = ""
                if 'Reverse Repo Foreign' in display_data.columns and len(display_data) > 1:
                    current_repo = latest['Reverse Repo Foreign']
                    prev_repo = display_data.iloc[-2]['Reverse Repo Foreign']
                    if current_repo < prev_repo:
                        repo_change = "🔻 Decreasing - Foreign banks may be pulling cash"
                    elif current_repo > prev_repo:
                        repo_change = "🔺 Increasing - Foreign demand for USD safety"
                
                st.info(f"""
                **Current Foreign Repo: ${latest.get('Reverse Repo Foreign', 0):.1f}B**
                {repo_change}
                """)
    else:
        st.warning("Select foreign sector metrics to view this analysis")

# Final educational section
st.markdown("---")
st.subheader("🎓 Fed Balance Sheet Quick Notes")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("**🤔 Why Watch the Fed?**")
    st.markdown("""
    - Fed controls money supply
    - Affects interest rates
    - Impacts all asset prices
    - Early warning system
    - Predicts policy changes
    """)

with col2:
    st.markdown("**📈 Bullish Environments**")
    st.markdown("""
    - Balance sheet expanding (QE)
    - Stress indicators low
    - Foreign money flowing in
    - Stable composition
    - Low loan activity
    """)

with col3:
    st.markdown("**📉 Bearish Environments**")
    st.markdown("""
    - Balance sheet shrinking (QT)
    - Stress indicators high
    - Foreign money leaving
    - Composition changing rapidly
    - High loan activity
    """)

# Data source
st.caption("""
**Data Source**: Federal Reserve Economic Data (FRED) - Federal Reserve Bank of St. Louis  
**Last Updated**: Weekly (Thursday afternoons) via H.4.1 report  
**Note**: All values converted to billions of USD for display
""")