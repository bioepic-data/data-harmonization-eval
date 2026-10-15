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


# --- Severity -----------------------------------------------------------
#
# A single pass/fail bit cannot tell `ls ~/.local/.../site-packages` apart from
# reading a held-out answer, and conflating them produced spurious run
# failures. Severity is *derived*: take the character of the action and the
# location it landed in, then rank the evidential harm. Only CONTAMINATED
# invalidates a fold and fails the step.
CONTAMINATED = "CONTAMINATED"   # answer material for a withheld dataset was reachable
LEAK_RISK = "LEAK_RISK"         # answer location touched; no withheld content shown
BOUNDARY = "BOUNDARY"           # outside the env, but no answer material there
IN_BOUNDS = "IN_BOUNDS"         # inside the fold; the normal case

SEVERITY_RANK = {IN_BOUNDS: 0, BOUNDARY: 1, LEAK_RISK: 2, CONTAMINATED: 3}

# --- Access character ---------------------------------------------------
#
# `grep -r pat data/gold/` returns file *contents* while looking like an
# enumeration, so it is kept apart from name-only listing: treating both as
# "enumerate" would let the highest-bandwidth leak through as a warning.
READ = "read"                            # contents of a named file
ENUMERATE_CONTENT = "enumerate_content"  # grep/rg — searches *inside* files
ENUMERATE_NAMES = "enumerate_names"      # ls/find/glob — names only
TRAVERSE = "traverse"                    # cd — intent to look, nothing shown
WRITE = "write"
ACCESS = "access"                        # unclassified path mention

_CONTENT_SEARCH = re.compile(r"(?:^|[\s;|&(])(?:grep|egrep|fgrep|rg|ack|ag|zgrep)\b")
_NAME_SEARCH = re.compile(r"(?:^|[\s;|&(])(?:ls|find|tree|stat|du|basename|dirname)\b")
_CONTENT_READ = re.compile(
    r"(?:^|[\s;|&(])(?:cat|head|tail|less|more|od|xxd|strings|cp|rsync|install|sed|awk|python3?|jq)\b"
)


def _bash_character(segment: str) -> str:
    """Best-effort character of a Bash segment, biased toward the worse case."""
    if _CONTENT_SEARCH.search(segment):
        return ENUMERATE_CONTENT
    if _CONTENT_READ.search(segment):
        return READ
    if _NAME_SEARCH.search(segment):
        return ENUMERATE_NAMES
    return ACCESS


@dataclass
class Violation:
    tool: str
    path: str
    reason: str
    context: str
    severity: str = CONTAMINATED
    character: str = ACCESS


@dataclass
class Warning:
    """A recorded access that is benign but useful to report."""

    tool: str
    path: str
    reason: str
    context: str


@dataclass
class Access:
    """One resolved access, in-bounds or not.

    Violations answer "did the agent cheat?"; accesses answer "what did the
    agent actually look at?". The latter is the more useful signal for
    interpreting a run, and the substrate any severity/class scheme needs.
    """

    tool: str
    path: str
    in_bounds: bool
    zone: str
    context: str
    severity: str = IN_BOUNDS
    character: str = ACCESS


# Information zones inside a fold environment, matched against the env-relative
# path. Order matters: first match wins. These mirror build_env.py's layout
# constants (HARMONIZER_REL, MAPPING_REL, METADATA_REL, RAW_DATA_REL).
_ENV_ZONES: list[tuple[str, str]] = [
    ("output", "output"),
    ("raw_input", "inputs/raw"),
    ("exemplar_code", "data/gold/expert_code"),
    ("filtered_mapping", "data/processed"),
    ("essdive_metadata", "data/raw_cache/ess-dive_wfsfa_soil_metadata"),
    ("skills", "skills"),
    ("audit", "audit"),
    ("agent_settings", ".claude"),
]


def _zone(p: Path, in_bounds: bool, env_dir: Path) -> str:
    """Classify *where* an access landed, for the access trace."""
    if any(under(p, r) for r in IGNORED_ROOTS):
        return "system"
    if not in_bounds:
        return "outside_env"
    try:
        rel = p.relative_to(env_dir).as_posix()
    except ValueError:
        return "allowed_extra"
    if rel in (".", ""):
        return "env_root"
    for name, prefix in _ENV_ZONES:
        if rel == prefix or rel.startswith(prefix + "/"):
            return name
    if rel in ("AGENT_INSTRUCTIONS.md", "MANIFEST.json"):
        return "instructions"
    return "env_other"


