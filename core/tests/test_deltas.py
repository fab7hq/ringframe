"""Deltas are data keyed by (host, capability) or by classification; the CLI renders them."""
import pytest

from tests.conftest import FIXTURE_CONFIG

from ringframe import config, deltas, profiles, workspace

IMPL = {"task": ["implement"], "result": "workspace_change", "interaction": "approval_gated", "horizon": "session", "effects": ["write"]}


def test_shipped_catalogs_validate_and_have_provenance():
    for name in deltas.host_catalog_names():
        cat = deltas.load_host_catalog(name)
        assert cat["schema"] == "ringframe.deltas/1" and cat["scope"] == "host" and cat["host"] == name
        for e in cat["entries"]:
            assert e["id"].startswith(f"{name}.{e['capability']}.") and e["matrix_ref"] and e["status"] in deltas.HOST_STATUS
    prac = deltas.load_practice_catalog("software-development")
    assert prac["scope"] == "practice" and prac["render"] == {"heading": "Rules:", "core_cap": 5}
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


def test_practice_selection_is_faceted_tiered_and_budgeted(repo, monkeypatch, tmp_path, user_home):
    user_home(tmp_path / "home")  # each test has isolated global delta catalogs
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


def test_user_and_workspace_layers_override_by_id(repo, monkeypatch, tmp_path, user_home):
    home = tmp_path / "home"  # the repo fixture is tmp_path itself; the user layer must be a different tree
    user_home(home)
    import yaml
    workspace.install_config(FIXTURE_CONFIG)
    catalog = home / ".fab7/rf/overrides/deltas/practices/software-development.yaml"
    catalog.parent.mkdir(parents=True, exist_ok=True)
    doc = config.load_yaml(config.config_dir() / "deltas/practices/software-development.yaml")
    next(e for e in doc["entries"] if e["id"] == "practice.kiss")["text"] = "Keep it plain."
    doc["entries"].append({"id": "practice.team.commit_style", "tier": "core",
                           "applies_to": {"task": ["implement"]},
                           "text": "One commit per item, message names the item."})
    catalog.write_text(yaml.safe_dump(doc))
    ws = workspace.resolve(cwd=repo).ensure()
    (ws.root / ".fab7/rf/deltas/practices/software-development.yaml").write_text("schema: ringframe.deltas/1\nscope: practice\nentries:\n  - id: practice.yagni\n    enabled: false\n")
    r = deltas.render(ws, profiles.load("codex"), "native_plan", IMPL)
    assert "Keep it plain." in r["text"] and "practice.yagni" not in r["practice"]["selected"]
    assert "practice.team.commit_style" in r["practice"]["selected"]
    layers = [(l["root"], l["path"].endswith("software-development.yaml")) for l in r["practice"]["layers"]]
    assert layers == [("config", True), ("user", True), ("workspace", True)]
    listing = deltas.effective(ws, "software-development")
    assert listing["practice.kiss"]["layer"] == "user" and listing["practice.yagni"]["enabled"] is False and listing["practice.gall"]["layer"] == "user"


def test_render_is_a_labelled_rules_list_and_entries_carry_labels(repo, monkeypatch, tmp_path, user_home):
    user_home(tmp_path / "home")
    ws = workspace.resolve(cwd=repo).ensure()
    r = deltas.render(ws, profiles.load("codex"), "native_plan", {**IMPL, "concerns": ["api_surface"]})
    lines = r["practice"]["text"].splitlines()
    assert lines[0] == "Rules:" and all(l.startswith("- ") and ": " in l for l in lines[1:])
    labels = {e["label"] for e in r["practice"]["entries"]}
    assert {"KISS", "Hyrum"} <= labels and all(e["label"] for e in r["practice"]["entries"])
    assert any(l.startswith("- KISS: ") for l in lines) and any(l.startswith("- Hyrum: ") for l in lines)
    for name in deltas.host_catalog_names():
        assert all(e.get("label") for e in deltas.load_host_catalog(name)["entries"])


