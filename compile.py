import subprocess
import sys
import os

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

    try:
        subprocess.check_call(cmd, cwd=os.path.dirname(os.path.abspath(__file__)))
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
