import json
from pathlib import Path

def load_mitre_kb():
    mitre_kb_path = Path(__file__).parent.parent / "mitre_kb" / "mitre.json"
    with open(mitre_kb_path) as f:
        mitre_kb = json.load(f)
    return mitre_kb