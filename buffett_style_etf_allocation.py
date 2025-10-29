import yfinance as yf
import pandas as pd
from datetime import datetime
from tabulate import tabulate

# --- ETF List ---
etfs = {
    "NIFTYBEES": "NIFTYBEES.NS",
    "BANKBEES": "BANKBEES.NS",
    "GOLDBEES": "GOLDBEES.NS",
    "SILVERIETF": "SILVERIETF.NS",
    "LIQUIDBEES": "LIQUIDBEES.NS"
}

# --- Current holdings (₹) ---
current_holdings = {
    "GOLDBEES": 160000,
    "SILVERIETF": 70000,
    "NIFTYBEES": 10000,
    "BANKBEES": 5000,
    "LIQUIDBEES": 30000
}

# --- Core allocation targets ---
core_allocation = {
    "NIFTYBEES": 0.45,
    "BANKBEES": 0.20,
    "GOLDBEES": 0.15,
    "SILVERIETF": 0.05
}

momentum_pct = 0.05
liquidbees_pct = 0.10

current_momentum_holding = None  # update if already holding something from momentum

# --- Helper Functions ---
def calculate_6m_return(hist):
    if len(hist) < 126:
        return None
    return (hist["Close"].iloc[-1] - hist["Close"].iloc[-126]) / hist["Close"].iloc[-126] * 100

def fetch_etf_data():
    results = []
    momentum_candidates = []

    for name, symbol in etfs.items():
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="3y")
        if hist.empty:
            results.append([name, "-", "-", "-", "-", "-", "No Data"])
            continue

        latest_price = hist["Close"].iloc[-1]
        ma_200 = hist["Close"].rolling(window=200).mean().iloc[-1]
        avg_1y = hist["Close"].tail(252).mean()
        uptrend = latest_price > ma_200
        val_status = "Fair Value"
        if latest_price > avg_1y * 1.2:
            val_status = "Overvalued"
        elif latest_price < avg_1y * 0.9:
            val_status = "Undervalued"

        return_6m = calculate_6m_return(hist)

        if name != "LIQUIDBEES" and val_status != "Overvalued" and uptrend and return_6m and return_6m > 0:
            momentum_candidates.append((name, return_6m))

        results.append([
            name,
            round(latest_price,2),
            round(ma_200,2),
            round(avg_1y,2),
            "Yes" if uptrend else "No",
            val_status,
            round(return_6m,2) if return_6m else "-"
        ])

    df = pd.DataFrame(results, columns=["ETF","Price","200-DMA","1Y Avg Price","Uptrend","Valuation","6M Return%"])
    df["Date"] = datetime.now().strftime("%Y-%m-%d")

    print(f"\n📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(tabulate(df, headers="keys", tablefmt="github", showindex=False))

    total_invested = sum(current_holdings.values())
    recommended_allocations = {}

    # --- Core allocation rules ---
    for _, row in df.iterrows():
        name = row["ETF"]
        if name == "LIQUIDBEES":
            continue

        val = row["Valuation"]
        uptrend = row["Uptrend"] == "Yes"
        target_pct = core_allocation.get(name, 0)

        if val == "Overvalued" or not uptrend:
            action = "REDUCE / EXIT"
            target_pct = 0
        elif val == "Undervalued" and uptrend:
            action = "BUY / INCREASE"
        else:
            action = "HOLD"

        recommended_allocations[name] = {"target_pct": target_pct, "action": action}

    # Always include liquidbees base
    recommended_allocations["LIQUIDBEES"] = {"target_pct": liquidbees_pct, "action": "HOLD"}

    # --- Momentum logic ---
    if momentum_candidates:
        momentum_candidates.sort(key=lambda x: x[1], reverse=True)
        top_momentum = momentum_candidates[0][0]
        recommended_allocations[top_momentum]["target_pct"] += momentum_pct
        recommended_allocations[top_momentum]["action"] = "BUY (Momentum)"
    else:
        recommended_allocations["LIQUIDBEES"]["target_pct"] += momentum_pct
        recommended_allocations["LIQUIDBEES"]["action"] = "HOLD (No Momentum)"

    # --- Calculate ₹ Difference ---
    print("\n💰 Recommended Portfolio Adjustments:\n")
    output_rows = []
    for name, data in recommended_allocations.items():
        target_amount = total_invested * data["target_pct"]
        current_amount = current_holdings.get(name, 0)
        diff = target_amount - current_amount

        if abs(diff) < 1000:
            recommendation = "HOLD"
        elif diff > 0:
            recommendation = f"BUY ₹{round(diff,0):,}"
        else:
            recommendation = f"SELL ₹{round(-diff,0):,}"

        output_rows.append([
            name,
            f"{data['action']}",
            f"{data['target_pct']*100:.1f}%",
            f"₹{current_amount:,.0f}",
            f"₹{target_amount:,.0f}",
            recommendation
        ])

    print(tabulate(output_rows, headers=["ETF","Signal","Target %","Current ₹","Target ₹","Action"], tablefmt="github"))

if __name__ == "__main__":
    fetch_etf_data()
