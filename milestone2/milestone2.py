import ast
import json
import os
import re
import shlex
from typing import Any, Dict, Iterable, List, Optional, Tuple
from thefuzz import fuzz

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))
TRAJ_ROOT = os.path.join(REPO_ROOT, "Trajectories")


GPT_INSTANCES = [
    'django__django-13109',
    'django__django-17029',
    'django__django-10880',
    'django__django-13837',
    'django__django-16661',
    'pylint-dev__pylint-7277',
    'sphinx-doc__sphinx-11510',
]

DEEPSEEK_INSTANCES = [
    'sphinx-doc__sphinx-9281',
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
    'sympy__sympy-24443',
]

SUCCESSFUL_TRAJS = [
    ('gpt-5-mini', 'django__django-13109'),
    ('gpt-5-mini', 'django__django-17029'),
    ('deepseek-v3', 'sphinx-doc__sphinx-9281'),
    ('deepseek-v3', 'sympy__sympy-14531'),
    ('deepseek-v3', 'sympy__sympy-24539'),
]

UNSUCCESSFUL_TRAJS = [
    ('deepseek-v3', 'astropy__astropy-13033'),
    ('deepseek-v3', 'django__django-11138'),
    ('deepseek-v3', 'django__django-11141'),
    ('deepseek-v3', 'django__django-11211'),
    ('deepseek-v3', 'django__django-12308'),
    ('deepseek-v3', 'django__django-14351'),
    ('deepseek-v3', 'django__django-15268'),
    ('deepseek-v3', 'pydata__xarray-4695'),
    ('deepseek-v3', 'pylint-dev__pylint-7277'),
    ('deepseek-v3', 'sympy__sympy-24443'),
    ('gpt-5-mini', 'django__django-10880'),
    ('gpt-5-mini', 'django__django-13837'),
    ('gpt-5-mini', 'django__django-16661'),
    ('gpt-5-mini', 'pylint-dev__pylint-7277'),
    ('gpt-5-mini', 'sphinx-doc__sphinx-11510'),
]

FAILURE_KEYWORDS = ['Traceback', ' Error', 'FAILED', 'here-document']


_STRONG_PATH_RE = re.compile(
    r"(^|/)(tests?|testing)(/|$)|(^|/)[^/]*(repro|reproduce|validate|regression|debug)[^/]*\.\w+$",
    re.IGNORECASE,
)
_WEAK_PATH_RE = re.compile(
    r"(^|/)(test_[^/]+\.\w+|[^/]+_test[^/]*\.\w+|[^/]*test[^/]*\.\w+)$",
    re.IGNORECASE,
)
_THOUGHT_RE = re.compile(
    r"\b(test(?:ing)?|repro(?:duce|duction)?|validate|validation|regression|debug|verify|pytest|unittest|unit test)\b",
    re.IGNORECASE,
)
_CODE_SIGNAL_RES = [
    re.compile(r"^\s*def\s+test_", re.MULTILINE),
    re.compile(r"\bpytest\b", re.IGNORECASE),
    re.compile(r"\bunittest\b", re.IGNORECASE),
    re.compile(r"\bTestCase\b"),
    re.compile(r"call_command\(\s*['\"]test['\"]"),
    re.compile(r"::test_[A-Za-z0-9_]+"),
]
_PYTEST_TARGET_RE = re.compile(
    r"::(?:(?P<class>[A-Z][A-Za-z0-9_]*)::)?(?P<method>test_[A-Za-z0-9_]+)"
)
_HEREDOC_RES = [
    re.compile(
        r"cat\s+<<-?\s*\\?['\"]?(?P<delim>[A-Za-z0-9_]+)['\"]?\s*>\s*(?P<path>\S+)\n"
        r"(?P<body>.*?)(?:\n(?P=delim)['\"]?)(?=\n|$)",
        re.DOTALL,
    ),
    re.compile(
        r"cat\s*>\s*(?P<path>\S+)\s*<<-?\s*\\?['\"]?(?P<delim>[A-Za-z0-9_]+)['\"]?\n"
        r"(?P<body>.*?)(?:\n(?P=delim)['\"]?)(?=\n|$)",
        re.DOTALL,
    ),
]
_REDIRECT_RE = re.compile(
    r"(?P<cmd>echo|printf)\s+(?:-(?:e|n)\s+)?(?P<quote>['\"])(?P<body>.*?)(?P=quote)\s*>\s*(?P<path>\S+)",
    re.DOTALL,
)


