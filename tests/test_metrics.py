"""Unit tests for the scoring package.

These use synthetic frames so they run without BERDL access. The known-answer
regression against fold 17 lives in ``docs/evaluation_metrics.md`` and requires
the lakehouse; it is not run here.
"""
from __future__ import annotations

import pandas as pd
import pytest

from src.metrics import diagnose, equivalence as eq, mapping_score, schema_score
from src.schemas.target_schema import HARMONIZED_COLUMNS


def frame(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=HARMONIZED_COLUMNS)


def row(dt="2022-01-01 00:00:00+00:00", site="A", depth=0.1, rep=1, vwc=0.3):
    return {
        "datetime_UTC": dt,
        "site_id": site,
        "depth_m": depth,
        "replicate": rep,
        "is_timeseries": True,
        "volumetric_water_content_m3_m3": vwc,
        "gravimetric_water_content_gH2O_gs": None,
        "water_potential_kPa": None,
    }


class TestLadder:
    def test_identical_frames_score_one_at_every_level(self):
        df = frame([row(), row(site="B", vwc=0.4)])
        r = eq.score(df, df)
        for level in ("L1", "L2", "L3"):
            assert r[level]["f1"] == pytest.approx(1.0)
        assert r["L3"]["cells"]["overall"] == pytest.approx(1.0)

    def test_row_order_is_irrelevant(self):
        a = frame([row(site="A"), row(site="B", vwc=0.4)])
        b = frame([row(site="B", vwc=0.4), row(site="A")])
        assert eq.score(a, b)["L3"]["f1"] == pytest.approx(1.0)

    def test_site_rename_zeroes_l3_but_not_l1(self):
        agent = frame([row(site="S1"), row(site="S2", vwc=0.4)])
        gold = frame([row(site="S1_HERB"), row(site="S2_HERB", vwc=0.4)])
        r = eq.score(agent, gold)
        assert r["L3"]["f1"] == pytest.approx(0.0)
        assert r["L1"]["recall"] == pytest.approx(1.0)
        # The crosswalk should recover the correspondence.
        assert r["crosswalk"]["kind"] == "suffix_stripped"
        assert r["L2"]["f1"] > 0.9

    def test_extra_agent_rows_cut_precision_not_recall(self):
        gold = frame([row(site="A")])
        agent = frame([row(site="A"), row(site="B", vwc=0.4)])
        r = eq.score(agent, gold)
        assert r["L3"]["recall"] == pytest.approx(1.0)
        assert r["L3"]["precision"] == pytest.approx(0.5)


class TestTimeOffset:
    def test_detects_uniform_shift(self):
        gold = frame([row(dt=f"2022-01-0{d} 00:00:00+00:00") for d in range(1, 6)])
        agent = frame([row(dt=f"2022-01-0{d} 06:00:00+00:00") for d in range(1, 6)])
        off = eq.detect_time_offset(eq.canonicalise(agent), eq.canonicalise(gold))
        assert off["detected"] is True
        assert off["offset_hours"] == 6

    def test_no_false_positive_on_aligned_frames(self):
        df = frame([row(dt=f"2022-01-0{d} 00:00:00+00:00") for d in range(1, 6)])
        off = eq.detect_time_offset(eq.canonicalise(df), eq.canonicalise(df))
        assert off["detected"] is False

    def test_correction_restores_the_score(self):
        gold = frame([row(dt=f"2022-01-0{d} 00:00:00+00:00") for d in range(1, 6)])
        agent = frame([row(dt=f"2022-01-0{d} 06:00:00+00:00") for d in range(1, 6)])
        r = eq.score(agent, gold)
        assert r["L3"]["f1"] == pytest.approx(0.0)
        assert r["offset_corrected"]["L3"]["f1"] == pytest.approx(1.0)


