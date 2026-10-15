"""Locate and load agent deliverables from an ``eval/*`` run branch.

Filenames drift between runs: the notes file has been seen as ``notes.md``,
``NOTES.md``, ``harmonization_notes.md``, ``dataset_10_notes.md`` and
``<id>_notes.md``; the location CSV has five variants; the transform code has
three plus occasional extra driver scripts. Only the harmonized CSV has a
stable name, and even that is ambiguous by glob -- ``*_harmonized.csv`` also
matches ``*_location_harmonized.csv``.

So identification is **content-based** wherever possible (header sets, "the
only .json"), with filename patterns as a tiebreaker only.
"""
from __future__ import annotations

import csv
import io
import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from src.schemas.target_schema import HARMONIZED_COLUMNS

#: ``<fold>-<target>`` is encoded in the branch name, e.g.
#: ``eval/fold-17-target-23-38804950485-1``.
BRANCH_RE = re.compile(r"fold-(\d+)-target-(\d+)-(\d+)-(\d+)$")

LOCATION_HINT = re.compile(r"location", re.IGNORECASE)
_PYCACHE = re.compile(r"__pycache__|\.pyc$")
#: Prefer a real transform module over a driver wrapper when both are present.
_TRANSFORM_PREFERRED = re.compile(
    r"(?:^|/)(?:harmonize_)?dataset_?\d+\.py$|_harmonize\.py$", re.IGNORECASE
)


class GitSource:
    """Read files out of a git ref without checking it out."""

    def __init__(self, repo: Path | str, ref: str):
        self.repo = Path(repo)
        self.ref = ref

    def _git(self, *args: str) -> bytes:
        return subprocess.run(
            ["git", "-C", str(self.repo), *args],
            check=True,
            capture_output=True,
        ).stdout

    def list_files(self) -> list[str]:
        out = self._git("ls-tree", "-r", "--name-only", self.ref)
        return out.decode().splitlines()

    def read_bytes(self, path: str) -> bytes:
        return self._git("show", f"{self.ref}:{path}")

    def read_text(self, path: str) -> str:
        return self.read_bytes(path).decode("utf-8", errors="replace")


def _csv_header(source: GitSource, path: str) -> list[str]:
    """First row of a CSV, without materialising the whole file."""
    raw = source.read_bytes(path)
    head = raw[:65536].decode("utf-8", errors="replace")
    line = head.splitlines()[0] if head.splitlines() else ""
    return next(csv.reader(io.StringIO(line)), [])


@dataclass
class FoldArtifacts:
    """Resolved paths (branch-relative) for one run, plus provenance."""

    branch: str
    fold_id: int
    target: int
    run_id: str
    harmonized_csv: str | None = None
    location_csv: str | None = None
    transform_code: str | None = None
    extra_code: list[str] = field(default_factory=list)
    mapping_json: str | None = None
    notes_md: str | None = None
    access_trace: str | None = None
    execution_json: str | None = None
    invigilator_report: str | None = None
    raw_inputs_manifest: str | None = None
    #: Anything that made identification ambiguous, for the audit trail.
    warnings: list[str] = field(default_factory=list)


def parse_branch(branch: str) -> tuple[int, int, str, str]:
    m = BRANCH_RE.search(branch)
    if not m:
        raise ValueError(f"unrecognised eval branch name: {branch!r}")
    return int(m.group(1)), int(m.group(2)), m.group(3), m.group(4)


def resolve(source: GitSource, branch: str) -> FoldArtifacts:
    """Identify every scoreable artifact on one run branch."""
    fold_id, target, run_id, _attempt = parse_branch(branch)
    art = FoldArtifacts(branch=branch, fold_id=fold_id, target=target, run_id=run_id)

    files = source.list_files()
    out = [f for f in files if f.startswith("output/") and not _PYCACHE.search(f)]

    csvs = [f for f in out if f.lower().endswith(".csv")]
    jsons = [f for f in out if f.lower().endswith(".json")]
    mds = [f for f in out if f.lower().endswith(".md")]
    pys = [f for f in out if f.lower().endswith(".py")]

    # --- harmonized CSV: match on header set, not filename ----------------
    want = set(HARMONIZED_COLUMNS)
    harmonized = [f for f in csvs if set(_csv_header(source, f)) == want]
    if len(harmonized) == 1:
        art.harmonized_csv = harmonized[0]
    elif harmonized:
        art.harmonized_csv = harmonized[0]
        art.warnings.append(f"{len(harmonized)} CSVs match the harmonized header; took first")
    else:
        # Fall back to the filename convention, excluding location files.
        cand = [f for f in csvs if f.endswith("_harmonized.csv") and not LOCATION_HINT.search(f)]
        if cand:
            art.harmonized_csv = cand[0]
            art.warnings.append("harmonized CSV identified by filename; header did not match schema")

    # --- location CSV: header-based, filename as fallback -----------------
    loc = []
    for f in csvs:
        if f == art.harmonized_csv:
            continue
        hdr = {c.lower() for c in _csv_header(source, f)}
        if {"site_id", "latitude", "longitude"} <= hdr:
            loc.append(f)
    if not loc:
        loc = [f for f in csvs if LOCATION_HINT.search(f) and f != art.harmonized_csv]
    if loc:
        art.location_csv = loc[0]
        if len(loc) > 1:
            art.warnings.append(f"{len(loc)} location-like CSVs; took {loc[0]}")

    # --- transform code ---------------------------------------------------
    if pys:
        preferred = [f for f in pys if _TRANSFORM_PREFERRED.search(f)]
        art.transform_code = (preferred or pys)[0]
        art.extra_code = [f for f in pys if f != art.transform_code]

    # --- mapping JSON / notes: "the only one" holds on every branch seen --
    if jsons:
        art.mapping_json = jsons[0]
        if len(jsons) > 1:
            art.warnings.append(f"{len(jsons)} JSON files under output/; took {jsons[0]}")
    if mds:
        art.notes_md = mds[0]
        if len(mds) > 1:
            art.warnings.append(f"{len(mds)} markdown files under output/; took {mds[0]}")

    for attr, path in (
        ("access_trace", "audit/access_trace.tsv"),
        ("execution_json", "audit/claude-execution.json"),
        ("invigilator_report", "audit/invigilator_report.txt"),
        ("raw_inputs_manifest", "audit/raw_inputs_manifest.tsv"),
    ):
        if path in files:
            setattr(art, attr, path)

    for label, value in (
        ("harmonized CSV", art.harmonized_csv),
        ("mapping JSON", art.mapping_json),
    ):
        if value is None:
            art.warnings.append(f"missing {label}")

    return art


def load_mapping(source: GitSource, path: str) -> list[dict]:
    """Agent mapping JSON, normalised to a list of entries.

    Runs emit either a bare dict or a one-element list; both appear in the
    corpus, so callers should never have to care which.
    """
    data = json.loads(source.read_text(path))
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return data
    raise TypeError(f"unexpected mapping JSON top-level type: {type(data).__name__}")


def list_eval_branches(repo: Path | str, prefix: str = "refs/remotes/origin/eval/") -> list[str]:
    out = subprocess.run(
        ["git", "-C", str(repo), "for-each-ref", "--format=%(refname:short)", prefix],
        check=True,
        capture_output=True,
    ).stdout.decode()
    return sorted(line.strip() for line in out.splitlines() if line.strip())
