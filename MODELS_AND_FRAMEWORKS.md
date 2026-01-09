# Models & Frameworks Comparison Guide

A detailed comparison of technologies you can experiment with for the Voice Agent POC.

---

## 🤖 Large Language Models (LLMs)

### Cloud-Based LLMs

| Model | Provider | Function Calling | Streaming | Latency | Cost | Best For |
|-------|----------|------------------|-----------|---------|------|----------|
| **GPT-4o** | OpenAI | ⭐⭐⭐⭐⭐ | Yes | ~500ms | $$$ | Production quality, complex reasoning |
| **GPT-4o-mini** | OpenAI | ⭐⭐⭐⭐⭐ | Yes | ~300ms | $ | Great balance of cost/quality |
| **Claude 3.5 Sonnet** | Anthropic | ⭐⭐⭐⭐ | Yes | ~400ms | $$ | Long context, nuanced responses |
| **Claude 3.5 Haiku** | Anthropic | ⭐⭐⭐⭐ | Yes | ~200ms | $ | Fast, cost-effective |
| **Gemini 1.5 Pro** | Google | ⭐⭐⭐⭐ | Yes | ~400ms | $$ | Massive context (1M tokens) |
| **Gemini 1.5 Flash** | Google | ⭐⭐⭐ | Yes | ~200ms | $ | Speed-optimized |

### Local/Open Source LLMs (via Ollama)

| Model | Parameters | Function Calling | Quality | RAM Required | Best For |
|-------|------------|------------------|---------|--------------|----------|
| **Llama 3.2** | 3B/11B/90B | ⭐⭐⭐ | ⭐⭐⭐⭐ | 4-64GB | General purpose |
| **Mistral 7B** | 7B | ⭐⭐ | ⭐⭐⭐ | 8GB | Fast local inference |
| **Mixtral 8x7B** | 46.7B | ⭐⭐⭐ | ⭐⭐⭐⭐ | 32GB | Quality + speed balance |
| **Qwen 2.5** | 7B/14B/72B | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 8-48GB | Strong tool use |
| **DeepSeek Coder** | 6.7B/33B | ⭐⭐⭐ | ⭐⭐⭐⭐ | 8-24GB | Code-heavy tasks |

### Recommendation for POC
```
Primary:   GPT-4o-mini (best cost/quality, excellent function calling)
Fallback:  Llama 3.2 11B via Ollama (local, no API costs)
Advanced:  Claude 3.5 Sonnet (for complex multi-turn conversations)
```

---

## 🎤 Speech-to-Text (STT)

### Options Comparison

| Service | Real-time | Accuracy | Latency | Cost | Local Option |
|---------|-----------|----------|---------|------|--------------|
| **OpenAI Whisper API** | No | ⭐⭐⭐⭐⭐ | 1-3s | $0.006/min | ✅ |
| **Whisper (local)** | No | ⭐⭐⭐⭐⭐ | 2-10s | Free | ✅ |
| **Deepgram** | Yes | ⭐⭐⭐⭐ | <300ms | $0.0043/min | ❌ |
| **AssemblyAI** | Yes | ⭐⭐⭐⭐ | <500ms | $0.0037/min | ❌ |
| **Google Speech-to-Text** | Yes | ⭐⭐⭐⭐ | <300ms | $0.006/min | ❌ |
| **Azure Speech** | Yes | ⭐⭐⭐⭐ | <300ms | $0.01/min | ❌ |

### Whisper Model Sizes

| Model | Parameters | Relative Speed | VRAM | English Accuracy |
|-------|------------|----------------|------|------------------|
| tiny | 39M | 32x | 1GB | Decent |
| base | 74M | 16x | 1GB | Good |
| small | 244M | 6x | 2GB | Very Good |
| medium | 769M | 2x | 5GB | Excellent |
| large-v3 | 1550M | 1x | 10GB | Best |

### Recommendation for POC
```
Development:  Whisper small/medium (local, free, good quality)
Demo:         OpenAI Whisper API or Deepgram (reliable, fast)
Production:   Deepgram (real-time streaming, <300ms latency)
```

---

## 🔊 Text-to-Speech (TTS)

### Options Comparison

