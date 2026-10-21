#!/bin/bash

# FFMaker-Mac Setup Script
# Run this on your MacBook Pro to prepare the environment.

echo "--- FFMaker macOS Setup ---"

# Check for Homebrew
if ! command -v brew &> /dev/null
then
    echo "Homebrew not found. Installing..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
else
    echo "Homebrew found."
fi

# Install dependencies
echo "Installing system dependencies..."
brew install cmake glew tkdnd

# Install Python dependencies
echo "Installing Python dependencies..."
pip3 install customtkinter pillow tkinterdnd2 pyinstaller

echo "--- Setup Complete ---"
echo "You can now run FFMaker via 'python3 src/main_gui.py' or build it with 'python3 compile_mac.py'"
