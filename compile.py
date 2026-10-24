import glob
import shutil
import subprocess
import sys
import os

def seal_mac_app(app):
    """Re-sign FFStudio.app ad hoc so `codesign --verify --deep --strict` passes.
    PyInstaller signs the binaries but leaves the app without a resource seal,
    and Syphon.framework (from syphon-python's wheel, which can't hold symlinks)
    has real folders at its top level where a framework has symlinks into
    Versions/Current, which codesign rejects. Relink those, sign each framework,
    then the app."""
    frameworks = sorted(glob.glob(os.path.join(app, "Contents", "Frameworks", "**", "*.framework"),
                                  recursive=True), key=len, reverse=True)     # nested ones first
    for fw in frameworks:
        for name in os.listdir(fw):
            path = os.path.join(fw, name)
            if name == "Versions" or os.path.islink(path):
                continue
            if os.path.exists(os.path.join(fw, "Versions", "Current", name)):
                shutil.rmtree(path) if os.path.isdir(path) else os.remove(path)
                os.symlink(os.path.join("Versions", "Current", name), path)
        subprocess.check_call(["codesign", "--force", "--sign", "-", fw])
    subprocess.check_call(["codesign", "--force", "--sign", "-", app])
    subprocess.check_call(["codesign", "--verify", "--deep", "--strict", app])

def build():
    print("Starting FFStudio build process...")

    # Check if pyinstaller is installed
    try:
        import PyInstaller
    except ImportError:
        print("PyInstaller not found. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    # Run pyinstaller using the .spec file (it handles Windows and macOS)
    print("Running PyInstaller...")
    cmd = [sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", "FFStudio.spec"]

    root = os.path.dirname(os.path.abspath(__file__))
    try:
        subprocess.check_call(cmd, cwd=root)
        if sys.platform == "darwin":
            print("Sealing the app's code signature...")
            seal_mac_app(os.path.join(root, "dist", "FFStudio.app"))
        print("\nBuild successful!")
        if sys.platform == "darwin":
            print("You can find FFStudio.app in the 'dist' folder.")
        else:
            print("You can find FFStudio.exe in the 'dist' folder.")
    except subprocess.CalledProcessError as e:
        print(f"\nBuild failed with error: {e}")
        sys.exit(1)     # so scripts that run this see the failure

if __name__ == "__main__":
    build()