| Service | Voice Quality | Latency | Streaming | Cost | Emotional Range |
|---------|---------------|---------|-----------|------|-----------------|
| **ElevenLabs** | ⭐⭐⭐⭐⭐ | <500ms | Yes | $$$$ | ⭐⭐⭐⭐⭐ |
| **OpenAI TTS** | ⭐⭐⭐⭐ | <400ms | Yes | $$ | ⭐⭐⭐ |
| **OpenAI TTS HD** | ⭐⭐⭐⭐⭐ | <600ms | Yes | $$$ | ⭐⭐⭐⭐ |
| **Coqui TTS** | ⭐⭐⭐ | 1-3s | No | Free | ⭐⭐ |
| **Piper** | ⭐⭐⭐ | <500ms | Yes | Free | ⭐⭐ |
| **Google TTS** | ⭐⭐⭐⭐ | <300ms | Yes | $$ | ⭐⭐⭐ |
| **Azure TTS** | ⭐⭐⭐⭐ | <300ms | Yes | $$ | ⭐⭐⭐⭐ |

### Voice Options

**OpenAI TTS Voices**: alloy, echo, fable, onyx, nova, shimmer
**ElevenLabs**: 1000s of voices + voice cloning
**Piper**: 100+ voices in 30+ languages (local)

### Recommendation for POC
```
Development:  Piper (local, free, good enough for testing)
Demo:         OpenAI TTS (good quality, reasonable cost)
Production:   ElevenLabs (best quality, most natural)
```

---

## 📚 RAG Frameworks

### Framework Comparison

| Framework | Learning Curve | Flexibility | Production Ready | Community |
|-----------|---------------|-------------|------------------|-----------|
| **LangChain** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **LlamaIndex** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Haystack** | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| **RAGFlow** | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| **Custom (no framework)** | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | N/A |

### LangChain vs LlamaIndex

| Aspect | LangChain | LlamaIndex |
|--------|-----------|------------|
| **Focus** | General LLM apps, agents | Data/document focused |
| **Strengths** | Agents, chains, tools | Advanced RAG patterns |
| **Weaknesses** | Can be over-abstracted | Less flexible for agents |
| **Best For** | Multi-tool agents | Document Q&A systems |
| **Learning** | More concepts to learn | Simpler mental model |

### Recommendation for POC
```
Start with:   LangChain (more versatile, better for agents with tools)
Consider:     LlamaIndex for advanced RAG (reranking, query routing)
Hybrid:       LangChain for agents + LlamaIndex for document handling
```

---

## 💾 Vector Databases

### Options Comparison

| Database | Setup | Performance | Scalability | Features | Cost |
|----------|-------|-------------|-------------|----------|------|
| **ChromaDB** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | Free |
| **Qdrant** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | Free/Paid |
| **Pinecone** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | $$$ |
| **Weaviate** | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Free/Paid |
| **Milvus** | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | Free |
| **pgvector** | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | Free |

### Recommendation for POC
```
Development:  ChromaDB (zero config, embedded, great for prototyping)
Production:   Qdrant (fast, self-hosted option, great API)
Alternative:  pgvector if already using PostgreSQL
```

---

## 🔌 Embedding Models

### Options Comparison

| Model | Dimensions | Quality | Speed | Cost |
|-------|------------|---------|-------|------|
| **OpenAI text-embedding-3-small** | 1536 | ⭐⭐⭐⭐ | Fast | $0.02/1M |
| **OpenAI text-embedding-3-large** | 3072 | ⭐⭐⭐⭐⭐ | Fast | $0.13/1M |
| **Cohere embed-v3** | 1024 | ⭐⭐⭐⭐⭐ | Fast | $0.10/1M |
| **Voyage AI** | 1024 | ⭐⭐⭐⭐⭐ | Fast | $0.10/1M |
| **BGE (local)** | 1024 | ⭐⭐⭐⭐ | Medium | Free |
| **E5 (local)** | 1024 | ⭐⭐⭐⭐ | Medium | Free |
| **all-MiniLM-L6-v2** | 384 | ⭐⭐⭐ | Fast | Free |

### Recommendation for POC
```
Primary:      OpenAI text-embedding-3-small (good balance)
Local:        BGE-large or E5-large via sentence-transformers
Budget:       all-MiniLM-L6-v2 (faster, smaller, decent quality)
```

---

## 🎙️ Voice AI Frameworks

For real-time voice agents, consider these specialized frameworks:

