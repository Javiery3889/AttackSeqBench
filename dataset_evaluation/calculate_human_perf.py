from pathlib import Path
import pandas as pd

def main():
    csv_dir = Path(__file__).parent / 'human_perf_scores'
    ref_dir = Path(__file__).parent / 'sampled_questions'
    tasks = ["Tactic", "Technique", "Procedure-Yes", "Procedure-No"]

    overall_sum = 0
    overall_tasks = 0

    for task in tasks:
        ref_df = pd.read_csv(ref_dir / f"sampled_{task}.csv")
        task_csvs = [csv_file for csv_file in csv_dir.glob(f"{task}*.csv")]
        eval1_df = pd.read_csv(task_csvs[0])
        eval2_df = pd.read_csv(task_csvs[1])

        assert len(eval1_df) == len(eval2_df)

        correct_answers = ref_df["Ground Truth"]
        if task in ["Tactic", "Technique"]:
            # For these tasks, "Answer" indicates a column name that holds the chosen value.
            eval1_chosen_vals = eval1_df.apply(lambda row: row[row["Answer"]], axis=1)
            eval2_chosen_vals = eval2_df.apply(lambda row: row[row["Answer"]], axis=1)
            eval1_correct = (eval1_chosen_vals == correct_answers).sum()
            eval2_correct = (eval2_chosen_vals == correct_answers).sum()
        else:
            # For the other tasks, compare the "Answer" column directly.
            eval1_correct = (eval1_df["Answer"] == correct_answers).sum()
            eval2_correct = (eval2_df["Answer"] == correct_answers).sum()
            
        eval1_acc = eval1_correct / len(eval1_df)
        eval2_acc = eval2_correct / len(eval2_df)
        avg_acc = (eval1_acc + eval2_acc) / 2
        
        overall_sum += avg_acc
        overall_tasks += 1
        
        print(f"Task {task}: Evaluator 1: {eval1_acc:.4f}, Evaluator 2: {eval2_acc:.4f}, Avg: {avg_acc:.4f}")

    overall_avg = overall_sum / overall_tasks if overall_tasks > 0 else 0
    print(f"\nOverall average accuracy among all tasks: {overall_avg:.4f}")


if __name__ == "__main__":
    main()