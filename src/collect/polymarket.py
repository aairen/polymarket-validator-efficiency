import requests
import pandas as pd
import os
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW_DIR = os.path.join(PROJECT_ROOT, 'data', 'raw', 'polymarket')
EVENTS_CSV = os.path.join(PROJECT_ROOT, 'data', 'events.csv')

def load_events() -> pd.DataFrame:
  """Load the events registry"""
  return pd.read_csv(EVENTS_CSV)

def _fetch_price_history(token_id: str) -> pd.DataFrame:
  """
  Fetch price history for a Yes token from the Polymarket CLOB API.
  Returns a dataframe with columns: timestamp, price.
  """
  r = requests.get(
    "https://clob.polymarket.com/prices-history",
    params={
      "market":   token_id,
      "interval": "max",
      "fidelity": 720,
    }
  ).json()
  
  if "history" not in r or not r["history"]:
    raise RuntimeError(f"No price history returned for token id: {token_id}")

  df = pd.DataFrame(r['history'])

  df['timestamp'] = pd.to_datetime(df['t'], unit='s', utc=True)
  df['price'] = df['p'].astype(float)

  df = df[['timestamp', 'price']].sort_values('timestamp').reset_index(drop=True)

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
  token_id = str(row['token_id_yes'])
  cache_path = os.path.join(RAW_DIR, f"{event_name}.csv")

  if os.path.exists(cache_path):
    df = pd.read_csv(cache_path)
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
    return df
  
  print(f"Fetching Polymarket price history for: {event_name}")
  df = _fetch_price_history(token_id)

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
    print(f"  price range: {df['price'].min():.3f} → {df['price'].max():.3f}")