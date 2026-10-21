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
    d = os.path.join(base, "FFMaker")
    os.makedirs(d, exist_ok=True)
    return d


def templates_dir():
    return os.path.join(bundle_dir(), "templates")


def ffgl_sdk_dir():
    return os.path.join(bundle_dir(), "boilerplates", "ffgl")


def default_output_dir():
    # A packaged Mac app can't write inside FFMaker.app (that breaks its
    # signature, and /Applications is read-only), so use Documents instead.
    if getattr(sys, "frozen", False) and sys.platform == "darwin":
        return os.path.join(os.path.expanduser("~/Documents"), "FFMaker", "output")
    return os.path.join(app_dir(), "output")
