"""Graded output-equivalence scoring: the L0-L3 match ladder.

A single strict join on ``(datetime_UTC, site_id, depth_m, replicate)`` scores
~0 whenever the agent's site vocabulary differs from the reference's, even when
every value is right -- and it cannot distinguish that from genuinely wrong
numbers. The ladder separates those failure modes:

====  =======================================  ==================================
L0    no join; distributions only              unit errors, gross filter errors
L1    datetime + depth + replicate             value accuracy, site set aside
L2    L1 + derived site crosswalk              site identity modulo vocabulary
L3    datetime + site_id + depth + replicate   conservative headline
====  =======================================  ==================================

Keys are **not unique** -- many sites share a timestamp -- so rows are paired by
multiset alignment: both sides are sorted deterministically and given a
within-key occurrence index, which makes matching well-defined and makes row
order irrelevant (the pilot's only disagreements were ordering artifacts).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.schemas.target_schema import HARMONIZED_COLUMNS

KEY_L1 = ["datetime_UTC", "depth_m", "replicate"]
KEY_L3 = ["datetime_UTC", "site_id", "depth_m", "replicate"]

VALUE_COLUMNS = [
    "is_timeseries",
    "volumetric_water_content_m3_m3",
    "gravimetric_water_content_gH2O_gs",
    "water_potential_kPa",
]
NUMERIC_COLUMNS = [
    "depth_m",
    "replicate",
    "volumetric_water_content_m3_m3",
    "gravimetric_water_content_gH2O_gs",
    "water_potential_kPa",
]

RTOL = 1e-5
ATOL = 1e-8

_SEP = re.compile(r"[\s_\-./]+")


def canonicalise(df: pd.DataFrame) -> pd.DataFrame:
    """Put a harmonized frame into a comparable form.

    Datetimes become a fixed UTC string (the lakehouse stores them that way and
    lexicographic order equals chronological), numerics become float, booleans
    become a nullable boolean.
    """
    out = pd.DataFrame(index=df.index)
    for col in HARMONIZED_COLUMNS:
        if col not in df.columns:
            out[col] = np.nan
            continue
        s = df[col]
        if col == "datetime_UTC":
            parsed = pd.to_datetime(s, utc=True, errors="coerce", format="mixed")
            out[col] = parsed.dt.strftime("%Y-%m-%d %H:%M:%S+00:00")
        elif col == "site_id":
            out[col] = s.astype("string").fillna("")
        elif col == "is_timeseries":
            out[col] = s.map(
                lambda v: bool(v) if not pd.isna(v) else pd.NA
            ).astype("boolean")
        else:
            out[col] = pd.to_numeric(s, errors="coerce").astype("float64")
    return out.reset_index(drop=True)


def _align(agent: pd.DataFrame, gold: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    """Pair rows by key with multiset semantics.

    Sorting by key then value and taking a within-key occurrence index makes
    the pairing deterministic and order-insensitive; for identical multisets it
    pairs every row correctly.
    """
    sort_cols = keys + [c for c in HARMONIZED_COLUMNS if c not in keys]

    def prep(df: pd.DataFrame, suffix: str) -> pd.DataFrame:
        d = df.sort_values(sort_cols, kind="mergesort", na_position="last").copy()
        d["_occ"] = d.groupby(keys, dropna=False).cumcount()
        return d.add_suffix(suffix).rename(
            columns={f"{k}{suffix}": k for k in keys + ["_occ"]}
        )

    a = prep(agent, "_a")
    g = prep(gold, "_g")
    return a.merge(g, on=keys + ["_occ"], how="outer", indicator=True)


def _cell_agreement(merged: pd.DataFrame, columns: list[str]) -> dict:
    """Per-column agreement over paired rows, plus NaN-mask agreement.

    Agreement computed only over cells where both sides are non-null would hide
    an agent writing 0 where the reference has NaN, so the null mask is scored
    as its own quantity.
    """
    both = merged[merged["_merge"] == "both"]
    n = len(both)
    out: dict[str, dict] = {}
    for col in columns:
        a, g = both.get(f"{col}_a"), both.get(f"{col}_g")
        if a is None or g is None or n == 0:
            out[col] = {"n": 0, "agreement": None, "null_mask_agreement": None}
            continue
        a_null, g_null = a.isna(), g.isna()
        mask_match = (a_null == g_null)
        if col in NUMERIC_COLUMNS:
            av = pd.to_numeric(a, errors="coerce").to_numpy(dtype="float64")
            gv = pd.to_numeric(g, errors="coerce").to_numpy(dtype="float64")
            close = np.isclose(av, gv, rtol=RTOL, atol=ATOL, equal_nan=True)
        else:
            close = (a.astype("object") == g.astype("object")) | (a_null & g_null)
            close = close.to_numpy(dtype=bool)
        out[col] = {
            "n": int(n),
            "agreement": float(np.mean(close)),
            "null_mask_agreement": float(mask_match.mean()),
            "both_null": int((a_null & g_null).sum()),
        }
    vals = [v["agreement"] for v in out.values() if v["agreement"] is not None]
    return {"by_column": out, "overall": float(np.mean(vals)) if vals else None}


def _prf(matched: int, n_agent: int, n_gold: int) -> dict:
    precision = matched / n_agent if n_agent else 0.0
    recall = matched / n_gold if n_gold else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "matched_rows": int(matched),
        "n_agent": int(n_agent),
        "n_gold": int(n_gold),
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def _level(agent: pd.DataFrame, gold: pd.DataFrame, keys: list[str]) -> dict:
    merged = _align(agent, gold, keys)
    matched = int((merged["_merge"] == "both").sum())
    result = _prf(matched, len(agent), len(gold))
    compare = [c for c in HARMONIZED_COLUMNS if c not in keys]
    result["cells"] = _cell_agreement(merged, compare)
    result["gap_structure"] = _gap_structure(merged)
    return result


def _gap_structure(merged: pd.DataFrame) -> dict:
    """Whether unmatched reference rows cluster by site or time, or scatter.

    A whole missing site or a missing time span is a systematic defect; the
    same row count scattered at random is a different one.
    """
    missing = merged[merged["_merge"] == "left_only"]  # in gold, absent from agent
    unmatched_gold = merged[merged["_merge"] == "right_only"]
    gold_side = unmatched_gold if len(unmatched_gold) else missing
    if gold_side.empty:
        return {"n_unmatched_gold": 0, "concentration": None}
    site_col = "site_id_g" if "site_id_g" in gold_side else "site_id"
    out: dict = {"n_unmatched_gold": int(len(gold_side))}
    if site_col in gold_side:
        by_site = gold_side[site_col].value_counts(normalize=True)
        out["top_site_share"] = float(by_site.iloc[0]) if len(by_site) else None
        out["n_sites_affected"] = int(len(by_site))
    dt = gold_side.get("datetime_UTC")
    if dt is not None and dt.notna().any():
        out["time_span"] = [str(dt.min()), str(dt.max())]
    return out


@dataclass
class Crosswalk:
    """Derived agent-site -> reference-site correspondence."""

    mapping: dict[str, str] = field(default_factory=dict)
    kind: str = "identity"
    matched: int = 0
    agent_only: list[str] = field(default_factory=list)
    gold_only: list[str] = field(default_factory=list)


def derive_crosswalk(agent_sites: set[str], gold_sites: set[str]) -> Crosswalk:
    """Reduce reference sites onto the agent's vocabulary where possible.

    Handles the observed case where the reference qualifies a site with a
    suffix the agent omits (``ER-WML1_HERB`` vs ``ER-WML1``). The reduction runs
    reference -> agent because it is many-to-one and therefore well defined.
    """
    cw = Crosswalk()
    if agent_sites == gold_sites:
        cw.kind = "identity"
        cw.mapping = {s: s for s in gold_sites}
        cw.matched = len(gold_sites)
        return cw

    def norm(s: str) -> str:
        return _SEP.sub("", s).lower()

    agent_norm = {norm(a): a for a in agent_sites}
    mapping: dict[str, str] = {}
    kinds: set[str] = set()
    for g in gold_sites:
        if g in agent_sites:
            mapping[g] = g
            kinds.add("exact")
            continue
        if norm(g) in agent_norm:
            mapping[g] = agent_norm[norm(g)]
            kinds.add("normalised")
            continue
        # Reference name extends an agent name with a separator + qualifier.
        prefixes = [a for a in agent_sites if g.startswith(a) and len(g) > len(a)
                    and not g[len(a)].isalnum()]
        if prefixes:
            mapping[g] = max(prefixes, key=len)
            kinds.add("suffix_stripped")
            continue
    cw.mapping = mapping
    cw.matched = len(mapping)
    cw.kind = "+".join(sorted(kinds)) if kinds else "none"
    cw.agent_only = sorted(agent_sites - set(mapping.values()))
    cw.gold_only = sorted(gold_sites - set(mapping))
    return cw


def detect_time_offset(agent: pd.DataFrame, gold: pd.DataFrame,
                       max_hours: int = 14) -> dict:
    """Find a uniform whole-hour shift between agent and reference timestamps.

    A timezone that was converted when it should not have been (or vice versa)
    moves every timestamp by the same amount, which drives the join to zero
    matches while every value is correct. Candidate offsets are scored by how
    much of the reference timestamp set they recover.
    """
    a = pd.to_datetime(agent["datetime_UTC"], utc=True, errors="coerce").dropna().unique()
    g = pd.to_datetime(gold["datetime_UTC"], utc=True, errors="coerce").dropna().unique()
    if len(a) == 0 or len(g) == 0:
        return {"detected": False}
    # Work in Timedelta space: pandas 3 stores datetimes at microsecond
    # resolution, so any hard-coded nanosecond constant is 1000x wrong.
    a_idx = pd.DatetimeIndex(a)
    gold_set = set(pd.DatetimeIndex(g))

    baseline = len(set(a_idx) & gold_set)
    best_shift, best_overlap = 0, baseline
    for h in range(-max_hours, max_hours + 1):
        if h == 0:
            continue
        overlap = len(set(a_idx - pd.Timedelta(hours=h)) & gold_set)
        if overlap > best_overlap:
            best_shift, best_overlap = h, overlap

    denom = min(len(a), len(g))
    # Only call it a shift if the timestamps genuinely fail to line up as-is
    # and the candidate recovers most of them. Without both conditions a
    # single coincidentally-matching timestamp would "detect" an offset on a
    # fold that was already aligned.
    baseline_frac = baseline / denom if denom else 0.0
    best_frac = best_overlap / denom if denom else 0.0
    return {
        "detected": bool(
            best_shift != 0 and baseline_frac < 0.5 and best_frac >= 0.5
        ),
        "offset_hours": best_shift,
        "overlap_at_offset": int(best_overlap),
        "overlap_at_zero": int(baseline),
        "recovered_fraction": (best_overlap / denom) if denom else None,
    }


def apply_time_offset(df: pd.DataFrame, offset_hours: int) -> pd.DataFrame:
    """Shift a canonical frame's timestamps by whole hours."""
    out = df.copy()
    dt = pd.to_datetime(out["datetime_UTC"], utc=True, errors="coerce")
    dt = dt - pd.Timedelta(hours=offset_hours)
    out["datetime_UTC"] = dt.dt.strftime("%Y-%m-%d %H:%M:%S+00:00")
    return out


