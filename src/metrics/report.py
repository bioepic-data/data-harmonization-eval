"""Build summary tables and figures from ``results/scored/summary.json``.

Usage::

    python -m src.metrics.report

Writes CSV tables to ``results/tables`` and PNG figures to ``results/figures``.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
SCORED = REPO_ROOT / "results" / "scored" / "summary.json"
TABLES = REPO_ROOT / "results" / "tables"
FIGURES = REPO_ROOT / "results" / "figures"

LEVELS = ["L1", "L2", "L3"]


def load(path: Path = SCORED) -> list[dict]:
    return json.loads(path.read_text())["folds"]


def per_fold_table(folds: list[dict]) -> pd.DataFrame:
    rows = []
    for f in folds:
        eq = f.get("equivalence") or {}
        row = {
            "fold": f["fold_id"],
            "target": f["target"],
            "cluster": (f.get("fold") or {}).get("cluster_name"),
            "exemplar_pool": (f.get("fold") or {}).get("exemplar_pool"),
            "gold_rows": (f.get("difficulty") or {}).get("gold_rows"),
            "row_ratio": (eq.get("L0") or {}).get("row_count_ratio"),
            "crosswalk": (eq.get("crosswalk") or {}).get("kind"),
            "n_agent_sites": (eq.get("crosswalk") or {}).get("n_agent_sites"),
            "n_gold_sites": (eq.get("crosswalk") or {}).get("n_gold_sites"),
            "schema_ok": (f.get("schema") or {}).get("conformant"),
        }
        for lv in LEVELS:
            d = eq.get(lv) or {}
            row[f"{lv}_f1"] = d.get("f1")
            row[f"{lv}_recall"] = d.get("recall")
            row[f"{lv}_precision"] = d.get("precision")
            row[f"{lv}_cells"] = (d.get("cells") or {}).get("overall")
        off = eq.get("time_offset") or {}
        row["tz_offset_h"] = off.get("offset_hours") if off.get("detected") else 0
        corr = (eq.get("offset_corrected") or {}).get("L3") or {}
        row["L3_f1_tz_corrected"] = corr.get("f1", row.get("L3_f1"))
        corr2 = (eq.get("offset_corrected") or {}).get("L2") or {}
        row["L2_cells_tz_corrected"] = (corr2.get("cells") or {}).get(
            "overall", row.get("L2_cells")
        )
        tel = f.get("telemetry") or {}
        row["cost_usd"] = tel.get("total_cost_usd")
        row["turns"] = tel.get("num_turns")
        acc = f.get("access") or {}
        row["exemplars_read"] = acc.get("n_exemplars_read")
        row["out_of_cluster_reads"] = acc.get("n_out_of_cluster_read")
        row["n_critical"] = sum(
            1 for x in f.get("findings", []) if x.get("severity") == "critical"
        )
        row["n_findings"] = len(f.get("findings", []))
        rows.append(row)
    return pd.DataFrame(rows).sort_values("fold").reset_index(drop=True)


def findings_table(folds: list[dict]) -> pd.DataFrame:
    rows = []
    for f in folds:
        for x in f.get("findings", []):
            rows.append(
                {
                    "fold": f["fold_id"],
                    "target": f["target"],
                    "cluster": (f.get("fold") or {}).get("cluster_name"),
                    "severity": x.get("severity"),
                    "code": x.get("code"),
                    "message": x.get("message"),
                }
            )
    return pd.DataFrame(rows)


def findings_frequency(findings: pd.DataFrame) -> pd.DataFrame:
    if findings.empty:
        return pd.DataFrame(columns=["code", "severity", "n_folds"])
    out = (
        findings.groupby(["code", "severity"])["fold"]
        .nunique()
        .reset_index(name="n_folds")
        .sort_values(["n_folds", "code"], ascending=[False, True])
    )
    return out.reset_index(drop=True)


def by_cluster(per_fold: pd.DataFrame) -> pd.DataFrame:
    """Aggregate by ablation stratum.

    Reported as medians with explicit n. Folds within a cluster are not
    independent -- cluster_1 is six instruments at one site -- so these are
    descriptive summaries, not estimates with sampling error.
    """
    g = per_fold.groupby(["cluster", "exemplar_pool"], dropna=False)
    out = g.agg(
        n_folds=("fold", "count"),
        median_L3_f1=("L3_f1", "median"),
        median_L2_cells=("L2_cells", "median"),
        median_L1_recall=("L1_recall", "median"),
        median_row_ratio=("row_ratio", "median"),
        median_cost=("cost_usd", "median"),
        median_exemplars_read=("exemplars_read", "median"),
        total_critical=("n_critical", "sum"),
    ).reset_index()
    return out.sort_values("exemplar_pool").reset_index(drop=True)


def column_agreement(folds: list[dict]) -> pd.DataFrame:
    """Per-column cell agreement at L2, with coverage caveats attached."""
    rows = []
    for f in folds:
        cells = (((f.get("equivalence") or {}).get("L2") or {}).get("cells") or {}).get(
            "by_column", {}
        )
        for col, d in cells.items():
            rows.append(
                {
                    "fold": f["fold_id"],
                    "column": col,
                    "agreement": d.get("agreement"),
                    "null_mask_agreement": d.get("null_mask_agreement"),
                    "n": d.get("n"),
                }
            )
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return (
        df.groupby("column")
        .agg(
            median_agreement=("agreement", "median"),
            min_agreement=("agreement", "min"),
            median_null_mask=("null_mask_agreement", "median"),
            n_folds=("fold", "nunique"),
        )
        .reset_index()
        .sort_values("median_agreement", ascending=False)
        .reset_index(drop=True)
    )


def make_figures(per_fold: pd.DataFrame, freq: pd.DataFrame, cols: pd.DataFrame) -> list[Path]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    FIGURES.mkdir(parents=True, exist_ok=True)
    written = []

    # Fig 1 -- the ladder, per fold.
    fig, ax = plt.subplots(figsize=(10, 5))
    x = range(len(per_fold))
    for lv, marker in zip(LEVELS, ["o", "s", "^"]):
        ax.plot(x, per_fold[f"{lv}_f1"], marker=marker, label=f"{lv} F1", alpha=0.85)
    ax.plot(x, per_fold["L2_cells"], marker="d", linestyle="--",
            label="L2 cell agreement", alpha=0.85)
    ax.set_xticks(list(x))
    ax.set_xticklabels([f"{r.fold:02d}\nt{r.target}" for r in per_fold.itertuples()], fontsize=7)
    ax.set_xlabel("fold / target")
    ax.set_ylabel("score")
    ax.set_ylim(-0.03, 1.03)
    ax.set_title("Output equivalence by match level")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    p = FIGURES / "fig1_match_ladder.png"
    fig.savefig(p, dpi=150)
    plt.close(fig)
    written.append(p)

    # Fig 2 -- finding frequency.
    if not freq.empty:
        fig, ax = plt.subplots(figsize=(9, 0.42 * len(freq) + 2))
        colors = {"critical": "#b2182b", "major": "#ef8a62", "minor": "#fddbc7",
                  "info": "#d9d9d9"}
        ax.barh(freq["code"], freq["n_folds"],
                color=[colors.get(s, "#999999") for s in freq["severity"]])
        ax.invert_yaxis()
        ax.set_xlabel("folds affected (of 19)")
        ax.set_title("Diagnostic findings across the corpus")
        ax.grid(axis="x", alpha=0.3)
        fig.tight_layout()
        p = FIGURES / "fig2_finding_frequency.png"
        fig.savefig(p, dpi=150)
        plt.close(fig)
        written.append(p)

    # Fig 3 -- per-column agreement.
    if not cols.empty:
        fig, ax = plt.subplots(figsize=(9, 4))
        ax.barh(cols["column"], cols["median_agreement"], color="#4575b4")
        ax.invert_yaxis()
        ax.set_xlim(0, 1.02)
        ax.set_xlabel("median L2 cell agreement")
        ax.set_title("Per-column agreement (median across folds)")
        ax.grid(axis="x", alpha=0.3)
        fig.tight_layout()
        p = FIGURES / "fig3_column_agreement.png"
        fig.savefig(p, dpi=150)
        plt.close(fig)
        written.append(p)

    # Fig 4 -- ablation vs performance, annotated as exploratory.
    fig, ax = plt.subplots(figsize=(7, 5))
    for cluster, grp in per_fold.groupby("cluster"):
        ax.scatter(grp["exemplar_pool"], grp["L2_cells"], label=f"{cluster} (n={len(grp)})",
                   s=70, alpha=0.8)
    ax.set_xlabel("exemplar pool size (datasets available as references)")
    ax.set_ylabel("L2 cell agreement")
    ax.set_title("Ablation vs accuracy\n(exploratory: folds within a cluster are not independent)",
                 fontsize=10)
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    p = FIGURES / "fig4_ablation.png"
    fig.savefig(p, dpi=150)
    plt.close(fig)
    written.append(p)

    return written


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scored", default=str(SCORED))
    args = ap.parse_args(argv)

    folds = load(Path(args.scored))
    TABLES.mkdir(parents=True, exist_ok=True)

    pf = per_fold_table(folds)
    fd = findings_table(folds)
    freq = findings_frequency(fd)
    cl = by_cluster(pf)
    cols = column_agreement(folds)

    for name, df in (
        ("per_fold", pf),
        ("findings", fd),
        ("finding_frequency", freq),
        ("by_cluster", cl),
        ("column_agreement", cols),
    ):
        df.to_csv(TABLES / f"{name}.csv", index=False)
        print(f"wrote {TABLES / (name + '.csv')}  ({len(df)} rows)")

    for p in make_figures(pf, freq, cols):
        print(f"wrote {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
