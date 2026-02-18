import re
import json
import matplotlib.pyplot as plt
import numpy as np


def count_steps(model_name: str, instance_id: str) -> int:
    """
    Extracts the number of steps taken by the agent from the trajectory file corresponding to the given model name and instance ID.

    :param model_name: deepseek-v3 or gpt-5-mini
    :param instance_id: ID of the instance for which to count the steps
    :return: Number of steps taken by the agent
    """
    # first read the trajectory file based on model_name and instance_id
    file_name = f"Trajectories/{model_name}/{instance_id}.traj"
    with open(file_name, 'r') as f:
        traj_data = f.read()

    num_steps = re.search(r'"api_calls":\s*(\d+)', traj_data)
    if num_steps:
        return int(num_steps.group(1))
    else:
        raise ValueError(
            f"Could not find the number of steps in the trajectory file for instance {instance_id} and model {model_name}.")


def write_to_json():
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
    gpt_steps = {}
    deepseek_steps = {}
    data = {}
    for instance in gpt_instances:
        gpt_steps[instance] = count_steps("gpt-5-mini", instance)
    for instance in deepseek_instances:
        deepseek_steps[instance] = count_steps("deepseek-v3", instance)

    data['gpt-5-mini'] = gpt_steps
    data['deepseek-v3'] = deepseek_steps

    with open("number_of_steps.json", "w") as f:
        json.dump(data, f, indent=4)


def plot_violin():
    # list of sucessful trajectories for gpt and deepseek
    successful_traj = {'deepseek-v3': 'sphinx-doc__sphinx-9281',
                       'deepseek-v3': 'sympy__sympy-14531',
                       'deepseek-v3': 'sympy__sympy-24539',
                       'gpt-5-mini': 'django__django-13109',
                       'gpt-5-mini': 'django__django-17029'}
    unsuccessful_traj = {'deepseek-v3': 'astropy__astropy-13033',
                         'deepseek-v3': 'django__django-11138',
                         'deepseek-v3': 'django__django-11141',
                         'deepseek-v3': 'django__django-11211',
                         'deepseek-v3': 'django__django-12308',
                         'deepseek-v3': 'django__django-14351',
                         'deepseek-v3': 'django__django-15268',
                         'deepseek-v3': 'pydata__xarray-4695',
                         'deepseek-v3': 'pylint-dev__pylint-7277',
                         'deepseek-v3': 'sympy__sympy-24443',
                         'gpt-5-mini': 'django__django-10880',
                         'gpt-5-mini': 'django__django-13837',
                         'gpt-5-mini': 'django__django-16661',
                         'gpt-5-mini': 'pylint-dev__pylint-7277',
                         'gpt-5-mini': 'sphinx-doc__sphinx-11510'}
    succ_num_steps = []
    unsucc_num_steps = []
    for model, traj in successful_traj.items():
        succ_num_steps.append(count_steps(model, traj))

    for model, traj in unsuccessful_traj.items():
        unsucc_num_steps.append(count_steps(model, traj))

    # plot the violin plot using matplotlib
    parts = plt.violinplot([succ_num_steps, unsucc_num_steps],
                           showextrema=False, quantiles=[[0.25, 0.75]]*2)

    # Style the quantile lines to be dashed/black like your reference
    if 'cquantiles' in parts:
        parts['cquantiles'].set_linestyle('--')
        parts['cquantiles'].set_edgecolor('black')

    # Add the text boxes
    __add_offset_annotations([succ_num_steps, unsucc_num_steps], [1, 2])

    plt.xticks([1, 2], ['Success', 'Failure'])
    plt.ylabel('Iterations')
    plt.title('Distribution of Steps')
    plt.savefig('number_of_steps.jpeg')
    plt.show()


def __add_offset_annotations(data, positions):
    for i, d in enumerate(data):
        # Calculate 25th, 50th (median), and 75th percentiles
        q1, q3 = np.percentile(d, [25, 75])

        # Define the offset (adjust 0.15 based on your plot's scale)
        offset = 0.15

        for val in [q1, q3]:
            plt.text(positions[i] + offset, val, f'{val:.1f}',
                     ha='left',            # Align text to the left of the point
                     va='center',          # Keep it vertically centered on the line
                     fontsize=9,
                     bbox=dict(facecolor='white', alpha=0.8, edgecolor='lightgray', boxstyle='round,pad=0.2'))
