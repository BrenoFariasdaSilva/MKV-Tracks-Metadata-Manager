<div align="center">
  
# [MKV Track Metadata Manager.](../README.md) <img src="https://github.com/devicons/devicon/blob/master/icons/python/python-original.svg"  width="3%" height="3%">

</div>

<div align="center">
  
---

Metadata-only Matroska track metadata renamer that generates human-editable audio and embedded-subtitle reports, sets the video track name from the filename, optionally sets selected default audio/subtitle tracks, and applies the selected changes with MKVToolNix `mkvpropedit` without re-encoding or remuxing media.

---

</div>

<div align="center">

![GitHub Build/WorkFlow](https://img.shields.io/github/actions/workflow/status/BrenoFariasDaSilva/Python/update-worked-example-miner-submodule.yml)
![GitHub Code Size in Bytes](https://img.shields.io/github/languages/code-size/BrenoFariasdaSilva/Python)
![GitHub Last Commit](https://img.shields.io/github/last-commit/BrenoFariasdaSilva/Python)
![GitHub](https://img.shields.io/github/license/BrenoFariasdaSilva/Python)

</div>

## Table of Contents
- [MKV Track Metadata Manager. ](#mkv-track-metadata-manager-)
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
		- [Review desired\_new\_name](#review-desired_new_name)
		- [Rename from reviewed reports](#rename-from-reviewed-reports)
		- [Default audio selection](#default-audio-selection)
		- [Default subtitle selection](#default-subtitle-selection)
		- [Integrated process workflow](#integrated-process-workflow)
		- [Logging](#logging)
		- [Direct Python execution](#direct-python-execution)
		- [Dependencies](#dependencies)
	- [Project Structure](#project-structure)
	- [Safety Notes](#safety-notes)
	- [Contributing](#contributing)
	- [Collaborators](#collaborators)
	- [License](#license)
		- [Apache License 2.0](#apache-license-20)

## Introduction

MKV Track Metadata Manager recursively scans the configured input directory for Matroska video files and collects every audio-track occurrence into a prefixed report under `Reports/`. Embedded subtitle tracks are collected separately into a prefixed subtitle report under `Reports/`.

The default input directory is:

```bash
E:/Movies/
```

Supported extensions are:

```bash
.mkv
.mk3d
```

The project modifies only explicitly selected track metadata. The actual file modification is performed by `mkvpropedit`, which edits Matroska metadata in place. The implementation sets one ordinary video track name to the MKV filename stem, applies report-driven audio and embedded-subtitle names, and can optionally set audio/subtitle `flag-default` values. It does not re-encode, remux, remove streams, reorder tracks, change forced flags, change language metadata, alter subtitles, alter chapters, alter attachments, or modify audio/video contents.

Language resolution prefers metadata first. Audio fallback extracts short temporary samples from multiple intermediate portions of the specific audio stream, analyzes them with Whisper, aggregates the sample results conservatively, and leaves the language unknown when confidence is insufficient or samples conflict. Embedded text subtitle fallback extracts the specific subtitle track to a temporary file, reads cues from multiple intermediate timeline regions, detects text language with `langdetect`, aggregates conservatively, and leaves the language unknown when evidence is weak or conflicting. Subtitle type is read from the forced flag first and explicit track-name words second. Image-based subtitles use metadata only. Temporary files are created only for analysis and are cleaned up automatically.

External subtitle files such as `.srt`, `.ass`, `.ssa`, `.vtt`, `.sub`, and `.idx` are ignored.

## Setup

From this project directory:

```bash
cd "MKV Track Metadata Manager"
```

The reviewed-report workflow is:

1. Install dependencies.
2. Generate prefixed reports under `Reports/`.
3. Review and edit `desired_new_name` values.
4. Execute renaming.

The integrated Makefile workflow generates the selected reports and then renames selected track names in one command.

Default report paths are based on the input directory. For `E:/Movies/`, Windows-safe defaults are:

```bash
Reports/E-Movies-audio_report.json
Reports/E-Movies-subtitles_report.json
Reports/E-Movies-audio_unresolved_report.json
```

The colon from `E:` is replaced because `:` is reserved in Windows filenames.

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
- `--audio-report "Reports/E-Movies-audio_report.json"`
- `--subtitle-report "Reports/E-Movies-subtitles_report.json"`
- `--unresolved-audio-report "Reports/E-Movies-audio_unresolved_report.json"`
- `--file "relative/path/Movie.mkv"`

Default audio options:

- `--default-audio-language "English"`

Default subtitle options:

- `--default-subtitle-language "Portuguese"`
- `--disable-forced-subtitles`
- `--disable-default-subtitles`

Makefile path variables:

- `INPUT_DIR="E:/Movies/"`
- `AUDIO_REPORT="Reports/E-Movies-audio_report.json"`
- `SUBTITLE_REPORT="Reports/E-Movies-subtitles_report.json"`
- `UNRESOLVED_AUDIO_REPORT="Reports/E-Movies-audio_unresolved_report.json"`
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

`Reports/<input-prefix>-audio_report.json` groups occurrences by the current audio-track name and occurrence count.

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

`Reports/<input-prefix>-subtitles_report.json` groups embedded subtitle-track occurrences by current subtitle-track name and occurrence count:

```json
{
    "<missing subtitle track name> (2)": {
        "desired_new_name": "",
        "Movie.mkv [subtitle:1 track-id:4 uid:123456789]": "Full Portuguese",
        "Movie.mkv [subtitle:2 track-id:5 uid:987654321]": "Forced Portuguese"
    }
}
```

Subtitle report occurrence values preserve known type before language:

- `Full Portuguese`
- `Forced Portuguese`
- `Full English`
- `Forced English`

The Matroska forced flag has priority for type classification. Existing names containing `Full`, `Complete`, `Completa`, or `Completo` become `Full`. Existing names containing `Forced`, `Forçada`, `Forcado`, `Forçado`, or `Forcada` become `Forced`. When the same canonical language has a Forced track and a non-forced counterpart, the non-forced counterpart becomes `Full`. A single known-language non-forced subtitle with no conflicting type marker is also treated as `Full`. If language is known but type is not safely known, the generated name remains language-only, such as `Portuguese`.

### Review desired_new_name

Edit the generated files under `Reports/` before renaming.

If `desired_new_name` is non-empty, every occurrence in that group uses that value as the target name.

If `desired_new_name` is empty, the renamer falls back to that occurrence's detected language from the report. If both values are empty, the track is skipped safely.

When regenerating prefixed audio or subtitle reports, existing manual `desired_new_name` values are preserved when the corresponding current-name group can be safely matched.

When audio processing is selected, the rename step also writes `Reports/<input-prefix>-audio_unresolved_report.json`. This file uses the same editable audio report shape but contains only audio occurrences that were skipped because no target language/name was available or failed validation during rename. Edit its `desired_new_name` values, then rerun rename against that report:

```powershell
make rename ARGS="--audio" AUDIO_REPORT="Reports/E-Movies-audio_unresolved_report.json" INPUT_DIR="E:/Movies/"
```

To retry unresolved audio while also keeping video naming active:

```powershell
make rename ARGS="--video --audio" AUDIO_REPORT="Reports/E-Movies-audio_unresolved_report.json" INPUT_DIR="E:/Movies/"
```

Use a custom unresolved report path when needed:

```powershell
make rename ARGS="--video --audio" UNRESOLVED_AUDIO_REPORT="Reports/manual_audio_retry.json" INPUT_DIR="E:/Movies/"
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
make rename ARGS="--video --audio --default-audio-language English"
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
mkvpropedit FILE --edit track:=SUBTITLE_UID --set flag-default=1
```

When a Track UID is unavailable, the implementation falls back to the MKVToolNix type ordinal selector:

```bash
mkvpropedit FILE --edit track:aN --set name=NEW_NAME
mkvpropedit FILE --edit track:vN --set name=NEW_NAME
mkvpropedit FILE --edit track:sN --set name=NEW_NAME
```

### Default audio selection

Default-audio selection means setting the Matroska audio-track `flag-default` metadata. It is disabled by default and only runs when `--default-audio-language` is supplied.

The actual Matroska `language` field is not changed. Omitting `--default-audio-language` preserves existing audio default flags.

Video/audio processing without default-audio changes:

```powershell
make process REPORT_ARGS="--audio" RENAME_ARGS="--video --audio"
```

English default:

```powershell
make process REPORT_ARGS="--audio" RENAME_ARGS="--video --audio --default-audio-language English"
```

Portuguese:

```powershell
make process REPORT_ARGS="--audio" RENAME_ARGS="--video --audio --default-audio-language Portuguese"
```

If exactly one audio track resolves to the requested language, that track becomes default and every other audio track is set to `flag-default=0`. If no requested-language audio track exists, existing default audio flags are left unchanged. If multiple requested-language audio tracks exist, existing default audio flags are left unchanged instead of guessing. If the requested-language track is already the only default audio track, no default-flag edit is generated.

### Default subtitle selection

Default-subtitle selection means setting the Matroska embedded subtitle-track `flag-default` metadata. It is disabled by default and only runs when `--default-subtitle-language`, `--disable-forced-subtitles`, or `--disable-default-subtitles` is supplied.

The actual Matroska `language` and `forced` fields are not changed. Omitting `--default-subtitle-language` preserves existing subtitle default flags unless `--disable-forced-subtitles` or `--disable-default-subtitles` is supplied.

Full Portuguese default subtitle:

```powershell
make process REPORT_ARGS="--audio --subtitles" RENAME_ARGS="--video --audio --subtitles --default-subtitle-language Portuguese"
```

English audio default plus Full Portuguese subtitle default:

```powershell
make process REPORT_ARGS="--audio --subtitles" RENAME_ARGS="--video --audio --subtitles --default-audio-language English --default-subtitle-language Portuguese"
```

Disable all default subtitles:

```powershell
make process REPORT_ARGS="--audio --subtitles" RENAME_ARGS="--video --audio --subtitles --disable-default-subtitles"
```

Disable only forced subtitle defaults when a same-language Full subtitle exists:

```powershell
make process REPORT_ARGS="--audio --subtitles" RENAME_ARGS="--video --audio --subtitles --disable-forced-subtitles"
```

English audio default, Full Portuguese subtitle default, and conditional Forced subtitle disabling:

```powershell
make process REPORT_ARGS="--audio --subtitles" RENAME_ARGS="--video --audio --subtitles --default-audio-language English --default-subtitle-language Portuguese --disable-forced-subtitles"
```

If exactly one embedded subtitle resolves to `Full Portuguese`, that track becomes default and other Portuguese subtitle tracks are set to `flag-default=0`. A `Forced Portuguese` subtitle is never used as a fallback target for requested `Full Portuguese`. If no requested full subtitle exists, existing subtitle default flags are left unchanged. If multiple requested full subtitle tracks exist, existing subtitle default flags are left unchanged instead of guessing. If the requested subtitle is already the only default subtitle for that language, no default-flag edit is generated.

`--disable-forced-subtitles` clears `flag-default` only on Forced subtitles whose same canonical language also has a Full subtitle. If only `Forced English` exists and no `Full English` exists, that Forced English default state is preserved. `--disable-default-subtitles` remains as a separate explicit stronger option that clears `flag-default=0` on every embedded subtitle track.

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
make process REPORT_ARGS="--audio --subtitles" RENAME_ARGS="--video --audio --subtitles --default-audio-language English"
```

Everything with English audio default and Full Portuguese subtitle default:

```powershell
make process REPORT_ARGS="--audio --subtitles" RENAME_ARGS="--video --audio --subtitles --default-audio-language English --default-subtitle-language Portuguese"
```

Everything with English audio default, Full Portuguese subtitle default, and conditional Forced subtitle disabling:

```powershell
make process REPORT_ARGS="--audio --subtitles" RENAME_ARGS="--video --audio --subtitles --default-audio-language English --default-subtitle-language Portuguese --disable-forced-subtitles"
```

Same workflow with only `INPUT_DIR` required:

```powershell
make process-all-defaults INPUT_DIR="E:/Movies/"
```

This runs `report.py` first with `REPORT_ARGS`, waits for successful completion, then runs `track_metadata_renamer.py` with `RENAME_ARGS`. `INPUT_DIR`, `AUDIO_REPORT`, `SUBTITLE_REPORT`, and `FILE` Make variables are passed to both stages. The rename stage sets ordinary single video track names from filename stems, consumes the selected report data, re-probes current metadata, validates Track UID and MKVToolNix track ID where available, and applies selected video/audio/subtitle `name=` edits plus optional audio/subtitle `flag-default=` edits for each MKV in one `mkvpropedit` invocation.

When subtitles are not selected, subtitle reports are not generated, subtitle content is not extracted, and subtitle track names are not changed.

40-minute delayed video and audio processing:

```powershell
Start-Sleep -Seconds 2400; make process REPORT_ARGS="--audio" RENAME_ARGS="--video --audio" INPUT_DIR="E:/Movies/"
```

40-minute delayed video and audio processing with explicit English default audio:

```powershell
Start-Sleep -Seconds 2400; make process REPORT_ARGS="--audio" RENAME_ARGS="--video --audio --default-audio-language English" INPUT_DIR="E:/Movies/"
```

40-minute delayed complete processing:

```powershell
Start-Sleep -Seconds 2400; make process REPORT_ARGS="--audio --subtitles" RENAME_ARGS="--video --audio --subtitles" INPUT_DIR="E:/Movies/"
```

40-minute delayed complete processing with explicit English default audio:

```powershell
Start-Sleep -Seconds 2400; make process REPORT_ARGS="--audio --subtitles" RENAME_ARGS="--video --audio --subtitles --default-audio-language English --default-subtitle-language Portuguese --disable-forced-subtitles" INPUT_DIR="E:/Movies/"
```

Unknown audio or subtitle languages are skipped safely. Image-based subtitle tracks are renamed only when reliable metadata resolves the language.

### Logging

Every executable Python entrypoint mirrors terminal output to a matching UTF-8 log file under `Logs/`.

```bash
Logs/report.log
Logs/track_metadata_renamer.log
Logs/auto_track_metadata_renamer.log
Logs/subtitle_report.log
Logs/subtitle_tracks_renamer.log
```

The log files are overwritten each time the corresponding script starts. ANSI terminal color sequences are stripped from file output.

### Direct Python execution

```bash
python report.py --audio --subtitles
python track_metadata_renamer.py --video --audio
python auto_track_metadata_renamer.py --video --audio --subtitles --default-audio-language English
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

- [report.py](report.py): Recursively inspects supported Matroska files under `INPUT_DIR`, detects audio languages, preserves manual report values, and writes prefixed audio reports under `Reports/` safely.
- [subtitle_report.py](subtitle_report.py): Generates prefixed subtitle reports under `Reports/` for embedded subtitle tracks.
- [track_metadata_renamer.py](track_metadata_renamer.py): Reads prefixed audio reports and optional prefixed subtitle reports, resolves audio/subtitle target names, resolves optional default audio/subtitle flag changes, resolves video target names from filename stems, validates current file metadata, writes prefixed unresolved audio reports under `Reports/`, and applies metadata edits.
- [auto_track_metadata_renamer.py](auto_track_metadata_renamer.py): Runs the complete selected report-and-rename workflow.
- [subtitle_tracks_renamer.py](subtitle_tracks_renamer.py): Applies embedded subtitle-track renames from the selected subtitle report only.
- [audio_language_detector.py](audio_language_detector.py): Resolves language from metadata first, then uses distributed temporary audio samples with Whisper only when needed.
- [subtitle_language_detector.py](subtitle_language_detector.py): Resolves embedded subtitle language from metadata first, then text subtitle content when available.
- [mkvpropedit_wrapper.py](mkvpropedit_wrapper.py): Builds and executes safe `mkvpropedit` argument lists for video/audio/subtitle track `name=` metadata and selected audio/subtitle `flag-default=` metadata only.
- [Logger.py](Logger.py): Mirrors executable script terminal output to matching files under `Logs/`.
- [install_windows.bat](install_windows.bat): Windows dependency installer.
- [install_linux.sh](install_linux.sh): Linux dependency installer.
- [install_macos.sh](install_macos.sh): macOS dependency installer.
- [Makefile](Makefile): Provides `help`, `install`, `report`, `reports`, `rename`, `rename_subtitles`, `process`, `process-audio-video`, `process-all`, `process-all-defaults`, `auto`, `run`, `dependencies`, `generate_requirements`, and `clean` targets.
- [requirements.txt](requirements.txt): Python dependency list.

## Safety Notes

This utility modifies Matroska files in place. Review generated reports under `Reports/` carefully before running `make rename`, or test on copies before running `make process`.

The implementation skips files or tracks safely when:

- `INPUT_DIR` is missing.
- The selected audio report is missing or malformed.
- A file was moved or deleted after report generation.
- A file is unsupported, corrupt, or has no audio tracks.
- A file has multiple video tracks and the video target is ambiguous.
- A track has no target name and no detected language.
- Requested default audio language is missing or ambiguous.
- Requested Full default subtitle target is missing or ambiguous.
- An image-based subtitle track has no reliable language metadata.
- The current track name, track ID, or Track UID no longer matches the report.
- `ffprobe`, `mkvmerge`, `ffmpeg`, or `mkvpropedit` is unavailable.
- `mkvpropedit` returns an error for one file.

When default-audio selection is enabled, unsupported language names fail at CLI parsing. `--default-audio-language` also requires `--audio`.

`mkvpropedit` exit codes are handled deliberately:

- `0`: clean success.
- `1`: modification completed with warning, and the warning is surfaced.
- `2` or higher: failure.

## Contributing

Contributions are what make the open-source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**. If you have suggestions for improving the code, your insights will be highly welcome.
In order to contribute to this project, please follow the guidelines below or read the [CONTRIBUTING.md](CONTRIBUTING.md) file for more details on how to contribute to this project, as it contains information about the commit standards and the entire pull request process.
Please follow these guidelines to make your contributions smooth and effective:

1. **Set Up Your Environment**: Ensure you've followed the setup instructions in the [Setup](#setup) section to prepare your development environment.

2. **Make Your Changes**:
   - **Create a Branch**: `git checkout -b feature/YourFeatureName`
   - **Implement Your Changes**: Make sure to test your changes thoroughly.
   - **Commit Your Changes**: Use clear commit messages, for example:
     - For new features: `git commit -m "FEAT: Add some AmazingFeature"`
     - For bug fixes: `git commit -m "FIX: Resolve Issue #123"`
     - For documentation: `git commit -m "DOCS: Update README with new instructions"`
     - For refactorings: `git commit -m "REFACTOR: Enhance component for better aspect"`
     - For snapshots: `git commit -m "SNAPSHOT: Temporary commit to save the current state for later reference"`
   - See more about crafting commit messages in the [CONTRIBUTING.md](CONTRIBUTING.md) file.

3. **Submit Your Contribution**:
   - **Push Your Changes**: `git push origin feature/YourFeatureName`
   - **Open a Pull Request (PR)**: Navigate to the repository on GitHub and open a PR with a detailed description of your changes.

4. **Stay Engaged**: Respond to any feedback from the project maintainers and make necessary adjustments to your PR.

5. **Celebrate**: Once your PR is merged, celebrate your contribution to the project!

## Collaborators

We thank the following people who contributed to this project:

<table>
  <tr>
    <td align="center">
      <a href="#" title="defina o titulo do link">
        <img src="https://github.com/BrenoFariasdaSilva.png" width="100px;" alt="My Profile Picture"/><br>
        <sub>
          <b>Breno Farias da Silva</b>
        </sub>
      </a>
    </td>
  </tr>
</table>

## License

### Apache License 2.0

This project is licensed under the [Apache License 2.0](LICENSE). This license permits use, modification, distribution, and sublicense of the code for both private and commercial purposes, provided that the original copyright notice and a disclaimer of warranty are included in all copies or substantial portions of the software. It also requires a clear attribution back to the original author(s) of the repository. For more details, see the [LICENSE](LICENSE) file in this repository.