class TestDiagnostics:
    def test_row_inflation_and_site_superset(self):
        gold = frame([row(site="A")])
        agent = frame([row(site="A"), row(site="B"), row(site="C")])
        r = eq.score(agent, gold)
        codes = {f["code"] for f in diagnose.diagnose(
            r, eq.canonicalise(agent), eq.canonicalise(gold))}
        assert "ROW_INFLATION" in codes
        assert "SITE_SUPERSET" in codes

    def test_unit_scale_detected(self):
        gold = frame([row(vwc=0.30), row(site="B", vwc=0.40)])
        agent = frame([row(vwc=30.0), row(site="B", vwc=40.0)])
        r = eq.score(agent, gold)
        findings = diagnose.diagnose(r, eq.canonicalise(agent), eq.canonicalise(gold))
        scale = [f for f in findings if f["code"] == "UNIT_SCALE"]
        assert scale and scale[0]["evidence"]["median_ratio"] == pytest.approx(100.0, rel=0.1)

    def test_clean_fold_yields_no_critical_findings(self):
        df = frame([row(), row(site="B", vwc=0.4)])
        r = eq.score(df, df)
        findings = diagnose.diagnose(r, eq.canonicalise(df), eq.canonicalise(df))
        assert [f for f in findings if f["severity"] == "critical"] == []

    def test_coord_unresolved(self):
        loc = {
            "available": True,
            "n_gold_sites_with_coords": 4,
            "n_agent_rows_with_coords": 0,
            "site_set": {"recall": 1.0, "n_gold": 4},
        }
        codes = {f["code"] for f in diagnose.diagnose_location(loc)}
        assert "COORD_UNRESOLVED" in codes


class TestSchema:
    def test_text_csv_is_conformant_when_coercible(self):
        # Values arrive as strings from a CSV; that must not count against the run.
        df = frame([row()]).astype(str)
        out = schema_score.score(df)
        assert out["n_uncoercible_columns"] == 0
        assert out["conformant"] is True

    def test_uncoercible_value_is_caught(self):
        df = frame([row()])
        df["depth_m"] = "not-a-number"
        out = schema_score.score(df)
        assert out["coercion"]["depth_m"]["uncoercible"] == 1
        assert out["conformant"] is False

    def test_out_of_range_counts_against_the_verdict(self):
        # TargetSchema.is_valid ignores ranges; this wrapper must not.
        df = frame([row(vwc=95.0)])
        out = schema_score.score(df)
        assert out["n_out_of_range_columns"] >= 1
        assert out["conformant"] is False


class TestMapping:
    def test_unit_conversion_templates_parse(self):
        assert mapping_score.parse_unit_conversion(None)["kind"] == "absent"
        assert mapping_score.parse_unit_conversion("None; source units are m3/m3.")["kind"] == "none"
        p = mapping_score.parse_unit_conversion("Divide by 1e2 to convert from cm to m.")
        assert p["kind"] == "scale"
        assert p["factor"] == pytest.approx(0.01)
        assert p["from_unit"] == "cm"

    def test_step_extraction_finds_filter_and_join(self):
        text = (
            "Join WM_SWC records to sensor_metadata by 'Sensor.SN'. "
            "Filter to Treatment=='control'. Rename 'Depth.cm' to depth_m."
        )
        steps = mapping_score.extract_steps(text)
        assert {"JOIN", "FILTER", "RENAME"} <= steps

    def test_steps_pool_across_variable_groups(self):
        # The filter lives in the depth group but governs the whole dataset.
        entry = {
            "harmonization_mappings": {
                "depth": {"pattern_1": {"transformation": "Filter to Treatment=='control'."}},
                "datetime": {"pattern_1": {"transformation": "Convert to ISO 8601 UTC format."}},
            }
        }
        counts, _ = mapping_score.dataset_steps(entry)
        assert counts["FILTER"] == 1
        assert counts["TIMEZONE"] >= 1

    def test_notes_count_toward_recall_but_not_mapping_precision(self):
        gold = {"harmonization_mappings":
                {"depth": {"p1": {"transformation": "Filter to Treatment=='control'."}}}}
        agent = {"harmonization_mappings":
                 {"depth": {"p1": {"transformation": "Rename Depth.cm to depth_m."}}}}
        out = mapping_score.score(agent, gold, notes_text="We filter to control plots.")
        assert out["steps"]["missing_ops"] == []
        assert out["steps"]["by_operation"]["FILTER"]["in_agent_mapping"] is False
        assert out["steps"]["by_operation"]["FILTER"]["in_agent_notes"] is True
