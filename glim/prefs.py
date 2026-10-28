"""GLim's own settings, kept between sessions in prefs.json in the user's
config folder (paths.config_dir()): for now, the folders last chosen for
built plugins, ISF exports and saved shader code.

{
  "folders": {"build": "C:/Users/me/Documents/Resolume Arena/Extra Effects",
              "isf": "...", "save": "..."}
}
"""
import json
import os

from . import paths

FILE = "prefs.json"


def _path():
    return os.path.join(paths.config_dir(), FILE)


def load():
    try:
        with open(_path(), encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save(data):
    """Write the whole file; a crash mid-write leaves the old one in place."""
    p = _path()
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, p)


def folder(kind):
    """The folder last chosen for `kind` ("build", "isf" or "save"), if it
    still exists, else None."""
    d = load().get("folders", {}).get(kind)
    return d if isinstance(d, str) and os.path.isdir(d) else None


def set_folder(kind, path):
    data = load()
    folders = data.get("folders")
    if not isinstance(folders, dict):
        folders = data["folders"] = {}
    folders[kind] = os.path.abspath(path)
    try:
        save(data)
    except OSError as e:            # remembering is a convenience; never block a build
        print(f"GLim: couldn't save {FILE} ({e})")
