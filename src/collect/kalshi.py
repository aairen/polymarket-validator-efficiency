import requests
import pandas as pd
import os
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW_DIR = os.path.join(PROJECT_ROOT, 'data', 'raw', 'kalshi')
EVENTS_CSV = os.path.join(PROJECT_ROOT, 'data', 'events.csv')

BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"

def load_events() -> pd.DataFrame:
  """Load the events registry"""
  return pd.read_csv(EVENTS_CSV)

def _fetch_candlesticks(ticker: str) -> pd.DataFrame:
  """
  Fetch price history for a Kalshi market from the historical candlesticks endpoint.
  Returns a DataFrame with columns: timestamp, price.
  """
  r = requests.get(
    f"{BASE_URL}/historical/markets/{ticker}/candlesticks",
    params={
      "start_ts": 1704067200, # Jan 1 2024
      "end_ts": 1772323200,  # Mar 1 2026
      "period_interval": 1440, # daily candles
    }
  ).json()

  if 'candlesticks' not in r or not r['candlesticks']:
    raise RuntimeError(f"No candlestick data returned for ticker: {ticker} — {r}")
  
  candles = r['candlesticks']
  df = pd.DataFrame([{
    'timestamp': pd.Timestamp(c['end_period_ts'], unit='s', tz='UTC'),
    'price': float(c['price']['close'])
  } for c in candles if c['price']['close'] is not None])

  df = df.sort_values('timestamp').reset_index(drop=True)
  return df

def get_price_history(event_name: str) -> pd.DataFrame:
  """
  Return price history for a given event, using cache if available.

  Parameter:
    event_name: matches the event_name column in events.csv

  Returns:
    DataFrame with columns: timestamp, price
  """
  events = load_events()
  row = events[events['event_name'] == event_name]

  if row.empty:
    raise ValueError(f"Event '{event_name}' not found in events.csv")
  
  row = row.iloc[0]
  ticker = str(row['kalshi_ticker'])
  cache_path = os.path.join(RAW_DIR, f"{event_name}.csv")

  if os.path.exists(cache_path):
    df = pd.read_csv(cache_path)
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
    return df
  
  print(f"Fetching Kalshi price history for: {event_name} ({ticker})")
  df = _fetch_candlesticks(ticker)

  os.makedirs(RAW_DIR, exist_ok=True)
  df.to_csv(cache_path, index=False)
  print(f"Saved to {cache_path}")

  return df

def get_all_price_histories() -> dict:
  """
  Fetch and cache price history for all events in events.csv.
  Returns a dict mapping event_name -> DataFrame.
  """
  events = load_events()
  results = {}

  for _, row in events.iterrows():
    event_name = row['event_name']

    try:
      results[event_name] = get_price_history(event_name)
      print(f"{event_name}: {len(results[event_name])} records")
    except Exception as e:
      print(f"{event_name} failed: {e}")

    time.sleep(0.3)
  
  return results

if __name__ == "__main__":
  results = get_all_price_histories()
  for event_name, df in results.items():
    print(f"\n{event_name}:")
    print(f"  records:    {len(df)}")
    print(f"  date range: {df['timestamp'].min()} → {df['timestamp'].max()}")
    print(f"  price range: {df['price'].iloc[-1]:.3f}")