def _trajectory_path(model_name: str, instance_id: str) -> str:
    return os.path.join(TRAJ_ROOT, model_name, f"{instance_id}.traj")


def count_tool_use(model_name: str, instance_id: str) -> dict:
    tools_to_search = ["view", "create", "str_replace", "insert", "undo_edit"]
    with open(_trajectory_path(model_name, instance_id), 'r') as f:
        trajectory = json.load(f)

    trajectory_steps = trajectory['trajectory']
    tool_use_count = {tool: 0 for tool in tools_to_search}
    pattern_string = r"str_replace_editor\s+(" + \
        "|".join(map(re.escape, tools_to_search)) + r")"
    for step in range(len(trajectory_steps)):
        actions = trajectory_steps[step]['action']
        matches = re.findall(pattern_string, actions)
        for match in matches:
            tool_use_count[match] += 1

    return tool_use_count


def locate_navigation(model_name: str, instance_id: str) -> list:
    with open(_trajectory_path(model_name, instance_id), 'r') as f:
        traj = json.load(f)

    nav_commands = {
        "find_file", "search_file", "search_dir",
        "ls", "cat", "pwd", "find", "grep", "cd", "sed",
    }
    steps = []

    trajectory = traj.get("trajectory", [])
    for idx, step in enumerate(trajectory, start=1):
        action = step.get("action")
        if not action:
            continue
        parts = action.split()
        if not parts:
            continue
        cmd = parts[0]
        if cmd == "str_replace_editor":
            if len(parts) > 1 and parts[1] == "view":
                steps.append(idx)
            continue
        if cmd in nav_commands:
            steps.append(idx)
    return steps


def _strip_testbed_prefix(path: str) -> str:
    return path[8:] if path.startswith("/testbed/") else path


def _path_signal(path: str) -> str:
    cleaned = _strip_testbed_prefix(path or "")
    if _STRONG_PATH_RE.search(cleaned):
        return "strong"
    if _WEAK_PATH_RE.search(cleaned):
        return "weak"
    return ""


def _text_has_test_context(text: str) -> bool:
    if not text:
        return False
    cleaned = re.sub(r"/testbed[^\s]*", " ", text)
    return bool(_THOUGHT_RE.search(cleaned))


def _extract_target_names(text: str) -> Tuple[str, str]:
    if not text:
        return "", ""

    match = _PYTEST_TARGET_RE.search(text)
    if match:
        return match.group("method") or "", match.group("class") or ""

    for dotted_target in re.findall(r"\b(?:[A-Za-z_]\w*\.)+test_[A-Za-z0-9_]+\b", text):
        parts = dotted_target.split(".")
        method_name = parts[-1]
        class_name = parts[-2] if len(
            parts) >= 2 and parts[-2][:1].isupper() else ""
        return method_name, class_name

    return "", ""


def _code_has_test_signal(code: str) -> bool:
    if not code:
        return False
    if any(pattern.search(code) for pattern in _CODE_SIGNAL_RES):
        return True
    method_name, _ = _extract_target_names(code)
    return bool(method_name)


def _is_generated_test(path: str, code: str, context: str) -> bool:
    signal = _path_signal(path)
    if signal == "strong":
        return True
    if signal == "weak" and (_text_has_test_context(context) or _code_has_test_signal(code)):
        return True
    return _code_has_test_signal(code)


def _unwrap_shell_script(action: str) -> str:
    script = action.strip()
    prefixes = [
        "bash -lc ",
        "bash -c ",
        "sh -lc ",
        "sh -c ",
        "zsh -lc ",
        "zsh -c ",
    ]

    while script:
        matched_prefix = next(
            (prefix for prefix in prefixes if script.startswith(prefix)), "")
        if not matched_prefix:
            return script

        script = script[len(matched_prefix):].strip()
        if len(script) >= 2 and script[0] == script[-1] and script[0] in {"'", '"'}:
            script = script[1:-1]
            continue
        return script

    return action


