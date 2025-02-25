import json
import tiktoken
import asyncio
from dotenv import load_dotenv
import pandas as pd
from openai import OpenAI
from pathlib import Path
from prompts.answerability import system_prompt
from load_mitre_kb import load_mitre_kb

def get_distractors(row: pd.Series, task_name: str) -> str:
    if task_name.startswith("AttackSeq-Procedure"):
        if row['Ground Truth'] == "Yes":
            return "No"
        return "Yes"
    answer_choices = {row['A'], row['B'], row['C'], row['D']}
    answer_choices.remove(row['Ground Truth'])
    return ', '.join(answer_choices)


def get_description(query, data):
    for tactic in data["tactics"]:
        if query == tactic["name"]:
            return tactic["description"]

        for technique in tactic["techniques"]:
            if query == technique["name"] or query == technique["id"]:
                return technique["description"]

            for sub_technique in technique.get("sub_techniques", []):
                if query == sub_technique["name"] or query == sub_technique["id"]:
                    return sub_technique["description"]
    return None


def prepare_batch_request(row, outline, ttp_description, masked_tactic, task_name):
    question_id = row['Question ID']
    question = row['Question']
    answer = row['Ground Truth']
    outline_string = "\n".join([f"{tactic}: {description}" for tactic, description in outline.items()])
    disstractors = get_distractors(row, task_name)
    user_prompt = (
        f"CTI Outline: {outline_string}\n"
        f"TTP Description: {ttp_description}\n"
        f"Question: {question}\n"
        f"Correct Answer: {answer}\n"
        f"Distractors: {disstractors}"
    )
    task_id = f"{task_name}_{question_id}"
    task = {
        "custom_id": task_id,
        "method": "POST",
        "url": "/v1/chat/completions",
        "body": {
            "model": "gpt-4o-2024-11-20",
            "max_completion_tokens": 1024,
            "messages": [
                {"role": "system", "content": system_prompt.format(masked_tactic=masked_tactic)},
                {"role": "user", "content": user_prompt}
            ]
        }
    }
    return task


async def poll_batch(client: OpenAI, batch_job, json_file: Path, batch_output_dir: Path):
    """Asynchronously poll the batch job until it finishes, then download and save its output."""
    while True:
        # Retrieve the batch status
        batch_data = client.batches.retrieve(batch_job.id)
        batch_status = batch_data.status

        if batch_status in {"completed", "failed", "cancelled"}:
            print(f"Batch {json_file.name} finished, status: {batch_status}")
            break
        elif batch_status == "in_progress":
            total_requests = batch_data.request_counts.total
            completed_requests = batch_data.request_counts.completed
            print(f"Batch {json_file.name} in progress, {completed_requests}/{total_requests} requests completed")
        # Wait for 60 seconds before checking again
        await asyncio.sleep(60)

    # Once finished, retrieve the output file
    batch_data = client.batches.retrieve(batch_job.id)
    batch_output_file_id = batch_data.output_file_id
    batch_output = client.files.content(batch_output_file_id).content
    output_path = batch_output_dir / f"{json_file.stem}.jsonl"
    with open(output_path, "wb") as f:
        f.write(batch_output)
    print(f"Batch output saved to {output_path}")


async def submit_batch_requests(client: OpenAI, batch_input_dir: Path, batch_output_dir: Path):
    """Submit each batch file and asynchronously poll for the results."""
    poll_tasks = []
    # Iterate over each batch input file
    for json_file in batch_input_dir.glob("AttackSeq-Tactic*.jsonl"):
        # Submit the batch file for processing
        with open(json_file, "rb") as f:
            batch_file = client.files.create(
                file=f,
                purpose="batch"
            )
        print(f"Submitted batch file for processing: {batch_file.filename}")

        batch_file_id = batch_file.id
        batch_job = client.batches.create(
            input_file_id=batch_file_id,
            endpoint="/v1/chat/completions",
            completion_window="24h",
            metadata={
                "description": "Batch of question verification (Answerability)"
            }
        )

        # Create an asynchronous task to poll the batch job
        task = asyncio.create_task(poll_batch(client, batch_job, json_file, batch_output_dir))
        poll_tasks.append(task)

    if poll_tasks:
        await asyncio.gather(*poll_tasks)

TOKEN_LIMIT = 2500000
def main(round_number=0):
    load_dotenv()
    client = OpenAI()
    enc = tiktoken.encoding_for_model("gpt-4o")
    mitre_kb = load_mitre_kb()

    input_dir = Path(__file__).parent / 'dataset' / f'round_{round_number}'
    attackseq_dir = Path(__file__).parent.parent / 'dataset_generation' / 'filtered_attackseqs'
    batch_input_dir = Path(__file__).parent / 'batch_input' / f'round_{round_number}' / 'answerability'
    batch_output_dir = Path(__file__).parent / 'batch_output' / f'round_{round_number}' / 'answerability'
    batch_input_dir.mkdir(parents=True, exist_ok=True)
    batch_output_dir.mkdir(parents=True, exist_ok=True)

    # Process each CSV and generate batch input files
    for csv_file in input_dir.glob('*.csv'):
        batch_count = 0
        task_name = csv_file.stem

        token_count = 0
        df = pd.read_csv(csv_file)
        for _, row in df.iterrows():
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
            with open(attackseq_dir / f"{attackseq_id}.json", 'r') as f:
                attackseq_data = json.load(f)
            outline = attackseq_data['rewrite']
            jsonl_row = prepare_batch_request(row, outline, ttp_description, masked_tactic, task_name)
            token_count += len(enc.encode(str(jsonl_row)))
            if token_count >= TOKEN_LIMIT:
                batch_count += 1
                token_count = 0
            # Append the JSONL row to the appropriate batch input file
            with open(batch_input_dir / f"{csv_file.stem}_{batch_count}.jsonl", "a") as f:
                f.write(json.dumps(jsonl_row) + '\n')

    # Run the asynchronous submission and polling of batch jobs
    asyncio.run(submit_batch_requests(client, batch_input_dir, batch_output_dir))


if __name__ == "__main__":
    main()
