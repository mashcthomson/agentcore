"""
Fine-tune a model on your chat history using Unsloth + QLoRA.
Runs on 6GB VRAM (RTX 4050).

Install first:
  pip install "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git"
  pip install --no-deps trl peft accelerate bitsandbytes
"""

from unsloth import FastLanguageModel
from trl import SFTTrainer
from transformers import TrainingArguments
from datasets import load_dataset
import torch

# ── Config ────────────────────────────────────────────────────────────────────

MODEL = "unsloth/Meta-Llama-3.1-8B-Instruct-bnb-4bit"  # fits in 6GB with QLoRA
# Alternatives (smaller = faster, less capable):
# "unsloth/Phi-3-mini-4k-instruct-bnb-4bit"   # 3.8B, very fast
# "unsloth/mistral-7b-instruct-v0.3-bnb-4bit" # 7B
# "unsloth/Qwen2.5-7B-Instruct-bnb-4bit"      # 7B, strong

MAX_SEQ_LENGTH = 2048   # reduce to 1024 if OOM
LORA_RANK = 16          # reduce to 8 if OOM
BATCH_SIZE = 1          # keep at 1 for 6GB
GRAD_ACCUM = 8          # effective batch = 8
EPOCHS = 1              # start with 1, increase if needed
OUTPUT_DIR = "output/lora_adapter"

# ── Load model ────────────────────────────────────────────────────────────────

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=MODEL,
    max_seq_length=MAX_SEQ_LENGTH,
    dtype=None,           # auto-detect
    load_in_4bit=True,    # QLoRA
)

model = FastLanguageModel.get_peft_model(
    model,
    r=LORA_RANK,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                    "gate_proj", "up_proj", "down_proj"],
    lora_alpha=LORA_RANK * 2,
    lora_dropout=0,
    bias="none",
    use_gradient_checkpointing="unsloth",  # saves ~30% VRAM
    random_state=42,
)

print(f"Trainable params: {model.get_nb_trainable_parameters():,}")

# ── Load dataset ──────────────────────────────────────────────────────────────

dataset = load_dataset("json", data_files="finetune/sharegpt.jsonl", split="train")
print(f"Dataset: {len(dataset)} conversations")

# Format into chat template
def format_conversation(example):
    messages = []
    for turn in example["conversations"]:
        role = "user" if turn["from"] == "human" else "assistant"
        messages.append({"role": role, "content": turn["value"]})

    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=False
    )
    return {"text": text}

dataset = dataset.map(format_conversation, remove_columns=dataset.column_names)

# Filter out very short or very long examples
dataset = dataset.filter(lambda x: 100 < len(x["text"]) < MAX_SEQ_LENGTH * 4)
print(f"After filtering: {len(dataset)} conversations")

# ── Train ─────────────────────────────────────────────────────────────────────

trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=dataset,
    dataset_text_field="text",
    max_seq_length=MAX_SEQ_LENGTH,
    dataset_num_proc=2,
    packing=True,   # packs short convos together for efficiency
    args=TrainingArguments(
        per_device_train_batch_size=BATCH_SIZE,
        gradient_accumulation_steps=GRAD_ACCUM,
        warmup_steps=10,
        num_train_epochs=EPOCHS,
        learning_rate=2e-4,
        fp16=not torch.cuda.is_bf16_supported(),
        bf16=torch.cuda.is_bf16_supported(),
        logging_steps=10,
        optim="adamw_8bit",
        weight_decay=0.01,
        lr_scheduler_type="linear",
        seed=42,
        output_dir=OUTPUT_DIR,
        save_strategy="epoch",
        report_to="none",
    ),
)

print("Starting training...")
trainer.train()

# ── Save ──────────────────────────────────────────────────────────────────────

model.save_pretrained(OUTPUT_DIR)
tokenizer.save_pretrained(OUTPUT_DIR)
print(f"LoRA adapter saved to {OUTPUT_DIR}")

# Optional: merge adapter into base model for a single deployable model
# model.save_pretrained_merged("output/merged_model", tokenizer, save_method="merged_16bit")
