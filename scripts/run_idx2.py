"""One-shot example run: curator + harmonizer on dataset index 2.

Dataset idx 2:
  identifier: ess-dive-9fd65df885a8e87-20250715T064942543
  doi:        doi:10.15485/1646477
  cluster:    cluster_1 (held out with indices 1, 3, 6, 16, 27)
  exemplar_pool: [4, 5, 7, 8, 9, 10, 15, 17, 18, 23, 24, 25, 26]

This script:
1. Builds a leave-one-cluster-out environment (no data leakage).
2. Invokes Skill 1 (curator) via the Anthropic API with tools.
3. Invokes Skill 2 (harmonizer) via the Anthropic API with the curator bundle.
4. Saves full agent traces and outputs to results/raw_runs/idx2/.

Usage:
    ANTHROPIC_API_KEY=<key> python scripts/run_idx2.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import anthropic

from src.folds.expert_harmonizer import assemble_source
from src.schemas.skill1_bundle import CuratorBundle

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
TARGET_IDX = 2
TARGET_DOI = "doi:10.15485/1646477"
TARGET_PACKAGE_ID = "ess-dive-9fd65df885a8e87-20250715T064942543"
CLUSTER_1_HOLDOUT = {1, 2, 3, 6, 16, 27}
EXEMPLAR_POOL = [4, 5, 7, 8, 9, 10, 15, 17, 18, 23, 24, 25, 26]

MODEL_ID = "claude-sonnet-4-5"
MAX_TOKENS = 8000

MAPPING_PATH = ROOT / "data" / "gold" / "sm_data_harmonization_mapping.json"
SKILL1_PATH = ROOT / "skills" / "essdive_sm_curator" / "SKILL.md"
SKILL2_PATH = ROOT / "skills" / "essdive_sm_harmonizer" / "SKILL.md"
OUT_DIR = ROOT / "results" / "raw_runs" / "idx2"


# ---------------------------------------------------------------------------
# Load context
# ---------------------------------------------------------------------------
def load_mapping() -> list[dict]:
    return json.loads(MAPPING_PATH.read_text())


def filter_mapping_for_exemplars(mapping: list[dict], holdout: set[int]) -> list[dict]:
    """Remove held-out entries so agent cannot see them."""
    return [e for e in mapping if e.get("index") not in holdout]


def load_skill_prompt(path: Path) -> str:
    """Extract the SYSTEM PROMPT section from a SKILL.md file."""
    text = path.read_text()
    # Everything after the SYSTEM PROMPT header
    marker = "# ============================================================\n# SYSTEM PROMPT\n# ============================================================\n"
    if marker in text:
        return text.split(marker, 1)[1]
    return text


def load_exemplar_code(holdout: set[int]) -> str:
    """Return held-out-free expert code for the harmonizer to reference."""
    return assemble_source(holdout, ROOT / "data" / "gold" / "expert_code" / "harmonize_sm")


# ---------------------------------------------------------------------------
# ESS-DIVE metadata fetch (via API)
# ---------------------------------------------------------------------------
def fetch_essdive_metadata(package_id: str) -> dict:
    """Fetch ESS-DIVE package metadata from public API."""
    import urllib.request
    url = f"https://api.ess-dive.lbl.gov/packages/{package_id}"
    headers = {"Accept": "application/json"}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e), "package_id": package_id}


def fetch_essdive_file_preview(package_id: str, filename: str, max_lines: int = 20) -> str:
    """Download first N lines of a file from ESS-DIVE."""
    import urllib.request
    url = f"https://api.ess-dive.lbl.gov/packages/{package_id}/download?file={filename}"
    try:
        req = urllib.request.Request(url, headers={"Accept": "*/*"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            lines = []
            for _ in range(max_lines):
                line = resp.readline()
                if not line:
                    break
                lines.append(line.decode("utf-8", errors="replace").rstrip())
            return "\n".join(lines)
    except Exception as e:
        return f"[Could not fetch file: {e}]"


# ---------------------------------------------------------------------------
# Skill 1: Curator
# ---------------------------------------------------------------------------
def run_skill1(client: anthropic.Anthropic, mapping: list[dict], trace_dir: Path) -> dict:
    """Invoke Skill 1 (curator) on TARGET_DOI using Claude API."""
    print("=== Running Skill 1 (Curator) ===")

    # Build system prompt from skill file
    system_prompt = load_skill_prompt(SKILL1_PATH)

    # Filtered exemplar mapping (no held-out datasets)
    exemplar_mapping = filter_mapping_for_exemplars(mapping, CLUSTER_1_HOLDOUT)

    # Prepare context: give the agent its exemplar reference material
    context_block = f"""## Exemplar Reference Material

