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
# CONFIGURATION & SECRETS
# ==========================================
# Streamlit uses st.secrets instead of os.environ for security
try:
    TELEGRAM_TOKEN = st.secrets["TELEGRAM_TOKEN"]
    TELEGRAM_CHAT_ID = st.secrets["TELEGRAM_CHAT_ID"]
except:
    st.warning("Telegram secrets not found. Alerts will not be sent.")
    TELEGRAM_TOKEN = ""
    TELEGRAM_CHAT_ID = ""

# High Volume / High Volatility NSE Stocks
WATCHLIST = ['RELIANCE.NS', 'HDFCBANK.NS', 'INFY.NS', 'ICICIBANK.NS', 'TCS.NS', 'ZOMATO.NS', 'TATASTEEL.NS']

# ==========================================
# CORE FUNCTIONS
# ==========================================
def send_telegram_alert(message):
    if not TELEGRAM_TOKEN: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

def fetch_global_sentiment():
    """Scrapes global & WION news via RSS and calculates AI sentiment."""
    url = "https://news.google.com/rss/search?q=global+markets+OR+WION+economy&hl=en-IN&gl=IN&ceid=IN:en"
    feed = feedparser.parse(url)
    
    sentiment_score = 0
    headlines = []
    
    for entry in feed.entries[:5]: # Analyze top 5 headlines
        text = entry.title
        headlines.append(text)
        # TextBlob calculates if words are positive (>0) or negative (<0)
        blob = TextBlob(text)
        sentiment_score += blob.sentiment.polarity
        
    avg_sentiment = sentiment_score / 5
    return avg_sentiment, headlines

def process_stock_data(ticker):
    """Fetches 5-minute data and calculates Intraday Technical Indicators."""
    stock = yf.Ticker(ticker)
    df = stock.history(period="2d", interval="5m")
    
    if df.empty:
        return None
        
    # Calculate MACD (Momentum)
    df['MACD'] = ta.trend.macd_diff(df['Close'])
    
    # Calculate RSI (Overbought/Oversold)
    df['RSI'] = ta.momentum.rsi(df['Close'], window=14)
    
    # Calculate Bollinger Bands (Volatility)
    indicator_bb = ta.volatility.BollingerBands(close=df['Close'], window=20, window_dev=2)
    df['BB_High'] = indicator_bb.bollinger_hband()
    df['BB_Low'] = indicator_bb.bollinger_lband()
    
    return df

# ==========================================
# FRONTEND DASHBOARD (STREAMLIT UI)
# ==========================================
st.set_page_config(page_title="Scalp AI Bot", layout="wide")
st.title("⚡ 5-Minute Intraday Scalping Dashboard")

# UI Sidebar for Controls
st.sidebar.header("Controls")
selected_ticker = st.sidebar.selectbox("Select Stock to View Chart:", WATCHLIST)

# 1. Fetch & Display News Sentiment
st.subheader("📰 Global & WION News Sentiment")
sentiment_score, news_headlines = fetch_global_sentiment()

if sentiment_score > 0.1:
    st.success(f"Market Sentiment is POSITIVE (Score: {sentiment_score:.2f})")
elif sentiment_score < -0.1:
    st.error(f"Market Sentiment is NEGATIVE (Score: {sentiment_score:.2f})")
else:
    st.warning(f"Market Sentiment is NEUTRAL (Score: {sentiment_score:.2f})")

with st.expander("View Latest Headlines Analyzed"):
    for headline in news_headlines:
        st.write(f"- {headline}")

# 2. Render the Live Chart for the selected stock
st.subheader(f"📊 Live 5-Minute Chart: {selected_ticker}")
df_chart = process_stock_data(selected_ticker)

if df_chart is not None:
    # Create an interactive Candlestick chart using Plotly
    fig = go.Figure(data=[go.Candlestick(x=df_chart.index,
                    open=df_chart['Open'],
                    high=df_chart['High'],
                    low=df_chart['Low'],
                    close=df_chart['Close'],
                    name="Price")])
    
    # Add Bollinger Bands to the chart
    fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['BB_High'], line=dict(color='gray', width=1, dash='dash'), name="BB High"))
    fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['BB_Low'], line=dict(color='gray', width=1, dash='dash'), name="BB Low"))
    
    fig.update_layout(height=500, margin=dict(l=0, r=0, t=0, b=0), xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

# 3. The Signal Engine (Scans all stocks)
st.subheader("🤖 Bot Signal Scanner")
if st.button("Scan Market for 5-Min Entry Signals"):
    with st.spinner("Scanning Nifty Watchlist..."):
        for ticker in WATCHLIST:
            df = process_stock_data(ticker)
            if df is None: continue
            
            # Get latest row of data
            latest = df.iloc[-1]
            prev = df.iloc[-2]
            
            # SCALPING BUY LOGIC
            # 1. MACD just crossed above 0 (Momentum shifting up)
            macd_bullish = prev['MACD'] < 0 and latest['MACD'] > 0
            # 2. RSI is not overbought (Room to grow)
            rsi_healthy = 40 < latest['RSI'] < 65
            # 3. News is generally positive
            news_positive = sentiment_score > 0
            
            if macd_bullish and rsi_healthy and news_positive:
                st.success(f"🟢 **BUY SIGNAL DETECTED:** {ticker}")
                
                # Calculate Targets
                entry_price = round(latest['Close'], 2)
                stop_loss = round(entry_price * 0.99, 2) # 1% risk for scalping
                target = round(entry_price * 1.02, 2) # 2% reward
                
                msg = (
                    f"⚡ **5-MIN SCALP ALERT: {ticker}**\n\n"
                    f"**Entry Price:** ₹{entry_price}\n"
                    f"**Target:** ₹{target}\n"
                    f"**Stop Loss:** ₹{stop_loss}\n\n"
                    f"**Why?** MACD crossed up, RSI is {round(latest['RSI'], 1)}, Global Sentiment is Positive."
                )
                send_telegram_alert(msg)
                st.write(f"Alert sent to Telegram for {ticker}")
            else:
                st.write(f"No entry signal for {ticker} at this time.")
