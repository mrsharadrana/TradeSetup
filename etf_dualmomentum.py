"""
portfolio_manager_simplified.py

Purpose:
- Buffett core allocation + Momentum tactical overlay
- Simplified Safe bucket (LiquidBees only)
- Calculates exact ₹ buy/sell recommendations
- Respects max turnover per run
- CSV logging for audit

How to use:
1. Update `current_holdings` amounts for your ETFs and newCash.
2. Adjust `bucket_targets`, `buffett_within_bucket_weights`, `momentum_pct`.
3. Run in Python / Jupyter: python portfolio_manager_simplified.py
"""

import yfinance as yf
import pandas as pd
from datetime import datetime
from tabulate import tabulate
import os
import csv

# -----------------------------
# USER PARAMETERS
# -----------------------------

# ETF -> Yahoo symbol
etfs = {
    "NIFTYBEES": "NIFTYBEES.NS",
    "BANKBEES": "BANKBEES.NS",
    "JUNIORBEES": "JUNIORBEES.NS",
    "MON100": "MON100.NS",        # Global tech/US ETF
    "GOLDBEES": "GOLDBEES.NS",
    "SILVERIETF": "SILVERIETF.NS",
    "LIQUIDBEES": "LIQUIDBEES.NS"
}

# Bucket assignment
etf_buckets = {
    "NIFTYBEES": "India",
    "BANKBEES": "India",
    "JUNIORBEES": "India",
    "MON100": "Global",
    "GOLDBEES": "Metal",
    "SILVERIETF": "Metal",
    "LIQUIDBEES": "Safe"
}

# Core bucket targets (Buffett-style)
bucket_targets = {
    "India": 0.45,
    "Global": 0.10,
    "Metal": 0.25,
    "Safe": 0.20
}

# Within bucket allocation
buffett_within_bucket_weights = {
    "India": {
        "NIFTYBEES": 0.5,
        "BANKBEES": 0.3,
        "JUNIORBEES": 0.2
    },
    "Global": {
        "MON100": 1.0
    },
    "Metal": {
        "GOLDBEES": 0.6,
        "SILVERIETF": 0.4
    },
    "Safe": {
        "LIQUIDBEES": 1.0
    }
}

# Your current holdings (INR)
current_holdings = {
    "GOLDBEES": 0,
    "SILVERIETF": 0,
    "NIFTYBEES": 103076,
    "BANKBEES": 102957,
    "LIQUIDBEES": 0,
    "JUNIORBEES": 0,
    "MON100": 10660,
    "newCash": 130588
}

# Tactical momentum allocation
momentum_pct = 0.05  # 5%
MAX_TURNOVER_PCT = .20
DRY_RUN = True
CSV_LOG_FOLDER = "rebalance_logs"
os.makedirs(CSV_LOG_FOLDER, exist_ok=True)

# -----------------------------
# Helper functions
# -----------------------------

def fetch_etf_metrics(etf_symbol):
    """Fetch last price, 200-DMA, 1y avg price, 6m return."""
    t = yf.Ticker(etf_symbol)
    hist = t.history(period="3y")
    if hist.empty:
        return None
    latest = hist["Close"].iloc[-1]
    ma200 = hist["Close"].rolling(window=200).mean().iloc[-1]
    avg1y = hist["Close"].tail(252).mean()
    r6m = None
    if len(hist) >= 130:
        r6m = (hist["Close"].iloc[-1] - hist["Close"].iloc[-126]) / hist["Close"].iloc[-126] * 100
    return {"price": latest, "ma200": ma200, "avg1y": avg1y, "r6m": r6m}

def classify_valuation(latest, avg1y):
    """Simple valuation buckets."""
    if latest > avg1y * 1.2:
        return "Overvalued"
    elif latest < avg1y * 0.9:
        return "Undervalued"
    else:
        return "Fair"

# -----------------------------
# Fetch ETF metrics
# -----------------------------

etf_metrics = {}
for name, sym in etfs.items():
    try:
        metrics = fetch_etf_metrics(sym)
    except:
        metrics = None
    etf_metrics[name] = metrics

# Display market snapshot
rows = []
for name, metrics in etf_metrics.items():
    if metrics is None:
        rows.append([name, "No Data", "-", "-", "-"])
    else:
        val = classify_valuation(metrics["price"], metrics["avg1y"])
        uptrend = metrics["price"] > metrics["ma200"]
        rows.append([name, round(metrics["price"],2), round(metrics["ma200"],2), val, "Yes" if uptrend else "No", round(metrics["r6m"],2) if metrics["r6m"] is not None else "-"])
df = pd.DataFrame(rows, columns=["ETF","Price","200-DMA","Valuation","Uptrend","6M Return%"])
print("\nMarket snapshot:")
print(tabulate(df, headers="keys", tablefmt="github", showindex=False))

# -----------------------------
# Portfolio calculations
# -----------------------------

total_value = sum(v for v in current_holdings.values())
print(f"\nTotal portfolio value (including newCash): ₹{total_value:,.0f}")

# 1) Core targets
core_targets = {}
for bucket, bucket_w in bucket_targets.items():
    if bucket not in buffett_within_bucket_weights:
        continue
    within = buffett_within_bucket_weights[bucket]
    for etf, w in within.items():
        core_targets[etf] = bucket_w * w

# 2) Tactical / momentum candidates
momentum_candidates = []
for name, metrics in etf_metrics.items():
    if metrics is None:
        continue
    val = classify_valuation(metrics["price"], metrics["avg1y"])
    uptrend = metrics["price"] > metrics["ma200"]
    r6m = metrics["r6m"]
    if name == "LIQUIDBEES":
        continue
    if val != "Overvalued" and uptrend and r6m is not None and r6m > 0:
        momentum_candidates.append((name, r6m))

