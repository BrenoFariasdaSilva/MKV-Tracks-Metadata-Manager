# Variables
VENV := venv
ARGS ?=
INPUT_DIR ?=
AUDIO_REPORT ?=
SUBTITLE_REPORT ?=
FILE ?=
HOST_OS := $(OS)
ifeq ($(HOST_OS),Windows_NT)
DETECTED_OS := Windows
else
DETECTED_OS := $(shell uname)
endif

# Detect correct Python and Pip commands based on OS
ifeq ($(DETECTED_OS), Windows) # Windows
	PYTHON := $(VENV)/Scripts/python.exe
	PIP := $(PYTHON) -m pip
	PYTHON_CMD := python
	CLEAR_CMD := cls
	TIME_CMD :=
	INSTALL_CMD := cmd /c install_windows.bat
else ifeq ($(findstring MINGW,$(DETECTED_OS)),MINGW) # Git Bash on Windows
	PYTHON := $(VENV)/Scripts/python.exe
	PIP := $(PYTHON) -m pip
	PYTHON_CMD := python
	CLEAR_CMD := clear
	TIME_CMD :=
	INSTALL_CMD := cmd /c install_windows.bat
else ifeq ($(DETECTED_OS), Darwin) # macOS
	PYTHON := $(VENV)/bin/python3
	PIP := $(PYTHON) -m pip
	PYTHON_CMD := python3
	CLEAR_CMD := clear
	TIME_CMD := time
	INSTALL_CMD := bash ./install_macos.sh
else # Unix-like
	PYTHON := $(VENV)/bin/python3
	PIP := $(PYTHON) -m pip
	PYTHON_CMD := python3
	CLEAR_CMD := clear
	TIME_CMD := time
	INSTALL_CMD := bash ./install_linux.sh
endif

# Logs directory
LOG_DIR := ./Logs
CLI_ARGS := $(ARGS)
ifneq ($(strip $(INPUT_DIR)),)
CLI_ARGS += --input-dir "$(INPUT_DIR)"
endif
ifneq ($(strip $(AUDIO_REPORT)),)
CLI_ARGS += --audio-report "$(AUDIO_REPORT)"
endif
ifneq ($(strip $(SUBTITLE_REPORT)),)
CLI_ARGS += --subtitle-report "$(SUBTITLE_REPORT)"
endif
ifneq ($(strip $(FILE)),)
CLI_ARGS += --file "$(FILE)"
endif

# Ensure logs directory exists (cross-platform)
ENSURE_LOG_DIR := @mkdir -p $(LOG_DIR) 2>/dev/null || $(PYTHON_CMD) -c "import os; os.makedirs('$(LOG_DIR)', exist_ok=True)"

# Run-and-log function
# On Windows: simply runs the Python script normally
# On Unix-like systems: supports DETACH variable
#   - If DETACH is set, runs the script in detached mode and tails the log file
#   - Else, runs the script normally
ifeq ($(DETECTED_OS), Windows) # Windows
RUN_AND_LOG = $(PYTHON) $(1)
else
RUN_AND_LOG = \ # Unix-like
if [ -z "$(DETACH)" ]; then \
	$(PYTHON) $(1); \
else \
	LOG_FILE=$(LOG_DIR)/$$(basename $(1) .py).log; \
	nohup $(PYTHON) $(1) > $$LOG_FILE 2>&1 & \
	tail -f $$LOG_FILE; \
fi
endif

# Default target
all: help

# Make Rules
help:
	@echo "Targets:"
	@echo "  make install"
	@echo "  make report ARGS=\"--audio|--subtitles|--audio --subtitles\""
	@echo "  make rename ARGS=\"--video --audio|--subtitles|--video --audio --subtitles\""
	@echo "  make process ARGS=\"--video --audio|--video --audio --subtitles\""
	@echo "  make process ARGS=\"--video --audio\" INPUT_DIR=\"E:/Movies/Test Folder\""
	@echo "  make process-audio-video"
	@echo "  make process-all"

install:
	$(INSTALL_CMD)

run: rename

reports: dependencies
	$(ENSURE_LOG_DIR)
	$(CLEAR_CMD)
	$(call RUN_AND_LOG, ./report.py --audio --subtitles $(CLI_ARGS))

process: dependencies
	$(ENSURE_LOG_DIR)
	$(CLEAR_CMD)
	$(call RUN_AND_LOG, ./auto_track_metadata_renamer.py $(CLI_ARGS))

auto: process

process-audio-video:
	$(MAKE) process ARGS="--video --audio"

process-all:
	$(MAKE) process ARGS="--video --audio --subtitles"

report: dependencies
	$(ENSURE_LOG_DIR)
	$(CLEAR_CMD)
	$(call RUN_AND_LOG, ./report.py $(CLI_ARGS))

subtitle_report: dependencies
	$(ENSURE_LOG_DIR)
	$(CLEAR_CMD)
	$(call RUN_AND_LOG, ./report.py --subtitles $(CLI_ARGS))

rename: dependencies
	$(ENSURE_LOG_DIR)
	$(CLEAR_CMD)
	$(call RUN_AND_LOG, ./track_metadata_renamer.py $(CLI_ARGS))

rename_subtitles: dependencies
	$(ENSURE_LOG_DIR)
	$(CLEAR_CMD)
	$(call RUN_AND_LOG, ./track_metadata_renamer.py --subtitles $(CLI_ARGS))

# Create virtual environment if missing
$(VENV):
	@echo "Creating virtual environment..."
	$(PYTHON_CMD) -m venv $(VENV)
	$(PYTHON) -m pip install --upgrade pip

dependencies: $(VENV)
	@echo "Installing/Updating Python dependencies..."
	$(PIP) install -r requirements.txt

# Generate requirements.txt from current venv
generate_requirements: $(VENV)
	$(PIP) freeze > requirements.txt

# Clean artifacts
clean:
	rm -rf $(VENV) || rmdir /S /Q $(VENV) 2>nul
	find . -type f -name '*.pyc' -delete || del /S /Q *.pyc 2>nul
	find . -type d -name '__pycache__' -delete || rmdir /S /Q __pycache__ 2>nul

.PHONY: all help install run reports process auto process-audio-video process-all report subtitle_report rename rename_subtitles clean dependencies generate_requirements
