import pytest

from ringframe import profiles


def test_claude_profile_loads_and_digests():
    p = profiles.load("claude-code")
    assert p["profile_id"] == "claude-code"
    assert {c["id"] for c in p["capabilities"]} == {"native_plan", "native_goal", "native_direct"}
    assert len(profiles.sha256("claude-code")) == 64


@pytest.mark.parametrize("host", ["claude-code", "codex"])
@pytest.mark.parametrize("version", ["0.1.0", "2.2.0", "10.0.0-beta.1", "codex-cli 0.153.4", "2.1.263 (Claude Code)", "development", "", None])
def test_known_host_keeps_capabilities_independent_of_version(host, version):
    p = profiles.for_host({"name": host, "version": version})
    assert p["profile_id"] == host
    assert p["version_range"] is None
    assert profiles.capability(p, "native_plan") is not None
    assert profiles.for_host({"name": host}) == p


@pytest.mark.parametrize("host", ["cursor", "../codex", "", None])
def test_unrecognized_host_uses_manual_handoff(host):
    p = profiles.for_host({"name": host, "version": "2.2.0"})
    assert p["profile_id"] == "unknown"
    assert p["fallback"] == "human_handoff"
    assert profiles.capability(p, "native_plan") is None


def test_capability_lookup():
    p = profiles.load("claude-code")
    cap = profiles.capability(p, "native_plan")
    assert cap["activation"]["tool"] == "EnterPlanMode" and cap["delivery_mode"] == "native_dispatch"
    assert profiles.capability(p, "native_review") is None
    assert "write" in profiles.capability(p, "native_direct")["requires_explicit_request_for_effects"]


def test_codex_profile_is_handoff_only_with_request_user_input():
    p = profiles.load("codex")
    assert p["profile_id"] == "codex" and p["confirmation"] == {"tool": "request_user_input", "requires_feature": None}
    assert {c["id"] for c in p["capabilities"]} == {"native_plan", "native_goal", "native_direct"}
    for c in p["capabilities"]:
        if c["id"] != "native_direct":
            assert c["delivery_mode"] == "human_handoff" and c["activation"]["mechanism"] is None
    assert profiles.capability(p, "native_goal")["prompt_prefix"] == "/goal " and profiles.capability(p, "native_goal")["max_prompt_chars"] == 4000
    assert profiles.for_host({"name": "codex", "version": "codex-cli 0.153.1"})["profile_id"] == "codex"


def test_goal_is_a_capability_on_both_hosts_and_subagents_are_declared():
    for name in ("claude-code", "codex"):
        p = profiles.load(name)
        goal = profiles.capability(p, "native_goal")
        assert goal["delivery_mode"] == "human_handoff" and goal["prompt_prefix"] == "/goal " and p["subagents"] is True
