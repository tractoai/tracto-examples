from datasets import load_dataset, Dataset
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, AutoTokenizer
from peft import LoraConfig
from trl import SFTTrainer, SFTConfig
from transformers import TrainingArguments
from tractorun.toolbox import Toolbox

import os



def get_train_func(table_path: str, result_path: str):
    def train(toolbox: Toolbox):
        ytc = toolbox.yt_client

        # Load the dataset. Since the dataset is small we just read it to memory.
        dataset = Dataset.from_list(list(ytc.read_table(table_path)))

        # Load the model + tokenizer. Here we just download the weights of the model from HF.
        # To avoid downloading weights every time they can be uploaded to Cypress and passed as cypress_binds.
        model_name = "NousResearch/Llama-2-7b-chat-hf"
        tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
        tokenizer.pad_token = tokenizer.eos_token
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            trust_remote_code=True,
            use_cache = False
        )

        # PEFT config.
        lora_alpha = 16
        lora_dropout = 0.1
        lora_r = 64
        peft_config = LoraConfig(
            lora_alpha=lora_alpha,
            lora_dropout=lora_dropout,
            r=lora_r,
            bias="none",
            task_type="CAUSAL_LM",
            target_modules=["k_proj", "q_proj", "v_proj", "up_proj", "down_proj", "gate_proj"]
        )

        # Args.
        max_seq_length = 512
        output_dir = "./results"
        per_device_train_batch_size = 8
        gradient_accumulation_steps = 2
        optim = "adamw_hf"
        logging_steps = 1
        learning_rate = 2e-4
        max_grad_norm = 0.3
        max_steps = len(dataset) // (per_device_train_batch_size * gradient_accumulation_steps * int(os.environ["WORLD_SIZE"]))
        warmup_ratio = 0.1
        lr_scheduler_type = "cosine"
        training_arguments = SFTConfig(
            dataset_text_field="text",
            output_dir=output_dir,
            per_device_train_batch_size=per_device_train_batch_size,
            gradient_accumulation_steps=gradient_accumulation_steps,
            optim=optim,
            save_strategy="steps",
            save_steps=0.0,  #  Do not save intermediate checkpoints, save only result.
            logging_steps=logging_steps,
            learning_rate=learning_rate,
            fp16=True,
            max_grad_norm=max_grad_norm,
            max_steps=max_steps,
            warmup_ratio=warmup_ratio,
            group_by_length=True,
            lr_scheduler_type=lr_scheduler_type,
            gradient_checkpointing=True,
            gradient_checkpointing_kwargs={'use_reentrant':False},
            max_seq_length=max_seq_length,
        )

        # Trainer
        trainer = SFTTrainer(
            model=model,
            train_dataset=dataset,
            peft_config=peft_config,
            processing_class=tokenizer,
            args=training_arguments,
        )

        trainer.train()

        # Upload result from one peer only.
        if os.environ["RANK"] == "0":
            # Now the result of the fine-tuning is stored on a local filesystem in a job's sandbox
            # which will be removed after the job is completed.
            # We will move it to the Cypress.

            local_result_path = output_dir
            tracto_result_path = result_path

            print("Uploading result to {tracto_result_path}")

            ytc = toolbox.yt_client

            # Cypress does not like paths with trailing slashes,
            # so we join paths carefully.
            def join_paths(l, r):
                if l and r:
                    return f"{l}/{r}"
                else:
                    return l + r

            def dfs(path):
                local_path = join_paths(local_result_path, path)
                tracto_path = join_paths(tracto_result_path, path)

                if os.path.isdir(local_path):
                    print(f"Creating directory {tracto_path}")
                    ytc.create("map_node", tracto_path, ignore_existing=True, recursive=True)
                    for f in os.listdir(local_path):
                        dfs(join_paths(path, f))
                else:
                    print(f"Uploading file {tracto_path}")
                    with open(local_path, "rb") as f:
                        ytc.write_file(tracto_path, f)
            dfs("")

            print("Results uploaded to {tracto_result_path}")

    return train
