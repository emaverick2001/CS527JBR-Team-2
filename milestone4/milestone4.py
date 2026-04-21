from __future__ import annotations
from itertools import combinations
import json
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent
GRAPH_DIR = REPO_ROOT / "milestone3" / "graphs"
GRAPHECTORY_DIR = REPO_ROOT / "milestone3" / "graphectory"
PHASE_SEQUENCE_PATH = BASE_DIR / "phase_sequence.json"
SHORTCUTS_BACKTRACKS_PATH = BASE_DIR / "shortcuts_backtracks.json"
PLAN_COMPLIANCE_PATH = BASE_DIR / "plan_compliance.json"
SHARED_STRATEGY_PATH = BASE_DIR / "shared_strategy.json"

if str(GRAPHECTORY_DIR) not in sys.path:
    sys.path.insert(0, str(GRAPHECTORY_DIR))

from lang_construction.buildPhases import (build_phase_sequence, build_phase_sequence_rle)
from lang_construction.computeLCP import PatternMiner
from lang_construction.extractSeq import extract_node_sequence


def _iter_graph_pairs():
    for graph_path in sorted(GRAPH_DIR.glob("*.json")):
        stem = graph_path.stem
        if stem.startswith("gpt-5-mini-"):
            yield "gpt-5-mini", stem.removeprefix("gpt-5-mini-")
        elif stem.startswith("deepseek-v3-"):
            yield "deepseek-v3", stem.removeprefix("deepseek-v3-")


def write_phase_sequence_json() -> dict:
    payload: dict[str, dict[str, list[str]]] = {}
    for model_name, instance_id in _iter_graph_pairs():
        payload.setdefault(model_name, {})
        payload[model_name][instance_id] = extract_phase_sequences(
            model_name, instance_id
        )

    with PHASE_SEQUENCE_PATH.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2)
    return payload


def _load_graph_json(model_name: str, instance_id: str) -> dict:
    graph_path = GRAPH_DIR / f"{model_name}-{instance_id}.json"
    if not graph_path.exists():
        raise FileNotFoundError(
            f"Missing graph JSON for model '{model_name}' and instance "
            f"'{instance_id}': {graph_path}"
        )
    with graph_path.open(encoding="utf-8") as file:
        return json.load(file)


def extract_phase_sequences(model_name: str, instance_id: str) -> list:
    graph_json = _load_graph_json(model_name, instance_id)
    step_nodes = extract_node_sequence(graph_json)
    return build_phase_sequence(step_nodes)


def shortcuts_backtracks_detection(model_name: str, instance_id: str) -> dict:
    if not PHASE_SEQUENCE_PATH.exists():
        write_phase_sequence_json()

    with PHASE_SEQUENCE_PATH.open(encoding="utf-8") as file:
        phase_data = json.load(file)

    if model_name not in phase_data or instance_id not in phase_data[model_name]:
        raise KeyError(
            f"Missing phase sequence for model '{model_name}' and instance "
            f"'{instance_id}' in {PHASE_SEQUENCE_PATH}"
        )

    sequence = phase_data[model_name][instance_id]
    result = {"shortcuts": 0, "backtracks": 0}

    for current_phase, next_phase in zip(sequence, sequence[1:]):
        if current_phase == "L" and next_phase == "V":
            result["shortcuts"] += 1
        elif (current_phase == "P" and next_phase == "L") or (
            current_phase == "V" and next_phase == "P"
        ):
            result["backtracks"] += 1

    return result


def write_shortcuts_backtracks_json() -> dict:
    phase_data = _load_phase_sequence_json()

    payload: dict[str, dict[str, dict[str, int]]] = {}
    for model_name, instances in phase_data.items():
        payload[model_name] = {}
        for instance_id in instances:
            payload[model_name][instance_id] = shortcuts_backtracks_detection(
                model_name, instance_id
            )

    with SHORTCUTS_BACKTRACKS_PATH.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2)
    return payload

def _load_phase_sequence_json() -> dict:
    if not PHASE_SEQUENCE_PATH.exists():
        write_phase_sequence_json()

    with PHASE_SEQUENCE_PATH.open(encoding="utf-8") as file:
        return json.load(file)

def _load_phase_sequence(model_name: str, instance_id: str) -> list:
    phase_data = _load_phase_sequence_json()

    if model_name not in phase_data or instance_id not in phase_data[model_name]:
        raise KeyError(
            f"Missing phase sequence for model '{model_name}' and instance "
            f"'{instance_id}' in {PHASE_SEQUENCE_PATH}"
        )

    return phase_data[model_name][instance_id]

