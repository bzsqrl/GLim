"""Filesystem locations, valid both from source and from a PyInstaller bundle."""
import os
import sys


def bundle_dir():
    """Read-only resources (templates, FFGL SDK)."""
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def app_dir():
    """Folder next to the executable (or the project root from source)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def cache_dir():
    """Writable per-user cache for build workspaces and downloads."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~\\AppData\\Local")
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Caches")
    else:
        base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    d = os.path.join(base, "GLim")
    os.makedirs(d, exist_ok=True)
    return d


def config_dir():
    """Writable per-user folder for GLim's own settings (prefs.json)."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~\\AppData\\Roaming")
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    d = os.path.join(base, "GLim")
    os.makedirs(d, exist_ok=True)
    return d


def documents_dir():
    """The user's Documents folder (their home folder if there's none)."""
    d = os.path.expanduser(os.path.join("~", "Documents"))
    return d if os.path.isdir(d) else os.path.expanduser("~")


def templates_dir():
    return os.path.join(bundle_dir(), "templates")


def icon_dir():
    """GLim's icon files (made by assets/icon/make_icon.py)."""
    return os.path.join(bundle_dir(), "assets", "icon")


def ffgl_sdk_dir():
    return os.path.join(bundle_dir(), "boilerplates", "ffgl")


def default_output_dir():
    # A packaged Mac app can't write inside GLim.app (that breaks its
    # signature, and /Applications is read-only), so use Documents instead.
    if getattr(sys, "frozen", False) and sys.platform == "darwin":
        return os.path.join(os.path.expanduser("~/Documents"), "GLim", "output")
    return os.path.join(app_dir(), "output")
