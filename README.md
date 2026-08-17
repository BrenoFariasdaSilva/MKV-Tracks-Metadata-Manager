<div align="center">
  
# [MKV Track Metadata Renamer.](../README.md) <img src="https://github.com/devicons/devicon/blob/master/icons/python/python-original.svg"  width="3%" height="3%">

</div>

<div align="center">
  
---

Metadata-only Matroska track metadata renamer that generates human-editable audio and embedded-subtitle reports, sets the video track name from the filename, optionally sets a selected default audio language, and applies the selected changes with MKVToolNix `mkvpropedit` without re-encoding or remuxing media.

---

</div>

<div align="center">

![GitHub Build/WorkFlow](https://img.shields.io/github/actions/workflow/status/BrenoFariasDaSilva/Python/update-worked-example-miner-submodule.yml)
![GitHub Code Size in Bytes](https://img.shields.io/github/languages/code-size/BrenoFariasdaSilva/Python)
![GitHub Last Commit](https://img.shields.io/github/last-commit/BrenoFariasdaSilva/Python)
![GitHub](https://img.shields.io/github/license/BrenoFariasdaSilva/Python)

</div>

## Table of Contents
- [MKV Track Metadata Renamer. ](#mkv-track-metadata-renamer-)
	- [Table of Contents](#table-of-contents)
	- [Introduction](#introduction)
	- [Setup](#setup)
	- [Installation:](#installation)
		- [Windows](#windows)
		- [Linux](#linux)
		- [macOS](#macos)
	- [Run Python Code:](#run-python-code)
		- [Makefile CLI](#makefile-cli)
		- [Generate reports](#generate-reports)
		- [Review desired_new_name](#review-desired_new_name)
		- [Rename from reviewed reports](#rename-from-reviewed-reports)
		- [Default audio selection](#default-audio-selection)
		- [Integrated process workflow](#integrated-process-workflow)
		- [Direct Python execution](#direct-python-execution)
		- [Dependencies](#dependencies)
	- [Project Structure](#project-structure)
	- [Safety Notes](#safety-notes)
	- [License](#license)
		- [Creative Commons Zero v1.0 Universal](#creative-commons-zero-v10-universal)

## Introduction

MKV Track Metadata Renamer recursively scans the configured input directory for Matroska video files and collects every audio-track occurrence into `audio_report.json`. Embedded subtitle tracks are collected separately into `subtitles_report.json`.

The default input directory is:

```bash
E:/Movies/
```

Supported extensions are:

```bash
.mkv
.mk3d
```

The project modifies only explicitly selected track metadata. The actual file modification is performed by `mkvpropedit`, which edits Matroska metadata in place. The implementation sets one ordinary video track name to the MKV filename stem, applies report-driven audio and embedded-subtitle names, and can optionally set audio `flag-default` values. It does not re-encode, remux, remove streams, reorder tracks, change forced flags, change language metadata, alter subtitles, alter chapters, alter attachments, or modify audio/video contents.

Language resolution prefers metadata first. Audio fallback extracts short temporary samples from multiple intermediate portions of the specific audio stream, analyzes them with Whisper, aggregates the sample results conservatively, and leaves the language unknown when confidence is insufficient or samples conflict. Embedded text subtitle fallback extracts the specific subtitle track to a temporary file, reads cues from multiple intermediate timeline regions, detects text language with `langdetect`, aggregates conservatively, and leaves the language unknown when evidence is weak or conflicting. Image-based subtitles use metadata only. Temporary files are created only for analysis and are cleaned up automatically.

External subtitle files such as `.srt`, `.ass`, `.ssa`, `.vtt`, `.sub`, and `.idx` are ignored.

## Setup

From this project directory:

```bash
cd "MKV Track Metadata Renamer"
```

The reviewed-report workflow is:

1. Install dependencies.
2. Generate `audio_report.json` and `subtitles_report.json`.
3. Review and edit `desired_new_name` values.
4. Execute renaming.

The integrated Makefile workflow generates the selected reports and then renames selected track names in one command.

## Installation:

The installation scripts create or reuse the local `venv`, install Python packages from `requirements.txt`, install or verify FFmpeg/ffprobe, install or verify MKVToolNix, and verify that `ffmpeg`, `ffprobe`, `mkvpropedit`, `mkvmerge`, and `mkvextract` can run.

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

### Makefile CLI

All Makefile Python targets use the project `venv` automatically. Do not activate the virtual environment manually.

Forward CLI options to individual `report` and `rename` targets with `ARGS="..."`:

```bash
make help
make report ARGS="--audio"
make rename ARGS="--video --audio"
```

Forward separate CLI options to the integrated `process` target with `REPORT_ARGS="..."` and `RENAME_ARGS="..."`:

```bash
make process REPORT_ARGS="--audio" RENAME_ARGS="--video --audio"
make process REPORT_ARGS="--audio --subtitles" RENAME_ARGS="--video --audio --subtitles"
```

Supported processing flags:

- `--video`
- `--audio`
- `--subtitles`

Common CLI path options:

- `--input-dir "E:/Movies/"`
- `--audio-report "audio_report.json"`
- `--subtitle-report "subtitles_report.json"`
- `--unresolved-audio-report "audio_unresolved_report.json"`
- `--file "relative/path/Movie.mkv"`

Default audio options:

- `--set-default-audio`
- `--no-set-default-audio`
- `--default-audio-language "English"`

Makefile path variables:

- `INPUT_DIR="E:/Movies/"`
- `AUDIO_REPORT="audio_report.json"`
- `SUBTITLE_REPORT="subtitles_report.json"`
- `UNRESOLVED_AUDIO_REPORT="audio_unresolved_report.json"`
- `FILE="relative/path/Movie.mkv"`

PowerShell path with spaces through Make:

```powershell
make process REPORT_ARGS="--audio" RENAME_ARGS="--video --audio" INPUT_DIR="E:/Movies/Test Folder"
```

Single-file processing:

```powershell
make process REPORT_ARGS="--audio" RENAME_ARGS="--video --audio" FILE="Dual/300 2006 1080p Dual/300 2006 1080p Dual.mkv"
```

The `--file` value must name one exact supported MKV under `--input-dir`. No fuzzy matching is used.

### Generate reports

Audio report only:

```powershell
make report ARGS="--audio"
```

Subtitle report only:

```powershell
make report ARGS="--subtitles"
```

Both reports:

```powershell
make report ARGS="--audio --subtitles"
```

`--video` is accepted by report generation but creates no report, because video track names are derived from filename stems.

`audio_report.json` groups occurrences by the current audio-track name and occurrence count.

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

Edit `audio_report.json` and `subtitles_report.json` before renaming.

If `desired_new_name` is non-empty, every occurrence in that group uses that value as the target name.

If `desired_new_name` is empty, the renamer falls back to that occurrence's detected language from the report. If both values are empty, the track is skipped safely.

When regenerating `audio_report.json` or `subtitles_report.json`, existing manual `desired_new_name` values are preserved when the corresponding current-name group can be safely matched.

When audio processing is selected, the rename step also writes `audio_unresolved_report.json`. This file uses the same editable audio report shape but contains only audio occurrences that were skipped because no target language/name was available or failed validation during rename. Edit its `desired_new_name` values, then rerun rename against that report:

```powershell
make rename ARGS="--audio" AUDIO_REPORT="audio_unresolved_report.json" INPUT_DIR="E:/Movies/"
```

To retry unresolved audio while also keeping video naming active:

```powershell
make rename ARGS="--video --audio" AUDIO_REPORT="audio_unresolved_report.json" INPUT_DIR="E:/Movies/"
```

Use a custom unresolved report path when needed:

```powershell
make rename ARGS="--video --audio" UNRESOLVED_AUDIO_REPORT="manual_audio_retry.json" INPUT_DIR="E:/Movies/"
```

### Rename from reviewed reports

```bash
make rename ARGS="--video --audio"
```

This runs `track_metadata_renamer.py`, consumes only the selected report files, re-probes each file, sets selected video track names to exact filename stems, verifies selected audio/subtitle tracks still match their reports, and applies one `mkvpropedit` invocation per file when one or more track names need renaming.

Reviewed all-track rename:

```powershell
make rename ARGS="--video --audio --subtitles"
```

Reviewed video/audio rename and make English audio default:

```powershell
make rename ARGS="--video --audio --set-default-audio --default-audio-language English"
```

Subtitle-only renaming:

```bash
make rename ARGS="--subtitles"
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
mkvpropedit FILE --edit track:=AUDIO_UID --set flag-default=1
```

When a Track UID is unavailable, the implementation falls back to the MKVToolNix type ordinal selector:

```bash
mkvpropedit FILE --edit track:aN --set name=NEW_NAME
mkvpropedit FILE --edit track:vN --set name=NEW_NAME
mkvpropedit FILE --edit track:sN --set name=NEW_NAME
```

### Default audio selection

Default-audio selection means setting the Matroska audio-track `flag-default` metadata. It is disabled by default and only runs when `--set-default-audio` is supplied.

Preferred default audio language defaults to:

```bash
English
```

The actual Matroska `language` field is not changed. Supplying `--default-audio-language` without `--set-default-audio` does not change default flags.

Video/audio processing without default-audio changes:

```powershell
make process REPORT_ARGS="--audio" RENAME_ARGS="--video --audio"
```

English default:

```powershell
make process REPORT_ARGS="--audio" RENAME_ARGS="--video --audio --set-default-audio"
```

Explicit English with language option:

```powershell
make process REPORT_ARGS="--audio" RENAME_ARGS="--video --audio --set-default-audio --default-audio-language English"
```

Portuguese:

```powershell
make process REPORT_ARGS="--audio" RENAME_ARGS="--video --audio --set-default-audio --default-audio-language Portuguese"
```

Disable default-audio changes:

```powershell
make process REPORT_ARGS="--audio" RENAME_ARGS="--video --audio --no-set-default-audio"
```

If exactly one audio track resolves to the requested language, that track becomes default and every other audio track is set to `flag-default=0`. If no requested-language audio track exists, existing default audio flags are left unchanged. If multiple requested-language audio tracks exist, existing default audio flags are left unchanged instead of guessing. If the requested-language track is already the only default audio track, no default-flag edit is generated.

### Integrated process workflow

Video and audio only:

```powershell
make process REPORT_ARGS="--audio" RENAME_ARGS="--video --audio"
```

Everything:

```powershell
make process REPORT_ARGS="--audio --subtitles" RENAME_ARGS="--video --audio --subtitles"
```

Everything with English audio default:

```powershell
make process REPORT_ARGS="--audio --subtitles" RENAME_ARGS="--video --audio --subtitles --set-default-audio --default-audio-language English"
```

This runs `report.py` first with `REPORT_ARGS`, waits for successful completion, then runs `track_metadata_renamer.py` with `RENAME_ARGS`. `INPUT_DIR`, `AUDIO_REPORT`, `SUBTITLE_REPORT`, and `FILE` Make variables are passed to both stages. The rename stage sets ordinary single video track names from filename stems, consumes the selected report data, re-probes current metadata, validates Track UID and MKVToolNix track ID where available, and applies selected video/audio/subtitle `name=` edits plus optional audio `flag-default=` edits for each MKV in one `mkvpropedit` invocation.

When subtitles are not selected, subtitle reports are not generated, subtitle content is not extracted, and subtitle track names are not changed.

40-minute delayed video and audio processing:

```powershell
Start-Sleep -Seconds 2400; make process REPORT_ARGS="--audio" RENAME_ARGS="--video --audio" INPUT_DIR="E:/Movies/"
```

40-minute delayed video and audio processing with explicit English default audio:

```powershell
Start-Sleep -Seconds 2400; make process REPORT_ARGS="--audio" RENAME_ARGS="--video --audio --set-default-audio --default-audio-language English" INPUT_DIR="E:/Movies/"
```

40-minute delayed complete processing:

```powershell
Start-Sleep -Seconds 2400; make process REPORT_ARGS="--audio --subtitles" RENAME_ARGS="--video --audio --subtitles" INPUT_DIR="E:/Movies/"
```

40-minute delayed complete processing with explicit English default audio:

```powershell
Start-Sleep -Seconds 2400; make process REPORT_ARGS="--audio --subtitles" RENAME_ARGS="--video --audio --subtitles --set-default-audio --default-audio-language English" INPUT_DIR="E:/Movies/"
```

Unknown audio or subtitle languages are skipped safely. Image-based subtitle tracks are renamed only when reliable metadata resolves the language.

### Direct Python execution

```bash
python report.py --audio --subtitles
python track_metadata_renamer.py --video --audio
python auto_track_metadata_renamer.py --video --audio --subtitles --set-default-audio
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
- `mkvextract`

Python packages are defined only in [requirements.txt](requirements.txt).

## Project Structure

- [report.py](report.py): Recursively inspects supported Matroska files under `INPUT_DIR`, detects audio languages, preserves manual report values, and writes `audio_report.json` safely.
- [subtitle_report.py](subtitle_report.py): Generates `subtitles_report.json` for embedded subtitle tracks.
- [track_metadata_renamer.py](track_metadata_renamer.py): Reads `audio_report.json` and optional `subtitles_report.json`, resolves audio/subtitle target names, resolves optional default audio flag changes, resolves video target names from filename stems, validates current file metadata, writes `audio_unresolved_report.json` for actionable audio skips/failures, and applies metadata edits.
- [auto_track_metadata_renamer.py](auto_track_metadata_renamer.py): Runs the complete selected report-and-rename workflow.
- [subtitle_tracks_renamer.py](subtitle_tracks_renamer.py): Applies embedded subtitle-track renames from `subtitles_report.json` only.
- [audio_language_detector.py](audio_language_detector.py): Resolves language from metadata first, then uses distributed temporary audio samples with Whisper only when needed.
- [subtitle_language_detector.py](subtitle_language_detector.py): Resolves embedded subtitle language from metadata first, then text subtitle content when available.
- [mkvpropedit_wrapper.py](mkvpropedit_wrapper.py): Builds and executes safe `mkvpropedit` argument lists for video/audio/subtitle track `name=` metadata and selected audio `flag-default=` metadata only.
- [install_windows.bat](install_windows.bat): Windows dependency installer.
- [install_linux.sh](install_linux.sh): Linux dependency installer.
- [install_macos.sh](install_macos.sh): macOS dependency installer.
- [Makefile](Makefile): Provides `help`, `install`, `report`, `reports`, `rename`, `rename_subtitles`, `process`, `process-audio-video`, `process-all`, `auto`, `run`, `dependencies`, `generate_requirements`, and `clean` targets.
- [requirements.txt](requirements.txt): Python dependency list.

## Safety Notes

This utility modifies Matroska files in place. Review `audio_report.json` and `subtitles_report.json` carefully before running `make rename`, or test on copies before running `make process`.

The implementation skips files or tracks safely when:

- `INPUT_DIR` is missing.
- `audio_report.json` is missing or malformed.
- A file was moved or deleted after report generation.
- A file is unsupported, corrupt, or has no audio tracks.
- A file has multiple video tracks and the video target is ambiguous.
- A track has no target name and no detected language.
- Requested default audio language is missing or ambiguous.
- An image-based subtitle track has no reliable language metadata.
- The current track name, track ID, or Track UID no longer matches the report.
- `ffprobe`, `mkvmerge`, `ffmpeg`, or `mkvpropedit` is unavailable.
- `mkvpropedit` returns an error for one file.

When default-audio selection is enabled, unsupported language names fail at CLI parsing. `--set-default-audio` also requires `--audio`.

`mkvpropedit` exit codes are handled deliberately:

- `0`: clean success.
- `1`: modification completed with warning, and the warning is surfaced.
- `2` or higher: failure.

## License

### Creative Commons Zero v1.0 Universal

This project is licensed under the [Creative Commons Zero v1.0 Universal](../LICENSE), which means you are free to use, modify, and distribute the code, as long as you include the license and attribute the original author for the repository. See the [LICENSE](../LICENSE) file for more details.
