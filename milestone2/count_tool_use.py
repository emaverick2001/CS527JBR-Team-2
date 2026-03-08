from typing import Dict
import json
import re


def count_tool_use(model_name: str, instance_id: str) -> dict:
    # keywords to search for
    tools_to_search = ["view", "create", "str_replace", "insert", "undo_edit"]
    # read in the trajectory file
    with open(f'../Trajectories/{model_name}/{instance_id}.traj', 'r') as f:
        trajectory = json.load(f)

    # Extract out the Trajectory only
    trajectory_steps = trajectory['trajectory']
    # intialise the count dictionary
    tool_use_count = {tool: 0 for tool in tools_to_search}
    # loop through the trajectory and count the tool use
    pattern_string = r"str_replace_editor\s+(" + \
        "|".join(map(re.escape, tools_to_search)) + r")"
    for step in range(len(trajectory_steps)):
        actions = trajectory_steps[step]['action']
        matches = re.findall(pattern_string, actions)
        for match in matches:
            tool_use_count[match] += 1

    return tool_use_count


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
#         gpt_steps[instance] = count_tool_use("gpt-5-mini", instance)
#     for instance in deepseek_instances:
#         deepseek_steps[instance] = count_tool_use("deepseek-v3", instance)

#     data['gpt-5-mini'] = gpt_steps
#     data['deepseek-v3'] = deepseek_steps

#     with open("thought_entity_relevance.json", "w") as f:
#         json.dump(data, f, indent=4)
