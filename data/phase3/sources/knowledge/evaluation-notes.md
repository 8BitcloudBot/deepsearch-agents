# Evaluation Notes: Agent Research Baselines

Origin: curated internal evaluation notes
Captured at: 2026-08-07

- Offline deterministic runs use the versioned corpus only; mock evidence is never presented as real Provider quality.
- Every evaluation number is bound to dataset/version hash, corpus ID, model identity, prompt identity, configuration fingerprint, strategy and Git commit.
- Phase 3 measures topic recall, source coverage and task success; no arbitrary S1 threshold is declared before measured baselines exist.
- Reports record success, failure and limitations together, and never embed credentials, absolute paths or raw Provider responses.
- Generated evaluation outputs go to caller-supplied ignored directories; only schemas, fixed datasets and accepted summary evidence are versioned.

## Metrics

- Topic recall: the share of expected topics present in the final answer.
- Source coverage: the share of allowed sources whose content contributed to the answer.
- Task success: a terminal, non-failed result for the case.
- Reports separate offline evidence from real Provider evidence and record skipped reasons explicitly.

## Reproducibility

- Each source file carries a content hash recorded in the source manifest; the corpus fingerprint covers every source record.
- Case files are immutable once a dataset version is frozen; any edit changes the file hash recorded in the dataset manifest.
