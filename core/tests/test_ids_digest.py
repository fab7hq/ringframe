import re

from ringframe import digest, ids


def test_id_shape_and_prefix():
    a = ids.new_id("ask")
    assert re.fullmatch(r"ask_[0-9A-HJKMNP-TV-Z]{26}", a)


def test_ids_unique_and_time_ordered():
    first = ids.new_id("evt")
    seen = {ids.new_id("evt") for _ in range(2000)}
    assert len(seen) == 2000
    assert all(first[:4 + 9] <= s[:4 + 9] for s in seen)  # timestamp prefix never goes backwards


def test_sha256_of_bytes_and_file(tmp_path):
    p = tmp_path / "f.txt"
    p.write_bytes(b"hello\n")
    assert digest.sha256_bytes(b"hello\n") == "5891b5b522d5df086d0ff0b110fbd9d21bb4fc7163af34d08286a2e846f6be03"
    assert digest.sha256_file(p) == digest.sha256_bytes(b"hello\n")
    assert digest.artifact_ref("source_intent", "asks/x/source.txt", p) == {
        "role": "source_intent",
        "path": "asks/x/source.txt",
        "bytes": 6,
        "sha256": digest.sha256_bytes(b"hello\n"),
    }
