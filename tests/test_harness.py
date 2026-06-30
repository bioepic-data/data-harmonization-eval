#!/usr/bin/env python3
"""Quick test script to validate harness wiring.

This script tests the skill invocation infrastructure without running
a full experiment. It verifies:
1. Skill definitions can be loaded
2. Context files can be prepared
3. API key is configured
4. Schemas are properly wired

Run with: python test_harness.py
"""
from pathlib import Path
import os

from src.harness.skill_invoker import SkillInvoker


def test_skill_loading():
    """Test that skills can be loaded."""
    print("=" * 60)
    print("TEST 1: Loading skill definitions")
    print("=" * 60)

    project_root = Path(__file__).parent.parent  # Go up from tests/ to project root
    skills_dir = project_root / "skills"
    data_dir = project_root / "data"

    # Check API key (but don't require it for this test)
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        print("✓ ANTHROPIC_API_KEY is set")
        invoker = SkillInvoker(skills_dir=skills_dir, data_dir=data_dir, api_key=api_key)
    else:
        print("⚠ ANTHROPIC_API_KEY not set (API calls will fail)")
        print("  Set with: export ANTHROPIC_API_KEY='your-key'")
        # Continue anyway to test loading logic
        invoker = SkillInvoker(skills_dir=skills_dir, data_dir=data_dir, api_key="dummy")

    # Test curator skill loading
    print("\nLoading essdive_sm_curator skill...")
    try:
        curator_def = invoker.load_skill_definition("essdive_sm_curator")
        print(f"✓ Skill loaded successfully")
        print(f"  - Name: {curator_def['metadata'].get('name')}")
        print(f"  - Version: {curator_def['metadata'].get('version')}")
        print(f"  - System prompt length: {len(curator_def['system_prompt'])} chars")
    except Exception as e:
        print(f"✗ Failed to load curator skill: {e}")
        return False

    # Test harmonizer skill loading
    print("\nLoading essdive_sm_harmonizer skill...")
    try:
        harmonizer_def = invoker.load_skill_definition("essdive_sm_harmonizer")
        print(f"✓ Skill loaded successfully")
        print(f"  - Name: {harmonizer_def['metadata'].get('name')}")
        print(f"  - Version: {harmonizer_def['metadata'].get('version')}")
        print(f"  - System prompt length: {len(harmonizer_def['system_prompt'])} chars")
    except Exception as e:
        print(f"✗ Failed to load harmonizer skill: {e}")
        return False

    return True


def test_context_loading():
    """Test that context files can be loaded."""
    print("\n" + "=" * 60)
    print("TEST 2: Loading context files")
    print("=" * 60)

    project_root = Path(__file__).parent.parent  # Go up from tests/ to project root
    skills_dir = project_root / "skills"
    data_dir = project_root / "data"

    invoker = SkillInvoker(skills_dir=skills_dir, data_dir=data_dir, api_key="dummy")

    # Test loading mapping JSON
    print("\nLoading context files for curator...")
    try:
        context_deps = ["data/gold/sm_data_harmonization_mapping.json"]
        context_files = invoker.prepare_context_files(context_deps)

        print(f"✓ Loaded {len(context_files)} context file(s)")
        for path in context_files:
            print(f"  - {path}: {len(context_files[path])} chars")
    except Exception as e:
        print(f"✗ Failed to load context: {e}")
        return False

    # Test exemplar pool filtering
    print("\nTesting exemplar pool filtering...")
    try:
        exemplar_pool = [0, 2, 3, 4, 5]
        filtered_context = invoker.prepare_context_files(context_deps, exemplar_pool)

        # Verify filtering worked (check that only exemplar pool indices appear)
        import json
        for path, content in filtered_context.items():
            if "mapping.json" in path:
                data = json.loads(content)
                indices = [entry["index"] for entry in data]
                print(f"✓ Filtered mapping to indices: {indices}")

                if set(indices) != set(exemplar_pool):
                    print(f"⚠ Warning: Expected {exemplar_pool}, got {indices}")
    except Exception as e:
        print(f"✗ Failed to filter context: {e}")
        return False

    return True


