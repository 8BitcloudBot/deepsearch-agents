# Formal Local Knowledge Showcase

The formal Showcase knowledge pack is a small, versioned set of official
engineering documents. It proves that the existing knowledge worker can
retrieve real public text, preserve a stable
`collection:document:chunk` identity, and deliver that evidence through the
same citation and report contracts as the other sources.

It is not a general crawler, enterprise document platform, or retrieval
accuracy benchmark.

## Frozen Sources

The nine-candidate comparison is stored as structured public data in
[`candidates.json`](../../data/knowledge/showcase-v1/candidates.json):

| Candidate | Official publisher / license | Estimated characters / chunks | Decision |
|---|---|---:|---|
| Deep Agents | LangChain / MIT | 6,924 / 10 | Selected: broad authoritative product overview |
| DeepAgents Python package README | LangChain / MIT | 6,529 / 9 | Excluded: substantially duplicates the root README |
| LangGraph overview | LangChain / MIT | 6,351 / 9 | Excluded: less precise than checkpoint documentation |
| LangGraph Checkpoint | LangChain / MIT | 6,132 / 12 | Selected: focused persistence terminology |
| Python Qdrant Client | Qdrant / Apache-2.0 | 10,030 / 15 | Selected: path mode and local inference boundary |
| FastEmbed | Qdrant / Apache-2.0 | 8,928 / 12 | Selected: local embedding responsibility and representations |
| OWASP Prompt Injection Prevention | OWASP / CC BY-SA 4.0 | 23,486 / 34 | Selected: RAG poisoning and untrusted-data defenses |
| OWASP AI Agent Security | OWASP / CC BY-SA 4.0 | 30,426 / 43 | Excluded: overlaps the selected security source |
| Ragas RAG Evaluation and Metrics | Vibrant Labs / Apache-2.0 | 43,081 / 57 | Selected: precise evaluation vocabulary |

The estimates come from the frozen official checkout at each listed commit.
The JSON also records the URL, version, retrieval date, intended questions,
selection value, recommendation, and decision reason for every candidate.

The public source inventory is
[`data/knowledge/showcase-v1/sources.json`](../../data/knowledge/showcase-v1/sources.json).
It records the official URL, frozen commit, publisher, license, retrieval date,
content hash, selection reason, and intended questions for six documents:

- DeepAgents official README (MIT);
- LangGraph Checkpoint README (MIT);
- qdrant-client README (Apache-2.0);
- FastEmbed README (Apache-2.0);
- OWASP Prompt Injection Prevention Cheat Sheet (CC BY-SA 4.0);
- Ragas RAG evaluation and metrics documentation (Apache-2.0).

The repository does not redistribute the third-party document bodies. Place
verified UTF-8 copies under the paths declared by
[`build-catalog.json`](../../data/knowledge/showcase-v1/build-catalog.json) in
an explicit local source directory. `.data/knowledge-corpus/` is ignored by
Git and is the recommended destination for the normalized manifest and local
evaluation report.

## Build And Validate

The builder reads only the catalog paths supplied by the caller. It does not
fetch URLs, discover directories, or follow links.

```bash
PYTHONPATH=. .venv/bin/python scripts/build_showcase_knowledge.py \
  --catalog data/knowledge/showcase-v1/build-catalog.json \
  --source-root /explicit/path/to/verified-source-copies \
  --output .data/knowledge-corpus/showcase-v1/manifest.json

PYTHONPATH=. .venv/bin/python scripts/index_knowledge.py \
  --manifest .data/knowledge-corpus/showcase-v1/manifest.json \
  --index-path .data/knowledge-index \
  --collection deepsearch-showcase-v1 \
  --validate-only

PYTHONPATH=. .venv/bin/python scripts/index_knowledge.py \
  --manifest .data/knowledge-corpus/showcase-v1/manifest.json \
  --index-path .data/knowledge-index \
  --collection deepsearch-showcase-v1
```

The frozen build uses `semantic-markdown-v1`, preserves heading hierarchy in
`section_path`, and assigns stable document-scoped chunk IDs. The current
corpus has 6 documents and 140 semantic chunks. Its normalized text is about
92,101 characters rather than the earlier 1-3 MB planning estimate: retaining
high-density source text and the 80-180 chunk acceptance range was preferred
over duplicating content to meet a byte target.

## Fixed Retrieval Check

The question set is
[`questions.json`](../../data/knowledge/showcase-v1/questions.json). It covers
single-document facts, cross-section summaries, a two-document comparison,
synonyms, an explicit no-evidence case, version boundaries, and prompt
injection text treated as query data.

```bash
PYTHONPATH=. .venv/bin/python scripts/evaluate_showcase_knowledge.py \
  --questions data/knowledge/showcase-v1/questions.json \
  --index-path .data/knowledge-index \
  --output .data/knowledge-corpus/showcase-v1/evaluation-results.json
```

The evaluator uses the frozen FastEmbed model descriptor, Top-K of 8, and a
minimum cosine score of `0.40`. Passing means each question met its declared
document, chunk, section, collection, and no-evidence expectations. It must not
be reported as retrieval accuracy, answer correctness, or production quality.

## Showcase Configuration

The formal knowledge source remains behind the existing explicit Showcase
capability boundary:

```text
APP_PROFILE=showcase
SHOWCASE_ENABLED=1
SHOWCASE_SOURCES=knowledge
KNOWLEDGE_PROVIDER=qdrant-local
KNOWLEDGE_INDEX_PATH=.data/knowledge-index
KNOWLEDGE_COLLECTION=deepsearch-showcase-v1
KNOWLEDGE_EMBEDDING_PROVIDER=fastembed
KNOWLEDGE_EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
KNOWLEDGE_CHUNKING_VERSION=semantic-markdown-v1
KNOWLEDGE_MIN_SCORE=0.40
```

Configuration is not authorization to run a real LLM or Provider. The
credential-free formal-knowledge integration smoke exercises local Qdrant,
FastEmbed, source normalization, live citation schema `2.0.0`, Markdown, and
PDF without starting a real model, Tavily, or MySQL. A separate, explicitly
authorized Phase 9 real smoke later enabled only `knowledge,uploaded-file` and
validated the same artifact contract; its degraded tool attempts remain
recorded in the evidence file.

## Run The Formal Knowledge UI

After building `.data/knowledge-index`, start the explicit credential-free
scenario:

```bash
PYTHONPATH=. .venv/bin/python scripts/portfolio_demo.py \
  --scenario formal-knowledge --host 127.0.0.1 --port 8000

VITE_API_BASE_URL=http://127.0.0.1:8000 pnpm --dir frontend dev \
  --host 127.0.0.1 --port 5173
```

Open `http://127.0.0.1:5173/`, upload
`examples/portfolio_demo/showcase-notes.txt`, and submit:

```text
What defenses help an agent treat retrieved RAG content as untrusted data rather than instructions?
```

Web, MySQL, and upload remain repository-safe fixtures; the knowledge source
actually queries the formal Qdrant Local index with FastEmbed. A deterministic
local answer replaces a real LLM. The UI must show the official document
title, full `collection:document:chunk` locator, Markdown preview, and
Markdown/PDF downloads. If the index is absent, the CLI exits before starting
the server rather than creating an empty index.

## Evidence Boundary

Exact hashes, counts, commands, warnings, the screenshot waiver, and the K6
real-smoke result are recorded in
[Formal knowledge evidence](../verification/showcase-knowledge-evidence.md).
The repository-safe source inventory and question set are public; third-party
bodies, the built manifest, FastEmbed cache, Qdrant index, and raw evaluation
result remain local and Git-ignored.
