# Groundwork — Architecture Spec (v2, exact parameters)

## Product identity
Groundwork is an AI agent that answers security questionnaires, vendor risk
assessments, and RFPs using ONLY evidence from a company's own uploaded
documents. Every answer must be traceable to a source. If no supporting
evidence exists, the agent must say so instead of guessing.

Target user: founders, sales engineers, and compliance leads at small B2B
SaaS companies who lose 20-40 hours per questionnaire.

## Front-loading rule (applies to README, text description, and video)
The first sentence anyone reads or hears must contain both: (1) that this
is two independent agents, not one, and (2) the real measured number
(verifier catch rate or accuracy). Do not build up to it — lead with it,
the way every winning entry in this category does. Example shape: "Two
independent agents — one drafts, one audits — catch X% of unsupported
answers before a human ever sees them."

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

## Chunking (knowledge base ingestion)
- Split by paragraph/section boundary first; hard-wrap anything still over
  512 tokens, with 50-token overlap between chunks.
- Store per chunk: doc_id, doc_name, chunk_id, chunk_text, section_heading
  (if extractable), page_number.
- Embed with a single consistent embedding model for the whole session
  (any current text-embedding model is fine — do not mix models within
  one knowledge base).

## Retrieval
- top_k = 5 chunks per question.
- similarity_threshold = 0.75 (cosine). Chunks below this are discarded,
  not just down-ranked.
- If zero chunks survive the threshold, evidence = [] for that question —
  this is the trigger for the automatic red/unsupported path. Do not
  fall back to a lower threshold to "find something."

## Draft — exact system prompt
You are a compliance response drafter. You will be given a question and a
set of evidence passages retrieved from the company's own knowledge base,
each with a chunk_id.

Rules:
1. Answer using ONLY information in the evidence passages. No outside
   knowledge, no general best practices not stated in the passages.
2. Every factual sentence must end with citation tags in the form
   [chunk_id].
3. If the evidence does not contain enough information, respond with
   exactly "INSUFFICIENT_EVIDENCE" and nothing else. Do not attempt a
   partial or best-guess answer.
4. Keep answers concise and in the tone of a formal compliance response.

Output JSON: {"answer_text": string, "cited_chunk_ids": [string]}
Temperature: 0.2.

## Verify — exact system prompt (separate call, separate context)
You are an independent compliance auditor. You did not write the draft you
are reviewing and have no access to anything beyond what is given here.

You will be given a draft answer and the exact evidence passages that were
cited to support it.

Classify as exactly one of:
- "grounded" — every claim is directly supported by the cited passages
- "partial" — some claims are supported, at least one goes beyond the
  passages
- "unsupported" — the passages do not support the core claim(s), or
  contradict them

Judge only whether the passages support the text — not whether the text
is true in general.

Output JSON: {"verdict": "grounded|partial|unsupported", "notes": string}
Temperature: 0.

If cited evidence list is empty, skip this call entirely — verdict is
"unsupported" by rule, not by model judgment.

## Confidence-status decision table
| Verdict      | Top similarity | Status |
|--------------|-----------------|--------|
| grounded     | >= 0.85         | green  |
| grounded     | 0.75 - 0.85     | yellow |
| partial      | any             | yellow |
| unsupported  | any             | red    |
| (no evidence, no call made) | -- | red  |

Note: "grounded" + weak match (0.75-0.85) → yellow. Technically grounded
but the similarity is marginal — worth a human glance.

## Data contracts (keep field names identical across all builds)
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

## Eval design (both builds implement the same eval, same test set)
- 15-25 labeled questions built from CAIQ-Lite content, each with an
  expected_status.
- Report two numbers, not one:
  - Overall accuracy: predicted status == expected status.
  - Unsupported-detection recall/precision: treat "unsupported" as the
    positive class. Recall = of the questions that SHOULD be flagged
    unanswerable, how many were correctly caught. Precision = of the
    questions flagged unanswerable, how many actually were. This second
    number is the real value proposition and belongs front and center in
    the submission, not buried — "correctly says I don't know" is the
    whole pitch.

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

### Tool signatures (write these exactly, fill in the bodies)
```python
# drafter.py
from strands import Agent, tool

@tool
def parse_questionnaire(file_path: str) -> list[dict]:
    """Split an uploaded questionnaire into discrete Question objects."""
    ...

@tool
def retrieve_evidence(question_text: str, kb_id: str) -> list[dict]:
    """Return up to 5 EvidenceChunk objects above the 0.75 similarity
    threshold. Returns [] if none clear the bar."""
    ...

@tool
def draft_answer(question_text: str, evidence: list[dict]) -> dict:
    """Call the LLM with the exact Draft system prompt from AGENTS.md.
    Returns a Draft object."""
    ...

DrafterAgent = Agent(
    model=...,  # Bedrock/Anthropic/OpenAI provider, whichever has credits
    system_prompt="You orchestrate parsing, retrieval, and grounded "
                  "drafting for one question at a time. Never answer "
                  "from your own knowledge.",
    tools=[parse_questionnaire, retrieve_evidence, draft_answer],
)
```
```python
# verifier.py
from strands import Agent, tool

@tool
def check_claim_against_sources(draft: dict, evidence: list[dict]) -> dict:
    """Call the LLM with the exact Verify system prompt from AGENTS.md.
    Returns a Verification object. If evidence is empty, skip the model
    call and return unsupported directly, per AGENTS.md."""
    ...

VerifierAgent = Agent(
    model=...,
    system_prompt="You audit drafts against their cited sources only. "
                  "You did not write the draft and have no other context.",
    tools=[check_claim_against_sources],
)
```

### Composition recommendation
For the hackathon timeline, default to plain Python orchestration —
call DrafterAgent, pass its output straight into VerifierAgent, apply
the status table in orchestrator.py. Same architectural separation
(two independent agents, two independent contexts) with far less risk
of losing hours to an unfamiliar multi-agent API. Only reach for
Strands' native Workflow primitive if there's real time left over.

### Background framing
trigger.py should represent "runs in the background, only surfaces for
a real decision" — for the demo, a manual trigger or a watched-folder
script that simulates a new questionnaire arriving is enough.
Green-status results should complete silently; only yellow/red should
produce visible output.

### AgentCore deployment (stretch goal — verified steps)
```bash
python -m venv .venv && source .venv/bin/activate
pip install "bedrock-agentcore-starter-toolkit>=0.1.21" \
            strands-agents strands-agents-tools boto3
aws configure

agentcore configure -e orchestrator.py
agentcore launch
```
Worth mentioning by name in ARCHITECTURE.md even if only partially
deployed — explicitly called out as strengthening Technical Implementation.
