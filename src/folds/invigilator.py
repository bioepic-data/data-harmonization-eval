"""Anti-cheat invigilator: audit an agent run's trace for out-of-bounds access.

A leave-one-cluster-out run hands an agent an answer-free environment whose two
answer-bearing artifacts have the held-out cluster removed. Isolation is by
*absence + instruction*; this module is the *audit* backstop: it reads the
agent's tool-call trace (`agent-<id>.jsonl`) and flags any file the agent read
or touched that lies outside the allowed roots.

Policy is **root-based**: an access is in-bounds iff its path resolves under

* the run environment,

plus any explicitly allowed extras. This works because every *answer* (the real
`data/gold/`, the full mapping with the held-out entry, any answer-key dir) lives
*outside* the env, while every legitimate *input* (skills, ablated code,
filtered mapping, metadata, and raw CSVs) lives inside the environment. No
per-identifier rules are needed.

Two things make the audit correct rather than naive:

* **cwd-aware Bash parsing.** Agents `cd` into the environment and use relative
  paths (`cd /isolated/cfg && cat data/processed/…`); a substring match would false-
  positive. We track `cd` per command and resolve relative tokens against the
  effective working directory.
* **Lexical containment, not realpath.** We normalize paths lexically (`..`
  handled) but do NOT follow symlinks. The environment builder copies inputs
  rather than linking them, and this rule also prevents a benign symlink from
  being mistaken for an out-of-bounds path in traces.

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

# System paths that show up as Bash tokens (mostly interpreter and redirect
# paths) but are never evaluation data access.
IGNORED_ROOTS = [
    Path("/dev"), Path("/proc"), Path("/sys"), Path("/usr"), Path("/bin"),
    Path("/opt"), Path("/etc"),
]

# Path-like tokens inside a Bash command: at least one '/', path-ish chars.
_PATH_TOKEN = re.compile(r"(?<![$\w])(?:~|\.{1,2}|/)?/?[\w.@+\-]+(?:/[\w.@+\-]+)+")
_CD = re.compile(r"^\s*cd\s+(?:--\s+)?['\"]?([^'\"&;|]+?)['\"]?\s*$")
_ASSIGNMENT = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=([^\s]+)")
_VARIABLE = re.compile(r"\$(?:\{([A-Za-z_][A-Za-z0-9_]*)\}|([A-Za-z_][A-Za-z0-9_]*))")
_HEREDOC = re.compile(r"<<-?\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?")
_PYTHON_C = re.compile(
    r"\bpython(?:3(?:\.\d+)?)?\s+-c\s+(?:'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\")"
)
_TIMEZONE = re.compile(r"(?:America|Antarctica|Arctic|Asia|Atlantic|Australia|Europe|Etc|Indian|Pacific)/[A-Za-z0-9_+\-]+$")
_DATE_FRAGMENT = re.compile(r"\d{1,4}/\d{1,2}/\d{1,4}$")


def load_tool_uses(trace_path: Path) -> list[tuple[str, dict]]:
    """Extract ``(tool_name, tool_input)`` pairs from a JSON or JSONL trace.

    Claude Code session transcripts are JSONL, while the GitHub action's
    ``execution_file`` output is a single JSON document. Supporting both lets
    the evaluator archive the action output verbatim rather than reserializing
    a partial view of it before audit.
    """
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

    text = Path(trace_path).read_text().strip()
    if not text:
        raise ValueError(f"trace is empty: {trace_path}")
    try:
        records = [json.loads(text)]
    except json.JSONDecodeError:
        records = [json.loads(line) for line in text.splitlines() if line.strip()]
    for record in records:
        walk(record)
    return out


def lexical_resolve(path: str, cwd: str) -> Path:
    """Resolve ``path`` against ``cwd`` lexically (expanduser + normpath).

    Does NOT follow symlinks — accessing an input via the env's symlink should
    count as inside the env.

    >>> str(lexical_resolve("data/x", "/isolated/cfg"))
    '/isolated/cfg/data/x'
    >>> str(lexical_resolve("../secret", "/isolated/cfg"))
    '/isolated/secret'
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
class Warning:
    """A recorded access that is benign but useful to report."""

    tool: str
    path: str
    reason: str
    context: str


