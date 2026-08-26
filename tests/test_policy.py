from __future__ import annotations

from autodev.policy import PolicyInput, decide


def _pi(role: str, kind: str, tool: str, path: str, *, red_test: bool = False) -> PolicyInput:
    return PolicyInput(role=role, kind=kind, tool_name=tool, tool_input={"file_path": path}, red_test=red_test)


def test_non_write_tools_are_always_allowed() -> None:
    assert decide(_pi("engineering", "implement", "Bash", "/x")).allow
    assert decide(_pi("engineering", "implement", "Read", "/repo/src/impl/x.py")).allow


def test_search_may_only_write_facts() -> None:
    assert decide(_pi("product-manager", "search", "Write", "/repo/artifacts/facts/f1.json")).allow
    denied = decide(_pi("product-manager", "search", "Write", "/repo/src/impl/x.py"))
    assert not denied.allow
    assert "artifacts/facts" in denied.reason


def test_contract_must_not_write_impl() -> None:
    assert decide(_pi("engineering", "contract", "Write", "/repo/contracts/rate_limit.pyi")).allow
    assert not decide(_pi("engineering", "contract", "Write", "/repo/src/impl/book/x.py")).allow


def test_implement_blocked_before_red_test() -> None:
    denied = decide(_pi("engineering", "implement", "Write", "/repo/src/impl/book/store.py"))
    assert not denied.allow
    assert "TDD gate" in denied.reason
    # once a failing test exists this pass, the same write is allowed.
    assert decide(_pi("engineering", "implement", "Write", "/repo/src/impl/book/store.py", red_test=True)).allow


def test_implement_may_write_tests_before_red() -> None:
    # writing the red test itself is not under src/**, so it is allowed.
    assert decide(_pi("engineering", "implement", "Write", "/repo/tests/book/test_store.py")).allow


def test_project_manager_must_not_edit_pod_source() -> None:
    denied = decide(_pi("project-manager", "reconcile", "Edit", "/repo/src/impl/book/store.py"))
    assert not denied.allow
    assert "pod source" in denied.reason
    # but it may write the tree JSON it owns.
    assert decide(
        _pi("project-manager", "reconcile", "Write", "/repo/product/pillars/p/features/f/leaves/l/leaf.json")
    ).allow


def test_integrate_is_allowed_here_enforced_physically() -> None:
    # integrate's boundary is sparse checkout (C5), so decide does not block it.
    assert decide(_pi("engineering", "integrate", "Write", "/repo/tests/integration/test_x.py")).allow


def test_missing_target_path_is_allowed() -> None:
    assert decide(PolicyInput(role="engineering", kind="implement", tool_name="Write", tool_input={})).allow
