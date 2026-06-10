# Second Brain Pipeline

## Setup

1. Drop your exports:
   - `raw/claude/` — Claude JSON exports
   - `raw/chatgpt/` — ChatGPT `conversations.json`
   - `raw/perplexity/` — Perplexity `.md` or `.rmd` files

2. Parse and normalize all chats:
   ```bash
   python parse_chats.py
   ```

3. Fine-tune on your RTX 4050 (run this ON YOUR LOCAL MACHINE, not here):
   ```bash
   pip install "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git"
   pip install --no-deps trl peft accelerate bitsandbytes
   python finetune.py
   ```

## What gets generated

| File | Used for |
|---|---|
| `processed/all_conversations.jsonl` | Source of truth, all chats normalized |
| `finetune/sharegpt.jsonl` | Fine-tuning input (Unsloth/Axolotl format) |
| `rag/chunks.jsonl` | Vector DB embedding (RAG layer) |
| `output/lora_adapter/` | Trained LoRA weights |

## Hardware expectations (RTX 4050 6GB)

| Model | VRAM usage | Time per epoch (~1800 convos) |
|---|---|---|
| Llama 3.1 8B (QLoRA) | ~5.5GB | 4-8 hours |
| Phi-3 mini 3.8B (QLoRA) | ~3.5GB | 2-4 hours |
| Qwen 2.5 7B (QLoRA) | ~5GB | 4-6 hours |

## If you run out of VRAM

Edit `finetune.py`:
- `MAX_SEQ_LENGTH = 1024` (from 2048)
- `LORA_RANK = 8` (from 16)
- Switch to Phi-3 mini model
