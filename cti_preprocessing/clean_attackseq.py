import re
import json
import json
from pathlib import Path
from load_mitre_kb import load_mitre_kb
pattern = r"^T\d{4}-[\S\s/]+$"

def get_technique_name(technique_id, mitre_kb):
    for tactic in mitre_kb['tactics']:
        for technique in tactic['techniques']:
            if technique['id'] == technique_id:
                return technique['name']
            for sub_technique in technique.get('sub_techniques', []):
                if sub_technique['id'] == technique_id:
                    return sub_technique['name']
    return None

def check_technique_name(technique_name: str) -> bool:
    return bool(re.match(pattern, technique_name))

def main():
    mitre_kb = load_mitre_kb()
    attackseq_dir = Path(__file__).parent.parent / 'filtered-attackseqs'

    for json_file in attackseq_dir.glob('*.json'):
        with open(json_file, 'r') as f:
            data = json.load(f)
        for event in data['triplets']:
            if event['tactic'] == "Others":
                continue
            if event['ObjectType'] == "network trafic":
                event['ObjectType'] = "network traffic"
            updated_techniques = []
            for technique in event['technique']:
                if technique == "Others":
                    updated_techniques.append(technique)
                    continue
                if not check_technique_name(technique):
                    # print(f"Invalid technique name: {event['technique']} in {json_file}")
                    technique_name = get_technique_name(technique, mitre_kb)
                    corrected_technique = f"{technique}-{technique_name}"
                    updated_techniques.append(corrected_technique)
                else:
                    updated_techniques.append(technique)
            event['technique'] = updated_techniques
        with open(json_file, "w") as f:
            json.dump(data, f, indent=4)

if __name__ == "__main__":
    main()