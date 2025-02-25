import json
from pathlib import Path
from collections import defaultdict

attackseq_dir = Path(__file__).parent / 'filtered_attackseqs'
write_dir = Path(__file__).parent / 'grouped_attackseqs'
write_dir.mkdir(exist_ok=True)

for json_file in attackseq_dir.glob('*.json'):
    grouped_by_tactic = defaultdict(lambda: defaultdict(list))
    with open(json_file, 'r') as f:
        data = json.load(f)
    for event in data['triplets']:
        if event['tactic'] == "Others":
            continue
        for technique in event['technique']:
            if technique == "Others":
                continue
            grouped_by_tactic[event['tactic']][technique].append(event)

    for tactic in grouped_by_tactic:
        for technique in grouped_by_tactic[tactic]:
            grouped_by_tactic[tactic][technique].sort(key=lambda x: x['id'])
    
    del data["triplets"]
    data["triplet_groups"] = grouped_by_tactic
    with open(write_dir / json_file.name, "w") as f:
        json.dump(data, f, indent=4)