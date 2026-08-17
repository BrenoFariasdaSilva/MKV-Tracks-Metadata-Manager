#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${PROJECT_DIR}/venv"
PYTHON_EXE="${VENV_DIR}/bin/python3"
PIP_EXE="${VENV_DIR}/bin/pip"
REQUIREMENTS_FILE="${PROJECT_DIR}/requirements.txt"

if [ "$(uname -s)" != "Darwin" ]; then
    echo "This installer must run on macOS."
    exit 1
fi

if ! command -v brew >/dev/null 2>&1; then
    echo "Homebrew was not found. Install Homebrew from https://brew.sh/ and re-run this script."
    exit 1
fi

install_system_packages() {
    if ! command -v python3 >/dev/null 2>&1; then
        brew install python
    fi
    if ! command -v ffmpeg >/dev/null 2>&1 || ! command -v ffprobe >/dev/null 2>&1; then
        brew install ffmpeg
    fi
    if ! command -v mkvpropedit >/dev/null 2>&1 || ! command -v mkvmerge >/dev/null 2>&1 || ! command -v mkvextract >/dev/null 2>&1; then
        brew install mkvtoolnix
    fi
}

install_python_requirements() {
    if ! command -v python3 >/dev/null 2>&1; then
        echo "python3 was not found after Homebrew installation."
        exit 1
    fi
    if [ ! -x "${PYTHON_EXE}" ]; then
        python3 -m venv "${VENV_DIR}"
    fi
    "${PYTHON_EXE}" -m pip install --upgrade pip
    "${PIP_EXE}" install -r "${REQUIREMENTS_FILE}"
}

verify_command() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "$1 could not be resolved after installation."
        exit 1
    fi
    "$1" --version >/dev/null 2>&1
}

install_system_packages
install_python_requirements
verify_command ffmpeg
verify_command ffprobe
verify_command mkvpropedit
verify_command mkvmerge
verify_command mkvextract
echo "Installation complete."