def _extract_shell_writes(action: str) -> Iterable[Tuple[str, str]]:
    script = _unwrap_shell_script(action)

    for pattern in _HEREDOC_RES:
        for match in pattern.finditer(script):
            yield match.group("path"), match.group("body")

    for match in _REDIRECT_RE.finditer(script):
        yield match.group("path"), match.group("body")


def _parse_editor_action(action: str) -> Optional[Tuple[str, str, Dict[str, Any]]]:
    if not action.startswith("str_replace_editor"):
        return None

    try:
        tokens = shlex.split(action)
    except Exception:
        tokens = []

    if len(tokens) >= 2 and tokens[0] == "str_replace_editor":
        args: Dict[str, Any] = {}
        path = tokens[2] if len(tokens) > 2 else ""
        index = 3
        while index < len(tokens):
            token = tokens[index]
            if token.startswith("--"):
                args[token[2:]] = tokens[index + 1] if index + \
                    1 < len(tokens) else ""
                index += 2
            else:
                index += 1
        return tokens[1], path, args

    if "\n" not in action:
        return None

    header, body = action.split("\n", 1)
    parts = header.split()
    if len(parts) < 2:
        return None

    try:
        payload = json.loads(body.strip())
    except Exception:
        return None

    if not isinstance(payload, dict):
        return None

    return parts[1], payload.get("path", ""), payload


def _extract_editor_text(subcmd: str, args: Dict[str, Any]) -> str:
    if subcmd == "create":
        return args.get("file_text") or args.get("content") or args.get("text") or ""
    if subcmd == "insert":
        return args.get("insert_text") or args.get("text") or args.get("new_str") or ""
    if subcmd == "str_replace":
        return args.get("new_str") or args.get("replacement") or ""
    return ""


def _editor_write_succeeded(subcmd: str, observation: str) -> bool:
    if subcmd == "create":
        return "Cannot overwrite files" not in observation and "File already exists at:" not in observation
    if "No replacement was performed" in observation or "did not appear verbatim" in observation:
        return False
    return True


def _full_file_from_observation(observation: str) -> Optional[str]:
    if "Here's the result of running `cat -n` on " not in observation:
        return None
    if "on a snippet of" in observation:
        return None

    lines = observation.splitlines()
    content: List[str] = []
    for line in lines[1:]:
        if "\t" not in line:
            continue
        _, text = line.split("\t", 1)
        content.append(text)
    return "\n".join(content)


def _apply_editor_write(
    path: str,
    subcmd: str,
    args: Dict[str, Any],
    observation: str,
    file_state: Dict[str, str],
) -> Tuple[str, bool]:
    current = file_state.get(path, "")
    observed = _full_file_from_observation(observation)
    snippet = _extract_editor_text(subcmd, args)

    if subcmd == "create":
        return snippet, True

    if subcmd == "insert":
        if current:
            separator = "" if current.endswith("\n") or not snippet else "\n"
            return current + separator + snippet, True
        if observed is not None:
            return observed, True
        return snippet, False

    if subcmd == "str_replace":
        old_text = args.get("old_str", "")
        if current and old_text and old_text in current:
            return current.replace(old_text, snippet, 1), True
        if observed is not None:
            return observed, True
        return (current or snippet), False

    return current, False


def _is_test_class(node: ast.ClassDef) -> bool:
    if node.name.startswith("Test") or node.name.endswith("Tests"):
        return True
    for base in node.bases:
        if isinstance(base, ast.Name) and base.id.endswith("TestCase"):
            return True
        if isinstance(base, ast.Attribute) and base.attr.endswith("TestCase"):
            return True
    return False


def _extract_names_from_ast(path: str, code: str) -> Tuple[str, str]:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return "", ""

    script_function_names: List[str] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("test_"):
                return node.name, ""
            if node.name.startswith(("repro", "reproduce", "validate", "debug", "main", "run")):
                script_function_names.append(node.name)
        if isinstance(node, ast.ClassDef):
            test_methods = [
                child.name
                for child in node.body
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name.startswith("test_")
            ]
            if test_methods and _is_test_class(node):
                return test_methods[0], node.name
            if _is_test_class(node):
                return "", node.name

    if _path_signal(path) == "strong" and script_function_names:
        return script_function_names[0], ""

    return "", ""


def _extract_names(path: str, code: str) -> Tuple[str, str]:
    method_name, class_name = _extract_target_names(code)
    if method_name or class_name:
        return method_name, class_name
    return _extract_names_from_ast(path, code)


