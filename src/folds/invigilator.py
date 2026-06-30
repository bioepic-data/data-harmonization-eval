"""Anti-cheat invigilator: audit an agent run's trace for out-of-bounds access.

A leave-one-cluster-out run hands an agent a `.runs/<cfg>/` env whose two
answer-bearing artifacts have the held-out cluster removed. Isolation is by
*absence + instruction*; this module is the *audit* backstop: it reads the
agent's tool-call trace (`agent-<id>.jsonl`) and flags any file the agent read
or touched that lies outside the allowed roots.

Policy is **root-based**: an access is in-bounds iff its path resolves under

* the run env (`.runs/<cfg>/`), or
* the shared raw-data dir (`~/ess-dive_wfsfa_soil_datasets/`),

plus any explicitly allowed extras. This works because every *answer* (the real
`data/gold/`, the full mapping with the held-out entry, any answer-key dir) lives
*outside* the env, while every legitimate *input* (skills, ablated code, filtered
mapping, the held-out dataset's metadata via the env symlink, raw CSVs) lives
inside one of those roots. No per-identifier rules are needed.

Two things make the audit correct rather than naive:

* **cwd-aware Bash parsing.** Agents `cd` into the env and use relative paths
  (`cd .runs/<cfg> && cat data/processed/…`); a substring match would false-
  positive. We track `cd` per command and resolve relative tokens against the
  effective working directory.
* **Lexical containment, not realpath.** The env symlinks shared inputs in
  (e.g. `data/external/ess-dive_meta`); resolving symlinks would point those
  reads back outside the env and wrongly flag them. We normalize paths
  lexically (`..` handled) but do NOT follow symlinks, so accessing an input
  *via the env* is in-bounds while reaching the same input by its real outside
  path is flagged.

Bash is not fully parseable, so unresolved commands are also surfaced verbatim
for human review — the audit never silently claims a command was clean when it
could not understand it.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import typer

DEFAULT_RAW_DATA = Path.home() / "ess-dive_wfsfa_soil_datasets"

# System paths that show up as Bash tokens (mostly `2>/dev/null` redirects) but
# are never data access — never treated as violations.
IGNORED_ROOTS = [Path("/dev"), Path("/proc"), Path("/sys")]

# Path-like tokens inside a Bash command: at least one '/', path-ish chars.
_PATH_TOKEN = re.compile(r"(?:~|\.{1,2}|/)?/?[\w.@+\-]+(?:/[\w.@+\-]+)+")
_CD = re.compile(r"^\s*cd\s+(?:--\s+)?['\"]?([^'\"&;|]+?)['\"]?\s*$")


def load_tool_uses(trace_path: Path) -> list[tuple[str, dict]]:
    """Extract ``(tool_name, tool_input)`` pairs from a JSONL agent trace."""
    out: list[tuple[str, dict]] = []

    def walk(o):
        if isinstance(o, dict):
            if o.get("type") == "tool_use":
                out.append((o.get("name", ""), o.get("input", {}) or {}))
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    for line in Path(trace_path).read_text().splitlines():
        line = line.strip()
        if line:
            walk(json.loads(line))
    return out


def lexical_resolve(path: str, cwd: str) -> Path:
    """Resolve ``path`` against ``cwd`` lexically (expanduser + normpath).

    Does NOT follow symlinks — accessing an input via the env's symlink should
    count as inside the env.

    >>> str(lexical_resolve("data/x", "/repo/.runs/cfg"))
    '/repo/.runs/cfg/data/x'
    >>> str(lexical_resolve("../secret", "/repo/.runs/cfg"))
    '/repo/.runs/secret'
    """
    p = os.path.expanduser(path)
    if not os.path.isabs(p):
        p = os.path.join(cwd, p)
    return Path(os.path.normpath(p))


def under(path: Path, root: Path) -> bool:
    """True if ``path`` is ``root`` or lexically inside it."""
    try:
        Path(path).relative_to(root)
        return True
    except ValueError:
        return False


@dataclass
class Violation:
    tool: str
    path: str
    reason: str
    context: str


@dataclass
class AuditReport:
    clean: bool
    violations: list[Violation] = field(default_factory=list)
    n_tool_calls: int = 0
    n_reads: int = 0
    reads_in_bounds: int = 0
    bash_commands: list[str] = field(default_factory=list)
    allowed_roots: list[str] = field(default_factory=list)


def _reason(p: Path, repo_root: Path, holdout_ids: list[str], raw: str) -> str:
    s = str(p)
    base = "outside allowed roots"
    if "eval_answer_keys" in s or re.search(r"expert_dataset_\d+|expert_mapping_entry", s):
        base = "ANSWER KEY"
    elif under(p, repo_root / "data" / "gold") or under(p, repo_root / "data" / "processed"):
        base = "real expert gold/mapping (outside env)"
    elif under(p, repo_root):
        base = "repo file outside env"
    hit = next((h for h in holdout_ids if h and h in raw), None)
    return f"{base} [references held-out {hit}]" if hit else base


def audit(
    trace_path: Path,
    env_dir: Path,
    raw_data_dir: Path = DEFAULT_RAW_DATA,
    repo_root: Optional[Path] = None,
    extra_roots: Optional[list[Path]] = None,
    holdout_identifiers: Optional[list[str]] = None,
) -> AuditReport:
    """Audit a trace; return an :class:`AuditReport` (``clean`` False on any violation)."""
    repo_root = Path(repo_root or Path.cwd()).resolve()

    def _abs(p) -> Path:
        # absolutize against repo_root, lexically (do NOT follow symlinks, so the
        # env's symlinked-in inputs stay "inside" the env).
        s = os.path.expanduser(str(p))
        if not os.path.isabs(s):
            s = os.path.join(str(repo_root), s)
        return Path(os.path.normpath(s))

    env_dir = _abs(env_dir)
    raw_data_dir = _abs(raw_data_dir)
    allowed = [env_dir, raw_data_dir] + [_abs(p) for p in (extra_roots or [])]
    holdout_ids = holdout_identifiers or []

    report = AuditReport(clean=True, allowed_roots=[str(r) for r in allowed])
    tool_uses = load_tool_uses(trace_path)
    report.n_tool_calls = len(tool_uses)

    def check(tool: str, abs_path: Path, raw: str):
        if any(under(abs_path, r) for r in IGNORED_ROOTS):
            return True  # /dev/null redirects etc. — not data access
        if any(under(abs_path, r) for r in allowed):
            return True
        report.clean = False
        report.violations.append(
            Violation(tool, str(abs_path), _reason(abs_path, repo_root, holdout_ids, raw), raw[:200])
        )
        return False

    for name, inp in tool_uses:
        if name in ("Read", "Write", "Edit", "NotebookEdit"):
            fp = inp.get("file_path") or inp.get("notebook_path") or ""
            if not fp:
                continue
            if name == "Read":
                report.n_reads += 1
            if check(name, lexical_resolve(fp, str(repo_root)), fp) and name == "Read":
                report.reads_in_bounds += 1
        elif name in ("Grep", "Glob"):
            p = inp.get("path")
            if p:
                check(name, lexical_resolve(p, str(repo_root)), p)
        elif name == "Bash":
            cmd = inp.get("command", "")
            report.bash_commands.append(cmd)
            cwd = str(repo_root)
            for seg in re.split(r"&&|\|\||\||;|\n", cmd):
                m = _CD.match(seg)
                if m:
                    cwd = str(lexical_resolve(m.group(1).strip(), cwd))
                    continue
                for tok in _PATH_TOKEN.findall(seg):
                    if tok in ("&&", "||"):
                        continue
                    check("Bash", lexical_resolve(tok, cwd), seg.strip())
    return report


app = typer.Typer(add_completion=False, help="Audit an agent run trace for out-of-bounds access.")


@app.command()
def main(
    trace: Path = typer.Option(..., "--trace", help="agent-<id>.jsonl trace file."),
    env: Path = typer.Option(..., "--env", help="Run env dir (.runs/<cfg>); reads its MANIFEST.json."),
    raw_data: Path = typer.Option(DEFAULT_RAW_DATA, "--raw-data", help="Shared raw-data root."),
    repo_root: Path = typer.Option(Path.cwd(), "--repo-root", help="Repo root (start cwd for relative paths)."),
    allow: list[Path] = typer.Option([], "--allow", help="Extra allowed root(s)."),
    show_bash: bool = typer.Option(False, "--show-bash", help="Print every Bash command for human review."),
) -> None:
    """Audit a run's trace; exit non-zero if any out-of-bounds access is found."""
    holdout_ids: list[str] = []
    manifest = env / "MANIFEST.json"
    if manifest.exists():
        holdout_ids = [h for h in json.loads(manifest.read_text()).get("holdout_identifiers", []) if h]

    r = audit(trace, env, raw_data_dir=raw_data, repo_root=repo_root,
              extra_roots=list(allow), holdout_identifiers=holdout_ids)

    typer.echo(f"tool calls: {r.n_tool_calls} | reads: {r.n_reads} ({r.reads_in_bounds} in-bounds)")
    typer.echo("allowed roots:")
    for root in r.allowed_roots:
        typer.echo(f"  - {root}")
    if r.clean:
        typer.echo("\n✅ CLEAN — no out-of-bounds access detected.")
    else:
        typer.echo(f"\n⚠ {len(r.violations)} VIOLATION(S):")
        for v in r.violations:
            typer.echo(f"  [{v.tool}] {v.reason}")
            typer.echo(f"      path: {v.path}")
            typer.echo(f"      in:   {v.context}")
    if show_bash:
        typer.echo("\n--- Bash commands (human review; parsing is best-effort) ---")
        for c in r.bash_commands:
            typer.echo(f"  $ {c.splitlines()[0] if c else ''}")
    raise typer.Exit(code=0 if r.clean else 1)


if __name__ == "__main__":
    app()
