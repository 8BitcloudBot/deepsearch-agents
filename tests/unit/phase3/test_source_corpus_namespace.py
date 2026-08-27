from benchmarks.evaluation.source_contracts import Corpus, SourceRecord, corpus_sha256
from benchmarks.evaluation.source_corpus import load_corpus


def test_phase3_source_corpus_is_owned_by_evaluation_package():
    corpus = load_corpus()

    assert isinstance(corpus, Corpus)
    assert all(isinstance(source, SourceRecord) for source in corpus.sources)
    assert len(corpus_sha256(corpus)) == 64
