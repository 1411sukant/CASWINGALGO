import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import requests
import feedparser
from textblob import TextBlob
import ta
import time

# ==========================================
# PAGE CONFIGURATION
# ==========================================
st.set_page_config(page_title="Scalp AI Bot", layout="wide", page_icon="⚡")
st.title("⚡ 5-Minute Intraday Scalping Dashboard")

WATCHLIST = ['RELIANCE.NS', 'HDFCBANK.NS', 'INFY.NS', 'ICICIBANK.NS', 'TCS.NS', 'ZOMATO.NS', 'TATASTEEL.NS']

# ==========================================
# SIDEBAR CONTROLS & TELEGRAM SETUP
# ==========================================
st.sidebar.header("⚙️ Bot Controls")
selected_ticker = st.sidebar.selectbox("Select Stock to View Chart:", WATCHLIST)

st.sidebar.markdown("---")
st.sidebar.subheader("📱 Telegram Setup")
st.sidebar.write("Paste your keys here to enable alerts.")
TELEGRAM_TOKEN = st.sidebar.text_input("Bot Token", type="password")
TELEGRAM_CHAT_ID = st.sidebar.text_input("Chat ID")

def send_telegram_alert(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        st.error("Missing Telegram Credentials! Signal generated but not sent.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

def fetch_global_sentiment():
    try:
        url = "https://news.google.com/rss/search?q=global+markets+OR+WION+economy&hl=en-IN&gl=IN&ceid=IN:en"
        feed = feedparser.parse(url)
        sentiment_score = 0
        headlines = [entry.title for entry in feed.entries[:5]]
        for text in headlines:
            sentiment_score += TextBlob(text).sentiment.polarity
        return sentiment_score / 5, headlines
    except:
        return 0, ["Could not fetch news."]

def process_stock_data(ticker):
    """Fetches data safely and prevents Rate Limit / MACD crashes."""
    try:
        stock = yf.Ticker(ticker)
        # Using .history() fixes the MACD formatting bug
        df = stock.history(period="2d", interval="5m")
        
        # If Yahoo blocks us or data is empty, safely stop here
        if df is None or df.empty or len(df) < 20:
            return None
            
        # Fix for yfinance MultiIndex bug
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        # Technical Indicators
        df['MACD'] = ta.trend.macd_diff(df['Close'])
        df['RSI'] = ta.momentum.rsi(df['Close'], window=14)
        indicator_bb = ta.volatility.BollingerBands(close=df['Close'], window=20, window_dev=2)
        df['BB_High'] = indicator_bb.bollinger_hband()
        df['BB_Low'] = indicator_bb.bollinger_lband()
        
        return df
    except Exception as e:
        # Fails silently instead of crashing the app
        return None

# ==========================================
# FRONTEND DASHBOARD (UI)
# ==========================================
col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("📰 AI News Sentiment")
    sentiment_score, news_headlines = fetch_global_sentiment()

    if sentiment_score > 0.05:
        st.success(f"📈 Sentiment: POSITIVE (Score: {sentiment_score:.2f})")
    elif sentiment_score < -0.05:
        st.error(f"📉 Sentiment: NEGATIVE (Score: {sentiment_score:.2f})")
    else:
        st.warning(f"⚖️ Sentiment: NEUTRAL (Score: {sentiment_score:.2f})")

    with st.expander("View Analyzed Headlines"):
        for headline in news_headlines:
            st.write(f"- {headline}")

with col2:
    st.subheader(f"📊 Live 5-Min Chart: {selected_ticker.replace('.NS', '')}")
    df_chart = process_stock_data(selected_ticker)

    if df_chart is not None:
        fig = go.Figure(data=[go.Candlestick(x=df_chart.index,
                        open=df_chart['Open'], high=df_chart['High'],
                        low=df_chart['Low'], close=df_chart['Close'], name="Price")])
        
        fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['BB_High'], line=dict(color='rgba(200,200,200,0.5)', width=1, dash='dash'), name="BB High"))
        fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['BB_Low'], line=dict(color='rgba(200,200,200,0.5)', width=1, dash='dash'), name="BB Low"))
        
        fig.update_layout(height=450, margin=dict(l=0, r=0, t=0, b=0), xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("⚠️ Yahoo Finance is temporarily rate-limiting the server. Waiting for data...")

# ==========================================
# ALGORITHMIC SCANNER & SIGNAL GENERATOR
# ==========================================
st.markdown("---")
st.subheader("🤖 Algorithmic Signal Scanner")

if st.button("🚀 Scan Market for Entry Signals", use_container_width=True):
    with st.spinner("Scanning Nifty Watchlist (Adding delay to prevent ban)..."):
        signals_found = 0
        
        for ticker in WATCHLIST:
            df = process_stock_data(ticker)
            
            if df is None:
                st.warning(f"Skipped {ticker} (Rate Limit or No Data)")
                time.sleep(1) # Wait 1 second before trying the next stock
                continue
            
            latest, prev = df.iloc[-1], df.iloc[-2]
            
            macd_bullish = prev['MACD'] < 0 and latest['MACD'] > 0
            rsi_healthy = 40 < latest['RSI'] < 70
            news_positive = sentiment_score > 0
            
            if macd_bullish and rsi_healthy and news_positive:
                signals_found += 1
                st.success(f"🟢 **BUY SIGNAL DETECTED:** {ticker.replace('.NS', '')}")
                
                entry_price = round(latest['Close'], 2)
                target, stop_loss = round(entry_price * 1.015, 2), round(entry_price * 0.99, 2)
                
                msg = f"⚡ **SCALP ALERT: {ticker}**\nEntry: ₹{entry_price}\nTarget: ₹{target}\nSL: ₹{stop_loss}"
                send_telegram_alert(msg)
            
            # Crucial: Pause for 1.5 seconds so Yahoo doesn't ban us for scanning too fast
            time.sleep(1.5) 
                
        if signals_found == 0:
            st.info("No perfect scalping setups found right now.")
