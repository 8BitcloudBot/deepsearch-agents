# source-review

**Description:** Reviews source materials for credibility and consistency.

**Trigger:** When the agent needs to verify claims against source documents.

**Input:** A claim and one or more source document snippets.

**Output:** A credibility assessment with supporting evidence.

**Rules:**

1. Every claim must be traceable to at least one source line.
2. Sources are ranked: official docs > release notes > README > blog posts.
3. Conflicting sources must be flagged, not silently resolved.

**No fabricated citations.** If a claim cannot be traced to a source, mark it as "unsupported."

**Example:**

Claim: "LangGraph supports checkpointing natively."
Source: "LangGraph's documentation describes `MemorySaver` as a built-in checkpointer."
Assessment: SUPPORTED — documentation is the authoritative source.