def test_schemas():
    """Test that schemas can be imported and instantiated."""
    print("\n" + "=" * 60)
    print("TEST 3: Schema validation")
    print("=" * 60)

    # Test CuratorBundle
    print("\nTesting CuratorBundle schema...")
    try:
        from src.schemas.skill1_bundle import CuratorBundle, LocationResolution, TimeSeriesInference, ExperimentalContext

        # Create minimal valid bundle
        bundle = CuratorBundle(
            package_id="test-123",
            doi="doi:10.15485/test",
            curator_decision="INCLUDE",
            location_resolution=LocationResolution(source="unresolvable"),
            time_series_inference=TimeSeriesInference(is_timeseries=True, reasoning="Test"),
            experimental_context=ExperimentalContext(
                manipulation_detected=False,
                recommendation="include_all"
            ),
        )

        print(f"✓ CuratorBundle instantiated successfully")
        print(f"  - Package ID: {bundle.package_id}")
        print(f"  - Decision: {bundle.curator_decision}")

        # Test JSON round-trip
        json_str = bundle.model_dump_json()
        parsed = CuratorBundle.model_validate_json(json_str)
        print(f"✓ JSON serialization/deserialization works")

    except Exception as e:
        print(f"✗ Failed CuratorBundle test: {e}")
        return False

    # Test Skill2Output
    print("\nTesting Skill2Output schema...")
    try:
        from src.schemas.skill2_mapping import Skill2Output, HarmonizationMapping

        # Create minimal valid mapping
        mapping = HarmonizationMapping(
            index=99,
            dataset_identifier="test-123",
            doi="doi:10.15485/test",
            harmonization_mappings="EXCLUDED: test"
        )

        output = Skill2Output(
            package_id="test-123",
            python_code="# Test code",
            mapping_json=mapping,
        )

        print(f"✓ Skill2Output instantiated successfully")
        print(f"  - Package ID: {output.package_id}")
        print(f"  - Has code: {len(output.python_code) > 0}")

        # Test JSON round-trip
        json_str = output.model_dump_json()
        parsed = Skill2Output.model_validate_json(json_str)
        print(f"✓ JSON serialization/deserialization works")

    except Exception as e:
        print(f"✗ Failed Skill2Output test: {e}")
        return False

    return True


def test_gold_data_access():
    """Test that gold data is accessible."""
    print("\n" + "=" * 60)
    print("TEST 4: Gold data accessibility")
    print("=" * 60)

    project_root = Path(__file__).parent.parent  # Go up from tests/ to project root

    # Check mapping JSON
    mapping_path = project_root / "data" / "gold" / "sm_data_harmonization_mapping.json"
    print(f"\nChecking {mapping_path}...")
    if mapping_path.exists():
        print(f"✓ Mapping JSON exists ({mapping_path.stat().st_size} bytes)")

        # Quick validation
        import json
        try:
            with open(mapping_path) as f:
                data = json.load(f)
            print(f"  - Contains {len(data)} dataset entries")
            print(f"  - Indices: {[d.get('index') for d in data[:5]]}...")
        except Exception as e:
            print(f"⚠ Warning: Could not parse mapping JSON: {e}")
    else:
        print(f"✗ Mapping JSON not found")
        return False

    # Check expert code
    code_dir = project_root / "data" / "gold" / "expert_code" / "harmonize_sm"
    print(f"\nChecking {code_dir}...")
    if code_dir.exists():
        code_files = list(code_dir.glob("dataset_*.py"))
        print(f"✓ Expert code directory exists")
        print(f"  - Found {len(code_files)} dataset files")
        if code_files:
            print(f"  - Examples: {[f.name for f in code_files[:3]]}")
    else:
        print(f"✗ Expert code directory not found")
        return False

    # Check common.py
    common_path = code_dir / "common.py"
    if common_path.exists():
        print(f"✓ common.py exists ({common_path.stat().st_size} bytes)")
    else:
        print(f"⚠ Warning: common.py not found (harmonizer code may fail)")

    return True


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("HARNESS VALIDATION TEST SUITE")
    print("=" * 60)
    print("\nThis script validates the skill invocation infrastructure.")
    print("It does NOT make actual API calls (unless you proceed to live test).\n")

    results = []

    # Run tests
    results.append(("Skill loading", test_skill_loading()))
    results.append(("Context loading", test_context_loading()))
    results.append(("Schema validation", test_schemas()))
    results.append(("Gold data access", test_gold_data_access()))

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {name}")

    all_passed = all(passed for _, passed in results)

    if all_passed:
        print("\n✓ All tests passed! Harness is ready to use.")
        print("\nNext steps:")
        print("  1. Set ANTHROPIC_API_KEY environment variable")
        print("  2. Review RUNNING_EXPERIMENTS.md for usage examples")
        print("  3. Try a single dataset test: python test_single_run.py")
        return 0
    else:
        print("\n✗ Some tests failed. Review errors above.")
        return 1


if __name__ == "__main__":
    exit(main())
