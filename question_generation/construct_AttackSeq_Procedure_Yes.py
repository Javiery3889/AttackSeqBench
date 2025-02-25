import json
import csv
from pathlib import Path

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

def create_csv_row(line, attackseqs_dir):
    custom_id = line.get('custom_id')
    attackseq_id, tactic, _ = custom_id.split('-', 2)
    with open(attackseqs_dir / f"{attackseq_id}.json", 'r') as f:
        attackseq_data = json.load(f)
    report_name = attackseq_data['file_name']
    outline = attackseq_data['rewrite']
    question, answer = process_json_line(line)
    if not question:
        return None
    key_points = f"{tactic}: " + outline[tactic].replace('\n', ' ')
    csv_row = {
        'AttackSeq ID': attackseq_id,
        'Batch ID': custom_id,
        'Question': question,
        'Key Points': key_points,
        'Context': mask_outline(outline, tactic),
        'Ground Truth': answer,
        'Source': report_name
    }
    return csv_row

def write_to_csv(csv_rows, output_csv, fieldnames):
    sorted_rows = sorted(csv_rows, key=lambda x: x['AttackSeq ID'])
    with open(output_csv, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for i, row in enumerate(sorted_rows):
            writer.writerow({'Question ID': i + 1, **row})
    print(f"Written to {output_csv}")

def main():
    input_dir = Path(__file__).parent / 'batch_output' / 'yes_procedure'
    attackseqs_dir = Path(__file__).parent / 'filtered_attackseqs'
    fieldnames = ['Question ID', 'AttackSeq ID', 'Batch ID','Question', 'Key Points', 'Context', 'Ground Truth', 'Source']
    csv_rows = []
    response_data = []
    output_csv = Path(__file__).parent / 'dataset' / 'AttackSeq-Procedure-Yes.csv'
    for json_file in input_dir.glob('yes_*.jsonl'):
        with open(json_file, 'r') as f:
            for line in f:
                response_data.append(json.loads(line))
    for line in response_data:
        csv_row = create_csv_row(line, attackseqs_dir)
        if csv_row:
            csv_rows.append(csv_row)
    write_to_csv(csv_rows, output_csv, fieldnames)

if __name__ == "__main__":
    main()