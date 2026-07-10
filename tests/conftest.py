from ledctl.core import MODE, MODES


def test_mode_names_match_constants():
    """Registry tripwire (CR-F4): guard against re-introducing a second
    source of truth for the mode name<->value map."""
    assert MODES["rainbow"] == MODE.RAINBOW
    assert MODES["breathing"] == MODE.BREATH
    assert MODES["cycle"] == MODE.CYCLE
    assert MODES["off"] == MODE.OFF
    assert MODES["auto"] == MODE.AUTO
