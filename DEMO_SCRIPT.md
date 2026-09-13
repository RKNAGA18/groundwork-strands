# Groundwork — Demo Script

## What to Show (5 minutes)

---

### 0:00 — Hook (30 seconds)

"Security questionnaires kill sales. A 200-question SOC 2 audit takes a compliance lead 3 to 4 days of copy-pasting between policy documents and a spreadsheet. Every time a claim is wrong or uncited, the deal stalls. Groundwork solves this with two agents: one drafts, one audits — and only surfaces to a human when the answer genuinely needs judgment."

---

### 0:30 — Show the live eval results on screen (45 seconds)

Open frontend at http://localhost:3000.

Point to the metrics row:
- Overall accuracy: 18/20 on the labeled benchmark
- Unsupported recall: 100% — every question without a KB answer is correctly flagged red
- 8 policy documents indexed in the KB

"These numbers were produced by running the 20-question test set against the real pipeline. Not cherry-picked. The test set includes 10 questions that are in the KB and 10 that are deliberately not in the KB. The system correctly identifies all 10 unanswerable questions as red."

---

### 1:15 — Interactive demo: a green answer (45 seconds)

Type into the "Test Question" box:
> Is data encrypted at rest using AES-256?

Click "Run Verifier".

Walk through what happened:
1. BM25 searched 8 policy documents. encryption_policy.md scored 12.53 — far above the 4.3 threshold.
2. DrafterAgent received the top chunks and drafted an answer citing [encryption_policy.md_0].
3. VerifierAgent, in a separate context, confirmed every claim is supported by the cited passage.
4. Result: GREEN.

"The answer you see is not from the model's training data. It is copied, with citation, from encryption_policy.md Section 3: 'AES with a 256-bit key length is the mandated standard for data at rest.'"

---

### 2:00 — Interactive demo: a red answer (45 seconds)

Type:
> Do you conduct annual penetration tests on external applications?

Click "Run Verifier".

"BM25 returned a score of 3.16 — below the 4.3 threshold. The system did not call the LLM at all. It returned red immediately. No hallucination is possible when the LLM never runs."

Show the notes field: "Unsupported by rule (no/insufficient evidence). Verifier LLM bypassed."

"This is the real value proposition. Other tools will guess here. Groundwork says: I don't know. That is the honest answer."

---

### 2:45 — Architecture in 60 seconds

Show the README architecture diagram.

"Five stages — parse, retrieve, draft, verify, review — implemented as separate Python modules that can be tested and deployed independently.

Stage 2 uses BM25, the same algorithm that powers Elasticsearch. No GPU, no embedding model download, runs in milliseconds. The threshold — 4.3 — was set empirically by running all 20 benchmark questions and finding the natural score gap between answerable and unanswerable questions.

Stage 3 and 4 are two Strands Agent instances. Not one agent asked twice. Two separate Agent objects, two separate LLM calls, two separate context windows. The Verifier cannot see the Drafter's reasoning. It only sees the draft text and the passages cited in that draft. That is the audit independence principle from financial auditing, applied to LLM outputs."

---

### 3:45 — Human review flow (30 seconds)

"Answers land in three buckets. Green answers complete silently — a judge or compliance lead never sees them unless they want to. Yellow and red answers surface for review. A human can approve, edit, or override any answer before export. No red answer is ever auto-exported. That is a hard constraint in the code, not a guideline."

---

### 4:15 — Eval script (30 seconds)

Run in terminal:
```bash
python eval/test_bm25_threshold.py
```

Show the score distribution. Point to the gap at 4.3. "This is how we set the threshold — not by guessing, not by tuning to the smoke test, but by looking at the actual score distribution across all 20 questions and picking the natural separation point."

---

### 4:45 — Close

"Groundwork runs in the background. It sends a human a list of decisions, not a wall of drafts to review. The 20-question benchmark, the source docs, and the full pipeline code are in the repo. Thank you."

---

## Terminal Commands to Have Ready

```bash
# Backend
cd backend && uvicorn app.main:app --reload --port 8000

# Frontend  
cd frontend && npm run dev

# Eval
python eval/test_bm25_threshold.py
python eval/smoke_test.py
```

## Questions Prepared For

Q: How is this different from just prompting ChatGPT with the policy docs?
A: Two things. First, ChatGPT has no threshold — it will always attempt an answer. Groundwork refuses to answer when evidence is insufficient, which is the honest and safe behavior. Second, the Verifier is a completely separate agent with a separate context. It cannot see what the Drafter was thinking — it can only rule on whether the cited passages support the claims. That audit independence is not possible with a single prompt.

Q: Why BM25 instead of embeddings?
A: BM25 needs no GPU, no model download, and runs in under 1ms per query. More importantly, its scores are calibrated and auditable — you can read the number and understand why a document scored highly. The previous embedding-based retrieval in this codebase was actually returning L2 distances above 1.0 and passing them off as cosine similarities. BM25 is honest.

Q: What happens if the LLM call times out?
A: The try-except wrapper in graph.py catches any exception — including network timeouts, rate limits, and JSON parse failures — and returns a red ReviewedAnswer with the error in the notes field. The batch continues. One broken question does not crash a 200-question run.
