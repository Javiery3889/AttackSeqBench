import json
import tiktoken
import asyncio
from dotenv import load_dotenv
import pandas as pd
from openai import OpenAI
from pathlib import Path
from prompts.get_eval_prompt import get_system_prompt
from load_mitre_kb import load_mitre_kb

def get_description(query, mitre_kb):
    for tactic in mitre_kb["tactics"]:
        if query == tactic["name"]:
            return tactic["description"]

        for technique in tactic["techniques"]:
            if query == technique["name"] or query == technique["id"]:
                return technique["description"]

            for sub_technique in technique.get("sub_techniques", []):
                if query == sub_technique["name"] or query == sub_technique["id"]:
                    return sub_technique["description"]
    return None


def get_distractors(row: pd.Series, task_name: str) -> str:
    if task_name.startswith("AttackSeq-Procedure"):
        if row['Ground Truth'] == "Yes":
            return "No"
        return "Yes"
    answer_choices = {row['A'], row['B'], row['C'], row['D']}
    answer_choices.remove(row['Ground Truth'])
    return ', '.join(answer_choices)


def prepare_batch_request(row, outline, ttp_description, task_name, criterion, masked_tactic):
    question_id = row['Question ID']
    question = row['Question']
    answer = row['Ground Truth']
    outline_string = "\n".join([f"{tactic}: {description}" for tactic, description in outline.items()])
    distractors = get_distractors(row, task_name)
    user_prompt = (
        f"CTI Outline: {outline_string}\n"
        f"Question: {question}\n"
        f"Correct Answer: {answer}\n"
        f"Distractors: {distractors}\n"
        f"Description to Correct Answer: {ttp_description}"
    )
    task_id = f"{task_name}_{question_id}_{criterion}"
    system_prompt = get_system_prompt(criterion, masked_tactic)
    task = {
        "custom_id": task_id,
        "method": "POST",
        "url": "/v1/chat/completions",
        "body": {
            "model": "gpt-4o-2024-11-20",
            "temperature": 0,
            "logprobs": True,
            "top_logprobs": 8,
            "max_completion_tokens": 5,
            "messages": [
                {"role": "developer", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        }
    }
    return task


async def poll_batch(client: OpenAI, batch_job, json_file: Path, batch_output_dir: Path):
    """
    Asynchronously poll the batch job until its status indicates completion.
    Once finished, download the output file and save it.
    """
    while True:
        # Retrieve the current batch status.
        batch_data = client.batches.retrieve(batch_job.id)
        batch_status = batch_data.status

        if batch_status in {"completed", "failed", "cancelled"}:
            print(f"Batch {json_file.name} finished, status: {batch_status}")
            break
        elif batch_status == "in_progress":
            total_requests = batch_data.request_counts.total
            completed_requests = batch_data.request_counts.completed
            print(f"Batch {json_file.name} in progress, {completed_requests}/{total_requests} requests completed")
        # Wait for 60 seconds before the next poll.
        await asyncio.sleep(60)
    
    # Retrieve the output file after the batch job is finished.
    batch_data = client.batches.retrieve(batch_job.id)
    batch_output_file_id = batch_data.output_file_id
    batch_output = client.files.content(batch_output_file_id).content
    output_path = batch_output_dir / f"{json_file.stem}_output.jsonl"
    with open(output_path, "wb") as f:
        f.write(batch_output)
    print(f"Batch output saved to {output_path}")


async def submit_batch_requests(client: OpenAI, batch_input_dir: Path, batch_output_dir: Path):
    """
    Submit each batch file for processing and create an async task to poll its progress.
    """
    poll_tasks = []
    for json_file in batch_input_dir.glob("*.jsonl"):
        # Submit the batch file.
        with open(json_file, "rb") as f:
            batch_file = client.files.create(
                file=f,
                purpose="batch"
            )
        print(f"Submitted batch file for processing: {batch_file.filename}")
        
        # Create a batch job using the submitted file.
        batch_job = client.batches.create(
            input_file_id=batch_file.id,
            endpoint="/v1/chat/completions",
            completion_window="24h",
            metadata={
                "description": "Batch of question feedback"
            }
        )
        # Create an asynchronous task to poll this batch job.
        task = asyncio.create_task(poll_batch(client, batch_job, json_file, batch_output_dir))
        poll_tasks.append(task)

    if poll_tasks:
        await asyncio.gather(*poll_tasks)

TOKEN_LIMIT = 3000000
def main():
    load_dotenv()
    client = OpenAI()
    enc = tiktoken.encoding_for_model("gpt-4o")
    batch_input_dir = Path(__file__).parent / 'batch_input'
    batch_output_dir = Path(__file__).parent / 'batch_output'
    batch_input_dir.mkdir(parents=True, exist_ok=True)
    batch_output_dir.mkdir(parents=True, exist_ok=True)
    dataset_dir = Path(__file__).parent.parent / 'dataset'
    att_seq_dir = Path(__file__).parent.parent / 'dataset_generation' / 'filtered_attackseqs'
    mitre_kb = load_mitre_kb()

    for csv_file in dataset_dir.glob("*.csv"):
        task_name = csv_file.stem
        if task_name == "AttackSeq-Procedure-No":
            criteria = ["Answer Consistency", "Answerability", "Clarity", "Consistency"]
        else:
            criteria = ["Answer Consistency", "Answerability", "Clarity", "Consistency", "Logical", "Relevance"]
        df = pd.read_csv(csv_file)
        for index, row in df.iterrows():
            if task_name == "AttackSeq-Tactic":
                query = row['Batch ID'].split('-', 1)[1]
                masked_tactic = query
                description = get_description(query, mitre_kb)
                ttp_description = f"Tactic: {masked_tactic}, Description: {description}"
            else:
                _, masked_tactic, technique = row['Batch ID'].split('-', 2)
                query = technique.split('-', 1)[0]
                description = get_description(query, mitre_kb)
                ttp_description = f"Tactic: {masked_tactic}, Technique: {technique}, Description: {description}"
                if ttp_description is None:
                    print(f"Could not find description for {query}")
            attackseq_id = row['AttackSeq ID']
            with open(att_seq_dir / f"{attackseq_id}.json", 'r') as f:
                att_seq_data = json.load(f)
            cti_outline = att_seq_data['rewrite']
            for criterion in criteria:
                token_count = 0
                batch_count = 0
                jsonl_line = prepare_batch_request(row, cti_outline, ttp_description, task_name, criterion, masked_tactic)
                token_count += len(enc.encode(str(jsonl_line)))
                if token_count >= TOKEN_LIMIT:
                    batch_count += 1
                    token_count = 0
                with open(batch_input_dir / f"{task_name}_{criterion}_{batch_count}.jsonl", "a") as f:
                    f.write(json.dumps(jsonl_line) + '\n')

    # Asynchronously submit all batch requests and poll for their completion.
    asyncio.run(submit_batch_requests(client, batch_input_dir, batch_output_dir))

if __name__ == "__main__":
    main()
