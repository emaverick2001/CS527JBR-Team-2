import json
import os
import re
import shlex
import glob
from typing import Any, Dict, List, Optional, Tuple

# =========================
# Bullet-proof paths (works no matter where you run from)
# =========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))      # .../milestone2
REPO_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))  # repo root
TRAJ_ROOT = os.path.join(REPO_ROOT, "Trajectories")        # .../Trajectories


# =========================
# Task 3: locate_generated_tests
# =========================

def _strip_testbed_prefix(path: str) -> str:
    # IMPORTANT: /testbed contains "test" but it's not a tests/ directory.
    return path[8:] if path.startswith("/testbed/") else path


# ---- Path heuristics ----
_TEST_DIR_PAT = re.compile(r"(^|/)(tests?|testing)(/|$)", re.IGNORECASE)
_TEST_FILE_PAT = re.compile(r"(^|/)(test_[^/]+\.\w+|[^/]+_test\.\w+)$", re.IGNORECASE)
_REPRO_VALIDATE_PAT = re.compile(
    r"(^|/)[^/]*(repro|reproduce|validate|regression)[^/]*\.\w+$",
    re.IGNORECASE,
)

# ---- Thought / response heuristics ----
_THOUGHT_PATS = [
    re.compile(r"\brepro(duce)?\b", re.IGNORECASE),
    re.compile(r"\bvalidate\b", re.IGNORECASE),
    re.compile(r"\bregression\b", re.IGNORECASE),
    re.compile(r"\b(write|add|create|generate)\b.*\btest\b", re.IGNORECASE),
    re.compile(r"\bunit\s+test\b", re.IGNORECASE),
    re.compile(r"\bpytest\b", re.IGNORECASE),
    re.compile(r"\bunittest\b", re.IGNORECASE),
]

# ---- Code heuristics ----
_CODE_PATS = [
    re.compile(r"^\s*def\s+test_", re.MULTILINE),
    re.compile(r"\bpytest\b", re.IGNORECASE),
    re.compile(r"\bunittest\b", re.IGNORECASE),
    re.compile(r"\bTestCase\b"),
    re.compile(r"\bassert\b"),
]

# ---- Optional name extraction ----
_CLASS_RE = re.compile(r"^\s*class\s+([A-Za-z_]\w*)\b", re.MULTILINE)
_DEF_RE = re.compile(r"^\s*def\s+([A-Za-z_]\w*)\b", re.MULTILINE)

# Stricter "test class" detection
_TESTLIKE_CLASS_NAME = re.compile(r"^(Test\w+|\w*Tests?)$")
_TESTCASE_INHERIT = re.compile(
    r"^\s*class\s+([A-Za-z_]\w*)\s*\(([^)]*TestCase[^)]*)\)\s*:",
    re.MULTILINE
)


def _path_is_testish(path: str) -> bool:
    p = _strip_testbed_prefix(path or "")
    return bool(_TEST_DIR_PAT.search(p) or _TEST_FILE_PAT.search(p) or _REPRO_VALIDATE_PAT.search(p))


def _thought_is_testish(text: str) -> bool:
    if not text:
        return False
    # Remove /testbed/... fragments so "testbed" doesn't accidentally trigger logic.
    cleaned = re.sub(r"/testbed[^\s]*", " ", text)
    return any(p.search(cleaned) for p in _THOUGHT_PATS)


def _code_is_testish(code: str) -> bool:
    if not code:
        return False
    return any(p.search(code) for p in _CODE_PATS)