def _update_record(
    records: Dict[str, Dict[str, Any]],
    path: str,
    step: int,
    code: str,
    full_snapshot: bool,
) -> None:
    method_name, class_name = _extract_names(path, code)
    record = records.get(path)
    if record is None:
        records[path] = {
            "path": path,
            "step": step,
            "steps": [step],
            "code": code,
            "method_name": method_name,
            "test_class_name": class_name,
        }
        return

    if step not in record["steps"]:
        record["steps"].append(step)
    if step < record["step"]:
        record["step"] = step

    if code and (full_snapshot or not record["code"] or len(code) >= len(record["code"])):
        record["code"] = code

    if method_name:
        record["method_name"] = method_name
    if class_name:
        record["test_class_name"] = class_name


def locate_generated_tests(model_name: str, instance_id: str) -> list:
    with open(_trajectory_path(model_name, instance_id), "r") as handle:
        traj = json.load(handle)

    file_state: Dict[str, str] = {}
    records: Dict[str, Dict[str, Any]] = {}

    for index, step in enumerate(traj.get("trajectory", []), start=1):
        action = step.get("action") or ""
        observation = step.get("observation") or ""
        context = "\n".join(
            filter(None, [step.get("thought"), step.get("response")]))

        parsed = _parse_editor_action(action)
        if parsed and parsed[0] == "view":
            view_text = _full_file_from_observation(observation)
            if parsed[1] and view_text is not None:
                file_state[parsed[1]] = view_text
            continue

        events: List[Tuple[str, str, str, bool]] = []

        if parsed and parsed[0] in {"create", "insert", "str_replace"}:
            subcmd, path, args = parsed
            if _editor_write_succeeded(subcmd, observation):
                updated_code, is_full_snapshot = _apply_editor_write(
                    path, subcmd, args, observation, file_state)
                file_state[path] = updated_code
                events.append((path, updated_code, updated_code or _extract_editor_text(
                    subcmd, args), is_full_snapshot))

        for path, code in _extract_shell_writes(action):
            file_state[path] = code
            events.append((path, code, code, True))

        for path, snapshot, evidence, is_full_snapshot in events:
            if path not in records and not _is_generated_test(path, evidence or snapshot, context):
                continue
            _update_record(records, path, index, snapshot, is_full_snapshot)

    output = list(records.values())
    for record in output:
        record["steps"].sort()
    output.sort(key=lambda item: (item["step"], item["path"]))
    return output


def _is_failure(observation: str) -> bool:
    return any(kw.lower() in observation.lower() for kw in FAILURE_KEYWORDS)


def count_fail_to_pass(model_name: str, instance_id: str) -> dict:
    with open(f'../Trajectories/{model_name}/{instance_id}.traj', 'r') as f:
        trajectory = json.load(f)

    # read in the json generated from step 3
    steps = trajectory['trajectory']
    total_steps = len(steps)
    generated_tests = locate_generated_tests(model_name, instance_id)
    # each entry in the list of dict is 1 test generated
    # the step will give us the step where the test was first generated
    # check for the precense of python <test path> if the action contain this
    # check for the observation see if it has error keywords
    # this will trigger the first flag, then keep going and identify the step contains python testpath,
    # if no Error keyword then test is passed, can cross check by checking the next step thought

    # take note we need to subtract -1 from the generated_test step

    fail_to_pass_tests = []
    for test in generated_tests:
        test_path = test['path']
        create_step = test['step']  # 1-indexed

        first_failure_seen = False
        for step in range(create_step-1, total_steps):
            # there can be different version of python and the agent can cd before running the script so just check if the filename and python appear
            file_name = test_path.split('/')[-1]
            python_regex = r'python\d*(?:\.\d+)*'
            pattern = rf'{python_regex}\s+(?:{test_path}|{file_name})'
            matches = re.findall(pattern, steps[step]['action'])
            if matches:
                # when we run the code sometime we get output that is not an error so we need to check if it is a expected output or not in the thought of the next step
                if _is_failure(steps[step]['observation']):
                    # is this the first time we are seeing this failure
                    if not first_failure_seen:
                        first_failure_seen = True

                    else:
                        score = fuzz.partial_ratio(
                            steps[step+1]['thought'].lower(), 'verified the fix')
                        score2 = fuzz.partial_ratio(
                            steps[step+1]['thought'].lower(), 'produces the expected outcome')
                        if score > 70 or score2 > 70:
                            fail_to_pass_tests.append({
                                'path': test_path,
                                'code': test['code'],
                            })

                # sometimes the output does not contain any error but this is not the expected outcome
                elif fuzz.partial_ratio(steps[step+1]['thought'].lower(), "did not produce expected outcome") > 70:
                    # the test script did not produce the expected outcome so considered a failed test
                    if not first_failure_seen:
                        first_failure_seen = True

                else:
                    # check if it encountered an error before
                    # or the thought in the next step says that this is the error that we expected
                    if first_failure_seen:
                        fail_to_pass_tests.append({
                            'path': test_path,
                            'code': test['code'],
                        })
                    break

    return {'tests': fail_to_pass_tests, 'count': len(fail_to_pass_tests)}


