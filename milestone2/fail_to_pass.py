import json
import re
import matplotlib.pyplot as plt
import numpy as np

from locate_generated_tests import locate_generated_tests


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

FAILURE_KEYWORDS = ['Traceback', ' Error', 'FAILED']


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
            if 'python' not in action.lower():
                continue
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
            return
        q1, q3 = np.percentile(d, [25, 75])
        offset = 0.15
        for val in [q1, q3]:
            plt.text(positions[i] + offset, val, f'{val:.1f}',
                     ha='left', va='center', fontsize=9,
                     bbox=dict(facecolor='white', alpha=0.8,
                               edgecolor='lightgray', boxstyle='round,pad=0.2'))


def plot_violin():
    succ_counts = [count_fail_to_pass(m, i)['count'] for m, i in SUCCESSFUL_TRAJS]
    unsucc_counts = [count_fail_to_pass(m, i)['count'] for m, i in UNSUCCESSFUL_TRAJS]

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
