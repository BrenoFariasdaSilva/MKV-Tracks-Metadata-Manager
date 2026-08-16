#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${PROJECT_DIR}/venv"
PYTHON_EXE="${VENV_DIR}/bin/python3"
PIP_EXE="${VENV_DIR}/bin/pip"
REQUIREMENTS_FILE="${PROJECT_DIR}/requirements.txt"

if [ "$(id -u)" -eq 0 ]; then
    SUDO=""
else
    if ! command -v sudo >/dev/null 2>&1; then
        echo "sudo was not found. Re-run as root or install sudo."
        exit 1
    fi
    SUDO="sudo"
fi

install_apt_packages() {
    ${SUDO} apt-get update
    ${SUDO} apt-get install -y python3 python3-venv python3-pip ffmpeg mkvtoolnix
}

install_dnf_packages() {
    ${SUDO} dnf install -y python3 python3-pip ffmpeg mkvtoolnix
}

install_pacman_packages() {
    ${SUDO} pacman -Sy --needed --noconfirm python python-pip ffmpeg mkvtoolnix-cli
}

install_system_packages() {
    if command -v apt-get >/dev/null 2>&1; then
        install_apt_packages
        return
    fi
    if command -v dnf >/dev/null 2>&1; then
        install_dnf_packages
        return
    fi
    if command -v pacman >/dev/null 2>&1; then
        install_pacman_packages
        return
    fi
    echo "Unsupported Linux package manager. Install ffmpeg, ffprobe, mkvpropedit, mkvmerge, python3, and venv support manually."
    exit 1
}

install_python_requirements() {
    if ! command -v python3 >/dev/null 2>&1; then
        echo "python3 was not found after system package installation."
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
echo "Installation complete."
