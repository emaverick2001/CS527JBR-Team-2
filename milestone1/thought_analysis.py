import json
import re
from thefuzz import fuzz, process


def find_relevance(model_name: str, instance_id: str):
    # Read in the Json file with the entities
    with open('issue_entities.json', 'r') as f:
        entities = json.load(f)
    # read in the releavant JSON file
    with open(f'Trajectories/{model_name}/{instance_id}.traj', 'r') as f:
        trajectory = json.load(f)

    # Find the relevant entities in the issue_entities.json file
    relevant_entities = entities[model_name][instance_id]
    # Extract out the Trajectory only
    trajectory_steps = trajectory['trajectory']
    # iterate through the steps
    matched_entities_per_step = {}
    for step in range(len(trajectory_steps)):
        thoughts = trajectory_steps[step]['thought']
        # some thoughts might be empty string
        matches = []
        if thoughts:
            for word in relevant_entities:
                score = fuzz.partial_ratio(word.lower(), thoughts.lower())
                if score > 70:
                    matches.append(word)
        matched_entities_per_step[str(step+1)] = matches
    return matched_entities_per_step


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
#         gpt_steps[instance] = find_relevance("gpt-5-mini", instance)
#     for instance in deepseek_instances:
#         deepseek_steps[instance] = find_relevance("deepseek-v3", instance)

#     data['gpt-5-mini'] = gpt_steps
#     data['deepseek-v3'] = deepseek_steps

#     with open("thought_entity_relevance.json", "w") as f:
#         json.dump(data, f, indent=4)
