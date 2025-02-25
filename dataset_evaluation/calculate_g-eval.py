import json
from pathlib import Path
import pandas as pd
import math

output_dir = Path(__file__).parent / 'batch_output'
g_eval_output_dir = Path(__file__).parent / 'g_eval_scores'
g_eval_output_dir.mkdir(parents=True, exist_ok=True)

scores_by_task = {}

for json_file in output_dir.glob('*.jsonl'):
    task, criteria, _ = json_file.stem.split('_', 2)
    if task not in scores_by_task:
        scores_by_task[task] = {}
    with open(json_file, 'r') as f:
        data = [json.loads(line) for line in f]
    
    for jsonl_line in data:
        weights = dict.fromkeys(["1", "2", "3", "4", "5"], 0)
        _, question_id, _ = jsonl_line.get('custom_id').split('_', 2)
        logprobs = jsonl_line['response']['body']['choices'][0]['logprobs']['content']
        for token_info in logprobs:
            top_logprobs = token_info.get('top_logprobs')
            for token in top_logprobs:
                weight = token['token']
                prob = math.exp(token['logprob'])
                if weight in weights:
                    weights[weight] = prob
        score = sum(int(w) * p for w, p in weights.items())
        if question_id not in scores_by_task[task]:
            scores_by_task[task][question_id] = {}
        scores_by_task[task][question_id][criteria] = score
for task, questions in scores_by_task.items():
    if task != "AttackSeq-Procedure-No":
        columns = ["Answerability", "Clarity", "Logical", "Relevance", "Consistency", "Answer Consistency"]
    else:
        columns = ["Answerability", "Clarity", "Consistency", "Answer Consistency"]
    df = pd.DataFrame.from_dict(questions, orient='index')
    df = df.reset_index().rename(columns={'index': 'Question ID'})
    sorted_columns = ['Question ID'] + columns
    df = df[sorted_columns]
    output_file = g_eval_output_dir / f"{task}_scores.csv"
    df.to_csv(output_file, index=False)
    print(f"Saved scores CSV for {task} to {output_file}")