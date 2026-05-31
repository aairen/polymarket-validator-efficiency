import pandas as pd
import numpy as np
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROCESSED_DIR = os.path.join(PROJECT_ROOT, 'data', 'processed')
METRICS_CSV   = os.path.join(PROCESSED_DIR, 'decentralization.csv')

def nakamoto(stakes: pd.Series) -> int:
  """
  Calculates the minimum number of validators needed to control at least 51% of total stake.
  Lower value = more concentrated.
  """
  stakes = stakes.sort_values(ascending=False).reset_index(drop=True)
  total = stakes.sum()
  threshold = total * 0.51
  cumulative = stakes.cumsum()

  return int((cumulative < threshold).sum() + 1)

def gini(stakes: pd.Series) -> float:
  """
  Calculates the Gini coefficient of the stake distribution.
  0 = perfectly equal, 1 = one validator controls everything. 
  """
  stakes = stakes.values
  stakes = np.sort(stakes)
  n = len(stakes)
  index = np.arange(1, n + 1)

  return float((2 * (index * stakes).sum()) / (n * stakes.sum()) - (n + 1) / n)

def hhi(stakes: pd.Series) -> float:
  """
  Calculates the Herfindahl-Hirschman Index (HHI) of stake distribution.
  Sum of market shares squared (as whole numbers), ranges from 0 to 10,000.
  Higher = more concentrated. DOJ threshold; >2,500 = highly concentrated.
  """
  shares = stakes / stakes.sum() * 100
  return float((shares ** 2).sum())

def load_validators() -> pd.DataFrame:
  """Load raw validator stake data from collection layer"""
  from src.collect.validators import load_validators
  return load_validators()

def compute_daily_metrics(df: pd.DataFrame) -> pd.DataFrame:
  """
  Compute Nakamoto, Gini, and HHI for each day in the validator dataset.
  Handles forward-filling of missing validator-day combinations.

  Parameter:
    df: validator dataframe with columns: date, validator_id, amount

  Returns:
    DataFrame with columns: date, nakamoto, gini, hhi
  """
  # forward-fill missing validator-day combinations
  pivot = df.pivot_table(index='date', columns='validator_id', values='amount')

  # forward-fill each validator's stake on days with no update
  pivot = pivot.ffill()

  records = []
  for date, row in pivot.iterrows():
    stakes = row.dropna()
    if len(stakes) == 0:
      continue

    records.append({
      'date': date,
      'nakamoto': nakamoto(stakes),
      'gini': gini(stakes),
      'hhi': hhi(stakes),
    })
  
  result = pd.DataFrame(records)
  result['date'] = pd.to_datetime(result['date'])
  result = result.sort_values('date').reset_index(drop=True)
  return result

def save_metrics(df: pd.DataFrame):
  """Save daily metrics to data/processed/decentralization.csv"""
  os.makedirs(PROCESSED_DIR, exist_ok=True)
  df.to_csv(METRICS_CSV, index=False)
  print(f"Saved {len(df)} rows to {METRICS_CSV}")

def load_metrics() -> pd.DataFrame:
  """Load precomputed daily metrics from disk"""
  if not os.path.exists(METRICS_CSV):
    raise FileNotFoundError("decentralization.csv not found. Run compute_daily_metrics() first.")

  df = pd.read_csv(METRICS_CSV)
  df['date'] = pd.to_datetime(df['date'])
  return df

if __name__ == "__main__":
  print("Loading validator data...")
  validators = load_validators()
  print(f"{len(validators)} rows, {validators['date'].nunique()} unique dates")

  print("Computing daily metrics...")
  metrics = compute_daily_metrics(validators)

  print(f"\nSample output:")
  print(metrics.head(10).to_string())

  print(f"\nSummary:")
  print(f"date range: {metrics['date'].min().date()} → {metrics['date'].max().date()}")
  print(f"mean nakamoto: {metrics['nakamoto'].mean():.2f}")
  print(f"mean gini: {metrics['gini'].mean():.4f}")
  print(f"mean hhi: {metrics['hhi'].mean():.6f}")

  save_metrics(metrics)