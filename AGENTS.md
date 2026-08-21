# Groundwork — Project Rules

## Product identity
Groundwork is an AI agent that answers security questionnaires, vendor risk
assessments, and RFPs using ONLY evidence from a company's own uploaded
documents. Every answer must be traceable to a source. If no supporting
evidence exists, the agent must say so instead of guessing.

Target user: founders, sales engineers, and compliance leads at small B2B
SaaS companies who lose 20-40 hours per questionnaire.

## Non-negotiable architecture contract
The pipeline has five stages and they must remain separable, testable units,
not one long prompt:
1. Parse — split an uploaded questionnaire (PDF/XLSX) into discrete atomic
   questions.
2. Retrieve — semantic search over the user's own knowledge base for each
   question; return top-k relevant chunks with similarity scores.
3. Draft — generate an answer using ONLY the retrieved chunks as grounding;
   every sentence must cite a source chunk id.
4. Verify — a SEPARATE model call (different invocation, not the same
   context asking "are you sure?"). Given only the draft and its cited
   chunks, judge support: grounded / partial / unsupported. If the
   retrieved-chunk list is empty, skip the model call entirely and
   auto-return "unsupported" — never let drafting improvise from nothing.
5. Review & export — surface a confidence status per answer: green
   (grounded), yellow (partial), red (unsupported/no evidence). A human
   approves or edits before export. Never auto-export a red answer.

## Data contracts (keep field names identical across all three builds)
```json
// Question
{ "id": "string", "text": "string", "source_row": "number|null" }

// EvidenceChunk
{ "doc_id": "string", "doc_name": "string", "chunk_id": "string",
  "chunk_text": "string", "similarity": "number" }

// Draft
{ "question_id": "string", "answer_text": "string",
  "cited_chunk_ids": ["string"] }

// Verification
{ "question_id": "string", "verdict": "grounded|partial|unsupported",
  "status": "green|yellow|red", "notes": "string" }

// ReviewedAnswer
{ "question_id": "string", "final_text": "string",
  "human_approved": "boolean" }
```

## Sample data policy
Use the free public CAIQ-Lite bundle (Cloud Security Alliance) as the
demo questionnaire. Build a small synthetic company knowledge base
(5-10 short policy docs) for the demo — never use real customer or
company confidential data in a hackathon submission.

## Definition of done for the pipeline (applies to every build)
- A full questionnaire batch (not one cherry-picked question) processes
  end to end.
- At least one answer in the demo legitimately lands on red or yellow —
  an all-green result looks staged and should be treated as a bug, not
  a win.
- A small labeled test set (15-25 Q&A pairs with known correct grounding)
  exists and an eval script reports a measured accuracy/grounding
  percentage. This number belongs in the final submission materials.

---

## Target: Agents for Humans Hackathon (AWS Strands SDK, Professional Agents track)
- Framework: Strands Agents SDK (`pip install strands-agents`).
  Model-driven agent loop, not an explicit graph — express the pipeline
  as two composed agents, not one, to preserve verifier independence:
    - DrafterAgent: tools = parse_questionnaire, retrieve_evidence,
      draft_answer
    - VerifierAgent: tools = check_claim_against_sources
  Top-level orchestration calls DrafterAgent per question, then passes
  its output to VerifierAgent, then routes on the resulting status —
  same contract as AGENTS.md, implemented Strands-natively rather than
  as a LangGraph state machine.
- Model: Bedrock, Anthropic, or OpenAI via Strands' model providers —
  pick whichever you have credits for (the $50 AWS credit covers Bedrock
  usage).
- Frame the product for THIS event's theme explicitly: it should run
  autonomously against a watched inbox/folder for incoming
  questionnaires and only surface to a human when an answer lands on
  yellow or red — "runs in the background, only surfaces for a real
  decision" is the event's own framing, and it's also just what the
  confidence-scoring design already does.
- Track: Professional Agents ("makes someone dramatically better at
  work they already do... repetitive, judgment-heavy tasks").
- Stretch goal, not required: deploy via AgentCore — explicitly called
  out as strengthening the Technical Implementation score.
- Required: MIT or Apache license visible in the repo's About section,
  an AWS Builder ID, a README, an architecture diagram, and a demo
  video (≤5 min, no on-camera appearance needed) covering the problem,
  who it's for, and why it matters.
- This is a fresh repo — do not carry commit history from the AI
  Builders build even though the underlying spec is the same.
