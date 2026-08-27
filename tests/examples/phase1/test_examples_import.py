"""Import tests — verify all Phase 1 example modules are importable.

These tests run without network access and without API keys.
"""

import importlib


def test_import_settings():
    from examples.phase1 import settings  # noqa: F401


def test_import_events():
    from examples.phase1 import events  # noqa: F401


def test_import_runner():
    from examples.phase1 import runner  # noqa: F401


def test_import_01_invoke():
    mod = importlib.import_module("examples.phase1.01_invoke")
    assert hasattr(mod, "main")


def test_import_02_stream():
    mod = importlib.import_module("examples.phase1.02_stream_chunks")
    assert hasattr(mod, "main")


def test_import_03_subagents():
    mod = importlib.import_module("examples.phase1.03_dictionary_subagents")
    assert hasattr(mod, "main")


def test_import_04_runnable():
    mod = importlib.import_module("examples.phase1.04_runnable_subagent")
    assert hasattr(mod, "main")


def test_import_05_interrupt():
    mod = importlib.import_module("examples.phase1.05_interrupt_resume")
    assert hasattr(mod, "main")


def test_import_06_backend():
    mod = importlib.import_module("examples.phase1.06_backend_store_memory")
    assert hasattr(mod, "main")


def test_import_07_middleware():
    mod = importlib.import_module("examples.phase1.07_middleware_skills")
    assert hasattr(mod, "main")
