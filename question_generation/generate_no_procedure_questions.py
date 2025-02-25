import json
import tiktoken
import random
import asyncio
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
from prompts.no_procedure import system_prompt
from load_mitre_kb import load_mitre_kb

def get_random_technique_and_procedures(chosen_tactic, attackseq_techniques):
    mitre_kb = load_mitre_kb()
    techniques = {}
    for tactic in mitre_kb['tactics']:
        if tactic['name'] != chosen_tactic:
            continue
        for technique in tactic['techniques']:
            technique_name = technique['name']
            technique_id = technique['id']
            if technique_id in attackseq_techniques or not technique.get("examples"):
                continue
            dict_key = f"{technique_id}-{technique_name}"
            procedures = " ".join(procedure.get("description").strip() for procedure in technique.get("examples")[:3])
            techniques[dict_key] = procedures
            # Check for sub-techniques
            if 'sub_techniques' not in technique:
                continue
            for sub_technique in technique['sub_techniques']:
                if not sub_technique.get("examples"):
                    continue
                procedures = "\n".join(f"{idx}. {procedure.get('description').strip()}" for idx, procedure in enumerate(sub_technique.get("examples")[:3], 1))
                dict_key = f"{sub_technique['id']}-{sub_technique['name']}"
                techniques[dict_key] = procedures
    random_technique = random.choice(list(techniques.keys()))
    return random_technique, techniques[random_technique]

def prepare_batch_request(ref_qn_id, ref_qn, tactic, technique, procedures):
    user_prompt = f"Reference Question: {ref_qn}\nReference TTP: Tactic: {tactic}\nTechnique: {technique}\nExample Procedures: {procedures}"
    task_id = f"{ref_qn_id}-{tactic}-{technique}"
    task = {
        "custom_id": task_id,
        "method": "POST",
        "url": "/v1/chat/completions",
        "body": {
            "model": "gpt-4o-2024-11-20",
            "max_tokens": 256,
            "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
        }
    }
    return task

def generate_batch_files(attackseq_dir, batch_input_dir, sampled_df):
    enc = tiktoken.encoding_for_model("gpt-4o")
    token_count = 0
    batch_count = 0
    for _, row in sampled_df.iterrows():
        attackseq_id = row['TTA ID']
        ref_tactic = row['Batch ID'].split("-")[1]
        
        with open(attackseq_dir / f"{attackseq_id}.json", 'r') as fp:
            attackseq_data = json.load(fp)
        ref_qn = f"Question: {row['Question']} Answer: {row['Ground Truth']}"
        ref_qn_id = row['Question ID']
        attackseq_techniques = set(attackseq_data["triplet_groups"][ref_tactic].keys())
        ref_technique, ref_procedures = get_random_technique_and_procedures(ref_tactic, attackseq_techniques)
        task_jsonl = prepare_batch_request(ref_qn_id, ref_qn, ref_tactic, ref_technique, ref_procedures)
        token_count += len(enc.encode(str(task_jsonl)))
        if token_count >= TOKEN_LIMIT:
            batch_count += 1
            token_count = 0
        with open(batch_input_dir / f"no_procedure_batch_{batch_count}.jsonl", "a") as f:
            f.write(json.dumps(task_jsonl) + '\n')

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
                "description": "Generate questions for AttackSeq-Procedure-No"
            }
        )
        # Create an asynchronous task to poll this batch job.
        task = asyncio.create_task(poll_batch(client, batch_job, json_file, batch_output_dir))
        poll_tasks.append(task)

    if poll_tasks:
        await asyncio.gather(*poll_tasks)

# Set random seed for the random TTP selection from MITRE KB
TOKEN_LIMIT = 2000000
RANDOM_SEED = 56
def main():
    load_dotenv()
    random.seed(RANDOM_SEED)
    client = OpenAI()
    attackseq_dir = Path(__file__).parent / 'grouped_attackseqs'
    batch_input_dir = Path(__file__).parent / 'batch_input' / 'no_procedure'
    batch_output_dir = Path(__file__).parent / 'batch_output' / 'no_procedure'
    yes_procedure_csv = Path(__file__).parent.parent / 'dataset' / 'good_AttackSeq-Procedure-Yes.csv'
    df = pd.read_csv(yes_procedure_csv)
    # Randomly sample 70% of Yes questions
    sampled_df = df.sample(frac=0.7, random_state=RANDOM_SEED)
    batch_input_dir.mkdir(parents=True, exist_ok=True)
    batch_output_dir.mkdir(parents=True, exist_ok=True)

    print("Generating batch files...")
    generate_batch_files(attackseq_dir, batch_input_dir, sampled_df)
    print("Submitting batch request... This will take awhile")
    asyncio.run(submit_batch_requests(client, batch_input_dir, batch_output_dir))

if __name__ == "__main__":
    main()