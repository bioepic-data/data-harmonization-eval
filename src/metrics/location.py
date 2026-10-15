"""Site and coordinate scoring against ``sdt_location``.

The lakehouse has no ``qc_flag`` column, but it does carry
``geolocation_resolution_method`` -- a 10-value provenance vocabulary that is
the ground truth the agents' ``g1``/``g2`` flags encode. See
:func:`src.metrics.reference.qc_flag_from_method`.
"""
from __future__ import annotations

import math

import pandas as pd

from src.metrics.reference import qc_flag_from_method

EARTH_RADIUS_M = 6_371_000.0


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def _prf(tp: int, n_pred: int, n_true: int) -> dict:
    p = tp / n_pred if n_pred else 0.0
    r = tp / n_true if n_true else 0.0
    return {
        "tp": tp,
        "precision": p,
        "recall": r,
        "f1": (2 * p * r / (p + r)) if (p + r) else 0.0,
    }


def score(agent_loc: pd.DataFrame | None, gold_loc: pd.DataFrame,
          crosswalk: dict | None = None) -> dict:
    """Score the agent's location table against the reference sites."""
    if agent_loc is None or agent_loc.empty:
        return {"available": False}

    cols = {c.lower(): c for c in agent_loc.columns}
    site_c = cols.get("site_id")
    lat_c, lon_c = cols.get("latitude"), cols.get("longitude")
    qc_c = cols.get("qc_flag")
    if site_c is None:
        return {"available": False, "reason": "no site_id column"}

    agent_sites = set(agent_loc[site_c].dropna().astype(str)) - {""}
    gold_sites = set(gold_loc["site_id"].dropna().astype(str)) - {""}

    # The reference location table can carry rows with no coordinates (sites
    # present in the observations but absent from the harmonized location
    # table), so the resolvable denominator is smaller than the site count.
    has_coords = gold_loc["latitude"].notna() & gold_loc["longitude"].notna()
    gold_sites_with_coords = set(
        gold_loc.loc[has_coords, "site_id"].dropna().astype(str)
    ) - {""}
    agent_with_coords = 0
    if lat_c is not None and lon_c is not None:
        agent_with_coords = int(
            (pd.to_numeric(agent_loc[lat_c], errors="coerce").notna()
             & pd.to_numeric(agent_loc[lon_c], errors="coerce").notna()).sum()
        )

    out: dict = {
        "available": True,
        "n_agent_sites": len(agent_sites),
        "n_gold_sites": len(gold_sites),
        "n_gold_sites_with_coords": len(gold_sites_with_coords),
        "n_agent_rows_with_coords": agent_with_coords,
        "site_set": _prf(len(agent_sites & gold_sites), len(agent_sites), len(gold_sites)),
    }

    # Coordinates, compared on sites that correspond on either side directly
    # or through the derived crosswalk.
    mapping = (crosswalk or {}).get("mapping") or {}
    gold_by_site = {
        str(r["site_id"]): r for _, r in gold_loc.iterrows() if pd.notna(r.get("site_id"))
    }
    distances: list[float] = []
    compared = 0
    for _, row in agent_loc.iterrows():
        name = str(row[site_c])
        candidates = [name] + [g for g, a in mapping.items() if a == name]
        g = next((gold_by_site[c] for c in candidates if c in gold_by_site), None)
        if g is None or lat_c is None or lon_c is None:
            continue
        try:
            alat, alon = float(row[lat_c]), float(row[lon_c])
            glat, glon = float(g["latitude"]), float(g["longitude"])
        except (TypeError, ValueError):
            continue
        if any(pd.isna(v) for v in (alat, alon, glat, glon)):
            continue
        distances.append(haversine_m(alat, alon, glat, glon))
        compared += 1

    if distances:
        s = pd.Series(distances)
        out["coordinates"] = {
            "n_compared": compared,
            "median_error_m": float(s.median()),
            "max_error_m": float(s.max()),
            "within_10m": float((s <= 10).mean()),
            "within_100m": float((s <= 100).mean()),
            "within_1km": float((s <= 1000).mean()),
        }
    else:
        out["coordinates"] = {"n_compared": 0}

    # qc_flag against the reference's resolution-method vocabulary.
    if qc_c is not None and "geolocation_resolution_method" in gold_loc.columns:
        expected = {
            str(r["site_id"]): qc_flag_from_method(r.get("geolocation_resolution_method"))
            for _, r in gold_loc.iterrows()
        }
        agree = total = 0
        for _, row in agent_loc.iterrows():
            name = str(row[site_c])
            candidates = [name] + [g for g, a in mapping.items() if a == name]
            exp = next((expected[c] for c in candidates if c in expected), "__missing__")
            if exp == "__missing__":
                continue
            got = row[qc_c]
            got = None if pd.isna(got) or str(got).strip().lower() in {"", "nan", "none"} else str(got)
            total += 1
            agree += int(got == exp)
        out["qc_flag"] = {
            "n_compared": total,
            "accuracy": (agree / total) if total else None,
        }
    return out
