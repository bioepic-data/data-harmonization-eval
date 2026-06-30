"""Fetch ESS-DIVE metadata for dataset idx 2 and save to cache."""
import json
import urllib.request
import sys

PACKAGE_ID = "ess-dive-9fd65df885a8e87-20250715T064942543"
OUT_FILE = "data/raw_cache/ess-dive_meta_idx2.json"

url = f"https://api.ess-dive.lbl.gov/packages/{PACKAGE_ID}"
print(f"Fetching: {url}")

try:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    with open(OUT_FILE, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Saved to {OUT_FILE}")
    print(json.dumps(data, indent=2)[:3000])
except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)
