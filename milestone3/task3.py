import pandas as pd
import json
import os


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


# if __name__ == "__main__":
#     # the trajectories to find steps for
#     gpt_instances = ['django__django-13109',
#                      'django__django-17029',
#                      'django__django-10880',
#                      'django__django-13837',
#                      'django__django-16661',
#                      'pylint-dev__pylint-7277',
#                      'sphinx-doc__sphinx-11510']

#     deepseek_instances = ['sphinx-doc__sphinx-9281',
#                           'sympy__sympy-14531',
#                           'sympy__sympy-24539',
#                           'astropy__astropy-13033',
#                           'django__django-11138',
#                           'django__django-11141',
#                           'django__django-11211',
#                           'django__django-12308',
#                           'django__django-14351',
#                           'django__django-15268',
#                           'pydata__xarray-4695',
#                           'pylint-dev__pylint-7277',
#                           'sympy__sympy-24443']
#     gpt_steps = {}
#     deepseek_steps = {}
#     data = {}
#     for instance in gpt_instances:
#         gpt_steps[instance] = detect_inefficiency_patterns(
#             "gpt-5-mini", instance)
#     for instance in deepseek_instances:
#         deepseek_steps[instance] = detect_inefficiency_patterns(
#             "deepseek-v3", instance)

#     data['gpt-5-mini'] = gpt_steps
#     data['deepseek-v3'] = deepseek_steps

#     with open("inefficiency_patterns.json", "w") as f:
#         json.dump(data, f, indent=4)