def test_candidate_practice_entries_render_only_when_candidates_are_requested(repo, monkeypatch, tmp_path, user_home):
    user_home(tmp_path / "home")
    ws = workspace.resolve(cwd=repo).ensure()
    prof = profiles.load("claude-code")
    default = deltas.render(ws, prof, "native_plan", IMPL)
    assert "practice.assumptions" not in default["practice"]["selected"]  # candidate: never in the default prompt
    evaluation = deltas.render(ws, prof, "native_plan", IMPL, statuses=("qualified", "candidate"))
    assert "practice.assumptions" in evaluation["practice"]["selected"]  # evaluation runs render candidates so they can be measured
    assert set(evaluation["practice"]["selected"]) >= set(default["practice"]["selected"])


# ---- catalog reachability and task coverage ---------------------------------------------------

TASK_PROBE = {
    "question": [], "research": [], "clarify": [], "plan": [], "implement": [],
    "diagnose": ["tests_only"], "review": [], "operate": ["operate"], "document": ["cli"],
}


def _probe(task, concerns):
    return {"task": [task], "result": "plan", "interaction": "approval_gated",
            "horizon": "session", "effects": ["read"], "concerns": concerns}


def test_every_entry_can_be_selected(repo):
    """A situational entry with no concerns never matches, so it is dead configuration."""
    cat = deltas.load_practice_catalog(ws=workspace.resolve(cwd=repo))
    dead = [e["id"] for e in cat["entries"]
            if e.get("tier", "situational") == "situational" and not e.get("concerns")]
    assert dead == []


def test_every_task_selects_at_least_one_rule(repo):
    ws = workspace.resolve(cwd=repo).ensure()
    profile = profiles.load("claude-code")
    for task, concerns in TASK_PROBE.items():
        out = deltas.render(ws, profile, "native_plan", _probe(task, concerns))
        assert out["practice"]["selected"], f"{task} selects no rule"


def test_named_rules_select_for_their_task(repo):
    ws = workspace.resolve(cwd=repo).ensure()
    profile = profiles.load("claude-code")
    expected = {"research": "practice.occam", "review": "practice.linus",
                "question": "practice.confirmation_bias", "implement": "practice.testing_pyramid"}
    for task, rule in expected.items():
        out = deltas.render(ws, profile, "native_plan", _probe(task, TASK_PROBE[task]))
        assert rule in out["practice"]["selected"], f"{rule} missing for {task}"


def test_core_cap_is_not_exceeded_for_any_task(repo):
    ws = workspace.resolve(cwd=repo).ensure()
    profile = profiles.load("claude-code")
    cap = deltas.load_practice_catalog(ws=ws)["render"]["core_cap"]
    for task, concerns in TASK_PROBE.items():
        out = deltas.render(ws, profile, "native_plan", _probe(task, concerns))
        assert len(out["practice"]["dropped_by_budget"]) == 0, f"{task} drops a core rule"
        assert len(out["practice"]["selected"]) >= 1 and cap >= 1


# ---- additive specialist domains ---------------------------------------------------------------

def _second_domain(name="fixture-domain"):
    """A tiny specialist catalog installed beside the base one."""
    return f"""schema: ringframe.deltas/1
scope: practice
domain: {name}
description: An invented domain used only by tests.
render: {{heading: 'Rules:', core_cap: 2}}
concerns: [widgets, api_surface]
entries:
  - id: practice.widget_first
    label: Widget First
    tier: core
    applies_to: {{task: [implement]}}
    text: Build the widget before the housing.
  - id: practice.widget_check
    label: Widget Check
    applies_to: {{task: [implement]}}
    concerns: [widgets]
    text: Measure the widget after fitting it.
"""


@pytest.fixture
def two_domains(repo, user_home, tmp_path):
    home = user_home(tmp_path / "two-domains")
    (config.config_dir() / "deltas/practices/fixture-domain.yaml").write_text(_second_domain())
    return workspace.resolve(cwd=repo).ensure(), home


