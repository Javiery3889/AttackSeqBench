import json
import tiktoken
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
from prompts.yes_procedure import system_prompt

def convert_group_to_string(group):
    items_to_remove = ("id", "tactic", "technique")
    cleaned_group = []
    for event in group:
        for item in items_to_remove:
            event.pop(item, None)
        cleaned_group.append(", ".join([f"{k}: {v}" for k, v in event.items()]))
    return "\n".join(f"{idx}. {event}" for idx, event in enumerate(cleaned_group, start=1))

def format_user_content(tactic, technique, group, outline):
    return f"Report: {outline}\nTactic: {tactic}\nTechnique: {technique}\nProcedures: {convert_group_to_string(group)}"

def generate_batch_files(grouped_attackseq_dir: Path, batch_input_dir: Path):
    enc = tiktoken.encoding_for_model("gpt-4o")
    token_count = 0
    batch_count = 0
    for json_file in grouped_attackseq_dir.glob("*.json"):
        with open(json_file, 'r') as f:
            data = json.load(f)
        outline = data.get("rewrite")
        outline_string = "\n".join([f"{tactic}: {description}" for tactic, description in outline.items()])
        for tactic, techniques in data.get("triplet_groups").items():
            for technique, group in techniques.items():
                user_content = format_user_content(tactic, technique, group, outline_string)
                task = {
                    "custom_id": f"{json_file.stem}-{tactic}-{technique}",
                    "method": "POST",
                    "url": "/v1/chat/completions",
                    "body": {
                        "model": "gpt-4o-2024-11-20",
                        "max_tokens": 100,
                        "messages": [
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": user_content}
                            ]
                    }
                }
                token_count += len(enc.encode(str(task)))
                if token_count >= TOKEN_LIMIT:
                    batch_count += 1
                    token_count = 0
                with open(batch_input_dir / f"yes_procedure_batch_{batch_count}.jsonl", "a") as f:
                    f.write(json.dumps(task) + '\n')

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
                "description": "Generate questions for AttackSeq-Procedure-Yes"
            }
        )
        # Create an asynchronous task to poll this batch job.
        task = asyncio.create_task(poll_batch(client, batch_job, json_file, batch_output_dir))
        poll_tasks.append(task)

    if poll_tasks:
        await asyncio.gather(*poll_tasks)

# Set number of tokens for each batch file created
TOKEN_LIMIT = 2000000
def main():
    load_dotenv()
    client = OpenAI()
    grouped_attackseq_dir = Path(__file__).parent / 'grouped_attackseqs'
    batch_input_dir = Path(__file__).parent / 'batch_input' / 'yes_procedure'
    batch_output_dir = Path(__file__).parent / 'batch_output' / 'yes_procedure'
    batch_input_dir.mkdir(parents=True, exist_ok=True)
    batch_output_dir.mkdir(parents=True, exist_ok=True)

    print("Generating batch files...")
    generate_batch_files(grouped_attackseq_dir, batch_input_dir)
    print("Submitting batch request... This will take awhile")
    asyncio.run(submit_batch_requests(client, batch_input_dir, batch_output_dir))

if __name__ == "__main__":
    main()