# CWRV Web App

Flask-based web app to predict next 5-min candle for 5 pairs using CWRV logic with Twelve Data API.

## Setup (Local)
```bash
pip install -r requirements.txt
export TWELVE_DATA_API_KEY=your_api_key   # or set in Windows PowerShell
python app.py
```
Go to `http://localhost:5000`.

## Render Deployment
- Push to GitHub
- Connect repo to Render
- Add environment variable: `TWELVE_DATA_API_KEY`
- Deploy!
