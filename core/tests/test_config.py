"""Authored configuration is YAML (ADR-0008 §7); identities are digests of the parsed document's canonical JSON."""
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
    assert p["profile_id"] == "codex@0.153"
    assert profiles.sha256("codex") == config.sha256_of(p)
