import json
import csv
import random
from pathlib import Path

RANDOM_SEED = 56

MITRE_TACTICS = {
    "Reconnaissance", "Resource Development", "Initial Access", "Execution", "Persistence",
    "Privilege Escalation", "Defense Evasion", "Credential Access", "Discovery", "Lateral Movement",
    "Collection", "Command and Control", "Exfiltration", "Impact"
}

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

def main():
    input_dir = Path(__file__).parent / 'batch_output' / 'tactic'
    attackseq_dir = Path(__file__).parent / 'filtered_attackseqs'
    output_csv = Path(__file__).parent / 'dataset' / 'AttackSeq-Tactic.csv'
    csv_rows = []
    fieldnames = ['Question ID', 'AttackSeq ID', 'Batch ID', 'Question', 'A', 'B', 'C', 'D', 'Key Points', 'Context', 'Ground Truth', 'Source', 'Unshuffled Choices']
    for json_file in input_dir.rglob('*.jsonl'):
        response_data = []
        with open(json_file, 'r') as f:
            for line in f:
                response_data.append(json.loads(line))
        for line in response_data:
            custom_id = line.get('custom_id')
            attackseq_id, ground_truth = custom_id.split('-')
            with open(attackseq_dir / f"{attackseq_id}.json", 'r') as f:
                attackseq_data = json.load(f)
            report_name = attackseq_data['file_name']
            attackseq_tactics = [tactic for tactic in attackseq_data['rewrite'] if tactic != 'Others']
            outline = attackseq_data['rewrite']
            key_points = f"{ground_truth}: " + outline[ground_truth].replace('\n', ' ')
            index = attackseq_tactics.index(ground_truth)
            adjacent_tactics = []
            if index == 0:
                adjacent_tactics.append(attackseq_tactics[index + 1])
            elif index == len(attackseq_tactics) - 1:
                adjacent_tactics.append(attackseq_tactics[index - 1])
            else:
                adjacent_tactics.append(attackseq_tactics[index - 1])
                adjacent_tactics.append(attackseq_tactics[index + 1])
            question, answer = process_json_line(line)
            if not question:
                continue
            choice_a = ground_truth
            choice_b = random.choice(adjacent_tactics)
            remaining_tactics = list(set(MITRE_TACTICS) - {choice_a, choice_b})
            choice_c = random.choice(remaining_tactics) if remaining_tactics else random.choice(MITRE_TACTICS)
            remaining_tactics.remove(choice_c)
            choice_d = random.choice(remaining_tactics)
            choices = [choice_a, choice_b, choice_c, choice_d]
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
                'Context': mask_outline(outline, ground_truth),
                'Ground Truth': ground_truth,
                'Source': report_name,
                'Unshuffled Choices': ', '.join(choices)
            })
    sorted_rows = sorted(csv_rows, key=lambda x: x['AttackSeq ID'])
    with open(output_csv, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for i, row in enumerate(sorted_rows):
            writer.writerow({'Question ID': i + 1, **row})

if __name__ == "__main__":
    main()
