"""
Parse Claude, ChatGPT, and Perplexity exports into a unified dataset.

Drop your exports here:
  raw/claude/     - Claude JSON exports (conversations.json or individual files)
  raw/chatgpt/    - ChatGPT conversations.json
  raw/perplexity/ - Perplexity .md or .rmd files

Outputs:
  processed/all_conversations.jsonl  - unified format
  finetune/sharegpt.jsonl            - ready for Unsloth/TRL fine-tuning
  rag/chunks.jsonl                   - chunked for vector DB embedding
"""

import json
import re
import glob
import hashlib
from pathlib import Path
from datetime import datetime

RAW = Path("raw")
PROCESSED = Path("processed")
FINETUNE = Path("finetune")
RAG = Path("rag")

# ── Unified message format ────────────────────────────────────────────────────
# {"id": str, "source": "claude"|"chatgpt"|"perplexity",
#  "title": str, "created_at": str,
#  "messages": [{"role": "user"|"assistant", "content": str}]}

def make_id(source, title, idx):
    return hashlib.md5(f"{source}:{title}:{idx}".encode()).hexdigest()[:12]


# ── Claude parser ─────────────────────────────────────────────────────────────
def parse_claude(path: Path) -> list[dict]:
    convos = []
    try:
        data = json.loads(path.read_text())
    except Exception as e:
        print(f"  [claude] Failed to parse {path}: {e}")
        return []

    # Claude export can be a list of conversations or a single conversation
    if isinstance(data, dict):
        data = [data]

    for i, convo in enumerate(data):
        # Claude format: {"name": ..., "created_at": ..., "chat_messages": [...]}
        # or: {"uuid": ..., "name": ..., "updated_at": ..., "chat_messages": [...]}
        messages = []
        raw_messages = convo.get("chat_messages", convo.get("messages", []))

        for msg in raw_messages:
            role = msg.get("sender", msg.get("role", ""))
            # Claude uses "human"/"assistant" or "user"/"assistant"
            if role in ("human", "user"):
                role = "user"
            elif role in ("assistant", "ai"):
                role = "assistant"
            else:
                continue

            # Content can be a string or list of content blocks
            content = msg.get("text", msg.get("content", ""))
            if isinstance(content, list):
                # Extract text from content blocks
                parts = []
                for block in content:
                    if isinstance(block, str):
                        parts.append(block)
                    elif isinstance(block, dict):
                        parts.append(block.get("text", block.get("content", "")))
                content = "\n".join(filter(None, parts))

            if content and content.strip():
                messages.append({"role": role, "content": content.strip()})

        if len(messages) >= 2:
            convos.append({
                "id": make_id("claude", convo.get("name", str(i)), i),
                "source": "claude",
                "title": convo.get("name", convo.get("title", f"conversation_{i}")),
                "created_at": convo.get("created_at", convo.get("updated_at", "")),
                "messages": messages
            })

    return convos


# ── ChatGPT parser ────────────────────────────────────────────────────────────
def parse_chatgpt(path: Path) -> list[dict]:
    convos = []
    try:
        data = json.loads(path.read_text())
    except Exception as e:
        print(f"  [chatgpt] Failed to parse {path}: {e}")
        return []

    if isinstance(data, dict):
        data = [data]

    for convo in data:
        messages = []
        mapping = convo.get("mapping", {})

        # Traverse the tree in order via parent/child links
        # Find root node (no parent or parent is None)
        nodes = {}
        for node_id, node in mapping.items():
            nodes[node_id] = node

        # Build ordered list by following children from root
        def get_ordered_messages(mapping):
            # Find root
            root = None
            for nid, node in mapping.items():
                if node.get("parent") is None:
                    root = nid
                    break
            if root is None:
                return []

            ordered = []
            def traverse(nid):
                node = mapping.get(nid, {})
                msg = node.get("message")
                if msg:
                    author = msg.get("author", {}).get("role", "")
                    if author in ("user", "assistant"):
                        content_obj = msg.get("content", {})
                        parts = content_obj.get("parts", [])
                        text = " ".join(str(p) for p in parts if isinstance(p, str) and p.strip())
                        if text.strip():
                            ordered.append({"role": author, "content": text.strip()})
                for child in node.get("children", []):
                    traverse(child)

            traverse(root)
            return ordered

        messages = get_ordered_messages(mapping)

        if len(messages) >= 2:
            ts = convo.get("create_time", "")
            created = datetime.fromtimestamp(ts).isoformat() if ts else ""
            convos.append({
                "id": make_id("chatgpt", convo.get("title", ""), len(convos)),
                "source": "chatgpt",
                "title": convo.get("title", "untitled"),
                "created_at": created,
                "messages": messages
            })

    return convos