@dataclass
class AuditReport:
    clean: bool
    violations: list[Violation] = field(default_factory=list)
    warnings: list[Warning] = field(default_factory=list)
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


def _forbidden(p: Path, repo_root: Path) -> bool:
    """True if a path is a known *answer* location (answer key, real gold/mapping).

    Used to flag ``cd`` into such a directory even when the subsequent
    single-component file read (e.g. ``cat expert.py``) isn't itself tokenized.
    """
    s = str(p)
    if "eval_answer_keys" in s or re.search(r"expert_dataset_\d+|expert_mapping_entry", s):
        return True
    return under(p, repo_root / "data" / "gold") or under(p, repo_root / "data" / "processed")


def _benign_external_input(p: Path, repo_root: Path) -> Optional[str]:
    """Return a warning reason for an approved input reached outside its env copy."""
    if under(p, repo_root / "skills"):
        return "external repo input (skills; use the environment copy)"
    if under(p, repo_root / "data" / "external" / "ess-dive_meta"):
        return "external repo input (ESS-DIVE metadata; use the environment copy)"
    parts = p.parts
    if ".claude" in parts and "projects" in parts and "tool-results" in parts:
        return "Claude tool-result transcript"
    return None


def _expand_variables(text: str, variables: dict[str, str]) -> str:
    """Expand only previously recorded, simple shell variables.

    This deliberately does not evaluate command substitutions, defaults, or
    arbitrary shell syntax. Unknown variables remain untouched and therefore
    cannot be mistaken for relative path prefixes.
    """
    return _VARIABLE.sub(lambda m: variables.get(m.group(1) or m.group(2), m.group(0)), text)


def _consume_assignments(segment: str, variables: dict[str, str]) -> str:
    """Record leading ``VAR=value`` / ``export VAR=value`` assignments."""
    rest = segment
    while (match := _ASSIGNMENT.match(rest)):
        name, value = match.groups()
        value = _expand_variables(value, variables).strip("'\"")
        variables[name] = value
        rest = rest[match.end():]
    return rest


def _strip_heredoc_bodies(command: str) -> str:
    """Remove heredoc bodies, which are source/data rather than shell arguments."""
    kept: list[str] = []
    delimiter: Optional[str] = None
    for line in command.splitlines():
        if delimiter is not None:
            if line.strip() == delimiter:
                delimiter = None
            continue
        match = _HEREDOC.search(line)
        if match:
            delimiter = match.group(1)
            line = line[:match.start()]
        kept.append(line)
    return "\n".join(kept)


def _shell_segments(command: str) -> list[str]:
    """Split shell command lists without splitting inside quoted code strings."""
    segments: list[str] = []
    buf: list[str] = []
    quote: Optional[str] = None
    escaped = False
    i = 0
    while i < len(command):
        char = command[i]
        if escaped:
            buf.append(char)
            escaped = False
        elif char == "\\":
            buf.append(char)
            escaped = True
        elif quote:
            buf.append(char)
            if char == quote:
                quote = None
        elif char in "'\"":
            buf.append(char)
            quote = char
        elif char == "\n" or char == ";" or char == "|":
            segments.append("".join(buf))
            buf = []
            if char == "|" and i + 1 < len(command) and command[i + 1] == "|":
                i += 1
        elif char == "&" and i + 1 < len(command) and command[i + 1] == "&":
            segments.append("".join(buf))
            buf = []
            i += 1
        else:
            buf.append(char)
        i += 1
    if buf:
        segments.append("".join(buf))
    return segments


def _path_tokens(segment: str) -> list[str]:
    """Return path-like shell arguments, excluding embedded Python source."""
    shell_only = _PYTHON_C.sub("python -c", segment)
    return [
        token for token in _PATH_TOKEN.findall(shell_only)
        if not _TIMEZONE.fullmatch(token) and not _DATE_FRAGMENT.fullmatch(token)
    ]


