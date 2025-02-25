import json
import pandas as pd
from pathlib import Path

def main(round_number=0):
    dataset_dir = Path(__file__).parent / 'dataset' / f'round_{round_number}'
    dataset_dir.mkdir(parents=True, exist_ok=True)

    tasks = ["AttackSeq-Tactic", "AttackSeq-Technique", "AttackSeq-Procedure-Yes"]

    for task in tasks:
        output_file = dataset_dir / f"filtered_{task}.csv"
        question_ids = set()
        batch_output_dir = Path(__file__).parent / 'batch_output' / f'round_{round_number}' / 'answerability'
        for json_file in batch_output_dir.glob(f"{task}*.jsonl"):
            with open(json_file, 'r') as f:
                data = [json.loads(line) for line in f]
            for jsonl_line in data:
                question_id = jsonl_line.get('custom_id').split('_')[1]
                response = jsonl_line['response']['body']['choices'][0]['message']['content']
                if "Evaluation Result:" not in response:
                    continue
                answer = response.split('Evaluation Result:')[1].strip()
                if answer != 'A':
                    continue
                question_ids.add(int(question_id))
        df = pd.read_csv(dataset_dir / f"{task}.csv")
        filtered_df = df[df['Question ID'].isin(question_ids)]
        print("{}: {} -> {}".format(task, len(df), len(filtered_df)))
        with open(output_file, 'w') as f:
            filtered_df.to_csv(f, index=False)
    
if __name__ == "__main__":
    main()