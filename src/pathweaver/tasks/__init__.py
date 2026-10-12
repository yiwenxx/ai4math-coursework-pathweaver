"""Task catalogue presentation shared by private and curated public CLIs."""
import json
import tomllib
from importlib.resources import files


def describe_tasks(*, as_json: bool = False) -> str:
    """Render the installed catalogue; reading it never loads task solvers."""
    catalogue = tomllib.loads(files(__package__).joinpath("catalog.toml").read_text(encoding="utf-8"))
    if as_json:
        return json.dumps(catalogue, ensure_ascii=False, indent=2)
    if not catalogue["task"]:
        return "No public task implementations have been released."
    lines = []
    for task in catalogue["task"]:
        details = "; ".join(str(task[key]) for key in ("status", "scope") if key in task)
        lines.append(f"{task['id']}: {task['title']} [{details}]")
    return "\n".join(lines)
