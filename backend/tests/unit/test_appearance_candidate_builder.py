from __future__ import annotations

import inspect

from ops import build_appearance_candidates


def test_candidate_builder_is_non_active_complete_scene_and_restores_runtime():
    source = inspect.getsource(build_appearance_candidates.build)
    assert '"status": "staged"' in source
    assert '"visual_approval_required": True' in source
    assert '"presentation": "complete_scene"' in source
    assert '"matting": False' in source
    assert 'visual_approved=False' in source
    assert '_launcher("stop", component)' in source
    assert '_launcher("start", component)' in source
