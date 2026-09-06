import pytest

from ringframe import profiles


def test_claude_profile_loads_and_digests():
    p = profiles.load("claude-code")
    assert p["profile_id"] == "claude-code@2.1"
    assert {c["id"] for c in p["capabilities"]} == {"native_plan", "native_direct"}
    assert len(profiles.sha256("claude-code")) == 64


def test_for_host_matches_version_range():
    assert profiles.for_host({"name": "claude-code", "version": "2.1.260"})["profile_id"] == "claude-code@2.1"
    assert profiles.for_host({"name": "claude-code", "version": "2.1.999"})["profile_id"] == "claude-code@2.1"
    assert profiles.for_host({"name": "claude-code", "version": "2.1.263 (Claude Code)"})["profile_id"] == "claude-code@2.1"


def test_for_host_degrades_to_unknown_outside_range_or_unknown_host():
    assert profiles.for_host({"name": "claude-code", "version": "2.2.0"})["profile_id"] == "unknown"
    assert profiles.for_host({"name": "cursor", "version": "1.0"})["profile_id"] == "unknown"
    assert profiles.for_host({"name": "claude-code", "version": "2.2.0"})["fallback"] == "human_handoff"


def test_capability_lookup():
    p = profiles.load("claude-code")
    cap = profiles.capability(p, "native_plan")
    assert cap["activation"]["tool"] == "EnterPlanMode" and cap["delivery_mode"] == "native_dispatch"
    assert profiles.capability(p, "native_goal") is None
    assert "write" in profiles.capability(p, "native_direct")["requires_explicit_request_for_effects"]


def test_codex_profile_is_handoff_only_with_request_user_input():
    p = profiles.load("codex")
    assert p["profile_id"] == "codex@0.153" and p["confirmation"] == {"tool": "request_user_input", "requires_feature": "default_mode_request_user_input"}
    assert {c["id"] for c in p["capabilities"]} == {"native_plan", "native_goal", "native_direct"}
    for c in p["capabilities"]:
        if c["id"] != "native_direct":
            assert c["delivery_mode"] == "human_handoff" and c["activation"]["mechanism"] is None
    assert profiles.capability(p, "native_goal")["prompt_prefix"] == "/goal " and profiles.capability(p, "native_goal")["max_prompt_chars"] == 4000
    assert profiles.for_host({"name": "codex", "version": "codex-cli 0.153.1"})["profile_id"] == "codex@0.153"