def _infer_names_for_artifact(path: str, code: str) -> Tuple[str, str]:
    """
    Returns (method_name, test_class_name) (both optional).
    - For real test files: prefer def test_* and class Test*/Tests/TestCase
    - For repro/validate scripts: prefer def reproduce_* / validate_* / main
    - Never label random domain classes as test_class_name
    """
    if not code:
        return "", ""

    path_lower = (path or "").lower()
    defs = _DEF_RE.findall(code)
    classes = _CLASS_RE.findall(code)

    def pick_def(prefixes: List[str]) -> str:
        for d in defs:
            for p in prefixes:
                if d.startswith(p):
                    return d
        return ""

    def pick_test_class() -> str:
        m = _TESTCASE_INHERIT.search(code)
        if m:
            return m.group(1)
        for c in classes:
            if _TESTLIKE_CLASS_NAME.match(c):
                return c
        return ""

    is_real_test_file = (
        "/tests/" in path_lower
        or (path_lower.endswith(".py") and ("/test_" in path_lower or path_lower.endswith("_test.py")))
    )
    is_repro_script = any(k in path_lower for k in ["repro", "reproduce", "validate", "regression"])

    if is_real_test_file:
        return pick_def(["test_"]), pick_test_class()

    if is_repro_script:
        return pick_def(["reproduce", "repro", "validate", "main"]), pick_test_class()

    return pick_def(["test_"]), pick_test_class()


# =========================
# Parsing helpers
# =========================

def _parse_str_replace_editor_cli(action: str) -> Optional[Tuple[str, str, Dict[str, str]]]:
    """
    Parses:
      str_replace_editor create PATH --file_text '...'
      str_replace_editor str_replace PATH --old_str '...' --new_str '...'
      str_replace_editor insert PATH --insert_text '...'
      str_replace_editor view PATH --view_range ...
    """
    try:
        toks = shlex.split(action)
    except Exception:
        return None
    if len(toks) < 2 or toks[0] != "str_replace_editor":
        return None

    subcmd = toks[1]
    path = toks[2] if len(toks) > 2 else ""
    args: Dict[str, str] = {}

    i = 3
    while i < len(toks):
        tok = toks[i]
        if tok.startswith("--"):
            key = tok[2:]
            val = toks[i + 1] if i + 1 < len(toks) else ""
            args[key] = val
            i += 2
        else:
            i += 1

    return subcmd, path, args


def _parse_str_replace_editor_json(action: str) -> Optional[Tuple[str, str, Dict[str, Any]]]:
    """
    Parses (if it ever appears):
      str_replace_editor create
      { "path": "...", "file_text": "..." }
    """
    if not action.startswith("str_replace_editor") or "\n" not in action:
        return None
    first, rest = action.split("\n", 1)
    parts = first.split()
    if len(parts) < 2:
        return None
    subcmd = parts[1]
    try:
        payload = json.loads(rest.strip())
    except Exception:
        return None
    path = payload.get("path", "") if isinstance(payload, dict) else ""
    return subcmd, path, payload


def _extract_editor_code(subcmd: str, args: Dict[str, Any]) -> str:
    if not isinstance(args, dict):
        return ""
    if subcmd == "create":
        return args.get("file_text") or args.get("content") or args.get("text") or ""
    if subcmd == "str_replace":
        return args.get("new_str") or args.get("replacement") or ""
    if subcmd == "insert":
        return args.get("insert_text") or args.get("text") or args.get("new_str") or ""
    return ""


def _parse_view_observation_to_text(observation: str) -> Optional[str]:
    """
    Observations often include:
      Here's the result of running `cat -n` on /path:
       1\tline
       2\tline
    We reconstruct file content by removing the line numbers.
    """
    if not observation:
        return None
    if "Here's the result of running `cat -n` on " not in observation:
        return None
    if "on a snippet of" in observation:
        return None  # partial view; ignore

    lines = observation.splitlines()
    content: List[str] = []
    for line in lines[1:]:
        if "\t" in line:
            _, rest = line.split("\t", 1)
            content.append(rest)
    return "\n".join(content)


def _parse_echo_or_printf_redirect(action: str) -> Optional[Tuple[str, str]]:
    """
    Handles:
      echo "..." > /path/file.py
      echo "..." > /path/file.py && python /path/file.py
      printf "..." > /path/file.py && ...
    Returns (path, content).
    """
    stripped = action.strip()
    if not (stripped.startswith("echo ") or stripped.startswith("printf ")):
        return None

    try:
        toks = shlex.split(action)
    except Exception:
        return None

    if ">" not in toks:
        return None

    gt = toks.index(">")
    if gt >= len(toks) - 1:
        return None

    path = toks[gt + 1]

    # content tokens are between command and '>'
    cmd = toks[0]
    content_tokens = toks[1:gt]

    # strip common flags (-e/-n) for echo
    if cmd == "echo" and content_tokens and content_tokens[0] in ("-e", "-n"):
        content_tokens = content_tokens[1:]

    content = " ".join(content_tokens)
    return path, content


