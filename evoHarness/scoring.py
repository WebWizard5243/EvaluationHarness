import json
from pathlib import Path


def load_results(path : str) -> list[dict]:
   """Load evaluation results from a JSONL file."""
   results = []
   with open(path, 'r' , encoding='utf-8') as file:
    for line in file:
        if line.strip():
            results.append(json.loads(line))
return results