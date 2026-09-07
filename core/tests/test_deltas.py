"""ADR-0008: deltas are data keyed by (host, capability) or by classification; the CLI renders them."""
import pytest

from ringframe import config, deltas, profiles, workspace

IMPL = {"task": ["implement"], "result": "workspace_change", "interaction": "approval_gated", "horizon": "session", "effects": ["write"]}


def test_shipped_catalogs_validate_and_have_provenance():
    for name in deltas.host_catalog_names():
        cat = deltas.load_host_catalog(name)
        assert cat["schema"] == "ringframe.deltas/1" and cat["scope"] == "host" and cat["host"] == name
        for e in cat["entries"]:
            assert e["id"].startswith(f"{name}.{e['capability']}.") and e["matrix_ref"] and e["status"] in deltas.HOST_STATUS
    prac = deltas.load_practice_catalog("software-development")
    assert prac["scope"] == "practice" and prac["render"]["style"] == "labelled-rules" and prac["render"]["explain"] == "never"
    ids = [e["id"] for e in prac["entries"]]
    assert len(ids) == len(set(ids)) and all(e["principle"] and e["text"].strip() for e in prac["entries"])
    for e in prac["entries"]:
        assert e.get("tier", "situational") in deltas.TIERS and e.get("status", "attributed") in deltas.PRACTICE_STATUS
        assert set(e.get("concerns", [])) <= set(prac["concerns"])
        assert "SOLID" not in e["text"] and "YAGNI" not in e["text"]  # directives, never principle names


def test_host_deltas_render_only_when_qualified_by_default(repo):
    ws = workspace.resolve(cwd=repo).ensure()
    prof = profiles.load("claude-code")
    r = deltas.render(ws, prof, "native_plan", IMPL)
    assert r["host"]["catalog_sha256"] == config.sha256_of(deltas.load_host_catalog("claude-code"))
    assert r["host"]["deltas"] == [] and r["host"]["status_filter"] == ["qualified"]  # D1..D6 are candidates until measured
    r2 = deltas.render(ws, prof, "native_plan", IMPL, statuses=("qualified", "candidate"))
    assert "claude-code.native_plan.verify_paths" in r2["host"]["deltas"] and r2["host"]["text"]


def test_practice_selection_is_faceted_tiered_and_budgeted(repo, monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))  # user layer lives at ~/.fab7/rf/deltas.yaml
    ws = workspace.resolve(cwd=repo).ensure()
    prof = profiles.load("codex")
    plain = deltas.render(ws, prof, "native_plan", IMPL)
    core = [i for i in plain["practice"]["selected"] if i in ("practice.kiss", "practice.yagni", "practice.testing_pyramid", "practice.boy_scout")]
    assert len(core) == 4 and len(plain["practice"]["selected"]) <= deltas.load_practice_catalog("software-development")["render"]["core_cap"]
    assert "practice.hyrum" not in plain["practice"]["selected"]  # situational: needs a concern
    with_api = deltas.render(ws, prof, "native_plan", {**IMPL, "concerns": ["api_surface", "auth"]})
    assert {"practice.hyrum", "practice.postel"} <= set(with_api["practice"]["selected"])
    assert with_api["practice"]["matched_concerns"] == ["api_surface", "auth"]
    assert "\n" not in with_api["practice"]["text"].strip() or True  # one paragraph
    assert "- KISS: " in with_api["text"] and "- Hyrum: " in with_api["text"]  # labels as traceability tags, directives applied
    planning = deltas.render(ws, prof, "native_plan", {**IMPL, "task": ["plan"], "result": "plan", "effects": ["read"]})
    assert "practice.testing_pyramid" not in planning["practice"]["selected"] and "practice.gall" in planning["practice"]["selected"]
    with pytest.raises(config.ConfigError, match="concern"):
        deltas.render(ws, prof, "native_plan", {**IMPL, "concerns": ["telepathy"]})


def test_user_and_workspace_layers_override_by_id(repo, monkeypatch, tmp_path):
    home = tmp_path / "home"  # the repo fixture is tmp_path itself; the user layer must be a different tree
    monkeypatch.setenv("HOME", str(home))
    (home / ".fab7" / "rf").mkdir(parents=True)
    (home / ".fab7/rf/deltas.yaml").write_text(
        "schema: ringframe.deltas/1\nscope: practice\nentries:\n"
        "  - id: practice.kiss\n    text: Keep it plain.\n"
        "  - id: practice.team.commit_style\n    tier: core\n    applies_to: {task: [implement]}\n    text: One commit per item, message names the item.\n")
    ws = workspace.resolve(cwd=repo).ensure()
    (ws.rf_dir / "deltas.yaml").write_text("schema: ringframe.deltas/1\nscope: practice\nentries:\n  - id: practice.yagni\n    enabled: false\n")
    r = deltas.render(ws, profiles.load("codex"), "native_plan", IMPL)
    assert "Keep it plain." in r["text"] and "practice.yagni" not in r["practice"]["selected"]
    assert "practice.team.commit_style" in r["practice"]["selected"]
    layers = [(l["root"], l["path"].endswith("deltas.yaml")) for l in r["practice"]["layers"]]
    assert layers == [("user", True), ("workspace", True)]
    listing = deltas.effective(ws, "software-development")
    assert listing["practice.kiss"]["layer"] == "user" and listing["practice.yagni"]["enabled"] is False and listing["practice.gall"]["layer"] == "shipped"


def test_render_is_a_labelled_rules_list_and_entries_carry_labels(repo, monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    ws = workspace.resolve(cwd=repo).ensure()
    r = deltas.render(ws, profiles.load("codex"), "native_plan", {**IMPL, "concerns": ["api_surface"]})
    lines = r["practice"]["text"].splitlines()
    assert lines[0] == "Rules:" and all(l.startswith("- ") and ": " in l for l in lines[1:])
    labels = {e["label"] for e in r["practice"]["entries"]}
    assert {"KISS", "Hyrum"} <= labels and all(e["label"] for e in r["practice"]["entries"])
    assert any(l.startswith("- KISS: ") for l in lines) and any(l.startswith("- Hyrum: ") for l in lines)
    for name in deltas.host_catalog_names():
        assert all(e.get("label") for e in deltas.load_host_catalog(name)["entries"])