def _record(report: "AuditReport", tool: str, p: Path, in_bounds: bool,
            allowed: list[Path], env_dir: Path, context: str,
            severity: str = IN_BOUNDS, character: str = ACCESS) -> None:
    report.accesses.append(
        Access(tool, str(p), in_bounds, _zone(p, in_bounds, env_dir), context[:200],
               severity=severity, character=character)
    )


_DATASET_MODULE = re.compile(r"dataset_0*(\d+)\.py")
_ANSWER_KEY = re.compile(r"eval_answer_keys|expert_dataset_\d+|expert_mapping_entry")


def _is_answer_key(p: Path) -> bool:
    """A path whose only purpose is to hold answers."""
    return bool(_ANSWER_KEY.search(str(p)))


def _touches_withheld(p: Path, raw: str, holdout_ids: list[str],
                      holdout_indices: set[int]) -> Optional[bool]:
    """Does this access name a dataset withheld from this fold's exemplars?

    True = a withheld dataset; False = one that was *not* withheld, whose
    expert code the agent already had legitimately; None = the access does not
    identify a dataset at all — a whole-directory search, or the unfiltered
    mapping, both of which span withheld material.
    """
    hay = f"{p}\n{raw}"
    if any(h and h in hay for h in holdout_ids):
        return True
    if m := _DATASET_MODULE.search(hay):
        return int(m.group(1)) in holdout_indices
    return None


def _severity(character: str, p: Path, raw: str, repo_root: Path,
              holdout_ids: list[str], holdout_indices: set[int]) -> str:
    """Rank an out-of-bounds access.

    Not every out-of-bounds access is a leak, and not every answer-location
    touch shows withheld content:

    * nothing answer-bearing out there → BOUNDARY;
    * an answer-key path exists only to hold answers, so arriving there is
      never incidental → CONTAMINATED. This is also the case the ``cd`` rule
      was written for: ``cd <answer dir> && cat expert_dataset_07.py`` leaves a
      single-component read that is never tokenised, so the traversal is the
      only evidence there is;
    * a search that reads *inside* files across an answer directory spans
      withheld material whether or not it names a dataset → CONTAMINATED;
    * a read of answer material for a withheld dataset → CONTAMINATED; for a
      dataset never withheld, the agent already had that exemplar → LEAK_RISK;
    * merely arriving somewhere, or listing names → LEAK_RISK.
    """
    if not _forbidden(p, repo_root):
        return BOUNDARY
    if _is_answer_key(p):
        return CONTAMINATED
    if character == ENUMERATE_CONTENT:
        return CONTAMINATED
    if character in (READ, WRITE):
        withheld = _touches_withheld(p, raw, holdout_ids, holdout_indices)
        # None = unattributable (e.g. the unfiltered mapping, which carries
        # every held-out entry); treat as contaminated rather than guess.
        return LEAK_RISK if withheld is False else CONTAMINATED
    return LEAK_RISK