# ── Perplexity parser ─────────────────────────────────────────────────────────
def parse_perplexity(path: Path) -> list[dict]:
    """
    Perplexity .md/.rmd exports typically look like:
    # Title
    **You:** user message
    **Perplexity:** assistant response
    ---
    or similar markdown structure
    """
    convos = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        print(f"  [perplexity] Failed to read {path}: {e}")
        return []

    # Split into individual conversations if multiple in one file
    # Perplexity sometimes puts multiple convos separated by --- or ## headers
    sections = re.split(r'\n---+\n|\n#{1,2} ', text)

    for i, section in enumerate(sections):
        if not section.strip():
            continue

        messages = []
        lines = section.strip().split('\n')
        title = lines[0].strip('#').strip() if lines else f"conversation_{i}"

        # Extract messages - handle various Perplexity formats
        current_role = None
        current_content = []

        for line in lines[1:]:
            # Match "**You:**", "**User:**", "**Perplexity:**", "**Assistant:**"
            user_match = re.match(r'\*\*(You|User|Human)\*\*:?\s*(.*)', line, re.IGNORECASE)
            asst_match = re.match(r'\*\*(Perplexity|Assistant|AI)\*\*:?\s*(.*)', line, re.IGNORECASE)

            if user_match:
                if current_role and current_content:
                    content = "\n".join(current_content).strip()
                    if content:
                        messages.append({"role": current_role, "content": content})
                current_role = "user"
                current_content = [user_match.group(2)] if user_match.group(2) else []
            elif asst_match:
                if current_role and current_content:
                    content = "\n".join(current_content).strip()
                    if content:
                        messages.append({"role": current_role, "content": content})
                current_role = "assistant"
                current_content = [asst_match.group(2)] if asst_match.group(2) else []
            elif current_role:
                current_content.append(line)

        if current_role and current_content:
            content = "\n".join(current_content).strip()
            if content:
                messages.append({"role": current_role, "content": content})

        if len(messages) >= 2:
            convos.append({
                "id": make_id("perplexity", title, i),
                "source": "perplexity",
                "title": title,
                "created_at": "",
                "messages": messages
            })

    return convos


# ── Format for fine-tuning (ShareGPT) ────────────────────────────────────────
def to_sharegpt(convo: dict) -> dict:
    """ShareGPT format used by Unsloth, Axolotl, LLaMA-Factory."""
    return {
        "conversations": [
            {
                "from": "human" if m["role"] == "user" else "gpt",
                "value": m["content"]
            }
            for m in convo["messages"]
        ]
    }


# ── Format for RAG (chunked) ──────────────────────────────────────────────────
def to_rag_chunks(convo: dict, chunk_size: int = 2) -> list[dict]:
    """Split conversation into overlapping windows for vector DB embedding."""
    chunks = []
    msgs = convo["messages"]

    for i in range(0, len(msgs) - 1, chunk_size):
        window = msgs[i:i + chunk_size + 1]
        text = "\n\n".join(
            f"{'User' if m['role'] == 'user' else 'You'}: {m['content']}"
            for m in window
        )
        chunks.append({
            "id": f"{convo['id']}_chunk_{i}",
            "source": convo["source"],
            "title": convo["title"],
            "created_at": convo["created_at"],
            "text": text,
            "metadata": {
                "convo_id": convo["id"],
                "chunk_index": i,
                "message_count": len(window)
            }
        })

    return chunks


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    all_convos = []

    # Parse Claude
    claude_files = list(RAW.glob("claude/**/*.json")) + list(RAW.glob("claude/*.json"))
    print(f"Claude: found {len(claude_files)} file(s)")
    for f in claude_files:
        convos = parse_claude(f)
        print(f"  {f.name}: {len(convos)} conversations")
        all_convos.extend(convos)

    # Parse ChatGPT
    chatgpt_files = list(RAW.glob("chatgpt/**/*.json")) + list(RAW.glob("chatgpt/*.json"))
    print(f"ChatGPT: found {len(chatgpt_files)} file(s)")
    for f in chatgpt_files:
        convos = parse_chatgpt(f)
        print(f"  {f.name}: {len(convos)} conversations")
        all_convos.extend(convos)

    # Parse Perplexity
    perplexity_files = (
        list(RAW.glob("perplexity/**/*.md")) +
        list(RAW.glob("perplexity/**/*.rmd")) +
        list(RAW.glob("perplexity/*.md")) +
        list(RAW.glob("perplexity/*.rmd"))
    )
    print(f"Perplexity: found {len(perplexity_files)} file(s)")
    for f in perplexity_files:
        convos = parse_perplexity(f)
        print(f"  {f.name}: {len(convos)} conversations")
        all_convos.extend(convos)

    print(f"\nTotal conversations parsed: {len(all_convos)}")

    if not all_convos:
        print("\nNo conversations found. Drop your exports into the raw/ folders and rerun.")
        return

    # Write unified output
    out = PROCESSED / "all_conversations.jsonl"
    with open(out, "w") as f:
        for c in all_convos:
            f.write(json.dumps(c) + "\n")
    print(f"Unified dataset: {out} ({len(all_convos)} conversations)")

    # Write fine-tuning dataset
    ft_out = FINETUNE / "sharegpt.jsonl"
    with open(ft_out, "w") as f:
        for c in all_convos:
            f.write(json.dumps(to_sharegpt(c)) + "\n")
    print(f"Fine-tune dataset: {ft_out}")

    # Write RAG chunks
    all_chunks = []
    for c in all_convos:
        all_chunks.extend(to_rag_chunks(c))
    rag_out = RAG / "chunks.jsonl"
    with open(rag_out, "w") as f:
        for chunk in all_chunks:
            f.write(json.dumps(chunk) + "\n")
    print(f"RAG chunks: {rag_out} ({len(all_chunks)} chunks)")

    # Stats
    print("\n── Stats ─────────────────────────────")
    by_source = {}
    total_msgs = 0
    for c in all_convos:
        by_source[c["source"]] = by_source.get(c["source"], 0) + 1
        total_msgs += len(c["messages"])
    for src, count in by_source.items():
        print(f"  {src}: {count} conversations")
    print(f"  total messages: {total_msgs}")
    avg = total_msgs / len(all_convos) if all_convos else 0
    print(f"  avg messages/conversation: {avg:.1f}")


if __name__ == "__main__":
    import os
    os.chdir(Path(__file__).parent)
    main()
