import json


def locate_navigation(model_name: str, instance_id: str) -> list[int]:
  """
  Extracts each step that conducts a navigation action by its number/id
  :param model_name: deepseek-v3 or gpt-5-mini
  :param instance_id: ID of the instance for which to count the steps
  :return: list of steps that conduct a navigation action
  """
  # first read the trajectory file based on model_name and instance_id
  file_name = f"../Trajectories/{model_name}/{instance_id}/{instance_id}.traj"
  with open(file_name, 'r') as f:
      traj_data = f.read()

  nav_commands = {
      "find_file",
      "search_file",
      "search_dir",
      "ls",
      "cat",
      "pwd",
      "find",
      "grep",
      "cd",
      "sed",
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
      if cmd == "str_replace_editor": # Avoids substring hits inside str_replace_editor create/str_replace payloads.
          if len(parts) > 1 and parts[1] == "view":
              steps.append(idx)
          continue
      if cmd in nav_commands:
          steps.append(idx)
  return steps

  
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
      gpt_steps[instance] = locate_navigation("gpt-5-mini", instance)
  for instance in deepseek_instances:
      deepseek_steps[instance] = locate_navigation("deepseek-v3", instance)

  data['gpt-5-mini'] = gpt_steps
  data['deepseek-v3'] = deepseek_steps

  with open("locate_navigation.json", "w") as f:
      json.dump(data, f, indent=4)
      
if __name__ == "__main__":
    write_to_json()
