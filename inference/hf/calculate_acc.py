from pathlib import Path
import pandas as pd
import re

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
    
    # 2) Look for something like "B: No" or "B: Yes" or just "B" or "Yes"/"No"
    # pattern_choices = re.compile(
    #     r'(?i)([A-D])\s*:?\s*(Yes|No)?|(Yes|No)'
    # )
    mcq_pattern_choices = re.compile(r'([A-D])')
    yesno_pattern_choices = r'(?:.*([A-B]).*|(Yes|No))'
    # print(final_answer_line) 
    if task_name.startswith("AttackSeq-Procedure"):
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

subtasks_total = {
    "AttackSeq-Tactic": 1697,
    "AttackSeq-Technique": 1917,
    "AttackSeq-Procedure-Yes": 1223,
    "AttackSeq-Procedure-No": 1412,
}

def main():
    results = {}
    outputs_dir = Path(__file__).parent / "outputs"
    dataset_dir = Path(__file__).parent.parent.parent / 'dataset'
    for task_dir in outputs_dir.iterdir():
        if not task_dir.is_dir():
            continue
        task_name = task_dir.stem
        for model_dir in task_dir.iterdir():
            if not model_dir.is_dir():
                continue
            model_name = model_dir.name
            if model_name not in results:
                results[model_name] = {}
            for subtask_name in subtasks_total.keys():
                invalid_count = 0
                valid_count = 0
                correct_count = 0
                df = pd.read_csv(dataset_dir / f"{subtask_name}.csv")
                if subtask_name not in results[model_name]:
                        results[model_name][subtask_name] = {}
                for txt_file in model_dir.rglob(f"{subtask_name}*.txt"):
                    with open(txt_file, "r") as fp:
                        data = fp.read()
                    question_id = txt_file.stem.split('-')[-1]
                    answer_option = extract_final_answer(data, subtask_name)
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
                accuracy = correct_count / subtasks_total[subtask_name] if valid_count > 0 else 0
                results[model_name][subtask_name][task_name] = {
                    "valid_count": valid_count,
                    "invalid_count": invalid_count,
                    "correct_count": correct_count,
                    "accuracy": float(f"{accuracy:.4g}")
                }
    for model_name, subtasks in results.items():
        if "AttackSeq-Procedure-Yes" in subtasks and "AttackSeq-Procedure-No" in subtasks:
            # Get the common task names between the two subtasks.
            common_tasks = set(subtasks["AttackSeq-Procedure-Yes"].keys()).intersection(subtasks["AttackSeq-Procedure-No"].keys())
            # Create or clear the aggregate subtask.
            results[model_name]["AttackSeq-Procedure-All"] = {}
            for task in common_tasks:
                valid_count = (subtasks["AttackSeq-Procedure-Yes"][task]["valid_count"] +
                               subtasks["AttackSeq-Procedure-No"][task]["valid_count"])
                invalid_count = (subtasks["AttackSeq-Procedure-Yes"][task]["invalid_count"] +
                                 subtasks["AttackSeq-Procedure-No"][task]["invalid_count"])
                correct_count = (subtasks["AttackSeq-Procedure-Yes"][task]["correct_count"] +
                                 subtasks["AttackSeq-Procedure-No"][task]["correct_count"])
                total_for_proc = subtasks_total["AttackSeq-Procedure-Yes"] + subtasks_total["AttackSeq-Procedure-No"]
                accuracy = correct_count / total_for_proc if total_for_proc > 0 else 0
                results[model_name]["AttackSeq-Procedure-All"][task] = {
                    "valid_count": valid_count,
                    "invalid_count": invalid_count,
                    "correct_count": correct_count,
                    "accuracy": float(f"{accuracy:.4g}")
                }
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
