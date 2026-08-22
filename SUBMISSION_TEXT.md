# Groundwork — Submission Text
### For: Agents for Humans Hackathon submission form field

---

Groundwork is an AI agent, built with the Strands Agents SDK, that
answers security questionnaires and RFPs on behalf of small B2B SaaS
teams — using only the company's own documents, with every claim cited,
and nothing invented.

**Who it's for:** founders, sales engineers, and compliance leads who lose
20-40 hours to a first-time questionnaire, usually rewriting the same
answers slightly differently every time a new deal requires one.

**Why it matters:** getting a security answer wrong has real consequences,
so guessing isn't an option. Groundwork separates drafting from
verification into two independent agents — a DrafterAgent that can only
answer from retrieved evidence, and a VerifierAgent, with no visibility
into the drafter's reasoning, that checks whether the citations actually
support the claim. In testing, that independent check caught
{{VERIFIER_CATCH_RATE}}% of drafts that would otherwise have shipped an
unsupported claim.

**How it works:** point it at a folder or inbox and it runs quietly in the
background. Most answers are fully grounded and complete without any
input. Only the ones it can't support surface for a human decision —
which is the whole point: an agent that only interrupts you when there's
something real to decide.

**Track:** Professional Agents.
