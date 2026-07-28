"""Import tests — verify all Phase 1 example modules are importable.

These tests run without network access and without API keys.
"""


def test_import_settings():
    from examples.phase1 import settings  # noqa: F401


def test_import_events():
    from examples.phase1 import events  # noqa: F401


def test_import_runner():
    from examples.phase1 import runner  # noqa: F401
