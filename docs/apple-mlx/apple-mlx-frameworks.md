# Apple MLX & On-Device AI Framework Research

> Status: archived research snapshot.
> Active routing guidance now lives in `README.md` (use that first, then DeepWiki target repo on demand).

**TL;DR**: MLX is Apple's ML framework for Apple Silicon with first-party support for LLMs (mlx-lm), Swift (mlx-swift), and data loading (mlx-data). Apple Foundation Models provides on-device text generation (4K context, tool calling). MLX embeddings available separately.

---

## Opinion

**Verdict**: **Adopt** for Jarvis - MLX-lm is the best path for local LLM inference with Claude Agent SDK
**Confidence**: High
**Reasoning**: MLX provides the most comprehensive solution for running open-source LLMs on Apple Silicon with excellent performance via Metal backend. Combined with LM Studio for Anthropic-compatible API, enables local model usage with existing SDK.

---

## Libraries Summary

| Library | Language | Best For | Jarvis Integration |
|---------|----------|----------|-------------------|
| **mlx** | Python/C++/Swift | Core array framework | ✅ Already installed |
| **mlx-lm** | Python | LLM inference & fine-tuning | ✅ Already installed |
| **mlx-data** | Python | Efficient data loading | ✅ Already installed |
| **mlx-swift** | Swift | iOS/macOS native apps | ❌ Not needed |
| **mlx-embeddings** | Python | Text/image embeddings | ✅ Already installed |
| **apple-foundation-models** | Python | On-device Apple LLM | ✅ Installed, limited |

---

## Detailed Analysis

### 1. mlx (Core Framework)

**What**: NumPy-like array framework for ML on Apple Silicon

**Best For**:
- Custom ML operations
- Research prototyping
- Unified memory operations (CPU/GPU share memory)

**Key Features**:
- Lazy computation (build graph, eval when needed)
- Automatic differentiation (mx.grad, mx.value_and_grad)
- Multi-device (Metal, CUDA, CPU)
- Unified memory model
- Quantization support (4-bit, 8-bit)

```python
import mlx.core as mx
a = mx.array([1, 2, 3])
```

---

### 2. mlx-lm (LLM Inference)

**What**: Pre-built package for running & fine-tuning LLMs

**Best For**:
- Running Qwen3, Llama, Mistral, Gemma models
- Fine-tuning with LoRA/QLoRA
- Model quantization (GPTQ, AWQ, GGUF)

**Key Features**:
- 30+ model architectures supported
- HuggingFace Hub integration
- OpenAI-compatible server
- CLI tools

```bash
# Run a model
mlx_lm.generate --model mlx-community/Qwen2.5-3B-Instruct-4bit

# Fine-tune with LoRA
mlx_lm.lora --model <model> --train --data <dataset>
```

**Jarvis Status**: ✅ Installed (v0.30.7)

---

### 3. mlx-swift

**What**: Swift API for MLX (native Apple development)

**Best For**:
- iOS/macOS native ML apps
- SwiftUI integration
- Metal performance

**Examples**:
- MNIST training app
- LLM chat interfaces
- Stable Diffusion generation

---

### 4. mlx-data

**What**: Efficient data loading library

**Best For**:
- Fast image/audio data pipelines
- Large dataset handling
- Framework-agnostic (works with PyTorch, JAX, MLX)

**Key Features**:
- Lazy evaluation
- Prefetching
- Dynamic batching
- Distributed training support

---

### 5. mlx-embeddings

**What**: Text and image embeddings

**Best For**:
- Semantic search
- RAG applications
- Similarity matching

**Supported Models**:
- XLM-RoBERTa
- BERT
- ModernBERT
- Qwen3 embedding model

**Jarvis Usage**: Already used in `introspection_processor.py` for semantic code clustering!

---

### 6. apple-foundation-models

**What**: Python bindings for Apple's on-device LLM

**Best For**:
- Privacy-focused text generation
- Simple chat without cloud

**Key Features**:
- Tool calling support
- Structured output (JSON/Pydantic)
- Streaming
- Async support

**Limitations**:
- 4,096 token context window
- macOS 26.0+ required
- Alpha software (v0.2.2)

```python
from applefoundationmodels import Session

with Session() as session:
    response = session.generate("Hello!")
    print(response.text)
```

---

## Integration Path for Jarvis

### Option 1: LM Studio (Recommended ✅)

**How**: LM Studio provides Anthropic-compatible API

1. Install LM Studio
2. Start server: `lms server start --port 1234`
3. Set env vars:
```bash
export ANTHROPIC_BASE_URL=http://localhost:1234
export ANTHROPIC_AUTH_TOKEN=lmstudio
```

**Works with**: Claude Agent SDK ✅

---

### Option 2: Direct mlx-lm

**How**: Use mlx-lm for inference, wrap in MCP

**Pros**: 
- Full control
- Any model from HuggingFace

**Cons**:
- Need to implement tool calling manually
- More complex integration

---

### Option 3: apple-foundation-models

**How**: Use Apple's on-device model

**Pros**:
- Free
- Privacy-focused
- No internet needed

**Cons**:
- 4K context limit
- No Claude Agent SDK integration
- Alpha quality

---

## Recommendations for Jarvis

| Priority | Action | Status |
|----------|--------|--------|
| 1 | Keep using Claude SDK with Anthropic | ✅ Done |
| 2 | Add LM Studio option in Models tab | Pending |
| 3 | Use mlx-embeddings for RAG | ✅ In use |
| 4 | Explore mlx-lm for batch tasks | Future |
| 5 | Watch apple-foundation-models | Maturity |

---

## Claims Analysis

| Claim | Agree? | Evidence | Confidence |
|-------|--------|----------|------------|
| MLX is fastest for Apple Silicon | Yes | DeepWiki confirms Metal backend + unified memory | High |
| mlx-lm supports tool calling | Partial | Via MCP server, not native | Medium |
| apple-foundation-models ready for prod | No | Alpha, 4K limit | High |
| mlx-embeddings production-ready | Yes | Already in Jarvis | High |

---

## Integration Notes

**Tier**: 1 (Reference)
**Created**: 2026-02-18
**Sessions Used**: 0
**Promotion Status**: Pending validation

**Sources**:
- ml-explore/mlx
- ml-explore/mlx-lm
- ml-explore/mlx-swift
- ml-explore/mlx-examples
- ml-explore/mlx-data
- ml-explore/mlx-swift-examples
- pypi.org/project/apple-foundation-models
