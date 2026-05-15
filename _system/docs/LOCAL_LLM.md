# Local LLM Setup (Confidential Phase)

This document describes the local-LLM workflow for the Confidential phase. Any work that touches `confidential_tier: local-only` paths runs here, never on a cloud LLM.

## Hardware

Reference machine: MacBook Pro M4 Pro, 24 GB unified memory, macOS.

24 GB is the lower bound for the workflow described here. Drafting on grant-quality prose is workable but tight. 48 GB+ would allow swapping to a 32B-class model without RAM pressure, but is not required.

## Backend

**LM Studio** is the supported backend.

- Native MLX support on Apple Silicon (~20–30% faster than GGUF equivalents).
- Visible prompt/response panel — useful for confidential review (you see exactly what context was sent to the model).
- Local server is OFF by default; user must explicitly enable it. This is a security feature, not a bug.

Alternatives (Ollama, llama.cpp) work in principle because the `scripts/local_agent.py` entry point talks to any OpenAI-compatible local endpoint, but LM Studio is the documented path.

## Models

### Primary — single-model setup

**Qwen3.5 27B Instruct, MLX 4-bit.**

- Disk: ~16 GB. Loaded memory: ~16 GB weights + 1–2 GB KV cache at 8K context.
- Tokens/sec on M4 Pro: roughly 12–20 tok/s for 27B 4-bit. A 500-token paragraph draft completes in ~30–60 seconds.
- Used for all four local roles via system-prompt templating. No model swap.

### Notes on model selection

Coding-specialized variants (Qwen3.6, Qwen3 Coder Next, GLM-4.7) are not recommended for scientific prose. The marketing emphasis on "coding agent" use cases does not translate to grant or manuscript drafting.

MoE models (Nemotron 3 30B, LFM2-24B-A2B) are interesting in principle but their full parameter count must still reside in RAM. On 24 GB they are tight; do not assume the "active parameter" count reduces memory pressure.

Models above 30B (Qwen3.5 35B, Nemotron 3 Super 120B MoE, Llama 3.3 70B) will not fit on 24 GB at usable quantization. Do not attempt.

### Optional secondary — fast utility

**Gemma 4 7.9B Instruct MLX 4-bit** or **Qwen3.5 9B Instruct MLX 4-bit.**

For quick tagging, routing, or short summaries when the 27B model's latency is too slow. Switching requires unloading the 27B from LM Studio first (about 20–40 seconds round-trip), so reserve secondary-model use for explicit batched workloads, not for every other prompt.

## One model, multiple roles

The four confidential roles (Drafter, Argue, Demon, Rejection-Sim) all use the same Qwen3.5 27B instance. Role differentiation happens via system-prompt templating in `scripts/local_agent.py`:

    python3 scripts/local_agent.py --role {drafter|argue|demon|rejection-sim} --project {slug}

The script prepends the relevant `subagents/0X-{role}.md` content as the system message, then opens a conversation that has access to the named project's confidential files. The same LM Studio session serves all four roles by reloading the system prompt, not the model.

## Setup checklist

1. Install LM Studio from the official site.
2. In LM Studio, search for `Qwen3.5-27B-Instruct MLX` or `mlx-community/Qwen3.5-27B-Instruct-4bit`. Download.
3. Optional: download `Gemma 4 7.9B Instruct MLX 4bit` for fast utility tasks.
4. **Open LM Studio and load the model**: click the model in the left sidebar to load it into memory (~16 GB, takes 30–60 s).
5. **Start the local server**: in LM Studio's left sidebar click the `<->` (Local Server) icon → click **Start Server**. The server does NOT start automatically when you open LM Studio. Default endpoint: `http://localhost:1234/v1`.
6. Confirm the server responds: `curl http://localhost:1234/v1/models`
7. From the repo root, run the agent:
   ```
   python3 scripts/local_agent.py --role drafter --project {slug}
   ```
   To test with the included test project first:
   ```
   python3 scripts/local_agent.py --role drafter --project local-agent-test
   ```
   Delete `projects/local-agent-test/` once confirmed working.

## Operational rules

- **Server-off by default.** Quit LM Studio when not in active use. A running local server cannot leak by itself, but reducing attack surface is free.
- **Never paste a project file's content into LM Studio's GUI by hand if the GUI has internet-connected features enabled.** Use `scripts/local_agent.py` so paths are read by the script, sent to localhost, and never to a cloud endpoint.
- **Context budget: aim for 8K tokens or less per session.** Long contexts blow past KV cache headroom and degrade quality. If a draft is longer than fits, work section-by-section.
- **Watch RAM pressure.** Close Slack, Chrome, etc. before long drafting sessions. Activity Monitor's "Memory Used" should be under ~22 GB while the model is loaded.

## Cloud vs local boundary

| Activity | Layer |
|---|---|
| Brainstorming a wiki topic | Cloud (Claude Code or Codex CLI) |
| Scout, triage, ingest | Cloud (Codex CLI, then Ingester) |
| Synthesizing a `wiki/overviews/` page | Cloud (Synthesizer) |
| Drafting grant aims, manuscript sections, review prose | **Local (Drafter)** |
| Reviewer-#2 critique of own draft | **Local (Argue)** |
| Devil's-advocate critique of own draft | **Local (Demon)** |
| Pre-submission rejection simulation | **Local (Rejection-Sim)** |
| Polishing single sentences of already-public prose | Cloud, after manual redaction (rare) |

Anything in the local rows is processed only on the local machine. No part of it should ever reach a cloud API.

## Failure modes to watch

- **LM Studio shows the prompt was sent to a remote endpoint instead of localhost.** Stop immediately. Verify the Local Server tab's URL is `localhost`. This should never happen with default settings but is the most consequential failure mode.
- **The 27B model is unusually slow (under 5 tok/s).** Probably RAM pressure or model swap. Quit other apps. If still slow, restart LM Studio.
- **Output quality is noticeably worse than expected.** Probably context overflow. Trim the conversation or start a new session.
- **`scripts/local_agent.py` refuses to read a project.** Check that `Project_Brief.md` exists and that `confidential_tier: local-only` is in the frontmatter (or that the path matches a default confidential folder).

## Upgrading the hardware

If 24 GB starts limiting workflow:

- 48 GB unified memory → run Qwen3.5 32B 4-bit comfortably; or Qwen3.5 27B with 16K context; or load 27B + Gemma 4 7B simultaneously.
- 64 GB+ → 70B-class dense models at 4-bit; faster generation; meaningful multi-model orchestration becomes possible.

Hardware upgrade is the correct move only when 27B has become a measurable bottleneck. Until then, the bottleneck is almost always context discipline, not parameter count.
