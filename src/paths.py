import os
import sys

def get_bundle_dir():
    """Returns the root directory of the application bundle or source."""
    if getattr(sys, 'frozen', False):
        # Running as a bundled EXE
        return sys._MEIPASS
    else:
        # Running from source
        # __file__ is FFMaker/src/paths.py, so parent of parent is FFMaker/
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_executable_dir():
    """Returns the directory containing the executable or the source root."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_resource_path(relative_path):
    """Returns the path to a resource inside the bundle (like boilerplates)."""
    return os.path.join(get_bundle_dir(), relative_path)

def get_external_path(relative_path):
    """Returns the path to a folder outside the bundle (like output, deps)."""
    return os.path.join(get_executable_dir(), relative_path)
