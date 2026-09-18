import json
from pathlib import Path

from ..utils import sanitize, log_debug
from ..settings import TRAILER_FOLDER

def load_json_dict(path: Path) -> dict:
    """Load a JSON file to a dict, return {} on parse error."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}

def write_json_dict(path: Path, data: dict) -> None:
    """Write dict to JSON with one key per line, pretty-printed."""
    lines = ["{"]
    items = list(data.items())
    for i, (k, v) in enumerate(items):
        comma = "," if i < len(items) - 1 else ""
        safe_v = (v or "").replace('"', '\\"')
        lines.append(f'  "{k}": "{safe_v}"{comma}')
    lines.append("}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

def ensure_url_json_exists(sheet_title: str) -> Path:
    """
    Guarantee trailer-URL JSON exists for a sheet.
    Returns its Path.
    """
    safe = sanitize(sheet_title).replace(" ", "")
    json_file = TRAILER_FOLDER / f"{safe}Urls.json"
    if not json_file.exists():
        json_file.write_text("{}", encoding="utf-8")
        log_debug(f"Created URL JSON: {json_file.name}")
    return json_file

def build_master_cache_from_all_json() -> dict[str, str]:
    """
    Scan all '*.json' in TRAILER_FOLDER and build
    { normalized_title: url } for any non-empty entries.
    """
    cache: dict[str, str] = {}
    for file in TRAILER_FOLDER.glob("*.json"):
        data = load_json_dict(file)
        for title, url in data.items():
            if url and title not in cache:
                cache[title] = url
    return cache
