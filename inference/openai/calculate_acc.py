import json
import re
import pandas as pd
from pathlib import Path

def extract_final_answer(text: str, task_name: str) -> str:

    final_answer_line_pattern = re.compile(
        r'(?i)(final answer.*:.*|plausible answer.*:.*|correct answer.*:.*|[A-D]:.*)',
        re.MULTILINE
    )
    
    matches = final_answer_line_pattern.findall(text)
    if not matches:
        return None
    
    # Pick last occurrence.
    final_answer_line = matches[-1].split(":",1)[1].strip()
    
    # 1) Check for \boxed{A-D}
    pattern_boxed = re.compile(r'\\boxed\s*\{([A-D])\}', re.IGNORECASE)
    match_boxed = pattern_boxed.search(final_answer_line)
    if match_boxed:
        return match_boxed.group(1).upper()
    
    mcq_pattern_choices = re.compile(r'([A-D])')
    yesno_pattern_choices = r'(?:.*([A-B]).*|(Yes|No))'
    if task_name.startswith("TTA-Procedure"):
        match = re.match(yesno_pattern_choices, final_answer_line)
        if match:
            letter = match.group(1)
            if letter:
                if letter == "A":
                    return "Yes"
                return "No"
            yes_no = match.group(2)
            if yes_no:
               return yes_no
        return None
    match = mcq_pattern_choices.findall(final_answer_line)
    if match:
        letter = match[0]
        return letter.upper()
    return None

tasks_total = {
    "AttackSeq-Tactic": 1697,
    "AttackSeq-Technique": 1917,
    "AttackSeq-Procedure-Yes": 1223,
    "Attackseq-Procedure-No": 1412,
}

def main():
    results = {}
    dataset_dir = Path(__file__).parent.parent.parent / 'dataset'
    batch_dir = Path(__file__).parent / 'batch_jobs'
    
    # Process each task directory and assign result for each subtask under the model.
    for task_dir in batch_dir.glob("**/batch_outputs"):
        task_name = task_dir.parent.name
        for model_dir in task_dir.iterdir():
            if not model_dir.is_dir():
                continue
            model_name = model_dir.name
            if model_name not in results:
                results[model_name] = {}
            for subtask in tasks_total.keys():
                invalid_count = 0
                valid_count = 0
                correct_count = 0
                for json_file in model_dir.glob(f"{subtask}*.jsonl"):
                    subtask_name = json_file.stem.split('_')[0]  # assumed to equal subtask
                    # Initialize dictionary for this subtask if needed.
                    if subtask_name not in results[model_name]:
                        results[model_name][subtask_name] = {}
                    df = pd.read_csv(dataset_dir / f"{subtask_name}.csv")
                    jsonl_lines = []
                    with open(json_file, 'r') as f:
                        for line in f:
                            jsonl_lines.append(json.loads(line))
                    for line in jsonl_lines:
                        question_id = line['custom_id'].split('_')[-1]
                        response = line['response']['body']['choices'][0]['message']['content']
                        answer_option = extract_final_answer(response, subtask_name)
                        if not answer_option:
                            invalid_count += 1
                            continue
                        valid_count += 1
                        answer_option = answer_option.strip()
                        row = df.loc[df['Question ID'] == int(question_id)]
                        if subtask_name.startswith("AttackSeq-Procedure"):
                            answer = answer_option
                        else:
                            answer = row[answer_option].values[0]
                        if answer == row['Ground Truth'].values[0]:
                            correct_count += 1
                accuracy = correct_count / tasks_total[subtask_name] if valid_count > 0 else 0
                results[model_name][subtask_name][task_name] = {
                    "valid_count": valid_count,
                    "invalid_count": invalid_count,
                    "correct_count": correct_count,
                    "accuracy": float(f"{accuracy:.4g}")
                }
    for model_name, subtasks in results.items():
        if "AttackSeq-Procedure-Yes" in subtasks and "AttackSeq-Procedure-No" in subtasks:
            # Get the common task names between the two subtasks.
            common_tasks = set(subtasks["TTA-Procedure-Yes"].keys()).intersection(subtasks["TTA-Procedure-No"].keys())
            # Create or clear the aggregate subtask.
            results[model_name]["AttackSeq-Procedure-All"] = {}
            for task in common_tasks:
                valid_count = (subtasks["AttackSeq-Procedure-Yes"][task]["valid_count"] +
                               subtasks["AttackSeq-Procedure-No"][task]["valid_count"])
                invalid_count = (subtasks["AttackSeq-Procedure-Yes"][task]["invalid_count"] +
                                 subtasks["AttackSeq-Procedure-No"][task]["invalid_count"])
                correct_count = (subtasks["AttackSeq-Procedure-Yes"][task]["correct_count"] +
                                 subtasks["AttackSeq-Procedure-No"][task]["correct_count"])
                total_for_proc = tasks_total["AttackSeq-Procedure-Yes"] + tasks_total["AttackSeq-Procedure-No"]
                accuracy = correct_count / total_for_proc if total_for_proc > 0 else 0
                results[model_name]["AttackSeq-Procedure-All"][task] = {
                    "valid_count": valid_count,
                    "invalid_count": invalid_count,
                    "correct_count": correct_count,
                    "accuracy": float(f"{accuracy:.4g}")
                }
    # Order the keys (i.e. the subtasks) based on the required order.
    ordered_subtask_order = ["AttackSeq-Tactic", "AttackSeq-Technique", "AttackSeq-Procedure-All"]
    for model_name, subtask_data in results.items():
        ordered_subtasks = {key: subtask_data[key] for key in ordered_subtask_order if key in subtask_data}
        results[model_name] = ordered_subtasks
    ordered_tasks = ["regular", "zero_shot", "rag"]
    for model_name, subtasks in results.items():
        output_fields = [model_name]
        for subtask in ordered_subtask_order:
            if subtask in subtasks:
                # Reorder task entries by the ordered_tasks.
                tasks = subtasks[subtask]
                ordered_task_entries = {task: tasks[task] for task in ordered_tasks if task in tasks}
                for task in ordered_tasks:
                    if task in ordered_task_entries:
                        stats = ordered_task_entries[task]
                        output_fields.append(str(stats["accuracy"]))
        print(" & ".join(output_fields))

if __name__ == "__main__":
    main()