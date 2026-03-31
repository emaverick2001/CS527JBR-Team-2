import json
from pathlib import Path

import pandas as pd
import sys


REPO_ROOT = Path(__file__).resolve().parent.parent
GRAPHS_DIR = REPO_ROOT / "milestone3" / "graphs"
GRAPH_METRICS_PATH = REPO_ROOT / "milestone3" / "graph_metrics.json"
GRAPHECTORY_DIR = REPO_ROOT / "graphectory"

if str(GRAPHECTORY_DIR) not in sys.path:
    sys.path.insert(0, str(GRAPHECTORY_DIR))

from graph_analysis.analyzer import TrajectoryGraphAnalyzer


def _analysis_csv_path(model_name: str) -> Path:
    """
    Resolve the model-level analysis CSV.
    """
    candidate_paths = [
        REPO_ROOT / "analysis" / "SWE-agent" / "analysis" / model_name / "trajectory_metrics.csv",
        REPO_ROOT / "graphectory" / "data" / "SWE-agent" / "analysis" / model_name / "trajectory_metrics.csv",
    ]

    for candidate_path in candidate_paths:
        if candidate_path.exists():
            return candidate_path

    raise FileNotFoundError(
        f"Could not find trajectory_metrics.csv for model '{model_name}'. "
        f"Checked: {candidate_paths}"
    )


def _instance_metrics_row(model_name: str, instance_id: str) -> pd.Series:
    """Read the model CSV and return the single row for the requested instance."""
    file_name = _analysis_csv_path(model_name)
    graph_metrics = pd.read_csv(file_name)
    instance_rows = graph_metrics.query('instance == @instance_id')

    if instance_rows.empty:
        raise KeyError(f"Instance '{instance_id}' was not found in {file_name}")

    return instance_rows.iloc[0]


def _graph_json_path(model_name: str, instance_id: str) -> Path:
    """Resolve the generated graph JSON for one model/instance pair."""
    graph_path = GRAPHS_DIR / model_name / instance_id / f"{instance_id}.json"
    if not graph_path.exists():
        raise FileNotFoundError(f"Graph JSON does not exist for '{model_name}/{instance_id}': {graph_path}")
    return graph_path


def _structural_breadth(model_name: str, instance_id: str) -> int:
    """
    Paper definition of Structural Breadth (SB):
    maximum out-degree over structural edges.
    """
    graph_data = json.loads(_graph_json_path(model_name, instance_id).read_text())
    analyzer = TrajectoryGraphAnalyzer(graph_data)
    hier_graph = analyzer.get_hier_graph()
    return max((degree for _, degree in hier_graph.out_degree()), default=0)


def _load_graph_metrics_json() -> dict:
    """Load the consolidated graph metrics JSON if it already exists."""
    if not GRAPH_METRICS_PATH.exists():
        return {}

    with GRAPH_METRICS_PATH.open() as json_file:
        return json.load(json_file)


def _write_graph_metrics_json(payload: dict) -> None:
    """Persist the consolidated graph metrics JSON."""
    with GRAPH_METRICS_PATH.open("w") as json_file:
        json.dump(payload, json_file, indent=2)


def _normalize_number(value):
    """Convert pandas numeric values to plain Python ints/floats."""
    numeric_value = float(value)
    if numeric_value.is_integer():
        return int(numeric_value)
    return numeric_value


def collect_graph_metrics(model_name: str, instance_id: str) -> dict:
    """
    Args:
        model_name (str): gpt-5-mini or deepseek-v3
        instance_id (str): trajectory

    Computes and records the following metrics for a generated graph:
    Node Count, Temporal Edge Count, Loop Count, Average Loop Length,
    Structural Edge Count, and Structural Breadth.

    Returns:
        dict: JSON file containing each model and instance id
        with the required graph metrics.
    """
    row = _instance_metrics_row(model_name, instance_id)

    instance_metrics = {
        "NodeCount": _normalize_number(row["node_count"]),
        "TempEdgeCount": _normalize_number(row["exec_edge_count"]),
        "LoopCount": _normalize_number(row["loop_count"]),
        "AvgLoopLength": _normalize_number(row["avg_loop_length"]),
        "StructuralEdgeCount": _normalize_number(row["hier_edge_count"]),
        "StructuralBreadth": _structural_breadth(model_name, instance_id),
    }

    graph_metrics_json = _load_graph_metrics_json()
    graph_metrics_json.setdefault(model_name, {})
    graph_metrics_json[model_name][instance_id] = instance_metrics
    _write_graph_metrics_json(graph_metrics_json)
    return graph_metrics_json


def detect_inefficiency_patterns(model_name, instance_id):
    # model : instance {status, }
    # metric can be obtained from csv
    # iterate through the dataframe
    # read in the dataframe based on the model name
    # iloc the instance ID
    # the assumption is analysis file is stored in analysis/swe-agent/analysis
    inefficent_pattern = {}
    file_name = f'analysis/SWE-agent/analysis/{model_name}/trajectory_metrics.csv'
    graph_metrics = pd.read_csv(file_name)
    status = graph_metrics.query(
        f'instance == "{instance_id}"').iloc[0]['resolution']
    inefficent_pattern['Status'] = status

    anti_patterns = ['repeat_failed_edit',
                     'flip_flop',
                     'scroll_behavior',
                     'back_and_forth_switch',
                     'zoom_out',
                     'abandonment']
    patterns_present = []
    for pattern in anti_patterns:
        is_pattern_present = graph_metrics.query(
            f'instance == "{instance_id}"').iloc[0][pattern]
        if is_pattern_present:
            patterns_present.append(pattern)
    inefficent_pattern['Patterns'] = patterns_present
    return inefficent_pattern
    

if __name__ == "__main__":
    # the trajectories to find steps for
    gpt_instances = ['django__django-13109',
                     'django__django-17029',
                     'django__django-10880',
                     'django__django-13837',
                     'django__django-16661',
                     'pylint-dev__pylint-7277',
                     'sphinx-doc__sphinx-11510']

    deepseek_instances = ['sphinx-doc__sphinx-9281',
                          'sympy__sympy-14531',
                          'sympy__sympy-24539',
                          'astropy__astropy-13033',
                          'django__django-11138',
                          'django__django-11141',
                          'django__django-11211',
                          'django__django-12308',
                          'django__django-14351',
                          'django__django-15268',
                          'pydata__xarray-4695',
                          'pylint-dev__pylint-7277',
                          'sympy__sympy-24443']
    data = {
        "gpt-5-mini": {},
        "deepseek-v3": {},
    }
    for instance in gpt_instances:
        data["gpt-5-mini"][instance] = collect_graph_metrics(
            "gpt-5-mini", instance
        )["gpt-5-mini"][instance]
    for instance in deepseek_instances:
        data["deepseek-v3"][instance] = collect_graph_metrics(
            "deepseek-v3", instance
        )["deepseek-v3"][instance]

    with GRAPH_METRICS_PATH.open("w") as json_file:
        json.dump(data, json_file, indent=2)