momentum_candidates.sort(key=lambda x: x[1], reverse=True)

tactical_allocation = {etf: 0.0 for etf in etfs.keys()}
if momentum_candidates:
    top = momentum_candidates[0][0]
    tactical_allocation[top] = momentum_pct
    tactical_note = f"Tactical target: {top} (+{momentum_pct*100:.1f}%) due to 6M return {momentum_candidates[0][1]:.2f}%"
else:
    tactical_allocation["LIQUIDBEES"] = momentum_pct
    tactical_note = f"No momentum candidate -> tactical {momentum_pct*100:.1f}% allocated to LIQUIDBEES"

# 3) Final blended targets
final_targets = {}
for etf in etfs.keys():
    core = core_targets.get(etf, 0.0)
    tactical = tactical_allocation.get(etf, 0.0)
    metrics = etf_metrics.get(etf)
    val = None
    if metrics:
        val = classify_valuation(metrics["price"], metrics["avg1y"])
    if val == "Overvalued":
        tactical = 0.0
    final_targets[etf] = core + tactical

# Normalize if >1
sum_targets = sum(final_targets.values())
if sum_targets > 1.0:
    for k in final_targets:
        final_targets[k] = final_targets[k] / sum_targets

# 4) Compute ₹ targets and actions
output = []
for etf in final_targets:
    target_pct = final_targets[etf]
    target_amt = total_value * target_pct
    current_amt = current_holdings.get(etf, 0)
    diff = target_amt - current_amt
    if abs(diff) < 1000:
        action = "HOLD"
    elif diff > 0:
        action = f"BUY ₹{round(diff,0):,}"
    else:
        action = f"SELL ₹{round(-diff,0):,}"
    val = None
    if etf in etf_metrics and etf_metrics[etf]:
        val = classify_valuation(etf_metrics[etf]["price"], etf_metrics[etf]["avg1y"])
    output.append({
        "ETF": etf,
        "Bucket": etf_buckets.get(etf, "Other"),
        "Valuation": val if val else "-",
        "Target %": f"{target_pct*100:.2f}%",
        "Current ₹": f"₹{current_amt:,.0f}",
        "Target ₹": f"₹{target_amt:,.0f}",
        "Action": action
    })

# 5) Enforce MAX_TURNOVER_PCT
trades = [abs((float(o["Target ₹"].replace("₹","").replace(",","")) - float(o["Current ₹"].replace("₹","").replace(",","")))) for o in output]
total_proposed_turnover = sum(trades)
turnover_limit = MAX_TURNOVER_PCT * total_value
turnover_note = ""
if total_proposed_turnover > turnover_limit and total_proposed_turnover > 0:
    scale = turnover_limit / total_proposed_turnover
    turnover_note = f"Turnover exceeds cap (proposed ₹{round(total_proposed_turnover):,} > limit ₹{round(turnover_limit):,}). Scaling trades by {scale*100:.1f}%"
    new_output = []
    for o in output:
        cur = float(o["Current ₹"].replace("₹","").replace(",",""))
        tgt = float(o["Target ₹"].replace("₹","").replace(",",""))
        diff = tgt - cur
        diff_scaled = diff * scale
        new_tgt = cur + diff_scaled
        if abs(diff_scaled) < 1000:
            action = "HOLD"
        elif diff_scaled > 0:
            action = f"BUY ₹{round(diff_scaled,0):,}"
        else:
            action = f"SELL ₹{round(-diff_scaled,0):,}"
        o["Target ₹"] = f"₹{round(new_tgt,0):,}"
        o["Action"] = action
        new_output.append(o)
    output = new_output

# 6) Print final recommendations
print("\nTactical note:", tactical_note)
print("\nFinal recommendations (₹ amounts):")
rows = [[o["ETF"], o["Bucket"], o["Valuation"], o["Target %"], o["Current ₹"], o["Target ₹"], o["Action"]] for o in output]
print(tabulate(rows, headers=["ETF","Bucket","Valuation","Target %","Current ₹","Target ₹","Action"], tablefmt="github"))

# 7) Save CSV log
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
csv_file = os.path.join(CSV_LOG_FOLDER, f"rebalance_{ts}.csv")
if not DRY_RUN:
    with open(csv_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", datetime.now().isoformat()])
        writer.writerow(["total_value", total_value])
        writer.writerow([])
        writer.writerow(["ETF","Bucket","Valuation","Target %","Current ₹","Target ₹","Action"])
        for o in output:
            writer.writerow([o["ETF"], o["Bucket"], o["Valuation"], o["Target %"], o["Current ₹"], o["Target ₹"], o["Action"]])
    print(f"\nSaved log: {csv_file}")
else:
    print("\nDRY_RUN is ON — no CSV written. Set DRY_RUN=False to save logs automatically.")

# 8) Total buys / sells
buy_amounts = sum(float(o["Target ₹"].replace("₹","").replace(",","")) - float(o["Current ₹"].replace("₹","").replace(",","")) for o in output if o["Action"].startswith("BUY"))
sell_amounts = sum(float(o["Current ₹"].replace("₹","").replace(",","")) - float(o["Target ₹"].replace("₹","").replace(",","")) for o in output if o["Action"].startswith("SELL"))
print(f"\nTotal suggested BUY ₹{round(buy_amounts):,}, Total suggested SELL ₹{round(sell_amounts):,}")
if turnover_note:
    print("\n⚠️", turnover_note)