def _add_offset_annotations(data, positions):
    import matplotlib.pyplot as plt
    import numpy as np

    for i, d in enumerate(data):
        if len(d) < 2:
            continue
        q1, q3 = np.percentile(d, [25, 75])
        offset = 0.15
        for val in [q1, q3]:
            plt.text(positions[i] + offset, val, f'{val:.1f}',
                     ha='left', va='center', fontsize=9,
                     bbox=dict(facecolor='white', alpha=0.8,
                               edgecolor='lightgray', boxstyle='round,pad=0.2'))


def plot_violin():
    import matplotlib.pyplot as plt

    succ_counts = []
    unsucc_counts = []

    for model, instance in SUCCESSFUL_TRAJS:
        result = count_fail_to_pass(model, instance)
        succ_counts.append(result['count'])

    for model, instance in UNSUCCESSFUL_TRAJS:
        result = count_fail_to_pass(model, instance)
        unsucc_counts.append(result['count'])

    if len(succ_counts) < 2:
        succ_counts = succ_counts + [0] * (2 - len(succ_counts))
    if len(unsucc_counts) < 2:
        unsucc_counts = unsucc_counts + [0] * (2 - len(unsucc_counts))

    parts = plt.violinplot(
        [succ_counts, unsucc_counts],
        showextrema=False,
        quantiles=[[0.25, 0.75]] * 2
    )

    if 'cquantiles' in parts:
        parts['cquantiles'].set_linestyle('--')
        parts['cquantiles'].set_edgecolor('black')

    _add_offset_annotations([succ_counts, unsucc_counts], [1, 2])

    plt.xticks([1, 2], ['Success', 'Failure'])
    plt.ylabel('Fail-to-Pass Count')
    plt.title('Distribution of Fail-to-Pass Tests')
    plt.savefig('fail_to_pass.jpeg')
    plt.close()


def write_all_json():
    locate_tests_data = {}
    fail_to_pass_data = {}
    tool_use_data = {}
    locate_nav_data = {}

    all_trajectories = [('gpt-5-mini', inst) for inst in GPT_INSTANCES] + \
                       [('deepseek-v3', inst) for inst in DEEPSEEK_INSTANCES]

    for model, instance in all_trajectories:
        if model not in locate_tests_data:
            locate_tests_data[model] = {}
        if model not in fail_to_pass_data:
            fail_to_pass_data[model] = {}
        if model not in tool_use_data:
            tool_use_data[model] = {}
        if model not in locate_nav_data:
            locate_nav_data[model] = {}

        locate_tests_data[model][instance] = locate_generated_tests(
            model, instance)
        fail_to_pass_data[model][instance] = count_fail_to_pass(
            model, instance)

        tool_use_data[model][instance] = count_tool_use(model, instance)
        locate_nav_data[model][instance] = locate_navigation(model, instance)

    with open('locate_generated_tests.json', 'w') as f:
        json.dump(locate_tests_data, f, indent=4)

    with open('fail_to_pass.json', 'w') as f:
        json.dump(fail_to_pass_data, f, indent=4)

    with open('count_tool_use.json', 'w') as f:
        json.dump(tool_use_data, f, indent=4)

    with open('locate_navigation.json', 'w') as f:
        json.dump(locate_nav_data, f, indent=4)


if __name__ == "__main__":
    write_all_json()
    plot_violin()