### LiveKit Agents
- **What**: Open-source framework for building real-time voice AI
- **Strengths**: Low latency, WebRTC built-in, good ecosystem
- **Use When**: Building production voice apps
- **GitHub**: [livekit/agents](https://github.com/livekit/agents)

### Pipecat
- **What**: Open-source framework for voice and multimodal AI
- **Strengths**: Modular, supports many STT/TTS/LLM providers
- **Use When**: Rapid prototyping, flexible pipelines
- **GitHub**: [pipecat-ai/pipecat](https://github.com/pipecat-ai/pipecat)

### Daily Bots (RTVI)
- **What**: Framework for real-time voice AI with Daily's infrastructure
- **Strengths**: Production-ready, handles scaling
- **Use When**: Need managed infrastructure

### Recommendation for POC
```
Start simple:     Custom WebSocket + Whisper + TTS (understand the basics)
Then upgrade to:  Pipecat (when you need more sophisticated pipelines)
Production:       LiveKit Agents (if you need to scale)
```

---

## 📊 Comparison Matrix for Your Use Case

Given your goals (POC for demo + learning), here's the recommended stack:

### Tier 1: Quick Start (Week 1-2)
| Component | Choice | Reason |
|-----------|--------|--------|
| LLM | GPT-4o-mini | Fast, cheap, excellent function calling |
| STT | OpenAI Whisper API | Simple, reliable |
| TTS | OpenAI TTS | Good quality, easy setup |
| RAG | LangChain | Well-documented, versatile |
| Vector DB | ChromaDB | Zero config |
| Backend | FastAPI | Async, modern Python |
| Frontend | Next.js + shadcn | Beautiful, production-quality |

### Tier 2: Enhanced (Week 3-6)
| Component | Choice | Reason |
|-----------|--------|--------|
| LLM | Add Claude 3.5 Sonnet | Compare quality |
| STT | Add local Whisper | Cost-free development |
| TTS | Test ElevenLabs | Hear the difference |
| RAG | Add LlamaIndex | Advanced retrieval |
| Voice | Consider Pipecat | Better streaming |

### Tier 3: Production-Like (Week 7+)
| Component | Choice | Reason |
|-----------|--------|--------|
| STT | Deepgram | Real-time streaming |
| TTS | ElevenLabs | Best voice quality |
| Vector DB | Qdrant | Production-ready |
| Voice | LiveKit | Full real-time stack |
| Monitoring | LangSmith | Observability |

---

## 💰 Cost Estimation

### Development Phase (per month)
| Service | Usage | Cost |
|---------|-------|------|
| OpenAI GPT-4o-mini | 1M tokens | ~$0.60 |
| OpenAI Embeddings | 500K tokens | ~$0.01 |
| OpenAI Whisper API | 60 min | ~$0.36 |
| OpenAI TTS | 100K chars | ~$1.50 |
| **Total** | | **~$3/month** |

### Demo Phase (for a 30-min demo)
| Service | Usage | Cost |
|---------|-------|------|
| GPT-4o-mini | 50K tokens | ~$0.03 |
| Whisper | 15 min | ~$0.09 |
| TTS | 25K chars | ~$0.37 |
| **Total** | | **~$0.50/demo** |

---

## 🚀 Quick Start Commands

### Install Core Dependencies
```bash
# Backend
pip install fastapi uvicorn openai langchain langchain-openai chromadb \
  python-multipart websockets pydantic-settings

# For voice
pip install openai-whisper sounddevice numpy scipy

# For document processing
pip install pypdf python-docx unstructured

# Frontend
npx create-next-app@latest frontend --typescript --tailwind --eslint
cd frontend && npx shadcn@latest init
```

### Test API Connections
```python
# test_apis.py
import os
from openai import OpenAI

client = OpenAI()

# Test chat
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Hello!"}]
)
print("Chat:", response.choices[0].message.content)

# Test embeddings
embedding = client.embeddings.create(
    model="text-embedding-3-small",
    input="Hello world"
)
print("Embedding dims:", len(embedding.data[0].embedding))

# Test TTS
speech = client.audio.speech.create(
    model="tts-1",
    voice="nova",
    input="Hello! I am your AI assistant."
)
speech.stream_to_file("test_output.mp3")
print("TTS: Generated test_output.mp3")
```

---

*This guide will be updated as you progress through the POC.*



