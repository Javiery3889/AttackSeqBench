import json
import csv
import pandas as pd
from pathlib import Path

def main(round_number=0):
    dataset_dir = Path(__file__).parent / 'dataset'

    tasks = ["AttackSeq-Tactic", "AttackSeq-Technique", "AttackSeq-Procedure-Yes"]
    batch_output_dir = Path(__file__).parent / 'batch_output' / f'round_{round_number}' / 'feedback'

    for task in tasks:
        question_ids = set()
        feedback_responses = {}
        df = pd.read_csv(dataset_dir / f"round_{round_number}" / f"filtered_{task}.csv")
        if round_number > 0:
            df = df.drop(columns=['Feedback'], errors='ignore')
        filtered_output_file = dataset_dir / f"good_{task}.csv"
        refine_output_file = dataset_dir / f"round_{round_number}" / f"torefine_{task}.csv"

        for json_file in batch_output_dir.glob(f"filtered_{task}*.jsonl"):

            with open(json_file, 'r') as f:
                data = [json.loads(line) for line in f]

            for jsonl_line in data:
                question_id = jsonl_line.get('custom_id').split('_')[1]
                question_id = int(question_id)  # **Ensure it's an integer**
                response = jsonl_line['response']['body']['choices'][0]['message']['content']

                if "Total Score" not in response:
                    continue

                feedback_responses[question_id] = response  # Store feedback
                answer = response.split('Total Score')[1].strip()
                if task == "TTA-Procedure-No":
                    criteria = "15/15"
                else:
                    criteria = "25/25"
                if not criteria in answer:
                    continue

                question_ids.add(question_id)

        # **Create copies to avoid SettingWithCopyWarning**
        filtered_df = df[df['Question ID'].isin(question_ids)].copy()
        excluded_df = df[~df['Question ID'].isin(question_ids)].copy()

        excluded_df = excluded_df[excluded_df['Question ID'].isin(feedback_responses.keys())].copy()

        # **Fix 1: Ensure all question IDs map correctly**
        excluded_df['Feedback'] = excluded_df['Question ID'].map(feedback_responses)

        print("{}: {} -> {}".format(task, len(df), len(filtered_df)))

        header_flag = not filtered_output_file.exists()
        filtered_df.to_csv(filtered_output_file, mode='a', header=header_flag, index=False)

    excluded_df.to_csv(refine_output_file, mode='w', index=False, header=True, quoting=csv.QUOTE_ALL)

if __name__ == "__main__":
    main()