def audit(
    trace_path: Path,
    env_dir: Path,
    raw_data_dir: Optional[Path] = None,
    repo_root: Optional[Path] = None,
    extra_roots: Optional[list[Path]] = None,
    holdout_identifiers: Optional[list[str]] = None,
) -> AuditReport:
    """Audit a trace; return an :class:`AuditReport` (``clean`` False on any violation)."""
    repo_root = Path(repo_root or Path.cwd()).resolve()

    def _abs(p) -> Path:
        # Absolutize against repo_root lexically; do not follow symlinks.
        s = os.path.expanduser(str(p))
        if not os.path.isabs(s):
            s = os.path.join(str(repo_root), s)
        return Path(os.path.normpath(s))

    env_dir = _abs(env_dir)
    allowed = [env_dir] + ([_abs(raw_data_dir)] if raw_data_dir is not None else []) \
        + [_abs(p) for p in (extra_roots or [])]
    holdout_ids = holdout_identifiers or []

    report = AuditReport(clean=True, allowed_roots=[str(r) for r in allowed])
    tool_uses = load_tool_uses(trace_path)
    report.n_tool_calls = len(tool_uses)

    def check(tool: str, abs_path: Path, raw: str):
        if any(under(abs_path, r) for r in IGNORED_ROOTS):
            return True  # /dev/null redirects etc. — not data access
        if any(under(abs_path, r) for r in allowed):
            return True
        if warning := _benign_external_input(abs_path, repo_root):
            report.warnings.append(Warning(tool, str(abs_path), warning, raw[:200]))
            return False
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
        elif name in ("Grep", "Glob", "LS"):
            p = inp.get("path")
            if p:
                check(name, lexical_resolve(str(p), str(repo_root)), str(p))
            for key in ("glob", "pattern"):  # a path-bearing glob can leak too
                val = inp.get(key)
                if val:
                    for tok in _PATH_TOKEN.findall(str(val)):
                        check(name, lexical_resolve(tok, str(repo_root)), str(val))
        elif name == "Bash":
            cmd = inp.get("command", "")
            report.bash_commands.append(cmd)
            cwd = str(repo_root)
            variables: dict[str, str] = {}
            for seg in _shell_segments(_strip_heredoc_bodies(cmd)):
                seg = _consume_assignments(seg, variables)
                seg = _expand_variables(seg, variables)
                if not seg.strip():
                    continue
                m = _CD.match(seg)
                if m:
                    target = lexical_resolve(m.group(1).strip(), cwd)
                    if _forbidden(target, repo_root):  # cd-ing into an answer location
                        report.clean = False
                        report.violations.append(
                            Violation("Bash(cd)", str(target),
                                      _reason(target, repo_root, holdout_ids, seg), seg.strip()))
                    cwd = str(target)
                    continue
                for tok in _path_tokens(seg):
                    check("Bash", lexical_resolve(tok, cwd), seg.strip())
    return report


app = typer.Typer(add_completion=False, help="Audit an agent run trace for out-of-bounds access.")


@app.command()
def main(
    trace: Path = typer.Option(..., "--trace", help="agent-<id>.jsonl trace file."),
    env: Path = typer.Option(..., "--env", help="Answer-free run environment; reads its MANIFEST.json."),
    raw_data: Optional[Path] = typer.Option(None, "--raw-data", help="Legacy external raw-data root to allow (avoid for isolated runs)."),
    repo_root: Optional[Path] = typer.Option(None, "--repo-root", help="Repo root (start cwd for relative paths); defaults to the current dir."),
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
    if r.warnings:
        typer.echo(f"\nℹ {len(r.warnings)} WARNING(S):")
        for w in r.warnings:
            typer.echo(f"  [{w.tool}] {w.reason}")
            typer.echo(f"      path: {w.path}")
            typer.echo(f"      in:   {w.context}")
    if show_bash:
        typer.echo("\n--- Bash commands (human review; parsing is best-effort) ---")
        for c in r.bash_commands:
            typer.echo("  $ " + (c or "").replace("\n", "\n      "))
    raise typer.Exit(code=0 if r.clean else 1)


if __name__ == "__main__":
    app()
