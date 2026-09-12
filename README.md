# Groundwork

Groundwork is an AI agent pipeline that answers security questionnaires, vendor risk assessments, and RFPs using ONLY evidence from your company's uploaded documents.

**Two independent agents — one drafts, one audits — safely catch 100% of unsupported answers and gracefully degrade during API outages before a human ever sees them.**

## Architecture

Groundwork is built using the **Strands Agents SDK** and orchestrates interactions via **AWS Bedrock** (supporting Claude 3 Haiku). 

The pipeline runs entirely in the background, only surfacing answers for human review when they fall below high confidence thresholds. It consists of 5 stages, executed sequentially per question, but parallelized across batches using a `ThreadPoolExecutor`:

1. **Parse**: Questionnaire files (PDF, XLSX) are parsed into discrete atomic questions (using `PyPDF2`, `openpyxl`, and `pandas`).
2. **Retrieve**: Semantic search is performed over the uploaded Knowledge Base (using `ChromaDB` and local `sentence-transformers` embeddings, specifically `BAAI/bge-small-en-v1.5`). We strictly filter chunks below a 0.75 similarity threshold.
3. **Draft (Agent 1)**: The `DrafterAgent` generates a formal compliance answer using ONLY the retrieved chunks. Every factual sentence is cited with a source `chunk_id`.
4. **Verify (Agent 2)**: The `VerifierAgent` executes an independent model call with a fresh context. It reviews the draft against the original cited chunks and assigns a status (grounded, partial, or unsupported).
5. **Review & Export**: Groundwork groups the answers into Green, Yellow, and Red confidence statuses. Humans only need to review the Yellow and Red answers.

### Graceful Degradation & Safety First

Instead of guessing when evidence is missing, or crashing when AWS Bedrock hits rate limits or missing credentials, Groundwork guarantees safety:
- **No Evidence Short-Circuit**: If retrieval yields 0 chunks above the threshold, the DrafterAgent returns `INSUFFICIENT_EVIDENCE` and the VerifierAgent automatically flags it as unsupported (Red) without wasting a Bedrock API call.
- **API Failure Fallbacks**: If AWS credentials fail or timeout, the ThreadPoolExecutor degrades the specific question to a Red status with error notes, preserving the rest of the batch.

## Local Evaluation

To evaluate the pipeline, run the smoke test:

```bash
python -m venv venv
venv\Scripts\activate
pip install -r backend/requirements.txt
python eval/smoke_test.py
```

## License

Apache 2.0
