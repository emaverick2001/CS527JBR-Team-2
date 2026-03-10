import re
import json
import matplotlib.pyplot as plt
import numpy as np


# Instance lists
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

# Successful trajectories (from milestone1 classification)
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

# Keywords that indicate a test/reproduce file
TEST_KEYWORDS = ['test', 'reproduce', 'debug', 'validate', 'fix']

# Keywords that indicate failure in observation
FAILURE_KEYWORDS = ['Traceback', ' Error', 'FAILED']


def count_tool_use(model_name: str, instance_id: str) -> dict:
    tools_to_search = ["view", "create", "str_replace", "insert", "undo_edit"]
    with open(f'../Trajectories/{model_name}/{instance_id}.traj', 'r') as f:
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
    file_name = f"../Trajectories/{model_name}/{instance_id}.traj"
    with open(file_name, 'r') as f:
        traj_data = f.read()

    nav_commands = {
        "find_file", "search_file", "search_dir",
        "ls", "cat", "pwd", "find", "grep", "cd", "sed",
    }
    steps = []

    traj = json.loads(traj_data)
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


def locate_generated_tests(model_name: str, instance_id: str) -> list:
    with open(f'../Trajectories/{model_name}/{instance_id}.traj', 'r') as f:
        trajectory = json.load(f)

    steps = trajectory.get('trajectory', [])
    results = []

    # Regex: str_replace_editor create <path> --file_text <content>
    create_pattern = re.compile(
        r'str_replace_editor\s+create\s+(\S+)\s+--file_text\s+(.+)',
        re.DOTALL
    )

    for idx, step in enumerate(steps, start=1):
        action = step.get('action', '')
        match = create_pattern.search(action)
        if not match:
            continue

        path = match.group(1)
        filename = path.split('/')[-1].lower()

        # Filter: filename must contain a test-related keyword
        if not any(kw in filename for kw in TEST_KEYWORDS):
            continue

        raw_code = match.group(2)
        # Strip surrounding quotes if present
        code = raw_code.strip()
        if (code.startswith("'") and code.endswith("'")) or \
           (code.startswith('"') and code.endswith('"')):
            code = code[1:-1]
        # Remove trailing flags appended after --file_text content
        # (e.g., " --view_range  --old_str '' --new_str '' --insert_line 0")
        trailing = re.search(r"\s+--(?:view_range|old_str|new_str|insert_line)\b", code)
        if trailing:
            code = code[:trailing.start()]

        method_name = None
        test_class_name = None
        method_match = re.search(r'def\s+(test_\w+)', code)
        if method_match:
            method_name = method_match.group(1)
        class_match = re.search(r'class\s+(\w+)', code)
        if class_match:
            test_class_name = class_match.group(1)

        results.append({
            'path': path,
            'step': idx,
            'code': code,
            'method_name': method_name,
            'test_class_name': test_class_name,
        })

    return results


def _is_failure(observation: str) -> bool:
    return any(kw in observation for kw in FAILURE_KEYWORDS)


def count_fail_to_pass(model_name: str, instance_id: str) -> dict:
    with open(f'../Trajectories/{model_name}/{instance_id}.traj', 'r') as f:
        trajectory = json.load(f)

    steps = trajectory.get('trajectory', [])
    generated_tests = locate_generated_tests(model_name, instance_id)
    fail_to_pass_tests = []

    for test in generated_tests:
        test_path = test['path']
        create_step = test['step']  # 1-indexed

        first_failure_seen = False
        later_pass_seen = False

        for idx, step in enumerate(steps, start=1):
            if idx <= create_step:
                continue
            action = step.get('action', '')
            observation = step.get('observation', '')
            # Check if this step runs the test file with python
            if 'python' not in action.lower():
                continue
            # Check if the test path (or its basename) appears in the action
            basename = test_path.split('/')[-1]
            if test_path not in action and basename not in action:
                continue

            if not first_failure_seen:
                if _is_failure(observation):
                    first_failure_seen = True
            else:
                if not _is_failure(observation):
                    later_pass_seen = True
                    break

        if first_failure_seen and later_pass_seen:
            fail_to_pass_tests.append({
                'path': test_path,
                'code': test['code'],
            })

    return {'tests': fail_to_pass_tests, 'count': len(fail_to_pass_tests)}


def _add_offset_annotations(data, positions):
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
    succ_counts = []
    unsucc_counts = []

    for model, instance in SUCCESSFUL_TRAJS:
        result = count_fail_to_pass(model, instance)
        succ_counts.append(result['count'])

    for model, instance in UNSUCCESSFUL_TRAJS:
        result = count_fail_to_pass(model, instance)
        unsucc_counts.append(result['count'])

    # Violin plots require >= 2 data points; pad with zeros if needed
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

    all_trajectories = [('gpt-5-mini', inst) for inst in GPT_INSTANCES] + \
                       [('deepseek-v3', inst) for inst in DEEPSEEK_INSTANCES]

    for model, instance in all_trajectories:
        if model not in locate_tests_data:
            locate_tests_data[model] = {}
        if model not in fail_to_pass_data:
            fail_to_pass_data[model] = {}

        locate_tests_data[model][instance] = locate_generated_tests(model, instance)
        fail_to_pass_data[model][instance] = count_fail_to_pass(model, instance)

    with open('locate_generated_tests.json', 'w') as f:
        json.dump(locate_tests_data, f, indent=4)

    with open('fail_to_pass.json', 'w') as f:
        json.dump(fail_to_pass_data, f, indent=4)


if __name__ == "__main__":
    write_all_json()
    plot_violin()
