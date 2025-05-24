import pandas as pd
from pathlib import Path

raw_dir = Path(__file__).parent / 'human_eval_scores'

tasks = ["Tactic", "Technique", "Procedure-Yes", "Procedure-No"]

for task in tasks:
    csv_files = list(raw_dir.glob(f"{task}_Expert*.csv"))
    eval1_df = pd.read_csv(csv_files[0])
    eval2_df = pd.read_csv(csv_files[1])
    eval3_df = pd.read_csv(csv_files[2])
    if task != "Procedure-No":
        columns = ["Answerability", "Clarity", "Logical", "Relevance", "Consistency", "Answer Consistency"]
    else:
        columns = ["Answerability", "Clarity", "Consistency", "Answer Consistency"]
        
    merged_df = pd.merge(eval1_df, eval2_df, on="Question ID", suffixes=('_Eval1', '_Eval2'))
    merged_df = pd.merge(merged_df, eval3_df, on="Question ID")
    for column in columns:
        merged_df.rename(columns={column: column + "_Eval3"}, inplace=True)
    for column in columns:
       merged_df[column + "_Avg"] = merged_df[[column + "_Eval1", column + "_Eval2", column + "_Eval3"]].mean(axis=1)
    overall_avg = merged_df[[col + "_Avg" for col in columns]].mean()
    print(f"Average Likert Scale Scores Across three evaluators for {task}:\n")
    print(overall_avg.round(4))