def _load_resolution_status(model_name: str, instance_id: str) -> str:
    graph_json = _load_graph_json(model_name, instance_id)
    graph_metadata = graph_json.get("graph", {})
    status = graph_metadata.get("resolution_status", "")
    status = str(status).strip().lower()
    if status in {"resolved", "unresolved"}:
        return status
    return ""

def check_plan_compliance(model_name: str, instance_id: str) -> dict:
    sequence = _load_phase_sequence(model_name, instance_id)
    resolution_status = _load_resolution_status(model_name, instance_id)

    has_localization = "L" in sequence
    has_patch = "P" in sequence
    has_validation = "V" in sequence

    first_patch_index = sequence.index("P") if has_patch else None
    first_localization_index = sequence.index("L") if has_localization else None
    patch_before_localization = bool(
        has_patch
        and (
            first_localization_index is None
            or first_patch_index < first_localization_index
        )
    )

    submit_without_validation = bool(
        resolution_status in {"resolved", "unresolved"}
        and sequence
        and sequence[-1] == "P"
    )

    return {
        "HasLocalization": has_localization,
        "HasPatch": has_patch,
        "HasValidation": has_validation,
        "PatchBeforeLocalizationViolation": patch_before_localization,
        "SubmitWithoutValidationViolation": submit_without_validation,
    }

def write_plan_compliance_json() -> dict:
    phase_data = _load_phase_sequence_json()

    payload: dict[str, dict[str, dict[str, bool]]] = {}
    for model_name, instances in phase_data.items():
        payload[model_name] = {}
        for instance_id in instances:
            payload[model_name][instance_id] = check_plan_compliance(
                model_name, instance_id
            )

    with PLAN_COMPLIANCE_PATH.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2)
    return payload

def _contains_subsequence(sequence: list[str], pattern: tuple[str, ...]) -> bool:
    pattern_index = 0
    for phase in sequence:
        if phase == pattern[pattern_index]:
            pattern_index += 1
            if pattern_index == len(pattern):
                return True
    return False

def _longest_common_subsequence(sequences: list[list[str]]) -> list[str]:
    if not sequences:
        return []

    shortest_sequence = min(sequences, key=len)
    for subsequence_length in range(len(shortest_sequence), 0, -1):
        candidates = {
            tuple(shortest_sequence[index] for index in indices)
            for indices in combinations(range(len(shortest_sequence)), subsequence_length)
        }
        for candidate in sorted(candidates, reverse=True):
            if all(_contains_subsequence(sequence, candidate) for sequence in sequences):
                return list(candidate)

    return []

def mine_shared_strategy(model_name: str) -> list:
    # to find the longest subsequence using Pattern Miner we need to the RLE
    # to get the rle we can use build-phase_seq_rle which is under buildphases
    # but the issue is it requires the node. So this function should read all the graphs.json file that is under graphs with the model as a prefix

    sequences_rle = []

    for graph_path in sorted(GRAPH_DIR.glob(f"{model_name}-*.json")):
        instance_id = graph_path.stem.removeprefix(f"{model_name}-")
        # helper function define in task 1
        graph_data = _load_graph_json(model_name, instance_id)

        # Use the repository scripts to get the sequence and lengths
        step_nodes = extract_node_sequence(graph_data)
        phases, lens = build_phase_sequence_rle(step_nodes)
        sequences_rle.append({"seq": phases, "lens": lens})

    # now all the sequence RLE is done, we can call the PatternMiner
    # the min support is set to 1 cos we want the longest subsequence across all instances
    miner = PatternMiner(min_support=1.0)
    try:
        result = miner.longest_ranked_top1(sequences_rle)
    except ModuleNotFoundError as error:
        if error.name != "gsppy":
            raise
        return _longest_common_subsequence(
            [item["seq"] for item in sequences_rle]
        )
    # the result contains pattern, percentage, lowerbound and we are only interested in pattern
    # but the result can be None as well so
    shared_seq = list(result[0]) if result else []
    return shared_seq

def write_LCP_seq():
    models = ["gpt-5-mini", "deepseek-v3"]
    payload = {}

    # 2. Compute the strategy for each model
    for model in models:
        payload[model] = mine_shared_strategy(model)

    # 3. Write the aggregated dictionary to shared_strategy.json
    with SHARED_STRATEGY_PATH.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2)
    


if __name__ == "__main__":
    write_phase_sequence_json()
    write_shortcuts_backtracks_json()
    write_plan_compliance_json()
    write_LCP_seq()
