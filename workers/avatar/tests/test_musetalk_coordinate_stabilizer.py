from __future__ import annotations

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from ops.build_musetalk_avatar import stabilize_coordinates


def test_source_coordinates_are_preserved():
    source = [[10, 20, 30, 40], [12, 22, 32, 42]]
    assert stabilize_coordinates(source, "source") == source


def test_median_coordinates_are_constant_and_rounded():
    source = [[10, 20, 30, 40], [12, 22, 32, 42], [14, 24, 34, 44]]
    assert stabilize_coordinates(source, "median") == [[12, 22, 32, 42]] * 3


def test_unknown_mode_fails_closed():
    with pytest.raises(ValueError, match="unsupported coordinate stabilization"):
        stabilize_coordinates([[10, 20, 30, 40]], "magic")
