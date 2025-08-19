from flask import Flask, render_template, jsonify
import requests, traceback

app = Flask(__name__)

# =================== CONFIG ===================
API_KEY = "b7ea33d435964da0b0a65b1c6a029891"
PAIRS = ["EUR/USD", "GBP/USD", "EUR/JPY", "USD/JPY", "AUD/USD"]

# =================== FETCH CANDLE DATA ===================
def fetch_candles(symbol, interval="5min", count=20):
    try:
        url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval={interval}&outputsize={count}&apikey={API_KEY}"
        r = requests.get(url, timeout=10)
        data = r.json()
        if "values" not in data:
            return None
        candles = []
        for v in reversed(data["values"]):
            candles.append({
                "t": v["datetime"],
                "o": float(v["open"]),
                "h": float(v["high"]),
                "l": float(v["low"]),
                "c": float(v["close"]),
                "v": float(v.get("volume", 0))
            })
        return candles
    except Exception as e:
        print("FETCH ERROR:", e, traceback.format_exc())
        return None

# =================== CWRV 123 PATTERN ===================
def cwrv123_predict(candles):
    """
    Simplified CWRV123:
    - Check last 3 swings (impulse–correction–impulse)
    - Use candle body + tick volume for strength
    """
    if not candles or len(candles) < 6:
        return {"prediction": "NO_TRADE", "confidence": "Low", "reason": "Not enough data"}

    last = candles[-6:]

    # Determine direction
    ups = sum(1 for c in last if c["c"] > c["o"])
    downs = sum(1 for c in last if c["c"] < c["o"])

    avg_vol = sum(c["v"] for c in last) / len(last)
    strong = [c for c in last if abs(c["c"] - c["o"]) > (c["h"] - c["l"]) * 0.5 and c["v"] >= avg_vol]

    if ups >= 4 and len(strong) >= 2:
        return {"prediction": "CALL", "confidence": "High", "reason": "Wave 1-3-5 impulse up with strong volume"}
    elif downs >= 4 and len(strong) >= 2:
        return {"prediction": "PUT", "confidence": "High", "reason": "Wave 1-3-5 impulse down with strong volume"}
    elif ups > downs:
        return {"prediction": "CALL", "confidence": "Medium", "reason": "More bullish candles in CWRV structure"}
    elif downs > ups:
        return {"prediction": "PUT", "confidence": "Medium", "reason": "More bearish candles in CWRV structure"}
    else:
        return {"prediction": "NO_TRADE", "confidence": "Low", "reason": "Unclear wave structure"}

# =================== ROUTES ===================
@app.route("/")
def index():
    return render_template("index.html", pairs=PAIRS)

@app.route("/analyze")
def analyze():
    results = {}
    for pair in PAIRS:
        candles = fetch_candles(pair)
        if not candles:
            results[pair] = {"error": "Failed to fetch data"}
            continue
        results[pair] = cwrv123_predict(candles)
        results[pair]["last_candle"] = candles[-1]
    return jsonify(results)

@app.route("/check_data")
def check_data():
    data = {}
    for pair in PAIRS:
        data[pair] = fetch_candles(pair, count=5)
    return jsonify(data)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)