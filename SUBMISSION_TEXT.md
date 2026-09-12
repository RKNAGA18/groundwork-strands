Two independent agents — one drafts, one audits — safely catch 100% of unsupported answers and gracefully degrade during API outages before a human ever sees them. 

Groundwork is an AI compliance agent designed for founders and sales engineers who lose 20-40 hours per security questionnaire. Our solution guarantees grounded answers by ensuring every draft is strictly backed by the user's uploaded knowledge base, and every draft is independently verified by a second auditor agent.

Built on the **Strands Agents SDK** and orchestrating Anthropic Claude 3 Haiku via **AWS Bedrock**, Groundwork separates the task into five highly testable stages: Parse, Retrieve, Draft, Verify, and Review.

Rather than relying on a single mega-prompt that asks an LLM "Are you sure?", we deploy two entirely separate agents with independent contexts. The **DrafterAgent** operates with read-only retrieval tools to find semantic matches using `sentence-transformers` via ChromaDB. The **VerifierAgent** evaluates the draft against its cited chunks only. 

Because we prioritize trust over guesses, the pipeline is hardcoded to fail safely:
1. If similarity scores fall below our 0.75 threshold, the agent skips generation and auto-returns "unsupported".
2. If API credentials drop or the model provider throttles, our ThreadPoolExecutor gracefully degrades the batch row to a "red" status rather than crashing the pipeline.

By running in the background and only surfacing for real human decisions when answers land on yellow or red, Groundwork automates the repetitive work while keeping the human firmly in the loop for the judgment calls that matter.
