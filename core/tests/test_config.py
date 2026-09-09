"""Authored configuration is YAML; identities are digests of the parsed document's canonical JSON."""
from ringframe import config, profiles


def test_yaml_identity_ignores_comments_and_formatting(tmp_path):
    a = tmp_path / "a.yaml"
    b = tmp_path / "b.yaml"
    a.write_text("schema: x/1\nname: demo   # a comment\nitems:\n  - one\n  - two\n")
    b.write_text("# different layout, same document\nitems: [one, two]\nschema: x/1\nname: demo\n")
    assert config.load_yaml(a) == config.load_yaml(b) == {"schema": "x/1", "name": "demo", "items": ["one", "two"]}
    assert config.sha256_of(config.load_yaml(a)) == config.sha256_of(config.load_yaml(b))


def test_yaml_loader_is_safe_and_requires_a_mapping(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("!!python/object/apply:os.system ['echo pwned']\n")
    try:
        config.load_yaml(bad)
    except config.ConfigError as e:
        assert "bad.yaml" in str(e)
    else:
        raise AssertionError("unsafe tag must be rejected")
    (tmp_path / "list.yaml").write_text("- just\n- a list\n")
    try:
        config.load_yaml(tmp_path / "list.yaml")
    except config.ConfigError as e:
        assert "mapping" in str(e)
    else:
        raise AssertionError("top level must be a mapping")


def test_profiles_are_yaml_with_canonical_identity():
    assert profiles.names() == ["claude-code", "codex", "unknown"]
    p = profiles.load("codex")
    assert p["profile_id"] == "codex"
    assert profiles.sha256("codex") == config.sha256_of(p)


def test_global_setup_moves_legacy_configuration_without_losing_custom_values(repo, tmp_path, monkeypatch):
    from ringframe import workspace, deltas
    home = tmp_path / 'user-home'
    monkeypatch.setenv('HOME', str(home))
    old = home / '.fab7/rf'
    (old / 'defaults/profiles').mkdir(parents=True)
    (old / 'defaults/profiles/codex.yaml').write_text('old exported profile\n')
    (old / 'deltas.yaml').write_text('schema: ringframe.deltas/1\nentries: [{id: practice.kiss, enabled: false}]\n')
    workspace.initialize_user()
    assert not (old / 'defaults').exists() and not (old / 'deltas.yaml').exists()
    assert profiles.load('codex')['confirmation']['tool'] == 'request_user_input'
    ws = workspace.resolve(cwd=repo).ensure()
    assert deltas.effective(ws)['practice.kiss']['enabled'] is False
    assert all(p.read_bytes() == b'' for p in (ws.root / '.fab7/rt/deltas').rglob('*.yaml'))
    assert set((home / '.fab7/rt').iterdir()) == {home / '.fab7/rt/deltas'}


def test_scoped_delta_catalogs_apply_project_conflicts_and_render_settings(repo, tmp_path, monkeypatch):
    from ringframe import workspace, deltas
    home = tmp_path / 'user-home'
    monkeypatch.setenv('HOME', str(home))
    workspace.initialize_user()
    ws = workspace.resolve(cwd=repo).ensure()
    global_file = home / '.fab7/rt/deltas/practice/software-development.yaml'
    global_doc = config.load_yaml(global_file)
    global_doc['render']['core_cap'] = 1
    global_doc['entries'][0]['text'] = 'Global rule.'
    import yaml
    global_file.write_text(yaml.safe_dump(global_doc))
    local = ws.root / '.fab7/rt/deltas/practice/software-development.yaml'
    local.write_text('render: {core_cap: 2}\nentries: [{id: practice.kiss, text: Project rule.}]\n')
    host_file = ws.root / '.fab7/rt/deltas/codex.yaml'
    host_file.write_text('entries: [{id: codex.native_plan.hand_back, status: qualified, text: Project host rule.}]\n')
    result = deltas.render(ws, profiles.load('codex'), 'native_plan', {'task': ['implement']})
    assert result['practice']['selected'] == ['practice.kiss', 'practice.yagni']
    assert 'Project rule.' in result['text'] and 'Global rule.' not in result['text']
    assert 'Project host rule.' in result['text']
    assert deltas.effective(ws)['practice.kiss']['layer'] == 'workspace'


def test_empty_legacy_override_inherits_and_project_can_clear_entries(repo, tmp_path, monkeypatch):
    from ringframe import workspace, deltas
    home = tmp_path / "user-home"
    monkeypatch.setenv("HOME", str(home))
    old = home / ".fab7/rf"
    old.mkdir(parents=True)
    (old / "deltas.yaml").write_text("schema: ringframe.deltas/1\nentries: []\n")
    workspace.initialize_user()
    ws = workspace.resolve(cwd=repo).ensure()
    original = deltas.effective(ws)
    assert "practice.kiss" in original
    local = ws.root / ".fab7/rt/deltas/practice/software-development.yaml"
    assert local.read_bytes() == b""
    local.write_text("entries: []\n")
    assert deltas.effective(ws) == {}
    local.write_text("# Only a comment\n")
    assert deltas.effective(ws) == original


def test_delta_merge_preserves_global_nested_fields_and_project_list_values(repo, tmp_path, monkeypatch):
    import yaml
    from ringframe import workspace, deltas
    monkeypatch.setenv("HOME", str(tmp_path / "user-home"))
    workspace.initialize_user()
    ws = workspace.resolve(cwd=repo).ensure()
    global_file = deltas.user_root() / "deltas/practice/software-development.yaml"
    global_doc = config.load_yaml(global_file)
    global_doc["entries"][0]["applies_to"] = {"task": ["implement"], "result": ["workspace_change"]}
    global_file.write_text(yaml.safe_dump(global_doc))
    local = ws.root / ".fab7/rt/deltas/practice/software-development.yaml"
    local.write_text("entries: [{id: practice.kiss, applies_to: {task: [plan]}, why: null}]\n")
    merged = deltas.effective(ws)["practice.kiss"]
    assert merged["applies_to"] == {"task": ["plan"], "result": ["workspace_change"]}
    assert merged["why"] is None
    assert config.load_yaml(global_file) == global_doc
