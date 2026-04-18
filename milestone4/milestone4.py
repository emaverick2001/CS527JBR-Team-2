from __future__ import annotations

import json
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent
GRAPH_DIR = REPO_ROOT / "milestone3" / "graphs"
GRAPHECTORY_DIR = REPO_ROOT / "graphectory"
PHASE_SEQUENCE_PATH = BASE_DIR / "phase_sequence.json"
SHORTCUTS_BACKTRACKS_PATH = BASE_DIR / "shortcuts_backtracks.json"

if str(GRAPHECTORY_DIR) not in sys.path:
    sys.path.insert(0, str(GRAPHECTORY_DIR))

from lang_construction.buildPhases import build_phase_sequence
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
    if not PHASE_SEQUENCE_PATH.exists():
        write_phase_sequence_json()

    with PHASE_SEQUENCE_PATH.open(encoding="utf-8") as file:
        phase_data = json.load(file)

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

def check_plan_compliance(model_name: str, instance_id: str) -> dict:
    pass

def mine_shared_strategy(model_name: str) -> list:
    pass


if __name__ == "__main__":
    write_phase_sequence_json()
    write_shortcuts_backtracks_json()
