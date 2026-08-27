# Phase 4 Trustworthy Citations Evidence

> **Historical evidence:** Provider smoke names below record the accepted
> Phase 4 environment at that time. They are not current route or configuration
> guidance.

**Result:** Phase 4 accepted at closeout checkpoint `acf7c46`

This is a Codex-only acceptance record. It does not claim real Provider or model
quality, create a release, or activate Phase 5.

## Git Boundary

- Implementation acceptance HEAD: `e817c79`
- Branch: `main`
- Evidence capture began on the Phase 3 checkpoint; the verified Phase 4
  implementation was committed as `e817c79`, and the remaining fixtures,
  plan, roadmap and baseline state were fixed in closeout `acf7c46`.
  The untracked `.reasonix/` directory was not read or processed.
- Phase 3 corpus, datasets, runner, reports, S0 and S1 remain read-only inputs.

## Fresh Gates

All commands below exited `0` unless stated otherwise.

| Command | Result |
|---|---|
| `.venv/bin/python -m pytest tests/integration/phase4 tests/unit/phase4 -q` | `184 passed, 1 skipped` |
| `.venv/bin/python -m pytest tests/e2e/phase2/test_tutorial_closure.py tests/e2e/phase3 tests/integration/phase3 tests/unit/phase3 -q` | `302 passed, 2 skipped` |
| `.venv/bin/python -m pytest -q` | `925 passed, 14 skipped` |
| `pnpm --dir frontend exec vitest run` | `75 passed` |
| `pnpm --dir frontend exec eslint src` | passed |
| `pnpm --dir frontend run build` | passed; Vite production build |
| `.venv/bin/ruff check app tests` | passed |
| `.venv/bin/ruff format --check app tests` | `111 files already formatted` |
| `.venv/bin/pre-commit run --all-files` | ruff, ruff-format, detect-secrets passed |
| `git diff --check` | passed |

The Phase 4 API/event subset was rerun independently: `7 passed`. It verifies
validated citation retrieval, foreign-thread isolation, both citation artifact
list/download paths, ordered version-1 citation events, and exactly one terminal
event on success and citation failure. Tutorial profile remains citation-free.

## Offline Reproducibility

The following was run twice with `--dataset seed-10 --offline`; no model,
Provider, network, or versioned data was consulted or modified. The output
directory name is redacted because it is a machine-local temporary path:

```text
.venv/bin/python scripts/evaluate_citations.py --dataset seed-10 --offline --output <temporary-output>
```

```text
rule/offline:    precision=1.000000 recall=0.750000 entailment=0.600000 unsupported_claims=0.400000
semantic/mock:   precision=0.857143 recall=0.750000 entailment=0.700000 unsupported_claims=0.300000
semantic/real:   precision=null recall=null entailment=null unsupported_claims=null
```

Both runs produced the same `partitions.jsonl` SHA-256:
`90716fdce9e607b707bec381fa988c4af770aa60618094b627b47985c0c78dae`.
Both produced report fingerprint
`715e8ce32f371079d3f39c41dd293511638555cdc47b0cff3b2d1118a5a995aa` and three
partitions. The report directories were scanned for credentials, absolute paths,
authorization headers and raw Provider response markers with zero matches.

## Browser Evidence

P4-6 browser smoke was independently captured at 1440px and at a true `375x812`
CSS viewport using local Vite only. The mobile CDP metrics were
`innerWidth=375`, `scrollWidth=375`, `bodyScrollWidth=375`; all workbench panels
ended at `right=359`, so there was no horizontal overflow. Citation statuses,
source snippets, metrics and links are covered by the 75-test rendered mock
scenarios; the local browser smoke itself used no backend and therefore does not
claim a live Provider result.

## Explicit Skips And Limitations

- Phase 4 real semantic smoke: `PHASE4_REAL_SEMANTIC_SMOKE` was unset; no
  credentials or network were accessed.
- Phase 2 MySQL integration: `PHASE2_MYSQL_INTEGRATION` was unset (six skips).
- Phase 2 external Provider smokes: `PHASE2_TAVILY_SMOKE` and
  `PHASE2_RAGFLOW_SMOKE` were unset.
- Real model/provider smokes in Phase 1/2/3: their opt-in flags and/or
  `MODEL_API_KEY` were absent; no credentials or network were accessed.
- Full backend emitted one existing Starlette/httpx deprecation warning; it did
  not fail a gate.

## Handoff

P4-1 through P4-7 are accepted and frozen at closeout `acf7c46`. No tag, push,
release, or Phase 5 action was performed by this node.
