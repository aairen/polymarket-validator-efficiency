import sys
import requests

def lookup(slug: str):
  response = requests.get(f"https://gamma-api.polymarket.com/events/slug/{slug}")
  response.raise_for_status()
  data = response.json()

  if 'markets' not in data or not data['markets']:
    print(f"No markets found for slug: {slug}")
    return

  for m in data['markets']:
    condition_id = m['conditionId']
    print(f"Question:     {m['question']}")
    print(f"Condition ID: {condition_id}")

    clob = requests.get(f"https://clob.polymarket.com/markets/{condition_id}").json()
    for token in clob.get('tokens', []):
      print(f"  {token['outcome']} token ID: {token['token_id']}")

    print()

if __name__ == "__main__":
  if len(sys.argv) != 2:
    print("Usage: python src/collect/event_collection.py <slug>")
    sys.exit(1)

  lookup(sys.argv[1])
