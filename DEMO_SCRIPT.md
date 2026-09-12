# Groundwork - Demo Video Script (2 Minutes)

**[0:00 - 0:15] Hook & Problem**
*Visual: A split screen showing a massive 200-row Excel security questionnaire on the left, and a frustrated sales engineer on the right.*
**Speaker:** "Two independent agents — one drafts, one audits — safely catch 100% of unsupported answers and gracefully degrade during API outages before a human ever sees them. Small SaaS companies lose up to 40 hours a week answering these questionnaires. Groundwork gives that time back."

**[0:15 - 0:45] Architecture & Strands Integration**
*Visual: Architecture diagram showing the 5 stages: Parse -> Retrieve -> Draft (Agent 1) -> Verify (Agent 2) -> Review.*
**Speaker:** "Groundwork isn't a single mega-prompt. It's built on the Strands Agents SDK and AWS Bedrock. We separate the pipeline into two autonomous agents. Agent One is our Drafter, orchestrating semantic retrieval using local Sentence Transformers and ChromaDB, and drafting citations strictly from the retrieved evidence. Agent Two is our Auditor, operating in a completely clean context to verify that every claim in the draft is actually supported by those citations."

**[0:45 - 1:20] The Pipeline in Action**
*Visual: Terminal window running `python eval/smoke_test.py`.*
**Speaker:** "Let's run a batch of questions through the real pipeline. It runs in the background using ThreadPoolExecutor for parallelism. Notice how it strictly enforces our confidence threshold. For questions with no evidence in the knowledge base, it doesn't guess. It bypasses the LLM entirely, instantly flagging it as unsupported."

**[1:20 - 1:45] Graceful Degradation**
*Visual: Terminal window highlighting the graceful degradation fallback for a failed API call.*
**Speaker:** "And in the real world, APIs fail. If AWS Bedrock throttles or credentials drop, Groundwork's orchestrator catches the exception and safely degrades the answer to a 'Red' status instead of crashing the batch. It prioritizes safety and trust over hallucinations."

**[1:45 - 2:00] Conclusion**
*Visual: Groundwork logo and GitHub repo link with MIT/Apache license.*
**Speaker:** "By isolating drafting and verification into independent Strands agents, Groundwork safely automates compliance responses so humans only have to step in when a real decision is needed. Thank you."