def score(agent_raw: pd.DataFrame, gold_raw: pd.DataFrame) -> dict:
    """Run the full ladder. Returns one dict per level plus the crosswalk."""
    agent = canonicalise(agent_raw)
    gold = canonicalise(gold_raw)

    agent_sites = set(agent["site_id"].dropna().unique()) - {""}
    gold_sites = set(gold["site_id"].dropna().unique()) - {""}
    cw = derive_crosswalk(agent_sites, gold_sites)

    gold_l2 = gold.copy()
    gold_l2["site_id"] = gold_l2["site_id"].map(lambda s: cw.mapping.get(s, s))

    result = {
        "L0": _distributions(agent, gold),
        "L1": _level(agent, gold, KEY_L1),
        "L2": _level(agent, gold_l2, KEY_L3),
        "L3": _level(agent, gold, KEY_L3),
        "crosswalk": {
            "kind": cw.kind,
            "n_agent_sites": len(agent_sites),
            "n_gold_sites": len(gold_sites),
            "n_mapped": cw.matched,
            "agent_only": cw.agent_only[:20],
            "gold_only": cw.gold_only[:20],
            "mapping": cw.mapping,
        },
    }

    # A uniform timestamp shift zeroes every keyed level while leaving values
    # intact, so report what the ladder would give once it is corrected. This
    # separates "one systematic clock error" from "the data is wrong".
    offset = detect_time_offset(agent, gold)
    result["time_offset"] = offset
    if offset.get("detected"):
        shifted = apply_time_offset(agent, offset["offset_hours"])
        result["offset_corrected"] = {
            "L1": _level(shifted, gold, KEY_L1),
            "L2": _level(shifted, gold_l2, KEY_L3),
            "L3": _level(shifted, gold, KEY_L3),
        }
    return result


