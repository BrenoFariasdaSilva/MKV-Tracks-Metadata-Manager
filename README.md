<div align="center">
  
# [Video Audio Tracks Renamer.](../README.md) <img src="https://github.com/devicons/devicon/blob/master/icons/python/python-original.svg"  width="3%" height="3%">

</div>

<div align="center">
  
---

Metadata-only Matroska track-name renamer that generates human-editable audio and embedded-subtitle reports, sets the video track name from the filename, and applies the selected changes with MKVToolNix `mkvpropedit` without re-encoding or remuxing media.

---

</div>

<div align="center">

![GitHub Build/WorkFlow](https://img.shields.io/github/actions/workflow/status/BrenoFariasDaSilva/Python/update-worked-example-miner-submodule.yml)
![GitHub Code Size in Bytes](https://img.shields.io/github/languages/code-size/BrenoFariasdaSilva/Python)
![GitHub Last Commit](https://img.shields.io/github/last-commit/BrenoFariasdaSilva/Python)
![GitHub](https://img.shields.io/github/license/BrenoFariasdaSilva/Python)

</div>

## Table of Contents
- [Video Audio Tracks Renamer. ](#video-audio-tracks-renamer-)
	- [Table of Contents](#table-of-contents)
	- [Introduction](#introduction)
	- [Setup](#setup)
	- [Installation:](#installation)
		- [Windows](#windows)
		- [Linux](#linux)
		- [macOS](#macos)
	- [Run Python Code:](#run-python-code)
		- [Generate report.json](#generate-reportjson)
		- [Generate subtitles_report.json](#generate-subtitles_reportjson)
		- [Review desired_new_name](#review-desired_new_name)
		- [Rename video and audio track metadata](#rename-video-and-audio-track-metadata)
		- [Direct Python execution](#direct-python-execution)
		- [Dependencies](#dependencies)
	- [Project Structure](#project-structure)
	- [Safety Notes](#safety-notes)
	- [License](#license)
		- [Creative Commons Zero v1.0 Universal](#creative-commons-zero-v10-universal)

## Introduction

Video Audio Tracks Renamer recursively scans the configured input directory for Matroska video files and collects every audio-track occurrence into `report.json`. Embedded subtitle tracks are collected separately into `subtitles_report.json`.

The default input directory is:

```bash
E:/Movies/
```

Supported extensions are:

```bash
.mkv
.mk3d
```

The project renames only track name metadata. The actual file modification is performed by `mkvpropedit`, which edits Matroska metadata in place. The implementation sets one ordinary video track name to the MKV filename stem and applies report-driven audio and embedded-subtitle names. It does not re-encode, remux, remove streams, reorder tracks, change default flags, change forced flags, change language metadata, alter subtitles, alter chapters, alter attachments, or modify audio/video contents.

Language resolution prefers metadata first. Audio fallback extracts short temporary samples from multiple intermediate portions of the specific audio stream, analyzes them with Whisper, aggregates the sample results conservatively, and leaves the language unknown when confidence is insufficient or samples conflict. Embedded text subtitle fallback extracts the specific subtitle track to a temporary file, reads cues from multiple intermediate timeline regions, detects text language with `langdetect`, aggregates conservatively, and leaves the language unknown when evidence is weak or conflicting. Image-based subtitles use metadata only. Temporary files are created only for analysis and are cleaned up automatically.

External subtitle files such as `.srt`, `.ass`, `.ssa`, `.vtt`, `.sub`, and `.idx` are ignored.

## Setup

From this project directory:

```bash
cd "Video Audio Tracks Renamer"
```

The intended workflow is:

1. Install dependencies.
2. Generate `report.json` and `subtitles_report.json`.
3. Review and edit `desired_new_name` values.
4. Execute renaming.

## Installation:

The installation scripts create or reuse the local `venv`, install Python packages from `requirements.txt`, install or verify FFmpeg/ffprobe, install or verify MKVToolNix, and verify that `ffmpeg`, `ffprobe`, `mkvpropedit`, and `mkvmerge` can run.

You can use the Makefile installer target:

```bash
make install
```

### Windows

```bash
install_windows.bat
```

The Windows installer uses Chocolatey when available, otherwise winget when available. It fails clearly if neither package manager is available.

### Linux

```bash
bash ./install_linux.sh
```

The Linux installer supports `apt-get`, `dnf`, and `pacman`. It installs command-line packages only.

### macOS

```bash
bash ./install_macos.sh
```

The macOS installer requires Homebrew and installs `ffmpeg` and the `mkvtoolnix` command-line tools.

## Run Python Code:

### Generate report.json

```bash
make report
```

This runs `report.py` and writes `report.json` in this project directory. The report groups occurrences by the current audio-track name and occurrence count.

Each occurrence key includes the relative file path, the audio ordinal, the MKVToolNix track ID, and the Matroska Track UID when available:

```json
{
    "English (2)": {
        "desired_new_name": "English",
        "Movie.mkv [audio:1 track-id:2 uid:123456789]": "English",
        "Show/Episode.mkv [audio:2 track-id:3 uid:987654321]": "English"
    }
}
```

### Generate subtitles_report.json

```bash
make subtitle_report
```

or generate both reports:

```bash
make reports
```

`subtitles_report.json` groups embedded subtitle-track occurrences by current subtitle-track name and occurrence count:

```json
{
    "<missing subtitle track name> (2)": {
        "desired_new_name": "",
        "Movie.mkv [subtitle:1 track-id:4 uid:123456789]": "Portuguese",
        "Movie.mkv [subtitle:2 track-id:5 uid:987654321]": "English"
    }
}
```

### Review desired_new_name

Edit `report.json` and `subtitles_report.json` before renaming.

If `desired_new_name` is non-empty, every occurrence in that group uses that value as the target name.

If `desired_new_name` is empty, the renamer falls back to that occurrence's detected language from the report. If both values are empty, the track is skipped safely.

When regenerating `report.json`, existing manual `desired_new_name` values are preserved when the corresponding current-name group can be safely matched.

### Rename video and audio track metadata

```bash
make rename
```

This runs `audio_tracks_renamer.py`, consumes `report.json` and optional `subtitles_report.json`, re-probes each file, sets the single video track name to the exact filename stem, verifies each audio/subtitle track still matches its report, and applies one `mkvpropedit` invocation per file when one or more track names need renaming.

Subtitle-only renaming is available with:

```bash
make rename_subtitles
```

For example:

```bash
300 2006 1080p Dual.mkv
```

sets the video track name to:

```bash
300 2006 1080p Dual
```

If an MKV contains multiple video tracks, the video rename is skipped for that file instead of guessing which video track should be renamed.

`mkvpropedit` uses the Matroska Track UID selector when available:

```bash
mkvpropedit FILE --edit track:=UID --set name=NEW_NAME
```

When a Track UID is unavailable, the implementation falls back to the MKVToolNix type ordinal selector:

```bash
mkvpropedit FILE --edit track:aN --set name=NEW_NAME
mkvpropedit FILE --edit track:vN --set name=NEW_NAME
mkvpropedit FILE --edit track:sN --set name=NEW_NAME
```

### Direct Python execution

```bash
python report.py
python subtitle_report.py
python audio_tracks_renamer.py
python subtitle_tracks_renamer.py
```

### Dependencies

1. Install the project dependencies and external tools with the following command:

```bash
make install
```

or install only Python dependencies with:

```bash
make dependencies
```

or:

```bash
pip install -r requirements.txt
```

External executables required by the final workflow:

- `ffmpeg`
- `ffprobe`
- `mkvmerge`
- `mkvpropedit`

Python packages are defined only in [requirements.txt](requirements.txt).

## Project Structure

- [report.py](report.py): Recursively inspects supported Matroska files under `INPUT_DIR`, detects audio languages, preserves manual report values, and writes `report.json` safely.
- [subtitle_report.py](subtitle_report.py): Generates `subtitles_report.json` for embedded subtitle tracks.
- [audio_tracks_renamer.py](audio_tracks_renamer.py): Reads `report.json` and optional `subtitles_report.json`, resolves audio/subtitle target names, resolves video target names from filename stems, validates current file metadata, skips unsafe entries, and applies renames.
- [subtitle_tracks_renamer.py](subtitle_tracks_renamer.py): Applies embedded subtitle-track renames from `subtitles_report.json` only.
- [audio_language_detector.py](audio_language_detector.py): Resolves language from metadata first, then uses distributed temporary audio samples with Whisper only when needed.
- [subtitle_language_detector.py](subtitle_language_detector.py): Resolves embedded subtitle language from metadata first, then text subtitle content when available.
- [mkvpropedit_wrapper.py](mkvpropedit_wrapper.py): Builds and executes safe `mkvpropedit` argument lists for video/audio/subtitle track `name=` metadata only.
- [install_windows.bat](install_windows.bat): Windows dependency installer.
- [install_linux.sh](install_linux.sh): Linux dependency installer.
- [install_macos.sh](install_macos.sh): macOS dependency installer.
- [Makefile](Makefile): Provides `install`, `report`, `subtitle_report`, `reports`, `rename`, `rename_subtitles`, `run`, `dependencies`, `generate_requirements`, and `clean` targets.
- [requirements.txt](requirements.txt): Python dependency list.

## Safety Notes

This utility modifies Matroska files in place. Review `report.json` and `subtitles_report.json` carefully before running `make rename`.

The implementation skips files or tracks safely when:

- `INPUT_DIR` is missing.
- `report.json` is missing or malformed.
- A file was moved or deleted after report generation.
- A file is unsupported, corrupt, or has no audio tracks.
- A file has multiple video tracks and the video target is ambiguous.
- A track has no target name and no detected language.
- An image-based subtitle track has no reliable language metadata.
- The current track name, track ID, or Track UID no longer matches the report.
- `ffprobe`, `mkvmerge`, `ffmpeg`, or `mkvpropedit` is unavailable.
- `mkvpropedit` returns an error for one file.

`mkvpropedit` exit codes are handled deliberately:

- `0`: clean success.
- `1`: modification completed with warning, and the warning is surfaced.
- `2` or higher: failure.

## License

### Creative Commons Zero v1.0 Universal

This project is licensed under the [Creative Commons Zero v1.0 Universal](../LICENSE), which means you are free to use, modify, and distribute the code, as long as you include the license and attribute the original author for the repository. See the [LICENSE](../LICENSE) file for more details.