The following is the exemplar mapping JSON (held-out cluster removed). 
You may reference these entries as patterns when evaluating the new dataset.

```json
{json.dumps(exemplar_mapping, indent=2)}
```

## Task

Please curate the following ESS-DIVE dataset and produce a structured output bundle.

DOI: {TARGET_DOI}
Package ID: {TARGET_PACKAGE_ID}

Note: This dataset belongs to the East River Watershed / Watershed Function SFA project.
You have access to the ESS-DIVE API at https://api.ess-dive.lbl.gov/packages/<package_id>
to retrieve metadata and inspect files.

Fetch the package metadata, inspect the files, and produce the full output bundle
as described in your system prompt (Section 9). Output the final bundle as a JSON
code block after your analysis.
"""

    messages = [{"role": "user", "content": context_block}]

    # Tool for fetching ESS-DIVE metadata
    tools = [
        {
            "name": "fetch_package_metadata",
            "description": "Fetch ESS-DIVE package metadata from the public API.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "package_id": {
                        "type": "string",
                        "description": "The ESS-DIVE package identifier"
                    }
                },
                "required": ["package_id"]
            }
        },
        {
            "name": "fetch_file_preview",
            "description": "Download and preview the first 20 lines of a file from an ESS-DIVE package.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "package_id": {
                        "type": "string",
                        "description": "The ESS-DIVE package identifier"
                    },
                    "filename": {
                        "type": "string",
                        "description": "The filename to preview"
                    }
                },
                "required": ["package_id", "filename"]
            }
        }
    ]

    # Agentic loop
    all_messages = list(messages)
    turn = 0
    max_turns = 10
    final_text = ""

    while turn < max_turns:
        turn += 1
        print(f"  Curator turn {turn}...")

        response = client.messages.create(
            model=MODEL_ID,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            tools=tools,
            messages=all_messages,
        )

        # Save raw response
        (trace_dir / f"skill1_turn{turn:02d}_response.json").write_text(
            json.dumps(response.model_dump(), indent=2, default=str)
        )

        # Collect text
        text_parts = []
        tool_uses = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
                final_text += block.text + "\n"
            elif block.type == "tool_use":
                tool_uses.append(block)

        print(f"    stop_reason={response.stop_reason}, tool_uses={len(tool_uses)}")

        if response.stop_reason == "end_turn" and not tool_uses:
            break

        if response.stop_reason == "tool_use":
            # Execute tools
            all_messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for tool_use in tool_uses:
                print(f"    Tool: {tool_use.name}({tool_use.input})")
                if tool_use.name == "fetch_package_metadata":
                    result = fetch_essdive_metadata(tool_use.input["package_id"])
                    result_text = json.dumps(result, indent=2)
                elif tool_use.name == "fetch_file_preview":
                    result_text = fetch_essdive_file_preview(
                        tool_use.input["package_id"],
                        tool_use.input["filename"]
                    )
                else:
                    result_text = f"Unknown tool: {tool_use.name}"

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": result_text,
                })

            all_messages.append({"role": "user", "content": tool_results})
        else:
            # No more tool calls
            all_messages.append({"role": "assistant", "content": response.content})
            break

    # Save full transcript
    transcript = {
        "skill": "curator",
        "target_doi": TARGET_DOI,
        "target_idx": TARGET_IDX,
        "exemplar_pool": EXEMPLAR_POOL,
        "model": MODEL_ID,
        "turns": turn,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "messages": _serialize_messages(all_messages),
        "final_response": final_text,
    }
    (trace_dir / "skill1_transcript.json").write_text(json.dumps(transcript, indent=2, default=str))

    # Parse curator bundle from final response
    bundle_dict = _extract_json_from_text(final_text)
    if bundle_dict:
        (trace_dir / "skill1_bundle.json").write_text(json.dumps(bundle_dict, indent=2))
        print("  Curator bundle extracted successfully.")
    else:
        print("  WARNING: Could not extract JSON bundle from curator response.")
        bundle_dict = {
            "package_id": TARGET_PACKAGE_ID,
            "doi": TARGET_DOI,
            "curator_decision": "FLAG_FOR_REVIEW",
            "exclusion_reason": None,
            "_parse_error": "Could not extract structured bundle from response",
            "_raw_response": final_text[:500],
        }
        (trace_dir / "skill1_bundle.json").write_text(json.dumps(bundle_dict, indent=2))

    return bundle_dict


# ---------------------------------------------------------------------------
# Skill 2: Harmonizer
# ---------------------------------------------------------------------------
def run_skill2(
    client: anthropic.Anthropic,
    bundle_dict: dict,
    mapping: list[dict],
    trace_dir: Path,
) -> dict:
    """Invoke Skill 2 (harmonizer) on the curator bundle."""
    print("=== Running Skill 2 (Harmonizer) ===")

    # System prompt
    system_prompt = load_skill_prompt(SKILL2_PATH)

    # Exemplar reference code (held-out cluster removed)
    exemplar_code = load_exemplar_code(CLUSTER_1_HOLDOUT)
    exemplar_mapping = filter_mapping_for_exemplars(mapping, CLUSTER_1_HOLDOUT)

    # Build user message with all inputs
    user_msg = f"""## Harmonization Task