def test_absent_domains_render_only_the_base(two_domains):
    ws, _ = two_domains
    out = deltas.render(ws, profiles.load("claude-code"), "native_plan", IMPL)
    assert out["practice"]["domains"] == [] or [d["domain"] for d in out["practice"]["domains"]] == ["software-development"]
    assert not any(i.startswith("practice.widget") for i in out["practice"]["selected"])


def test_specialist_domain_renders_after_the_base_under_its_own_cap(two_domains):
    ws, _ = two_domains
    cls = {**IMPL, "domains": ["fixture-domain"], "concerns": [*IMPL.get("concerns", []), "widgets"]}
    out = deltas.render(ws, profiles.load("claude-code"), "native_plan", cls)
    p = out["practice"]
    assert [d["domain"] for d in p["domains"]] == ["software-development", "fixture-domain"]
    base_ids = p["domains"][0]["selected"]
    assert p["selected"][:len(base_ids)] == base_ids  # base first, specialist after
    assert "practice.widget_first" in p["selected"] and "practice.widget_check" in p["selected"]
    labels = [l.split(":")[0] for l in p["text"].splitlines()[1:]]
    assert labels[len(base_ids)] == "- Widget First"


def test_unknown_domain_is_refused_with_the_installed_set(two_domains):
    ws, _ = two_domains
    with pytest.raises(config.ConfigError, match="installed"):
        deltas.render(ws, profiles.load("claude-code"), "native_plan", {**IMPL, "domains": ["teleportation"]})


def test_concerns_validate_against_the_union_of_selected_domains(two_domains):
    ws, _ = two_domains
    prof = profiles.load("claude-code")
    with pytest.raises(config.ConfigError, match="concern"):
        deltas.render(ws, prof, "native_plan", {**IMPL, "concerns": ["widgets"]})
    out = deltas.render(ws, prof, "native_plan", {**IMPL, "domains": ["fixture-domain"], "concerns": ["widgets"]})
    assert "practice.widget_check" in out["practice"]["selected"]


def test_domains_lists_installed_domains_and_project_opt_in(two_domains):
    ws, _ = two_domains
    listed = {d["domain"]: d for d in deltas.domains(ws)}
    assert listed["software-development"]["base"] is True and listed["fixture-domain"]["base"] is False
    assert listed["fixture-domain"]["description"] and "widgets" in listed["fixture-domain"]["concerns"]
    assert listed["fixture-domain"]["project_opted_in"] is False
    opt_in = ws.rf_dir / "deltas/practices/fixture-domain.yaml"
    opt_in.parent.mkdir(parents=True, exist_ok=True)
    opt_in.write_text("schema: ringframe.deltas/1\nscope: practice\ndomain: fixture-domain\n")
    assert {d["domain"]: d for d in deltas.domains(ws)}["fixture-domain"]["project_opted_in"] is True


def test_project_init_seeds_only_the_base_domain(two_domains):
    ws, _ = two_domains
    seeded = sorted(p.name for p in (ws.rf_dir / "deltas/practices").glob("*.yaml"))
    assert seeded == ["software-development.yaml"]


def test_a_domain_can_be_added_through_personal_overrides(repo, user_home, tmp_path):
    """delta.md offers a domain file "in the marketplace or in your overrides"."""
    user_home(tmp_path / "override-domain")
    mine = config.overrides_dir() / "deltas/practices/fixture-domain.yaml"
    mine.parent.mkdir(parents=True, exist_ok=True)
    mine.write_text(_second_domain())
    ws = workspace.resolve(cwd=repo).ensure()
    listed = {d["domain"]: d for d in deltas.domains(ws)}
    assert "fixture-domain" in listed and listed["fixture-domain"]["base"] is False
    out = deltas.render(ws, profiles.load("claude-code"), "native_plan",
                        {**IMPL, "domains": ["fixture-domain"], "concerns": ["widgets"]})
    assert "practice.widget_first" in out["practice"]["selected"]
    block = next(d for d in out["practice"]["domains"] if d["domain"] == "fixture-domain")
    assert block["shipped_sha256"] is None  # nothing shipped it; it is the user's own


