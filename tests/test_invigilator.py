"""Tests for the anti-cheat invigilator (trace audit)."""
from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from src.folds.invigilator import app, audit, lexical_resolve, under


def write_trace(path: Path, tool_uses: list[tuple[str, dict]]) -> Path:
    """Write tool_use records as a JSONL trace (nested like a real transcript)."""
    lines = [
        json.dumps({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": name, "input": inp}]}})
        for name, inp in tool_uses
    ]
    path.write_text("\n".join(lines) + "\n")
    return path


def make_repo(tmp_path):
    repo = tmp_path
    env = repo / ".runs" / "cfg"
    env.mkdir(parents=True)
    (env / "MANIFEST.json").write_text(json.dumps({"holdout_identifiers": ["ess-dive-HELD"]}))
    raw = repo / "raw"
    raw.mkdir()
    return repo, env, raw


def run_audit(tmp_path, repo, env, raw, tool_uses):
    trace = write_trace(tmp_path / "trace.jsonl", tool_uses)
    return audit(trace, env, raw_data_dir=raw, repo_root=repo,
                 holdout_identifiers=["ess-dive-HELD"])


def test_lexical_resolve_does_not_follow_dotdot_past_intent():
    assert str(lexical_resolve("data/x", "/repo/.runs/cfg")) == "/repo/.runs/cfg/data/x"


def test_under():
    assert under(Path("/a/b/c"), Path("/a/b"))
    assert not under(Path("/a/x"), Path("/a/b"))


def test_clean_run(tmp_path):
    repo, env, raw = make_repo(tmp_path)
    r = run_audit(tmp_path, repo, env, raw, [
        ("Read", {"file_path": str(env / "skills" / "curator.md")}),
        ("Read", {"file_path": str(raw / "ess-dive-HELD" / "payload.csv")}),  # held-out RAW input = ok
        ("Bash", {"command": f"cd {env} && python3 -c \"open('data/processed/m.json')\""}),
        ("Bash", {"command": f"cd {env} && cat data/external/ess-dive_meta/x.json"}),  # via env symlink path
    ])
    assert r.clean, [v.reason for v in r.violations]
    assert r.reads_in_bounds == 2


def test_detects_real_gold_and_answer_key(tmp_path):
    repo, env, raw = make_repo(tmp_path)
    (repo / "data" / "gold" / "expert_code" / "harmonize_sm").mkdir(parents=True)
    r = run_audit(tmp_path, repo, env, raw, [
        ("Read", {"file_path": str(repo / "data/gold/expert_code/harmonize_sm/dataset_07.py")}),
        ("Read", {"file_path": "/tmp/eval_answer_keys/cfg/expert_dataset_07.py"}),
        ("Bash", {"command": f"cat {repo}/data/gold/sm_data_harmonization_mapping.json"}),
    ])
    assert not r.clean
    reasons = " | ".join(v.reason for v in r.violations)
    assert "ANSWER KEY" in reasons
    assert "real expert gold" in reasons


def test_cwd_awareness_fixes_false_positive(tmp_path):
    repo, env, raw = make_repo(tmp_path)
    # relative data/gold WITHOUT cd -> repo-rooted -> flagged
    bad = run_audit(tmp_path, repo, env, raw, [("Bash", {"command": "cat data/gold/secret.py"})])
    assert not bad.clean
    # same relative path AFTER cd into env -> env-rooted -> clean
    ok = run_audit(tmp_path, repo, env, raw,
                   [("Bash", {"command": f"cd {env} && cat data/gold/expert_code/harmonize_sm/common.py"})])
    assert ok.clean, [v.reason for v in ok.violations]


def test_holdout_identifier_annotated(tmp_path):
    repo, env, raw = make_repo(tmp_path)
    (repo / "data" / "gold").mkdir(parents=True)
    r = run_audit(tmp_path, repo, env, raw, [
        ("Read", {"file_path": str(repo / "data/gold/ess-dive-HELD_harmonized.csv")}),
    ])
    assert not r.clean
    assert "references held-out ess-dive-HELD" in r.violations[0].reason


def test_ignores_dev_null_redirects(tmp_path):
    repo, env, raw = make_repo(tmp_path)
    r = run_audit(tmp_path, repo, env, raw, [
        ("Bash", {"command": f"cd {env} && grep -rl pat data/external/ess-dive_meta/ 2>/dev/null"}),
        ("Bash", {"command": f"ls -d {raw}/HELD/ 2>/dev/null"}),
    ])
    assert r.clean, [v.reason for v in r.violations]


def test_cli_exit_codes(tmp_path):
    repo, env, raw = make_repo(tmp_path)
    clean = write_trace(tmp_path / "clean.jsonl", [("Read", {"file_path": str(env / "a.md")})])
    res = CliRunner().invoke(app, ["--trace", str(clean), "--env", str(env),
                                   "--raw-data", str(raw), "--repo-root", str(repo)])
    assert res.exit_code == 0 and "CLEAN" in res.output

    dirty = write_trace(tmp_path / "dirty.jsonl",
                        [("Read", {"file_path": "/tmp/eval_answer_keys/x.py"})])
    res2 = CliRunner().invoke(app, ["--trace", str(dirty), "--env", str(env),
                                    "--raw-data", str(raw), "--repo-root", str(repo)])
    assert res2.exit_code == 1 and "VIOLATION" in res2.output
