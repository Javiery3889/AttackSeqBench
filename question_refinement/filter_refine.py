import json
import pandas as pd
from pathlib import Path

def main(round_number=0):
    input_dir = Path(__file__).parent / 'dataset' / f'round_{round_number}'
    output_dir = Path(__file__).parent / 'dataset' / f'round_{round_number + 1}'
    output_dir.mkdir(parents=True, exist_ok=True)

    tasks = ["AttackSeq-Tactic", "AttackSeq-Technique", "AttackSeq-Procedure-Yes"]
    for task in tasks:
        output_file = output_dir / f"{task}.csv"
        refined_questions = {}
        batch_output_dir = Path(__file__).parent / 'batch_output' / f'round_{round_number}' /'refine'
        for json_file in batch_output_dir.glob(f"{task}*.jsonl"):
            with open(json_file, 'r') as f:
                data = [json.loads(line) for line in f]
            for jsonl_line in data:
                question_id = int(jsonl_line.get('custom_id').split('_')[1])
                response = jsonl_line['response']['body']['choices'][0]['message']['content']
                if "Refined Question:" not in response:
                    continue
                refined_question = response.split('Refined Question:')[1].strip()
                refined_questions[question_id] = refined_question
        df = pd.read_csv(input_dir / f"torefine_{task}.csv")

        df["Feedback"] = df.apply(
            lambda row: f"Original Question: {row['Question']} {row['Feedback']}",
            axis=1
        )

        df["Question"] = df.apply(
            lambda row: refined_questions.get(int(row["Question ID"]), row["Question"]),
            axis=1
        )

        df.to_csv(output_file, index=False)