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


# --- J1: verb authority + technical-writer no-source-edit --------------------


def _bash(role: str, command: str) -> PolicyInput:
    return PolicyInput(role=role, kind="search", tool_name="Bash", tool_input={"command": command})


def test_only_product_manager_may_add_pillars() -> None:
    assert decide(_bash("product-manager", "uv run autodev product add-pillars proj --pillar x")).allow
    denied = decide(_bash("engineering", "uv run autodev product add-pillars proj --pillar x"))
    assert not denied.allow
    assert "only product-manager may run" in denied.reason


def test_only_product_manager_may_add_features() -> None:
    assert decide(_bash("product-manager", "python -m autodev product add-features proj --pillar x")).allow
    assert not decide(_bash("project-manager", "python -m autodev product add-features proj --pillar x")).allow


def test_only_project_manager_may_decompose_feature() -> None:
    assert decide(_bash("project-manager", "autodev product decompose-feature proj --feature f")).allow
    assert not decide(_bash("engineering", "autodev product decompose-feature proj --feature f")).allow


def test_only_engineering_may_set_leaf_status() -> None:
    assert decide(
        _bash("engineering", "autodev product set-leaf-status proj --feature f --leaf l --status verified")
    ).allow
    assert not decide(
        _bash("product-manager", "autodev product set-leaf-status proj --feature f --leaf l --status verified")
    ).allow


def test_unconstrained_bash_is_allowed_for_any_role() -> None:
    assert decide(_bash("engineering", "uv run pytest")).allow
    # a product verb with no authority row (set-pillar-docs) is unconstrained.
    assert decide(_bash("technical-writer", "autodev product set-pillar-docs proj --pillar x --state done")).allow


def test_technical_writer_may_write_only_the_pillar_docs() -> None:
    allowed = decide(
        PolicyInput(
            role="technical-writer",
            kind="document",
            tool_name="Write",
            tool_input={"file_path": "/repo/product/pillars/replay-engine/README.md"},
        )
    )
    assert allowed.allow
    denied = decide(
        PolicyInput(
            role="technical-writer",
            kind="document",
            tool_name="Write",
            tool_input={"file_path": "/repo/src/impl/replay-engine/store.py"},
        )
    )
    assert not denied.allow
    assert "pillar docs" in denied.reason
