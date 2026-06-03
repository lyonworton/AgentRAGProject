import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.agents.state import AgentState
from app.agents.executor import _resolve_groups


class TestResolveGroups:
    def test_no_dependencies_all_parallel(self):
        sub_tasks = [
            {"id": "t1", "depends_on": []},
            {"id": "t2", "depends_on": []},
        ]
        groups = _resolve_groups(sub_tasks)
        assert groups == [["t1", "t2"]]

    def test_linear_dependency_two_groups(self):
        sub_tasks = [
            {"id": "t1", "depends_on": []},
            {"id": "t2", "depends_on": ["t1"]},
        ]
        groups = _resolve_groups(sub_tasks)
        assert groups == [["t1"], ["t2"]]

    def test_diamond_dependency(self):
        sub_tasks = [
            {"id": "t1", "depends_on": []},
            {"id": "t2", "depends_on": ["t1"]},
            {"id": "t3", "depends_on": ["t1"]},
            {"id": "t4", "depends_on": ["t2", "t3"]},
        ]
        groups = _resolve_groups(sub_tasks)
        assert groups == [["t1"], ["t2", "t3"], ["t4"]]

    def test_circular_dependency_raises(self):
        sub_tasks = [
            {"id": "t1", "depends_on": ["t2"]},
            {"id": "t2", "depends_on": ["t1"]},
        ]
        with pytest.raises(ValueError, match="Circular dependency"):
            _resolve_groups(sub_tasks)

    def test_unknown_dependency_raises(self):
        sub_tasks = [
            {"id": "t1", "depends_on": ["nonexistent"]},
        ]
        with pytest.raises(ValueError, match="depends on unknown task"):
            _resolve_groups(sub_tasks)

    def test_empty_list(self):
        groups = _resolve_groups([])
        assert groups == []