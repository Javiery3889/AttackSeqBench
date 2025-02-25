from vllm import LLM, SamplingParams
from dotenv import load_dotenv
from prompts.rag_prompt import system_prompt
from pathlib import Path
import pandas as pd

load_dotenv()

def prepare_conversations(df: pd.DataFrame, task_name: str):
    conversations = []
    question_ids = []
    
    for _, row in df.iterrows():
        question = row["Question"]
        related_ttps_string = row["Related TTPs"]
        question_id = row["Question ID"]
        if "TTA-Procedure" in task_name:
            answer_choices = {"A": "Yes", "B": "No"}
        else:
            answer_choices = {}
            for answer_choice in ["A", "B", "C", "D"]:
                answer_choices[answer_choice] = row[answer_choice]
        answer_choices_string = "\n".join([f"{choice}: {answer}" for choice, answer in answer_choices.items()])
        user_prompt = f"Question: {question}\nAnswer Choices: {answer_choices_string}\nRelated TTPs: {related_ttps_string}"
        conversations.append([
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_prompt
            }]
        )
        question_ids.append(question_id)
    return conversations, question_ids

def main():
    model_name = "meta-llama/Llama-3.1-8B-Instruct"
    # model_name = "meta-llama/Llama-3.3-70B-Instruct"
    # model_name = "Qwen/Qwen2.5-72B-Instruct"
    # model_name = "deepseek-ai/DeepSeek-R1-Distill-Qwen-32B"
    # model_name = "Qwen/Qwen2.5-7B-Instruct"
    # model_name = "Qwen/QwQ-32B-Preview"
    # model_name = "deepseek-ai/DeepSeek-R1-Distill-Llama-8B"
    # model_name = "mistralai/Mistral-7B-Instruct-v0.3"
    # model_name = "THUDM/glm-4-9b-chat"
    embedding_model = "bge"

    dataset_dir = Path(__file__).parent / f'rag_dataset_{embedding_model}'
    llm = LLM(model=model_name, gpu_memory_utilization=0.8, enforce_eager=True, trust_remote_code=True, tensor_parallel_size=2)
    # llm = LLM(model=model_name, enforce_eager=True, gpu_memory_utilization=0.8, max_num_seqs=16, tensor_parallel_size=2, max_model_len=8192)
    # llm = LLM(model="deepseek-ai/DeepSeek-R1-Distill-Qwen-7B", gpu_memory_utilization=0.6, enforce_eager=True)
    sampling_params = SamplingParams(temperature=0, max_tokens=2048, top_p=1)
    for csv_file in dataset_dir.glob("*.csv"):
        task_name = csv_file.stem
        df = pd.read_csv(csv_file)
        conversations, question_ids = prepare_conversations(df, task_name)
        outputs = llm.chat(messages=conversations, sampling_params=sampling_params, use_tqdm=True)
        model_fp = model_name.split("/")[-1]
        outputs_dir = Path(__file__).parent / 'outputs' / 'rag' / model_fp / embedding_model
        write_dir = outputs_dir / csv_file.stem
        write_dir.mkdir(parents=True, exist_ok=True)
        for question_id, output in zip(question_ids, outputs):
             with open(write_dir / f"{task_name}-{question_id}.txt", "w") as fp:
                response = output.outputs[0].text
                fp.write(response)
if __name__ == "__main__":
    main()

