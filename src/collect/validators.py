import pandas as pd
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
VALIDATORS_CSV = os.path.join(PROJECT_ROOT, "data", "raw", "validators", "polygon_validators_2024_2025.csv")

def load_validators() -> pd.DataFrame:
  """
  Load the Polygon validator stake dataset collected from Dune Analytics.
  Returns a clean dataframe with one row per validator per day.

  Columns:
    amount         (float)         — stake in POL tokens
    validator_id   (int)           — numeric validator ID
    validator_name (str)           — human-readable validator name
    date           (datetime.date) — the snapshot date
  """
  
  df = pd.read_csv(VALIDATORS_CSV)

  df['time'] = pd.to_datetime(df['time'], utc=True)
  df['date'] = df['time'].dt.date

  df = df.drop(columns=['time', 'validator'])
  df = df.sort_values(['date', 'validator_id']).reset_index(drop=True)

  return df

if __name__ == "__main__":
  df = load_validators()
  print(df.shape)
  print(df.dtypes)
  print(df.head())