You have the following curator bundle for a dataset that needs harmonization.
Produce: (a) Python harmonization code and (b) a JSON mapping entry.

## Curator Bundle (Skill 1 Output)

```json
{json.dumps(bundle_dict, indent=2)}
```

## Exemplar Mapping JSON (exemplar_pool = {EXEMPLAR_POOL})
The held-out cluster (datasets {sorted(CLUSTER_1_HOLDOUT)}) has been removed.

```json
{json.dumps(exemplar_mapping, indent=2)}
```

## Exemplar Code Patterns (held-out cluster removed)

The following is the expert harmonization code for the exemplar datasets.
Use these as patterns for the code you generate.

```python
{exemplar_code}
```

## Instructions

Following your system prompt, reason through each step:
1. Identify payload files and their columns
2. Apply inclusion/exclusion rules
3. Map variables
4. Determine time series properties
5. Resolve location
6. Generate Python code block (following SECTION 6 conventions)
7. Generate JSON mapping entry (following SECTION 2 schema)

Produce the final Python code in a ```python``` block and the JSON mapping
in a ```json``` block. Dataset index for this dataset is {TARGET_IDX}.
"""

    messages = [{"role": "user", "content": user_msg}]
    all_messages = list(messages)

    turn = 0
    max_turns = 5
    final_text = ""

    while turn < max_turns:
        turn += 1
        print(f"  Harmonizer turn {turn}...")

        response = client.messages.create(
            model=MODEL_ID,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            messages=all_messages,
        )

        (trace_dir / f"skill2_turn{turn:02d}_response.json").write_text(
            json.dumps(response.model_dump(), indent=2, default=str)
        )

        text_parts = []
        for block in response.content:
            if hasattr(block, "text"):
                text_parts.append(block.text)
                final_text += block.text + "\n"

        print(f"    stop_reason={response.stop_reason}")

        all_messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            break

    # Save transcript
    transcript = {
        "skill": "harmonizer",
        "target_doi": TARGET_DOI,
        "target_idx": TARGET_IDX,
        "exemplar_pool": EXEMPLAR_POOL,
        "model": MODEL_ID,
        "turns": turn,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "messages": _serialize_messages(all_messages),
        "final_response": final_text,
    }
    (trace_dir / "skill2_transcript.json").write_text(json.dumps(transcript, indent=2, default=str))

    # Extract python code and json mapping
    python_code = _extract_code_block(final_text, "python")
    json_mapping = _extract_json_from_text(final_text)

    result = {
        "target_idx": TARGET_IDX,
        "target_doi": TARGET_DOI,
        "model": MODEL_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "python_code": python_code,
        "mapping_json": json_mapping,
        "raw_response_excerpt": final_text[:2000],
    }

    if python_code:
        (trace_dir / "skill2_harmonization_code.py").write_text(python_code)
        print("  Python harmonization code extracted.")
    else:
        print("  WARNING: Could not extract Python code block.")

    if json_mapping:
        (trace_dir / "skill2_mapping.json").write_text(json.dumps(json_mapping, indent=2))
        print("  JSON mapping extracted.")
    else:
        print("  WARNING: Could not extract JSON mapping.")

    (trace_dir / "skill2_result.json").write_text(json.dumps(result, indent=2, default=str))

    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _extract_json_from_text(text: str) -> dict | None:
    """Extract the first JSON object from a text block."""
    import re
    # Try ```json blocks first
    json_blocks = re.findall(r"```json\s*(.*?)```", text, re.DOTALL)
    for block in json_blocks:
        try:
            return json.loads(block.strip())
        except json.JSONDecodeError:
            continue
    # Try raw JSON
    start = text.find("{")
    if start >= 0:
        # Find matching closing brace
        depth = 0
        for i, ch in enumerate(text[start:], start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : i + 1])
                    except json.JSONDecodeError:
                        break
    return None


def _extract_code_block(text: str, lang: str = "python") -> str | None:
    """Extract the first code block of given language."""
    import re
    pattern = rf"```{lang}\s*(.*?)```"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None


def _serialize_messages(messages: list) -> list:
    """Serialize message list to JSON-safe format."""
    result = []
    for msg in messages:
        if isinstance(msg, dict):
            content = msg.get("content")
            if isinstance(content, list):
                serialized_content = []
                for item in content:
                    if hasattr(item, "model_dump"):
                        serialized_content.append(item.model_dump())
                    elif isinstance(item, dict):
                        serialized_content.append(item)
                    else:
                        serialized_content.append(str(item))
                result.append({"role": msg.get("role"), "content": serialized_content})
            else:
                result.append(msg)
        else:
            result.append(str(msg))
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY environment variable not set.")
        sys.exit(1)

    # Create output directory
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    trace_dir = OUT_DIR / "traces"
    trace_dir.mkdir(exist_ok=True)

    print(f"Output directory: {OUT_DIR}")
    print(f"Target: idx={TARGET_IDX}, doi={TARGET_DOI}")
    print(f"Exemplar pool: {EXEMPLAR_POOL}")
    print(f"Hold-out cluster: {sorted(CLUSTER_1_HOLDOUT)}")
    print()

    # Load mapping
    mapping = load_mapping()
    print(f"Loaded mapping with {len(mapping)} entries.")

    # Initialize client
    client = anthropic.Anthropic(api_key=api_key)

    # Run Skill 1
    t0 = time.time()
    bundle_dict = run_skill1(client, mapping, trace_dir)
    t1 = time.time()
    print(f"  Skill 1 completed in {t1-t0:.1f}s")
    print()

    # Run Skill 2 (only if included or flag for review)
    decision = bundle_dict.get("curator_decision", "INCLUDE")
    print(f"Curator decision: {decision}")

    t2 = time.time()
    skill2_result = run_skill2(client, bundle_dict, mapping, trace_dir)
    t3 = time.time()
    print(f"  Skill 2 completed in {t3-t2:.1f}s")

    # Write summary
    summary = {
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "target_idx": TARGET_IDX,
        "target_doi": TARGET_DOI,
        "target_package_id": TARGET_PACKAGE_ID,
        "exemplar_pool": EXEMPLAR_POOL,
        "holdout_cluster": sorted(CLUSTER_1_HOLDOUT),
        "model": MODEL_ID,
        "curator_decision": bundle_dict.get("curator_decision"),
        "skill1_duration_s": round(t1 - t0, 1),
        "skill2_duration_s": round(t3 - t2, 1),
        "total_duration_s": round(t3 - t0, 1),
        "skill1_bundle_path": str(trace_dir / "skill1_bundle.json"),
        "skill2_code_path": str(trace_dir / "skill2_harmonization_code.py"),
        "skill2_mapping_path": str(trace_dir / "skill2_mapping.json"),
    }
    (OUT_DIR / "run_summary.json").write_text(json.dumps(summary, indent=2))
    print()
    print("=== Run Complete ===")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