def _distributions(agent: pd.DataFrame, gold: pd.DataFrame) -> dict:
    """Join-free comparison: row counts, coverage, and value distributions."""
    out: dict = {
        "n_agent": int(len(agent)),
        "n_gold": int(len(gold)),
        "row_count_ratio": (len(agent) / len(gold)) if len(gold) else None,
    }
    cols: dict[str, dict] = {}
    for col in NUMERIC_COLUMNS + ["is_timeseries"]:
        a = pd.to_numeric(agent[col], errors="coerce").dropna()
        g = pd.to_numeric(gold[col], errors="coerce").dropna()
        entry = {
            "agent_non_null": int(len(a)),
            "gold_non_null": int(len(g)),
            "agent_null_rate": float(agent[col].isna().mean()),
            "gold_null_rate": float(gold[col].isna().mean()),
        }
        if len(a) and len(g):
            entry["agent_median"] = float(a.median())
            entry["gold_median"] = float(g.median())
            gm = g.median()
            entry["median_ratio"] = float(a.median() / gm) if gm else None
            entry["agent_min"], entry["agent_max"] = float(a.min()), float(a.max())
            entry["gold_min"], entry["gold_max"] = float(g.min()), float(g.max())
        cols[col] = entry
    out["columns"] = cols
    return out
