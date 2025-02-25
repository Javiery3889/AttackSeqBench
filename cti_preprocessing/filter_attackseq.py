import json
import re
from pathlib import Path

# Check if the outline has more than two tactics
def is_attackseq(report_data: dict) -> bool:
    outline = report_data.get('rewrite')
    non_empty_tactics = [tactic for tactic, description in outline.items() if description != "None" and tactic != "Others"]
    if len(non_empty_tactics) < 2:
        return False
    return True

def get_annotated_ttps(report_data: dict) -> list:
    annotated_ttps = []
    triplets = report_data.get('triplets')
    triplet_id = 1
    for triplet in triplets:
        if triplet['tactic'] == "Others":
            continue
        triplet['id'] = triplet_id
        annotated_ttps.append(triplet)
        triplet_id += 1
    return annotated_ttps

def remove_empty_tactics(report_data: dict) -> dict:
    outline = report_data.get('rewrite')
    for tactic in list(outline.keys()):
        if outline[tactic] == "None":
            del outline[tactic]
    return outline

def main():
    json_dir = Path(__file__).parent / 'original_reports'
    write_dir = Path(__file__).parent / 'filtered_attackseqs'
    write_dir.mkdir(exist_ok=True)
    attackseq_id = 1
    for json_file in json_dir.glob('*.json'):
        with open(json_file, 'r') as f:
            report_data = json.load(f)
        if not is_attackseq(report_data):
            continue
        report_data['rewrite'] = remove_empty_tactics(report_data)
        report_data['triplets'] = get_annotated_ttps(report_data)
        with open(write_dir / f"{attackseq_id}.json", "w") as f:
            json.dump(report_data, f, indent=4)
        attackseq_id += 1

        
if __name__ == "__main__":
    main()