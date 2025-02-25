import json
import csv
import pandas as pd
from pathlib import Path

def process_json_line(line):
    message_content = line['response']['body']['choices'][0]['message']['content']
    lines = [line.strip() for line in message_content.split("\n")]
    qa_pairs = {}
    for line in lines:
        if "Answer:" not in line:
            continue
        question, answer = line.split('Answer:', 1)
        question_number, cleaned_question = question.split(':', 1)
        qa_pairs[int(question_number.replace("Question ", ""))] = (cleaned_question.strip(), answer.strip())
    return qa_pairs
    

def create_csv_rows(line, df):
    qa_pairs = process_json_line(line)
    if not qa_pairs:
        return None
    original_question_id = line.get('custom_id').split('-', 1)[0]
    row = df[df['Question ID'] == int(original_question_id)].iloc[0]
    csv_rows = []
    for question_number, qa_pair in qa_pairs.items():
        question, answer = qa_pair
        if question_number == 1:
            batch_id = row['Batch ID']
        else:
            batch_id = line.get('custom_id').rstrip(')')
        csv_row = {
            'AttackSeq ID': row['AttackSeq ID'],
            'Batch ID': batch_id,
            'Question': question,
            'Key Points': row['Key Points'],
            'Context': row['Context'],
            'Ground Truth': answer
        }
        csv_rows.append(csv_row)
    return csv_rows

def write_to_csv(csv_rows, output_csv, fieldnames):
    sorted_rows = sorted(csv_rows, key=lambda x: x['AttackSeq ID'])
    with open(output_csv, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for i, row in enumerate(sorted_rows):
            writer.writerow({'Question ID': i + 1, **row})
    print(f"Written to {output_csv}")

def main():
    input_dir = Path(__file__).parent / 'batch_output' / 'no_procedure'
    attackseqs_dir = Path(__file__).parent / 'filtered_attackseqs'
    yes_procedure_csv = Path(__file__).parent.parent / 'dataset' / 'good_AttackSeq-Procedure-Yes.csv'
    df = pd.read_csv(yes_procedure_csv)
    fieldnames = ['Question ID', 'AttackSeq ID', 'Batch ID','Question', 'Key Points', 'Context', 'Ground Truth']

    csv_rows = []
    response_data = []
    output_csv = Path(__file__).parent / 'dataset' / 'AttackSeq-Procedure-No.csv'
    for json_file in input_dir.glob('no_*.jsonl'):
        with open(json_file, 'r') as f:
            for line in f:
                response_data.append(json.loads(line))
    for line in response_data:
        rows = create_csv_rows(line, attackseqs_dir, df)
        if not rows:
            continue
        csv_rows.extend(rows)
    write_to_csv(csv_rows, output_csv, fieldnames)

if __name__ == "__main__":
    main()