# Groundwork — Demo Walkthrough

## Prerequisites

1. **AWS credentials** configured via `aws configure` or env vars
2. **Python 3.11+** and **Node.js 18+** installed
3. Backend dependencies installed

---

## Terminal 1: Start the Backend

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
# source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

### What to watch for in the terminal

The backend outputs **color-coded ANSI logs** every time it hits AWS Bedrock:

```
🔷  INVOKING AWS BEDROCK: anthropic.claude-3-haiku-20240307-v1:0
✅  BEDROCK RESPONSE RECEIVED  (model: anthropic.claude-3-haiku-20240307-v1:0, stop: end_turn)
📊  Tokens — input: 342, output: 128  (cumulative: 342 / 128)
```

These logs are **critical for the live demo** — they prove every answer comes from AWS Bedrock, not a local mock.

---

## Terminal 2: Start the Frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

---

## Terminal 3: Tail Bedrock Logs (optional, for screen recording)

If you want a dedicated terminal showing only Bedrock activity:

```bash
# Windows PowerShell — filter for Bedrock invocation lines
cd backend
uvicorn app.main:app --port 8000 2>&1 | Select-String "BEDROCK|Tokens"
```

```bash
# macOS/Linux — filter with grep
cd backend
uvicorn app.main:app --port 8000 2>&1 | grep --color=always -E "BEDROCK|Tokens|INVOKING"
```

---

## Demo Flow

### 1. Upload Knowledge Base
- Click **"Upload Knowledge Base"** in the UI
- Upload the synthetic policy documents from `eval/synthetic_kb/`
- Wait for the embedding + indexing to complete

### 2. Upload Questionnaire
- Click **"Upload Questionnaire"**
- Upload a CAIQ-Lite questionnaire (PDF or XLSX)
- The parser extracts individual questions

### 3. Run Pipeline
- Click **"Process"** to start the dual-agent pipeline
- Watch Terminal 1 for the Bedrock invocation logs
- The `ThreadPoolExecutor` processes up to 5 questions in parallel

### 4. Review Results
- Each answer shows a confidence badge:
  - 🟢 **Green** — grounded, high similarity → auto-approvable
  - 🟡 **Yellow** — partial or marginal → quick human glance
  - 🔴 **Red** — unsupported, no evidence → must review/edit
- **At least one answer will land on yellow or red** — an all-green result is treated as a bug

### 5. Export
- Approve or edit answers as needed
- Click **"Export"** to download a `.docx` with all responses

---

## Run the Evaluation Suite

```bash
cd eval
python run_eval.py
```

This reports:
- **Overall accuracy**: predicted status == expected status
- **Unsupported-detection precision**: of questions flagged unanswerable, how many actually were
- **Unsupported-detection recall**: of questions that SHOULD be flagged, how many were caught

---

## Verify AWS Connection

```bash
# Confirm credentials
aws sts get-caller-identity

# List available Bedrock models (confirm Claude 3 Haiku access)
aws bedrock list-foundation-models --region us-east-1 --query "modelSummaries[?contains(modelId, 'claude')].[modelId]" --output table
```

---

## Key Architecture Points for Judges

1. **Two independent agents** — DrafterAgent and VerifierAgent run in separate contexts with separate Bedrock invocations
2. **Empty evidence rule** — if retrieval returns zero chunks, the pipeline skips the Bedrock call and auto-returns "unsupported" (saves cost, prevents hallucination)
3. **Graceful degradation** — a single bad row produces a red result with error details; the pipeline never crashes
4. **Configurable parallelism** — `MAX_WORKERS=5` in `.env` controls ThreadPoolExecutor concurrency to stay within Bedrock rate limits
5. **Token tracking** — every Bedrock call logs input/output token counts for cost transparency
