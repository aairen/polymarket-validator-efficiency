import requests
import pandas as pd
import numpy as np
import os
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROCESSED_DIR = os.path.join(PROJECT_ROOT, 'data', 'processed')
EFFICIENCY_CSV = os.path.join(PROCESSED_DIR, 'efficiency.csv')
EVENTS_CSV = os.path.join(PROJECT_ROOT, 'data', 'events.csv')

def load_events() -> pd.DataFrame:
  return pd.read_csv(EVENTS_CSV)

def _fetch_trades(condition_id: str) -> pd.DataFrame:
  """
  Fetch all 'Yes' trades for a Polymarket market from the Data API, given the condition ID.
  Returns a dataframe with columns: timestamp, price
  """
  all_trades = []
  offset = 0
  limit = 500

  while True:
    r = requests.get(
      "https://data-api.polymarket.com/trades",
      params = {
        "market": condition_id,
        "limit": limit,
        "offset": offset,
      }
    ).json()

    if not isinstance(r, list) or not r:
      break

    all_trades.extend(r)
    offset += limit

    if len(r) < limit:
      break

    time.sleep(0.2)

  if not all_trades:
    raise RuntimeError(f"No trades returned for condition ID: {condition_id}")
  
  df = pd.DataFrame([t for t in all_trades if isinstance(t, dict) and 'timestamp' in t])
  df = df[df['outcome'] == 'Yes'].copy()
  df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s', utc=True)
  df['price'] = df['price'].astype(float)
  df = df[['timestamp', 'price']].sort_values('timestamp').reset_index(drop=True)

  return df

def convergence_speed(trades: pd.DataFrame, resolved_value: float, 
                      resolution_time: pd.Timestamp, window_hours: int = 48) -> float:
  """
  Compute convergence speed as mean absolute deviation from resolved value in the 
  post-resolution window, resampled to hourly prices.
  Lower = faster convergence = more efficient.

  Parameters:
    trades: DataFrame with columns: timestamp, price
    resolved value: 1 (Yes) or 0 (No)
    resolution_time: timestamp when resolution became known
    window_hours: hours post-resolution to measure

  Returns:
    float - mean absolute deviation from resolved value
  """
  window_end = resolution_time + pd.Timedelta(hours=window_hours)
  post = trades[
    (trades['timestamp'] >= resolution_time) &
    (trades['timestamp'] <= window_end)
  ]

  if len(post) == 0:
    return np.nan
  
  hourly = post.set_index('timestamp')['price'].resample('1h').last().ffill().dropna()

  if len(hourly) == 0:
    return np.nan
  
  return float((hourly - resolved_value).abs().mean())

def kalshi_spread(event_name: str, resolution_time: pd.Timestamp, window_days: int = 7) -> float:
  """
  Compute mean absolute spread between Polymarket and Kalshi in the pre-resolution window.
  Higher = more divergence = less efficient.

  Parameters:
    event_name: matches event_name in events.csv
    resolution_time: resolution timestamp
    window_days: days pre-resolution to measure

  Returns:
    float - mean absolute spread
  """
  from src.collect.polymarket import get_price_history as pm_get
  from src.collect.kalshi import get_price_history as kal_get

  pm_df = pm_get(event_name)
  kal_df = kal_get(event_name)
  
  window_start = resolution_time - pd.Timedelta(days=window_days)

  pm_pre = pm_df[
    (pm_df['timestamp'] >= window_start) &
    (pm_df['timestamp'] < resolution_time)
  ]

  kal_pre = kal_df[
    (kal_df['timestamp'] >= window_start) &
    (kal_df['timestamp'] < resolution_time)
  ]

  if pm_pre.empty or kal_pre.empty:
    return np.nan
  
  pm_daily = pm_pre.set_index('timestamp')['price'].resample('1D').last().dropna()
  kal_daily = kal_pre.set_index('timestamp')['price'].resample('1D').last().dropna()

  common = pm_daily.index.intersection(kal_daily.index)
  if len(common) == 0:
    return np.nan
  
  return float((pm_daily[common] - kal_daily[common]).abs().mean())

def compute_event_metrics(event_name: str) -> dict:
  """
  Compute both efficiency metrics for a single event.

  Returns:
    dict with keys: event_name, convergence_speed, kalshi_spread, nakamoto_pre, 
                    gini_pre, hhi_pre, resolved_value, resolution_time
  """
  from src.signals.decentralization import load_metrics as load_dec

  events = load_events()
  match = events[events['event_name'] == event_name]
  if match.empty:
    raise ValueError(f"Event '{event_name}' not found in events.csv")
  row = match.iloc[0]
  condition_id = str(row['condition_id'])
  resolved_value = int(row['resolved_value'])
  resolution_ts = int(row['resolution_ts'])
  resolution_time = pd.Timestamp(resolution_ts, unit='s', tz='UTC')

  # fetch trades
  print(f"Fetching trades for {event_name}...")
  trades = _fetch_trades(condition_id)

  cs = convergence_speed(trades, resolved_value, resolution_time)
  ks = kalshi_spread(event_name, resolution_time)

  dec_df = load_dec()
  window_start = (resolution_time - pd.Timedelta(days=7)).date()
  window_end = resolution_time.date()
  dec_window = dec_df[
    (dec_df['date'].dt.date >= window_start) &
    (dec_df['date'].dt.date < window_end)
  ]
  nakamoto_pre = dec_window['nakamoto'].mean()
  gini_pre = dec_window['gini'].mean()
  hhi_pre = dec_window['hhi'].mean()

  return {
    'event_name': event_name,
    'convergence_speed': cs,
    'kalshi_spread': ks,
    'nakamoto_pre': nakamoto_pre,
    'gini_pre': gini_pre,
    'hhi_pre': hhi_pre,
    'resolved_value': resolved_value,
    'resolution_time': resolution_time,
  }

def compute_all_metrics() -> pd.DataFrame:
  """
  Compute efficiency metrics for all events in events.csv.
  Returns a clean dataframe ready for statistical analysis.
  """
  events = load_events()
  records = []

  for _, row in events.iterrows():
    event_name = row['event_name']
    print(f"Processing: {event_name}")

    try:
      result = compute_event_metrics(event_name)
      records.append(result)
      print(f"convergence_speed: {result['convergence_speed']:.4f}")
      print(f"kalshi_spread: {result['kalshi_spread']:.4f}")
      print(f"nakamoto_pre: {result['nakamoto_pre']:.2f}")
    except Exception as e:
      print(f"Error: {e}")
  
  return pd.DataFrame(records)

def save_metrics(df: pd.DataFrame):
  """Save efficiency metrics to data/processed/efficiency.csv"""
  os.makedirs(PROCESSED_DIR, exist_ok=True)
  df.to_csv(EFFICIENCY_CSV, index=False)
  print(f"\nSaved {len(df)} rows to {EFFICIENCY_CSV}")

def load_metrics() -> pd.DataFrame:
  """Load precomputed efficiency metrics from disk"""
  if not os.path.exists(EFFICIENCY_CSV):
    raise FileNotFoundError("efficiency.csv not found. Run compute_all_metrics() first.")

  df = pd.read_csv(EFFICIENCY_CSV)
  df['resolution_time'] = pd.to_datetime(df['resolution_time'], utc=True)

  return df

if __name__ == "__main__":
  metrics = compute_all_metrics()
  print(f"Final output:")
  print(metrics[['event_name', 'convergence_speed', 'kalshi_spread', 'nakamoto_pre']].to_string())
  save_metrics(metrics)