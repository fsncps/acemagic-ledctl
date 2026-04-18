import importlib

import pytest

from ledctl.patterns import list_patterns, run_pattern


def test_list_patterns_returns_list():
    result = list_patterns()
    assert isinstance(result, list)
    assert len(result) > 0


def test_list_patterns_contains_known_patterns():
    result = list_patterns()
    assert "stillred" in result
    assert "stillblue" in result
    assert "breathered" in result
    assert "alarm" in result


def test_list_patterns_sorted():
    result = list_patterns()
    assert result == sorted(result)


def test_run_pattern_unknown_raises():
    with pytest.raises(SystemExit, match="Unknown pattern"):
        run_pattern("nonexistent")


def test_run_pattern_unknown_lists_available():
    try:
        run_pattern("nope")
    except SystemExit as e:
        msg = str(e)
        assert "alarm" in msg or "stillred" in msg


def test_all_pattern_modules_importable():
    for name in list_patterns():
        mod = importlib.import_module(f"ledctl.patterns.{name}")
        assert hasattr(mod, "run")
