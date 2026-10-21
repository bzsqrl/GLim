import subprocess
import sys
import os

def build():
    print("Starting FFMaker build process...")
    
    # Check if pyinstaller is installed
    try:
        import PyInstaller
    except ImportError:
        print("PyInstaller not found. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    # Run pyinstaller using the .spec file
    print("Running PyInstaller...")
    cmd = ["pyinstaller", "--clean", "--noconfirm", "FFMaker.spec"]
    
    try:
        subprocess.check_call(cmd)
        print("\nBuild successful!")
        print("You can find the compiled application in the 'dist/FFMaker' folder.")
    except subprocess.CalledProcessError as e:
        print(f"\nBuild failed with error: {e}")

if __name__ == "__main__":
    build()
