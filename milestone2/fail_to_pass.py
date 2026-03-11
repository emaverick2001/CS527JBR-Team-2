import json
import re
import matplotlib.pyplot as plt
import numpy as np
from thefuzz import fuzz

from milestone2 import locate_generated_tests


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
        later_pass_seen = False
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
                            print('ge', step)
                            fail_to_pass_tests.append({
                                'path': test_path,
                                'code': test['code'],
                            })

                # sometimes the output does not contain any error but this is not the expected outcome
                elif fuzz.partial_ratio(steps[step+1]['thought'].lower(), "did not produce expected outcome") > 70:
                    # the test script did not produce the expected outcome so considered a failed test
                    print(step)
                    if not first_failure_seen:
                        first_failure_seen = True

                else:
                    # check if it encountered an error before
                    # or the thought in the next step says that this is the error that we expected
                    print(step)
                    if first_failure_seen:
                        fail_to_pass_tests.append({
                            'path': test_path,
                            'code': test['code'],
                        })
                    break

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
    succ_counts = [count_fail_to_pass(m, i)['count']
                   for m, i in SUCCESSFUL_TRAJS]
    unsucc_counts = [count_fail_to_pass(m, i)['count']
                     for m, i in UNSUCCESSFUL_TRAJS]

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


# if __name__ == "__main__":
    # # the trajectories to find steps for
    # gpt_instances = ['django__django-13109',
    #                  'django__django-17029',
    #                  'django__django-10880',
    #                  'django__django-13837',
    #                  'django__django-16661',
    #                  'pylint-dev__pylint-7277',
    #                  'sphinx-doc__sphinx-11510']

    # deepseek_instances = ['sphinx-doc__sphinx-9281',
    #                       'sympy__sympy-14531',
    #                       'sympy__sympy-24539',
    #                       'astropy__astropy-13033',
    #                       'django__django-11138',
    #                       'django__django-11141',
    #                       'django__django-11211',
    #                       'django__django-12308',
    #                       'django__django-14351',
    #                       'django__django-15268',
    #                       'pydata__xarray-4695',
    #                       'pylint-dev__pylint-7277',
    #                       'sympy__sympy-24443']
    # gpt_steps = {}
    # deepseek_steps = {}
    # data = {}
    # for instance in gpt_instances:
    #     gpt_steps[instance] = count_fail_to_pass("gpt-5-mini", instance)
    # for instance in deepseek_instances:
    #     deepseek_steps[instance] = count_fail_to_pass("deepseek-v3", instance)

    # data['gpt-5-mini'] = gpt_steps
    # data['deepseek-v3'] = deepseek_steps

    # with open("thought_entity_relevance.json", "w") as f:
    #     json.dump(data, f, indent=4)

    # plot_violin()

    # print(count_fail_to_pass('deepseek-v3', 'pydata__xarray-4695'))