@dataclass
class AuditReport:
    clean: bool
    violations: list[Violation] = field(default_factory=list)
    warnings: list[Warning] = field(default_factory=list)
    accesses: list[Access] = field(default_factory=list)
    n_tool_calls: int = 0
    n_reads: int = 0
    reads_in_bounds: int = 0
    bash_commands: list[str] = field(default_factory=list)
    allowed_roots: list[str] = field(default_factory=list)

    def zone_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for a in self.accesses:
            counts[a.zone] = counts.get(a.zone, 0) + 1
        return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))

    def severity_counts(self) -> dict[str, int]:
        """Findings by severity, worst first."""
        counts: dict[str, int] = {}
        for v in self.violations:
            counts[v.severity] = counts.get(v.severity, 0) + 1
        return dict(sorted(counts.items(), key=lambda kv: -SEVERITY_RANK.get(kv[0], 0)))

    @property
    def worst_severity(self) -> str:
        """Highest severity recorded; IN_BOUNDS when there are no findings."""
        return max((v.severity for v in self.violations),
                   key=lambda s: SEVERITY_RANK.get(s, 0), default=IN_BOUNDS)


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
    if under(p, repo_root / "data" / "raw_cache" / "ess-dive_wfsfa_soil_metadata"):
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
    holdout_indices: Optional[set[int]] = None,
) -> AuditReport:
    """Audit a trace; return an :class:`AuditReport`.

    ``clean`` stays True unless something reached CONTAMINATED. Lesser findings
    are still recorded as violations carrying their own severity — a fold can
    be worth reviewing without being worth invalidating.

    ``holdout_identifiers`` / ``holdout_indices`` are this fold's *reference
    holdout*: the datasets withheld from its exemplars. They decide whether
    answer material the agent touched was withheld from it or was already
    legitimately available — the difference between CONTAMINATED and
    LEAK_RISK. They are passed in rather than read from ``MANIFEST.json``,
    which deliberately hides holdout identities from the agent.
    """
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
    holdout_idx = set(holdout_indices or ())

    report = AuditReport(clean=True, allowed_roots=[str(r) for r in allowed])
    tool_uses = load_tool_uses(trace_path)
    report.n_tool_calls = len(tool_uses)

    def check(tool: str, abs_path: Path, raw: str, character: str = ACCESS):
        if any(under(abs_path, r) for r in IGNORED_ROOTS):
            _record(report, tool, abs_path, True, allowed, env_dir, raw, IN_BOUNDS, character)
            return True  # /dev/null redirects etc. — not data access
        if any(under(abs_path, r) for r in allowed):
            _record(report, tool, abs_path, True, allowed, env_dir, raw, IN_BOUNDS, character)
            return True
        sev = _severity(character, abs_path, raw, repo_root, holdout_ids, holdout_idx)
        _record(report, tool, abs_path, False, allowed, env_dir, raw, sev, character)
        if warning := _benign_external_input(abs_path, repo_root):
            report.warnings.append(Warning(tool, str(abs_path), warning, raw[:200]))
            return False
        if sev == CONTAMINATED:
            report.clean = False
        report.violations.append(
            Violation(tool, str(abs_path), _reason(abs_path, repo_root, holdout_ids, raw),
                      raw[:200], severity=sev, character=character)
        )
        return False

    for name, inp in tool_uses:
        if name in ("Read", "Write", "Edit", "NotebookEdit"):
            fp = inp.get("file_path") or inp.get("notebook_path") or ""
            if not fp:
                continue
            if name == "Read":
                report.n_reads += 1
            char = READ if name == "Read" else WRITE
            if check(name, lexical_resolve(fp, str(repo_root)), fp, char) and name == "Read":
                report.reads_in_bounds += 1
        elif name in ("Grep", "Glob", "LS"):
            # Grep searches inside files; Glob and LS reveal names only.
            char = ENUMERATE_CONTENT if name == "Grep" else ENUMERATE_NAMES
            p = inp.get("path")
            if p:
                check(name, lexical_resolve(str(p), str(repo_root)), str(p), char)
            for key in ("glob", "pattern"):  # a path-bearing glob can leak too
                val = inp.get(key)
                if val:
                    for tok in _PATH_TOKEN.findall(str(val)):
                        check(name, lexical_resolve(tok, str(repo_root)), str(val), char)
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
                    # Only an answer location *outside* the environment is a
                    # violation. The workflow audits with --repo-root equal to
                    # --env (post-rsync, the workspace *is* the fold), so
                    # `repo_root/data/gold/expert_code` is the fold's own
                    # ablated exemplar set — which AGENT_INSTRUCTIONS.md tells
                    # the agent to use. Testing `allowed` first keeps this
                    # branch consistent with `check()` and with the root-based
                    # policy described in the module docstring.
                    in_bounds = any(under(target, r) for r in allowed)
                    sev = IN_BOUNDS if in_bounds else _severity(
                        TRAVERSE, target, seg, repo_root, holdout_ids, holdout_idx)
                    _record(report, "Bash(cd)", target, in_bounds, allowed, env_dir,
                            seg.strip(), sev, TRAVERSE)
                    if not in_bounds and _forbidden(target, repo_root):
                        # Arriving somewhere proves intent, not exposure, so a
                        # bare cd ranks below a read of the same location —
                        # except at an answer-key path, where _severity already
                        # returns CONTAMINATED.
                        if sev == CONTAMINATED:
                            report.clean = False
                        report.violations.append(
                            Violation("Bash(cd)", str(target),
                                      _reason(target, repo_root, holdout_ids, seg), seg.strip(),
                                      severity=sev, character=TRAVERSE))
                    cwd = str(target)
                    continue
                seg_char = _bash_character(seg)
                for tok in _path_tokens(seg):
                    check("Bash", lexical_resolve(tok, cwd), seg.strip(), seg_char)
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
    access_trace: Optional[Path] = typer.Option(None, "--access-trace", help="Write a TSV of every resolved access (tool, severity, character, zone, path)."),
    reference_holdout: Optional[Path] = typer.Option(None, "--reference-holdout", help="File of this fold's reference-holdout dataset identifiers and/or indices, one per line. Decides CONTAMINATED vs LEAK_RISK."),
) -> None:
    """Audit a run's trace; exit non-zero only on CONTAMINATED."""
    holdout_ids: list[str] = []
    manifest = env / "MANIFEST.json"
    if manifest.exists():
        manifest_data = json.loads(manifest.read_text())
        # Target identifiers are the only answer identifiers exposed in newly
        # built environments. Retain the old field as a compatibility fallback
        # for previously staged runs.
        holdout_ids = [h for h in manifest_data.get(
            "target_identifiers", manifest_data.get("holdout_identifiers", [])
        ) if h]

    # The manifest hides the reference holdout from the agent, so the full set
    # is supplied out-of-band by the workflow, which still has the mapping at
    # the point the invigilator is preserved.
    holdout_indices: set[int] = set()
    if reference_holdout is not None and reference_holdout.exists():
        for token in reference_holdout.read_text().replace(",", " ").split():
            token = token.strip()
            if not token:
                continue
            if token.isdigit():
                holdout_indices.add(int(token))
            elif token not in holdout_ids:
                holdout_ids.append(token)

    r = audit(trace, env, raw_data_dir=raw_data, repo_root=repo_root,
              extra_roots=list(allow), holdout_identifiers=holdout_ids,
              holdout_indices=holdout_indices)

    typer.echo(f"tool calls: {r.n_tool_calls} | reads: {r.n_reads} ({r.reads_in_bounds} in-bounds)")
    typer.echo("allowed roots:")
    for root in r.allowed_roots:
        typer.echo(f"  - {root}")

    counts = r.zone_counts()
    if counts:
        typer.echo(f"\naccess by zone ({len(r.accesses)} resolved):")
        for zone, n in counts.items():
            typer.echo(f"  {n:>4}  {zone}")
    if access_trace is not None:
        access_trace.parent.mkdir(parents=True, exist_ok=True)
        with access_trace.open("w") as fh:
            fh.write("tool\tseverity\tcharacter\tin_bounds\tzone\tpath\tcontext\n")
            for a in r.accesses:
                ctx = a.context.replace("\t", " ").replace("\n", " ")
                fh.write(f"{a.tool}\t{a.severity}\t{a.character}\t{a.in_bounds}"
                         f"\t{a.zone}\t{a.path}\t{ctx}\n")
        typer.echo(f"\naccess trace written to {access_trace}")
    if not r.violations:
        typer.echo("\n✅ CLEAN — no out-of-bounds access detected.")
    else:
        # Worst first: the verdict is the first thing a reader needs.
        ranked = sorted(r.violations, key=lambda v: -SEVERITY_RANK.get(v.severity, 0))
        summary = ", ".join(f"{n} {s}" for s, n in r.severity_counts().items())
        typer.echo(f"\n{'⛔' if not r.clean else '⚠'} {len(ranked)} FINDING(S): {summary}")
        for v in ranked:
            typer.echo(f"  [{v.severity}/{v.character}] [{v.tool}] {v.reason}")
            typer.echo(f"      path: {v.path}")
            typer.echo(f"      in:   {v.context}")
        if r.clean:
            typer.echo("\n✅ No CONTAMINATED finding — the fold stands. "
                       "Findings above are recorded for review.")
        else:
            typer.echo("\n⛔ CONTAMINATED — withheld answer material was reachable; "
                       "this fold's result is not trustworthy.")
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
