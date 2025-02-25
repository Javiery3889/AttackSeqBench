import pandas as pd
import tiktoken
import json
import time
from dotenv import load_dotenv
from openai import OpenAI
from pathlib import Path
from pydantic import BaseModel
from prompts.zero_shot_prompt import system_prompt

TOKEN_LIMIT = 2000000
def prepare_batch_request(row: pd.Series, task_name: str, model_name: str):
    question = row["Question"]
    question_id = row["Question ID"]
    if "AttackSeq-Procedure" in task_name:
        answer_choices = {"A": "Yes", "B": "No"}
    else:
        answer_choices = {}
        for answer_choice in ["A", "B", "C", "D"]:
            answer_choices[answer_choice] = row[answer_choice]
    answer_choices_string = "\n".join([f"{choice}: {answer}" for choice, answer in answer_choices.items()])
    user_prompt = f"Question: {question}\nAnswer Choices: {answer_choices_string}"
    if model_name == "o3-mini-2025-01-31":
        task = {
            "custom_id": f"zeroshot_{task_name}_{question_id}",
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": {
                "model": model_name,
                "max_completion_tokens": 2048,
                "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ]
            }
        }
    else:
        task = {
            "custom_id": f"zeroshot_{task_name}_{question_id}",
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": {
                "model": model_name,
                "temperature": 0,
                "max_completion_tokens": 2048,
                "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ]
            }
        }
    return task
            
def submit_batch_request(client: OpenAI, batch_inputs_dir: Path, batch_outputs_dir: Path):
    for json_file in batch_inputs_dir.glob("remaining.jsonl"):
        batch_file = client.files.create(
            file=open(json_file, "rb"),
            purpose="batch"
        )
        print(f"Submitted batch file for processing: {batch_file.filename}")
        batch_file_id = batch_file.id
        batch_job = client.batches.create(
            input_file_id=batch_file_id,
            endpoint="/v1/chat/completions",
            completion_window="24h",
            metadata={
                "description": "Batch of evalaution questions for GPT-4o"
            }
        )
        while True:
            batch_status = client.batches.retrieve(batch_job.id).status
            if batch_status == "completed" or batch_status == "failed" or batch_status == "cancelled":
                print(f"Batch {batch_file.filename} finished, status: {batch_status}")
                break
            elif batch_status == "in_progress":
                total_requests = client.batches.retrieve(batch_job.id).request_counts.total
                completed_requests = client.batches.retrieve(batch_job.id).request_counts.completed
                print(f"Batch {batch_file.filename} in progress, {completed_requests}/{total_requests} requests completed")
            time.sleep(60)
        batch_output_file_id = client.batches.retrieve(batch_job.id).output_file_id
        batch_output = client.files.content(batch_output_file_id).content
        with open(batch_outputs_dir / f"{json_file.stem}_output.jsonl", "wb") as f:
            f.write(batch_output)
        print(f"Batch output saved to {batch_outputs_dir / f'{json_file.stem}_output.jsonl'}")

def main():
    load_dotenv()
    client = OpenAI()
    model_name = "gpt-4o-mini"
    # model_name = "gpt-4o-2024-11-20"
    # model_name = "o3-mini-2025-01-31"
    enc = tiktoken.encoding_for_model("gpt-4o")
    batch_inputs_dir = Path(__file__).parent / 'batch_jobs' / 'zero_shot' / 'batch_inputs' / model_name
    batch_outputs_dir = Path(__file__).parent / 'batch_jobs' /  'zero_shot' / 'batch_outputs' / model_name
    batch_outputs_dir.mkdir(parents=True, exist_ok=True)
    batch_inputs_dir.mkdir(parents=True, exist_ok=True)
    dataset_dir = Path(__file__).parent.parent.parent / 'dataset'
    for csv_file in dataset_dir.glob("*.csv"):
        token_count = 0
        batch_count = 0
        task_name = csv_file.stem
        df = pd.read_csv(csv_file)
        for index, row in df.iterrows():
            task = prepare_batch_request(row, task_name, model_name)
            token_count += len(enc.encode(str(task)))
            if token_count >= TOKEN_LIMIT:
                batch_count += 1
                token_count = 0
            with open(batch_inputs_dir / f"{task_name}_{batch_count}.jsonl", "a") as f:
                f.write(json.dumps(task) + '\n')
    submit_batch_request(client, batch_inputs_dir, batch_outputs_dir)

if __name__ == "__main__":
    main()