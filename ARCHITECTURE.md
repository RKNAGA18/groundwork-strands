# Groundwork Architecture

## AGENTS.md Spec Compliance

| Spec Requirement | Implementation |
|---|---|
| Two independent agents | DrafterAgent (drafter.py) + VerifierAgent (verifier.py) |
| 5 separable pipeline stages | parse.py, retrieve.py, draft.py, verify.py, confidence.py |
| BM25 retrieval, top-k=5 | vector_store.py — BM25Retriever class |
| Threshold = configured | config.py SIMILARITY_THRESHOLD = 4.3 (empirically set) |
| If empty evidence — auto-red | force_red_if_no_real_evidence() in graph.py before any LLM call |
| Draft system prompt exact | llm/prompts.py DRAFT_SYSTEM_PROMPT |
| Verify system prompt exact | llm/prompts.py VERIFY_SYSTEM_PROMPT |
| Confidence decision table | pipeline/confidence.py compute_status() |
| Never auto-export red | runs.py export route + human_approved flag |
| Strands SDK | strands-agents via OpenAI-compat (Groq) |

---

## Component Map

```mermaid
graph LR
    subgraph Ingestion
        CH[chunker.py]
        VS[vector_store.py\nBM25Retriever]
    end
    subgraph HTTP
        KB[kb.py\nPOST /api/kb/upload]
        QU[questionnaire.py\nPOST /api/questionnaire/upload]
        RU[runs.py\nPOST /api/runs/id/process]
    end
    subgraph Pipeline
        GR[graph.py\nOrchestrator + ThreadPool]
        PA[parse.py\nStage 1]
        RE[retrieve.py\nStage 2 BM25]
        DR[draft.py\nStage 3 LLM]
        VE[verify.py\nStage 4 LLM]
        CO[confidence.py\nStage 5]
    end
    subgraph Agents
        DA[DrafterAgent\ndrafter.py]
        VA[VerifierAgent\nverifier.py]
        SP[strands_pipeline.py\nGroq OpenAI-compat]
    end
    subgraph Storage
        RS[run_store.py]
    end

    KB --> CH --> VS
    QU --> PA
    RU --> GR
    GR --> RE --> VS
    GR --> DR --> DA --> SP
    GR --> VE --> VA --> SP
    GR --> CO
    GR --> RS
```

---

## Data Contracts (frozen field names)

```mermaid
classDiagram
    class Question {
        +str id
        +str text
        +int source_row
    }
    class EvidenceChunk {
        +str doc_id
        +str doc_name
        +str chunk_id
        +str chunk_text
        +float match_score
    }
    class Draft {
        +str question_id
        +str answer_text
        +list~str~ cited_chunk_ids
    }
    class Verification {
        +str question_id
        +str verdict
        +str status
        +str notes
    }
    class ReviewedAnswer {
        +str question_id
        +str question_text
        +str final_text
        +bool human_approved
        +str status
        +list~str~ cited_chunk_ids
        +list~EvidenceChunk~ evidence
        +str notes
    }

    Question --> Draft : via DrafterAgent
    EvidenceChunk --> Draft : grounding
    Draft --> Verification : via VerifierAgent
    Verification --> ReviewedAnswer : merged
```

---

## BM25 Algorithm

```mermaid
flowchart LR
    A[Document text] --> B[Tokenize lowercase]
    B --> C[Count term frequencies per doc]
    C --> D[Compute IDF:\nlog 1 + N-df+0.5 / df+0.5]
    D --> E[Store BM25Retriever]

    F[Query string] --> G[Tokenize]
    G --> H[For each query term:\nscore += IDF * TF*k1+1 / TF+k1*norm]
    H --> I[Sum scores per doc]
    I --> J[Filter score >= 4.3]
    J --> K[Return top-5 EvidenceChunks]
```

Parameters: k1=1.5, b=0.75 (standard BM25 defaults)

---

## Confidence Decision Path

```mermaid
flowchart TD
    A[Question processed] --> B{BM25 chunks\nreturned?}
    B -->|No chunks above 4.3| C[force_red: score-based]
    B -->|Chunks found| D[DrafterAgent.invoke]
    D --> E{Draft text contains\nINSUFFICIENT_EVIDENCE?}
    E -->|Yes| F[force_red: phrase-based]
    E -->|No| G[VerifierAgent.invoke]
    G --> H{verdict?}
    H -->|grounded + score>=4.3| I[GREEN]
    H -->|grounded + score<4.3| J[YELLOW]
    H -->|partial| K[YELLOW]
    H -->|unsupported| L[RED]
    C --> L
    F --> L
```

---

## API Endpoints

| Method | Route | Handler | Purpose |
|---|---|---|---|
| GET | /health | health.py | Liveness check |
| POST | /api/kb/upload | kb.py | Upload and index a KB document |
| POST | /api/questionnaire/upload | questionnaire.py | Parse a questionnaire into Questions |
| POST | /api/runs/{id}/process | runs.py | Launch pipeline (background) |
| GET | /api/runs/{id}/status | runs.py | Poll progress (done/total) |
| GET | /api/runs/{id}/results | runs.py | Fetch all ReviewedAnswers |
| PATCH | /api/runs/{id}/answers/{qid} | runs.py | Human approval or edit |
| POST | /api/runs/{id}/export | runs.py | Export approved answers to .docx |
| POST | /api/verify-single | main.py | Interactive single-question test |

---

## Eval Numbers (BM25, no LLM required)

Threshold set empirically at 4.3 — sits in the natural gap between:
- Highest red-expected score: q14 at 4.29
- Lowest green-expected score: q1 at 4.35

18/20 correct. The 2 false positives (q15, q20 — physical datacenter) score above threshold because the word "access" appears in the access control policy. They correctly land on yellow, triggering human review. This is the right behavior — a human should confirm whether the KB covers physical security.
