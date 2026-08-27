# Beginner v2 local knowledge pack

This is a separate six-document corpus for the beginner test set. It uses the
same formal Qdrant Local + FastEmbed contract as the existing knowledge pack,
but has its own collection, manifest, source inventory, and index path.

The source copies are downloaded from the pinned public URLs listed in
`sources.json`. They are local evidence only; the report must preserve source
titles, excerpts, and locators rather than treating them as answer text.

Build and validate with:

```bash
PYTHONPATH=. .venv/bin/python scripts/build_showcase_knowledge.py \
  --catalog data/knowledge/beginner-v2/build-catalog.json \
  --source-root .data/knowledge-corpus/beginner-v2/sources \
  --output .data/knowledge-corpus/beginner-v2/manifest.json

PYTHONPATH=. .venv/bin/python scripts/index_knowledge.py \
  --manifest .data/knowledge-corpus/beginner-v2/manifest.json \
  --index-path .data/knowledge-index-beginner-v2 \
  --collection deepsearch-beginner-v2 \
  --validate-only

PYTHONPATH=. .venv/bin/python scripts/index_knowledge.py \
  --manifest .data/knowledge-corpus/beginner-v2/manifest.json \
  --index-path .data/knowledge-index-beginner-v2 \
  --collection deepsearch-beginner-v2

PYTHONPATH=. .venv/bin/python scripts/evaluate_showcase_knowledge.py \
  --questions data/knowledge/beginner-v2/questions.json \
  --index-path .data/knowledge-index-beginner-v2 \
  --output .data/knowledge-corpus/beginner-v2/evaluation-results.json
```
