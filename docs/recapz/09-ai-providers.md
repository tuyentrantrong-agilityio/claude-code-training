# AI provider choice (T03)

Status: **Proposal** for review. Prices were read from the vendors' pages on 2026-11-26
(links at the end) and change often; check them again before going live. Cost examples
are our own arithmetic from those list prices.

## 1. What Recapz needs

| Function | Used by | Must have |
|---|---|---|
| Speech to text, batch | Uploaded recordings (T12) | English and Vietnamese, speaker labels, timestamps |
| Speech to text, streaming | Live transcript, interpreter (T41, T28, later) | Vietnamese streaming, low latency |
| LLM | Recap JSON (T13), Ask answers (T15) | Reliable JSON, good Vietnamese, streaming, low price |
| Embeddings | Search index and Ask (T36) | Multilingual quality, fixed dimension for an HNSW index |
| Text to speech | Daily read, interpreter (T25, T28, later) | Vietnamese voices (decided later) |

## 2. Speech to text

| Provider / model | Vietnamese | Speaker labels | Streaming | List price (pay as you go) | Notes |
|---|---|---|---|---|---|
| Deepgram Nova-3 | Yes (`language=vi`) | Yes, add-on | Yes | $0.0048/min monolingual, $0.0058/min multilingual; diarization +$0.0020/min | $200 free credit, no card; diarization v2 for batch |
| ElevenLabs Scribe v3 | Yes (90+ languages) | Yes (batch) | Scribe v3 Live, separate model | $0.20 per hour of audio (Scribe v3), $0.22/hour (Live) | Vendor reports low Vietnamese WER on FLEURS |
| AssemblyAI | Yes (Universal-2, 99 languages) | Yes, +$0.02/hour batch | Yes (fewer languages) | Universal-2 $0.15/hour, Universal-3.5 Pro $0.21/hour | Newest models cover fewer languages; check Vietnamese per model |
| OpenAI gpt-4o-transcribe-diarize | Yes | Yes | Separate realtime models | About $0.006/min | 25 MB file limit per request, so long meetings need splitting |

**Proposal: Deepgram Nova-3** for batch and later streaming.
- One vendor covers upload (T12) and the live features (T41, T28) with the same API style.
- The free credit covers the whole practice without spending.
- Risk: Vietnamese accuracy is the unknown for every vendor. Before deciding for real,
  run two of our own recordings (one Vietnamese, one English) through Deepgram and
  ElevenLabs Scribe and compare the transcripts. The adapter layer (T34) keeps the switch
  to Scribe a configuration change.

## 3. LLM (recap and Ask)

| Model | Input / output per 1M tokens | Notes |
|---|---|---|
| Claude Haiku 5.5 | $0.10 / $0.50 for prompts up to 100K tokens; $0.50 / $2.50 above | Cheapest Claude; our recap and Ask prompts stay under 100K tokens |
| Claude Sonnet 5.5 | $2 / $10 | Higher quality if Haiku recaps are weak |
| DeepSeek (V4 family) | Low; check the official page (third-party figures disagree) | Data is processed outside the company's usual regions; check rules for client meetings |

**Proposal: Claude Haiku 5.5** for both recap and Ask, with Sonnet 5.5 as the fallback
model name in settings.
- Prompt sizes: a one-hour meeting is roughly 8,000 to 12,000 words, which stays well under
  the 100K-token tier.
- Streaming is supported, which the Ask SSE flow needs.

## 4. Embeddings

Anthropic does not offer an embedding model, so this is a separate vendor.

| Model | Price | Dimensions | Notes |
|---|---|---|---|
| OpenAI text-embedding-3-small | $0.02 per 1M tokens | 1,536 default, can be shortened | Cheap, widely used; multilingual quality to verify on Vietnamese queries |
| OpenAI text-embedding-3-large | $0.13 per 1M tokens | 3,072 default | Only if small is not good enough |

**Proposal: text-embedding-3-small with 1,536 dimensions.** Once fixed, the
`search_chunks.embedding` column can get that dimension and an HNSW index (follow-up
to T36).

## 5. Cost of one meeting (estimate)

One hour of audio with the proposal, list prices:

| Step | Calculation | Cost |
|---|---|---|
| Transcription | 60 min x ($0.0048 + $0.0020) | about $0.41 |
| Recap | about 15K input tokens x $0.10/1M + 2K output tokens x $0.50/1M | under $0.01 |
| Embeddings | about 15K tokens x $0.02/1M | under $0.001 |
| One Ask question | about 3K input + 300 output tokens on Haiku 5.5 | under $0.001 |

Transcription is almost the whole cost; the usage table (`usage_events`) already records
audio seconds and tokens per call, so the monthly limits in T27 can be based on it.

## 6. Privacy

All three vendors receive meeting audio or text. Before using real client or candidate
meetings, check the company's rules and each vendor's data retention options. The UI
already warns about third-party providers (T40).

## 7. What changes in the code

- New adapters behind the existing interfaces (T34): `deepgram` (batch STT),
  `anthropic` (LLM, including streaming), `openai` (embeddings).
- Selection stays in `.env`: `PROVIDER_STT_BATCH=deepgram`, `PROVIDER_LLM=anthropic`,
  `PROVIDER_EMBEDDING=openai`, plus the API keys. The default stays `fake`, so tests and
  CI never call paid APIs.
- A smoke command checks each configured provider with a tiny request.

## 8. Decision needed

1. Accept Deepgram Nova-3 + Claude Haiku 5.5 + text-embedding-3-small, or change one.
2. Create the three API keys (Deepgram, Anthropic, OpenAI) and put them in the local
   `.env` only.
3. Run the comparison on two real recordings before relying on the Vietnamese results.

## Sources

- Deepgram pricing: https://deepgram.com/pricing
- Deepgram Vietnamese: https://deepgram.com/product/speech-to-text/vietnamese
- ElevenLabs API pricing: https://elevenlabs.io/pricing/api
- AssemblyAI pricing: https://www.assemblyai.com/pricing
- OpenAI gpt-4o-transcribe-diarize: https://developers.openai.com/api/docs/models/gpt-4o-transcribe-diarize
- Claude pricing: https://platform.claude.com/docs/en/about-claude/pricing
- OpenAI text-embedding-3-small: https://developers.openai.com/api/docs/models/text-embedding-3-small
- DeepSeek pricing: https://api-docs.deepseek.com/quick_start/pricing
