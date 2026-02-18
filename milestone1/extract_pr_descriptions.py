import re
import json
from pathlib import Path

PR_RE = re.compile(r"<pr_description>(.*?)</pr_description>", re.DOTALL | re.IGNORECASE)

def get_instance_id_from_filename(fname: str, model_name: str) -> str:
    stem = Path(fname).stem
    prefix = model_name + "-"
    if stem.startswith(prefix):
        return stem[len(prefix):]
    return stem

def extract_one(traj_path: Path) -> str:
    text = traj_path.read_text(encoding="utf-8", errors="replace")
    m = PR_RE.search(text)
    if not m:
        return ""
    return m.group(1).strip()

def main():
    root = Path("milestone1/Trajectories")
    out = {"gpt-5-mini": {}, "deepseek-v3": {}}

    for model in ["gpt-5-mini", "deepseek-v3"]:
        folder = root / model
        for traj_path in sorted(folder.rglob("*.traj")):
            instance_id = get_instance_id_from_filename(traj_path.name, model)
            pr = extract_one(traj_path)
            out[model][instance_id] = pr

    Path("milestone1/pr_descriptions.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print("Wrote milestone1/pr_descriptions.json")

if __name__ == "__main__":
    main()