_HEREDOC_1 = re.compile(r"cat\s+<<\s*['\"]?([A-Za-z0-9_]+)['\"]?\s*>\s*(\S+)", re.IGNORECASE)
_HEREDOC_2 = re.compile(r"cat\s*>\s*(\S+)\s*<<\s*['\"]?([A-Za-z0-9_]+)['\"]?", re.IGNORECASE)

def _parse_cat_heredoc(action: str) -> Optional[Tuple[str, str]]:
    """
    Best-effort heredoc parse:
      cat <<'EOF' > /path/file.py
      ...lines...
      EOF
    or:
      cat > /path/file.py <<'EOF'
      ...lines...
      EOF
    """
    if "cat" not in action or "<<" not in action or ">" not in action:
        return None

    m = _HEREDOC_1.search(action) or _HEREDOC_2.search(action)
    if not m:
        return None

    if m.re is _HEREDOC_1:
        delim = m.group(1)
        path = m.group(2)
    else:
        path = m.group(1)
        delim = m.group(2)

    # heredoc body starts after first newline
    if "\n" not in action:
        return None

    first_line, rest = action.split("\n", 1)
    body_lines = []
    for line in rest.splitlines():
        if line.strip() == delim:
            break
        body_lines.append(line)

    return path, "\n".join(body_lines)


# =========================
# Main required function
# =========================