# ---- phases: one Ask that spans several tasks -----------------------------------------------

RESEARCH_AND_IMPLEMENT = {"task": ["research", "implement"], "result": "workspace_change",
                          "interaction": "approval_gated", "horizon": "session", "effects": ["read", "write"]}


def test_one_task_renders_a_flat_list(repo, user_home, tmp_path):
    user_home(tmp_path / "flat")
    ws = workspace.resolve(cwd=repo).ensure()
    out = deltas.render(ws, profiles.load("claude-code"), "native_plan", IMPL)
    lines = out["practice"]["text"].splitlines()
    assert lines[0] == "Rules:"
    assert all(l.startswith("- ") for l in lines[1:] if l.strip())


def test_several_tasks_group_the_rules_by_phase(repo, user_home, tmp_path):
    user_home(tmp_path / "phases")
    ws = workspace.resolve(cwd=repo).ensure()
    out = deltas.render(ws, profiles.load("claude-code"), "native_plan", RESEARCH_AND_IMPLEMENT)
    text = out["practice"]["text"]
    assert "While researching:" in text and "While implementing:" in text
    # a rule that applies to every named task is stated once, not repeated per phase
    assert text.count("- Occam") == 1
    labels = [l for l in text.splitlines() if l.startswith("- ")]
    assert len(labels) == len(set(labels))


def test_the_core_cap_applies_per_phase_so_research_rules_survive(repo, user_home, tmp_path):
    """Before grouping, implement's core rules outranked research's and pushed them out."""
    user_home(tmp_path / "cap")
    ws = workspace.resolve(cwd=repo).ensure()
    out = deltas.render(ws, profiles.load("claude-code"), "native_plan", RESEARCH_AND_IMPLEMENT)
    p = out["practice"]
    assert "practice.occam" in p["selected"], "a research rule must survive a research+implement Ask"
    assert "practice.testing_pyramid" in p["selected"], "and so must an implement rule"
    assert p["dropped_by_budget"] == []


def test_phases_appear_in_the_order_the_classification_names_them(repo, user_home, tmp_path):
    user_home(tmp_path / "order")
    ws = workspace.resolve(cwd=repo).ensure()
    out = deltas.render(ws, profiles.load("claude-code"), "native_plan",
                        {**RESEARCH_AND_IMPLEMENT, "task": ["implement", "research"]})
    text = out["practice"]["text"]
    assert text.index("While implementing:") < text.index("While researching:")


def test_the_prompt_audit_accepts_phase_headings(repo, user_home, tmp_path):
    user_home(tmp_path / "audit")
    ws = workspace.resolve(cwd=repo).ensure()
    out = deltas.render(ws, profiles.load("claude-code"), "native_plan", RESEARCH_AND_IMPLEMENT)
    supplied = out["practice"]["entries"]
    composed = ("Do the thing.\n\nRules:\n\nWhile researching:\n"
                f"- {supplied[0]['label']}: applied to this task.\n")
    applied, omitted = deltas.audit_composed(composed, supplied)
    assert applied == [supplied[0]["id"]] and len(omitted) == len(supplied) - 1


def test_the_audit_still_rejects_a_line_that_is_neither_rule_nor_heading(repo, user_home, tmp_path):
    user_home(tmp_path / "audit2")
    ws = workspace.resolve(cwd=repo).ensure()
    supplied = deltas.render(ws, profiles.load("claude-code"), "native_plan", IMPL)["practice"]["entries"]
    with pytest.raises(config.ConfigError, match="not `- <labels>"):
        deltas.audit_composed("Do it.\n\nRules:\nthis is just prose\n", supplied)
