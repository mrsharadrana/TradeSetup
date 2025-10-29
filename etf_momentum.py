import yfinance as yf
import pandas as pd
from tabulate import tabulate
from datetime import datetime

# --- ETF List ---
etfs = {
    "GOLDBEES": "GOLDBEES.NS",
    "SILVERIETF": "SILVERIETF.NS",
    "NIFTYBEES": "NIFTYBEES.NS",
    "BANKBEES": "BANKBEES.NS",
    "LIQUIDBEES": "LIQUIDBEES.NS"
}

# --- Signal Logic ---
def get_signal(latest, ma_200):
    if latest > ma_200:
        return "BUY"
    elif latest > ma_200 * 0.98:
        return "HOLD"
    else:
        return "EXIT"

def fetch_etf_data():
    results = []
    for name, symbol in etfs.items():
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="250d")
        if hist.empty:
            results.append([name, "-", "-", "-", "No Data", 0])
            continue

        latest_price = hist["Close"].iloc[-1]
        ma_200 = hist["Close"].rolling(window=200).mean().iloc[-1]
        momentum = ((latest_price - ma_200) / ma_200) * 100
        signal = get_signal(latest_price, ma_200)

        # Only positive trend contributes to allocation ranking
        momentum_score = momentum if signal in ["BUY", "HOLD"] else -1000

        results.append([name, round(latest_price,2), round(ma_200,2), round(momentum,2), signal, momentum_score])

    df = pd.DataFrame(results, columns=["ETF","Price","200-DMA","Momentum%","Signal","Score"])
    df["Date"] = datetime.now().strftime("%Y-%m-%d")

    # --- Suggest Rotation ---
    # Sort by Score descending
    df_allocation = df[df["Signal"].isin(["BUY","HOLD"])].sort_values(by="Score", ascending=False)

    if df_allocation.empty:
        allocation_suggestion = ["All ETFs weak. Park money in LIQUIDBEES"]
    else:
        allocation_suggestion = df_allocation["ETF"].tolist()
        # Ensure LIQUIDBEES included if not already
        if "LIQUIDBEES" not in allocation_suggestion:
            allocation_suggestion.append("LIQUIDBEES")

    # --- Display ---
    print(f"\n📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(tabulate(df.drop(columns=["Score"]), headers="keys", tablefmt="github", showindex=False))

    print("\n💡 Trend-based Rotation Suggestion:")
    for i, etf in enumerate(allocation_suggestion,1):
        print(f"{i}. {etf}")

if __name__ == "__main__":
    fetch_etf_data()
