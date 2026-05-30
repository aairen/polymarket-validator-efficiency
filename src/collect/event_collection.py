import requests
import pandas as pd

# Find condition ID for the presidental election
slug = "slug-here"
response = requests.get(f"https://gamma-api.polymarket.com/events/slug/{slug}")
data = response.json()

for m in data['markets']:
  print("Question:     ", m['question'])
  print("Condition ID: ", m['conditionId'])
  print()

# Find token ID corresponding to "Yes" given the condition ID
condition_id = "condition-id-here"
clob = requests.get(f"https://clob.polymarket.com/markets/{condition_id}").json()

for token in clob['tokens']:
  print("Outcome:  ", token['outcome'])
  print("Token ID: ", token['token_id'])
  print()