def locate_generated_tests(model_name: str, instance_id: str) -> list:
    """
    Task 3:
    Return a list[dict] for each generated test artifact (usually one per file path).
    """
    file_name = os.path.join(TRAJ_ROOT, model_name, f"{instance_id}.traj")
    with open(file_name, "r") as f:
        traj = json.loads(f.read())

    trajectory = traj.get("trajectory", [])

    # Best-effort file state
    file_state: Dict[str, str] = {}

    # One output record per path; keep earliest step but update code as it changes
    records: Dict[str, Dict[str, Any]] = {}

    for idx, step in enumerate(trajectory, start=1):
        action = step.get("action") or ""
        observation = step.get("observation") or ""
        thought_blob = (step.get("thought") or "") + "\n" + (step.get("response") or "")

        # 0) track full content from view (helps reconstruct final full code)
        if action.startswith("str_replace_editor view"):
            parsed_view = _parse_str_replace_editor_cli(action) or _parse_str_replace_editor_json(action)
            if parsed_view:
                subcmd, path, args = parsed_view
                text = _parse_view_observation_to_text(observation)
                if path and text is not None:
                    file_state[path] = text
            continue

        # 1) echo/printf > file (including "&& python ...")
        ep = _parse_echo_or_printf_redirect(action)
        if ep:
            path, code = ep
            if _path_is_testish(path) or _thought_is_testish(thought_blob) or _code_is_testish(code):
                file_state[path] = code
                method_name, class_name = _infer_names_for_artifact(path, code)
                if path not in records:
                    records[path] = {
                        "path": path,
                        "step": idx,
                        "code": code,
                        "method_name": method_name,
                        "test_class_name": class_name,
                    }
                else:
                    records[path]["code"] = code
                    if method_name:
                        records[path]["method_name"] = method_name
                    if class_name:
                        records[path]["test_class_name"] = class_name
            continue

        # 2) cat heredoc > file (rare but safe)
        hd = _parse_cat_heredoc(action)
        if hd:
            path, code = hd
            if _path_is_testish(path) or _thought_is_testish(thought_blob) or _code_is_testish(code):
                file_state[path] = code
                method_name, class_name = _infer_names_for_artifact(path, code)
                if path not in records:
                    records[path] = {
                        "path": path,
                        "step": idx,
                        "code": code,
                        "method_name": method_name,
                        "test_class_name": class_name,
                    }
                else:
                    records[path]["code"] = code
                    if method_name:
                        records[path]["method_name"] = method_name
                    if class_name:
                        records[path]["test_class_name"] = class_name
            continue

        # 3) str_replace_editor create/insert/str_replace
        parsed = _parse_str_replace_editor_cli(action) or _parse_str_replace_editor_json(action)
        if not parsed:
            continue

        subcmd, path, args = parsed
        if subcmd not in {"create", "insert", "str_replace"} or not path:
            continue

        code_snippet = _extract_editor_code(subcmd, args)

        # Decide if test artifact
        is_test_event = False
        if _path_is_testish(path):
            is_test_event = True
        else:
            filename = os.path.basename(_strip_testbed_prefix(path))
            filename_hint = bool(
                _REPRO_VALIDATE_PAT.search("/" + filename) or _TEST_FILE_PAT.search("/" + filename)
            )
            if _thought_is_testish(thought_blob) and (filename_hint or _code_is_testish(code_snippet)):
                is_test_event = True

        if not is_test_event:
            continue

        # Update file_state best-effort
        if subcmd == "create":
            file_state[path] = code_snippet

        elif subcmd == "str_replace":
            old = args.get("old_str", "") if isinstance(args, dict) else ""
            new = args.get("new_str", "") if isinstance(args, dict) else code_snippet
            if path in file_state and old and old in file_state[path]:
                file_state[path] = file_state[path].replace(old, new, 1)
            else:
                # if we don't have state, at least keep the new snippet
                file_state[path] = file_state.get(path, "") or new or code_snippet

        elif subcmd == "insert":
            ins = args.get("insert_text", "") if isinstance(args, dict) else ""
            ins = ins or code_snippet
            file_state[path] = (file_state.get(path, "") + ("\n" if file_state.get(path, "") else "") + ins)

        final_code = file_state.get(path, "") or code_snippet
        method_name, class_name = _infer_names_for_artifact(path, final_code)

        if path not in records:
            records[path] = {
                "path": path,
                "step": idx,
                "code": final_code,
                "method_name": method_name,
                "test_class_name": class_name,
            }
        else:
            records[path]["code"] = final_code
            if method_name:
                records[path]["method_name"] = method_name
            if class_name:
                records[path]["test_class_name"] = class_name

    out = list(records.values())
    out.sort(key=lambda d: d["step"])
    return out


# =========================
# Helper to dump locate_generated_tests.json
# =========================

def _list_instances_in_dir(model_name: str) -> List[str]:
    base = os.path.join(TRAJ_ROOT, model_name)
    traj_files = glob.glob(os.path.join(base, "*.traj"))
    return sorted([os.path.splitext(os.path.basename(p))[0] for p in traj_files])


def write_locate_generated_tests_json(
    gpt_instances: Optional[List[str]] = None,
    deepseek_instances: Optional[List[str]] = None,
) -> None:
    if gpt_instances is None:
        gpt_instances = _list_instances_in_dir("gpt-5-mini")
    if deepseek_instances is None:
        deepseek_instances = _list_instances_in_dir("deepseek-v3")

    data = {"gpt-5-mini": {}, "deepseek-v3": {}}

    for inst in gpt_instances:
        data["gpt-5-mini"][inst] = locate_generated_tests("gpt-5-mini", inst)

    for inst in deepseek_instances:
        data["deepseek-v3"][inst] = locate_generated_tests("deepseek-v3", inst)

    out_path = os.path.join(BASE_DIR, "locate_generated_tests.json")
    with open(out_path, "w") as f:
        json.dump(data, f, indent=4)

    print(f"Wrote: {out_path}")
    print(f"Scanned gpt-5-mini: {len(gpt_instances)} trajs, deepseek-v3: {len(deepseek_instances)} trajs")


if __name__ == "__main__":
    write_locate_generated_tests_json()

