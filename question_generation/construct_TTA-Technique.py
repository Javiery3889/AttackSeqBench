import json
import csv
import random
from pathlib import Path
from load_mitre_kb import load_mitre_kb

def get_techniques_in_chosen_tactic(chosen_tactic, attackseq_techniques, choices, mitre_kb):
    attackseq_techniques_in_chosen_tactic = attackseq_techniques[chosen_tactic].keys()
    techniques = []
    for tactic in mitre_kb['tactics']:
        if tactic['name'] != chosen_tactic:
            continue
        for technique in tactic['techniques']:
            technique_name = technique['name']
            technique_id = technique['id']
            if technique_id in attackseq_techniques_in_chosen_tactic or technique_id in choices:
                continue
            techniques.append(f"{technique_id}-{technique_name}")
            # Check for sub-techniques
            if 'sub_techniques' in technique:
                for sub_technique in technique['sub_techniques']:
                    sub_technique_name = sub_technique['name']
                    sub_technique_id = sub_technique['id']
                    if sub_technique_id in attackseq_techniques_in_chosen_tactic or sub_technique_id in choices:
                        continue
                    techniques.append(f"{sub_technique_id}-{sub_technique_name}")
    return techniques

def get_all_techniques_not_in_attackseq_techniques(attackseq_techniques, choices, mitre_kb):
    techniques = []
    for tactic in mitre_kb['tactics']:
        if tactic['name'] in attackseq_techniques:
            attackseq_techniques_in_tactic = attackseq_techniques.get(tactic['name']).keys()
        for technique in tactic['techniques']:
            technique_name = technique['name']
            technique_id = technique['id']
            if technique_id in attackseq_techniques_in_tactic or technique_id in choices:
                continue
            techniques.append(f"{technique_id}-{technique_name}")
            # Check for sub-techniques
            if 'sub_techniques' in technique:
                for sub_technique in technique['sub_techniques']:
                    sub_technique_name = sub_technique['name']
                    sub_technique_id = sub_technique['id']
                    if sub_technique_id in attackseq_techniques_in_tactic or sub_technique_id in choices:
                        continue
                    techniques.append(f"{sub_technique_id}-{sub_technique_name}")
    return techniques

def get_attackseq_techniques_not_in_chosen_tactic(attackseq_techniques, chosen_tactic, choices):
    techniques = []
    for tactic, techniques_dict in attackseq_techniques.items():
        if tactic == chosen_tactic:
            continue
        for technique in techniques_dict:
            if technique in choices:
                continue
            techniques.append(technique)
    if not techniques:
        return None
    return techniques

def mask_outline(outline, tactic_to_mask):
    masked_outline = []
    for tactic, description in outline.items():
        if tactic == tactic_to_mask:
            continue
        description = description.replace('\n', ' ')
        masked_outline.append(f"{tactic}: {description}")
    return "\n".join(masked_outline)

def process_json_line(line):
    message_content = line['response']['body']['choices'][0]['message']['content']
    if "Answer:" not in message_content:
        return None, None
    question, answer = message_content.split('Answer:')
    question = question.replace('Question:', '').strip()
    answer = answer.strip()
    return question, answer

RANDOM_SEED = 56
def main():
    random.seed(RANDOM_SEED)
    input_dir = Path(__file__).parent / 'batch_output' / 'technique'
    attackseq_dir = Path(__file__).parent / 'grouped_attackseqs'
    output_csv = Path(__file__).parent / 'dataset' / 'AttackSeq-Technique.csv'
    mitre_kb = load_mitre_kb()
    csv_rows = []
    response_data = []
    for json_file in input_dir.rglob('*.jsonl'):
        with open(json_file, 'r') as f:
            for line in f:
                response_data.append(json.loads(line))
    for line in response_data:
        custom_id = line.get('custom_id')
        attackseq_id, triplet_tactic, ground_truth = custom_id.split('-', 2)
        with open(attackseq_dir / f"{attackseq_id}.json", 'r') as f:
            attackseq_data = json.load(f)
        report_name = attackseq_data['file_name']
        outline = attackseq_data['rewrite']
        attackseqs_techniques = attackseq_data['triplet_groups']
        question, answer = process_json_line(line)
        if not question:
            continue
        key_points = f"{triplet_tactic}: " + outline[triplet_tactic].replace('\n', ' ')
        choices = [ground_truth]
        choice_b = random.choice(get_techniques_in_chosen_tactic(triplet_tactic, attackseqs_techniques, choices, mitre_kb))
        choices.append(choice_b)
        remaining_techniques = get_attackseq_techniques_not_in_chosen_tactic(attackseqs_techniques, triplet_tactic, choices)
        if not remaining_techniques:
            choice_c = random.choice(get_all_techniques_not_in_attackseq_techniques(attackseqs_techniques, choices, mitre_kb))
        else:
            choice_c = random.choice(remaining_techniques)
        choices.append(choice_c)
        choice_d = random.choice(get_all_techniques_not_in_attackseq_techniques(attackseqs_techniques, choices, mitre_kb))
        choices.append(choice_d)
        random_choices = random.sample(choices, len(choices))
        csv_rows.append({
            'AttackSeq ID': attackseq_id,
            'Batch ID': custom_id,
            'Question': question,
            'A': random_choices[0],
            'B': random_choices[1],
            'C': random_choices[2],
            'D': random_choices[3],
            'Key Points': key_points,
            'Context': mask_outline(outline, triplet_tactic),
            'Ground Truth': ground_truth,
            'Source': report_name,
            'Unshuffled Choices': ', '.join(choices)
        })
    sorted_rows = sorted(csv_rows, key=lambda x: x['AttackSeq ID'])
    with open(output_csv, 'w', newline='') as csvfile:
        fieldnames = ['Question ID', 'AttackSeq ID', 'Batch ID', 'Question', 'A', 'B', 'C', 'D', 'Key Points', 'Context', 'Ground Truth', 'Source', 'Unshuffled Choices']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for i, row in enumerate(sorted_rows):
            writer.writerow({'Question ID': i + 1, **row})

if __name__ == "__main__":
    main()