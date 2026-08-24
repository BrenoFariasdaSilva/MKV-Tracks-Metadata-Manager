"""
================================================================================
Subtitle Language Detector
================================================================================
Author      : Breno Farias da Silva
Created     : 2026-08-15
Description :
    Detects the language of embedded subtitle tracks in Matroska video files
    using a two-stage approach: metadata inspection first, then fallback to
    text analysis when metadata is unavailable or unreliable.

    Key features include:
        - Metadata-first language detection from subtitle properties
        - Subtitle extraction and text-based language detection
        - Codec-aware extraction strategies (ASS, SRT, PGS, etc.)
        - Configurable text sampling for performance
        - Language normalization to ISO 639-2 codes
        - Context-aware type detection (forced, hearing-impaired, etc.)

Usage:
    1. Import and call detect_subtitle_track_language() with file and metadata
    2. Provide stream index, codec details, and optional duration
    3. Optional: Enable text-based detection for untagged subtitles
        $ python -c "from subtitle_language_detector import detect_subtitle_track_language"
    4. Returns ISO 639-2 language code or empty string if detection fails

Outputs:
    - ISO 639-2 language codes (e.g., "eng", "por", "spa")
    - Empty string if language cannot be determined
    - Detailed logging for text extraction and detection

TODOs:
    - Implement OCR-based detection for bitmap subtitles (PGS, VOBSUB)
    - Add confidence scoring and language probability distribution
    - Support for polyglot subtitle detection (multiple languages)
    - Cache extracted subtitle text between successive analyses

Dependencies:
    - Python >= 3.8
    - langdetect >= 1.0.9 (for text-based language detection)
    - re (standard library, for text parsing)
    - pathlib (standard library)

Assumptions & Notes:
    - Subtitles with valid BCP 47 language tags are trusted implicitly
    - Text extraction requires mkvextract or similar tool availability
    - Small text samples may result in unreliable detection
    - PGS and VOBSUB formats cannot be reliably detected via text analysis
"""

from __future__ import annotations  # Enable modern annotations on supported Python versions.

from collections import Counter  # Aggregate regional language votes.
import importlib  # Load optional text detector lazily.
import importlib.util  # Detect optional text detector without hard import errors.
from pathlib import Path  # Represent media and temporary subtitle paths.
import re  # Parse subtitle timestamps and clean subtitle markup.
import subprocess  # Extract embedded subtitle tracks with mkvextract.
import tempfile  # Own temporary extraction directories.
from typing import Any  # Type dynamic subtitle metadata and detector data.

from audio_language_detector import SAMPLE_FRACTIONS, metadata_language_values, normalize_subtitle_language_value, normalize_text  # Reuse metadata collection and subtitle-aware language normalization.
from mkvpropedit_wrapper import find_executable  # Locate MKVToolNix command-line tools.


SUBTITLE_REGION_SECONDS = 240.0  # Read multi-minute subtitle windows for meaningful text.
MIN_REGION_CHARACTERS = 80  # Require enough text per region.
MIN_VALID_REGIONS = 2  # Require more than one useful subtitle region.
MIN_LANGUAGE_PROBABILITY = 0.85  # Require strong text detector confidence.
MIN_WINNING_RATIO = 0.67  # Require conservative regional agreement.
TEXT_SUBTITLE_CODEC_PREFIXES = ("S_TEXT/",)  # Identify text subtitle codecs from Matroska codec IDs.
TEXT_SUBTITLE_CODEC_NAMES = ("SubRip", "SubStationAlpha", "WebVTT")  # Identify text subtitle codecs from MKVToolNix names.
PORTUGUESE_REGION_MIN_SCORE = 2  # Require at least two strong regional hits before trusting PT-BR/PT-PT classification.
PORTUGUESE_REGION_SCORE_MARGIN = 2  # Require a clear winner between Brazilian and European Portuguese markers.

BRAZILIAN_PORTUGUESE_MARKERS = {
    "voce",
    "voces",
    "voces vao",
    "voce vai",
    "pra",
    "pro",
    "para a gente",
    "a gente",
    "cara",
    "tchau",
    "legal",
    "onibus",
    "trem",
    "celular",
    "camiseta",
    "banheiro",
    "suco",
    "fazenda",
}

EUROPEAN_PORTUGUESE_MARKERS = {
    "tu",
    "estas",
    "estavas",
    "fixe",
    "giro",
    "autocarro",
    "comboio",
    "telemovel",
    "t shirt",
    "casa de banho",
    "sumo",
    "miudo",
    "miuda",
    "rapariga",
    "rapaz",
    "adeus",
    "pois",
}


def subtitle_codec_is_text(codec_id: str, codec_name: str) -> bool:
    """
    Resolve whether a subtitle codec contains directly readable text.

    :param codec_id: Matroska codec ID.
    :param codec_name: MKVToolNix codec display name.
    :return: True when subtitle text can be extracted safely.
    """

    normalized_codec_id = codec_id.strip()  # Normalize codec ID spacing.
    normalized_codec_name = codec_name.strip()  # Normalize codec name spacing.
    if any(normalized_codec_id.startswith(prefix) for prefix in TEXT_SUBTITLE_CODEC_PREFIXES):  # Verify known text codec ID prefix.
        return True  # Return text subtitle result.
    return any(name in normalized_codec_name for name in TEXT_SUBTITLE_CODEC_NAMES)  # Return known text codec name result.


def extract_subtitle_track(file_path: Path, track_id: int, output_path: Path) -> bool:
    """
    Extract one embedded subtitle track to a temporary file.

    :param file_path: Matroska file path.
    :param track_id: MKVToolNix track ID.
    :param output_path: Temporary subtitle output path.
    :return: True when extraction succeeds.
    """

    executable = find_executable("mkvextract")  # Locate mkvextract executable.
    if executable is None:  # Verify mkvextract is available.
        print(f"mkvextract unavailable for subtitle detection: executable not found")  # Report missing tool.
        return False  # Return failed extraction.

    command = [executable, "tracks", str(file_path), f"{track_id}:{output_path}"]  # Build stream-specific extraction command.
    try:  # Run mkvextract safely.
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)  # Execute subtitle extraction.
    except OSError as error:  # Handle unavailable mkvextract.
        print(f"mkvextract unavailable for subtitle detection: {error}")  # Report extraction failure.
        return False  # Return failed extraction.

    if result.returncode not in {0, 1}:  # Verify MKVToolNix did not fail.
        print(f"mkvextract subtitle extraction failed for {file_path}: {result.stderr.strip()}")  # Report extraction error.
        return False  # Return failed extraction.
    return output_path.exists() and output_path.stat().st_size > 0  # Return whether subtitle file exists with content.


def read_subtitle_text(subtitle_path: Path) -> str:
    """
    Read extracted subtitle text safely.

    :param subtitle_path: Extracted temporary subtitle path.
    :return: Subtitle text.
    """

    for encoding_name in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):  # Iterate common subtitle encodings.
        try:  # Try one encoding.
            return subtitle_path.read_text(encoding=encoding_name)  # Return decoded subtitle text.
        except UnicodeDecodeError:  # Handle wrong encoding.
            continue  # Try next encoding.
        except OSError as error:  # Handle unreadable file.
            print(f"subtitle text could not be read: {error}")  # Report read failure.
            return ""  # Return empty text.
    return ""  # Return empty text when decoding fails.


def parse_subtitle_time(value: str) -> float | None:
    """
    Parse one subtitle timestamp into seconds.

    :param value: Subtitle timestamp text.
    :return: Timestamp seconds or None.
    """

    cleaned_value = value.strip().replace(",", ".")  # Normalize decimal separator.
    parts = cleaned_value.split(":")  # Split timestamp parts.
    try:  # Convert timestamp parts.
        if len(parts) == 3:  # Verify hour-minute-second form.
            return int(parts[0]) * 3600.0 + int(parts[1]) * 60.0 + float(parts[2])  # Return parsed timestamp.
        if len(parts) == 2:  # Verify minute-second form.
            return int(parts[0]) * 60.0 + float(parts[1])  # Return parsed timestamp.
    except ValueError:  # Handle malformed timestamp.
        return None  # Return no timestamp.
    return None  # Return no timestamp.


def clean_subtitle_text(value: str) -> str:
    """
    Remove subtitle markup and timing noise from text.

    :param value: Raw subtitle cue text.
    :return: Cleaned subtitle cue text.
    """

    text = re.sub(r"\{\\[^}]*\}", " ", value)  # Remove ASS override tags.
    text = re.sub(r"<[^>]+>", " ", text)  # Remove HTML-like subtitle tags.
    text = re.sub(r"\[[^\]]{0,40}\]", " ", text)  # Remove short bracket annotations.
    text = re.sub(r"\([^)]{0,40}\)", " ", text)  # Remove short parenthetical annotations.
    text = re.sub(r"\\[Nn]", " ", text)  # Convert ASS line breaks.
    text = re.sub(r"\s+", " ", text).strip()  # Collapse whitespace.
    return text  # Return cleaned text.


def parse_text_subtitle_cues(subtitle_text: str) -> list[tuple[float, str]]:
    """
    Parse timestamped text cues from common text subtitle formats.

    :param subtitle_text: Extracted subtitle text.
    :return: Cue start times and cleaned cue text.
    """

    cues: list[tuple[float, str]] = []  # Store parsed subtitle cues.
    lines = subtitle_text.splitlines()  # Split subtitle text into lines.
    current_time: float | None = None  # Store current cue start time.
    current_text: list[str] = []  # Store current cue text lines.

    for line in lines:  # Iterate subtitle lines.
        stripped_line = line.strip()  # Normalize line spacing.
        dialogue_match = re.match(r"^Dialogue:[^,]*,(?P<start>[^,]+),(?P<end>[^,]+),(?:[^,]*,){6}(?P<text>.*)$", stripped_line)  # Parse ASS dialogue line.
        if dialogue_match is not None:  # Verify ASS dialogue cue exists.
            start_time = parse_subtitle_time(dialogue_match.group("start"))  # Parse ASS start time.
            cue_text = clean_subtitle_text(dialogue_match.group("text"))  # Clean ASS cue text.
            if start_time is not None and cue_text != "":  # Verify cue is usable.
                cues.append((start_time, cue_text))  # Store ASS cue.
            continue  # Continue to next line.

        time_match = re.search(r"(?P<start>\d{1,2}:\d{2}:\d{2}[\.,]\d{1,3}|\d{1,2}:\d{2}[\.,]\d{1,3})\s+-->", stripped_line)  # Parse SRT or VTT timing line.
        if time_match is not None:  # Verify timing cue exists.
            if current_time is not None and current_text:  # Verify prior cue has text.
                cleaned_text = clean_subtitle_text(" ".join(current_text))  # Clean prior cue text.
                if cleaned_text != "":  # Verify prior text is usable.
                    cues.append((current_time, cleaned_text))  # Store prior cue.
            current_time = parse_subtitle_time(time_match.group("start"))  # Store new cue start.
            current_text = []  # Reset cue text.
            continue  # Continue to next line.

        if current_time is not None and stripped_line != "" and not stripped_line.isdigit():  # Verify line belongs to current cue.
            current_text.append(stripped_line)  # Add cue text line.

    if current_time is not None and current_text:  # Verify final cue has text.
        cleaned_text = clean_subtitle_text(" ".join(current_text))  # Clean final cue text.
        if cleaned_text != "":  # Verify final text is usable.
            cues.append((current_time, cleaned_text))  # Store final cue.

    return cues  # Return parsed cues.


def collect_region_texts(cues: list[tuple[float, str]], duration_seconds: float) -> list[str]:
    """
    Collect subtitle text from distributed timeline regions.

    :param cues: Parsed subtitle cues.
    :param duration_seconds: Media duration in seconds.
    :return: Region text samples.
    """

    if not cues:  # Verify cues exist.
        return []  # Return no region text.

    last_cue_time = max(time_value for time_value, cue_text in cues if cue_text != "")  # Read final useful cue time.
    useful_duration = duration_seconds if duration_seconds > 0.0 else last_cue_time  # Resolve usable duration.
    region_texts: list[str] = []  # Store collected region texts.
    for fraction in SAMPLE_FRACTIONS:  # Iterate distributed timeline positions.
        center_time = useful_duration * fraction  # Calculate region center.
        start_time = max(0.0, center_time - SUBTITLE_REGION_SECONDS * 0.5)  # Calculate region start.
        end_time = min(useful_duration, center_time + SUBTITLE_REGION_SECONDS * 0.5)  # Calculate region end.
        selected_text = " ".join(cue_text for cue_time, cue_text in cues if start_time <= cue_time <= end_time)  # Collect cue text in region.
        cleaned_text = clean_subtitle_text(selected_text)  # Clean combined region text.
        if len(cleaned_text) >= MIN_REGION_CHARACTERS:  # Verify region has meaningful text.
            region_texts.append(cleaned_text)  # Store useful region text.
    return region_texts  # Return distributed text regions.


def detect_language_from_text(value: str) -> str:
    """
    Detect language from subtitle text.

    :param value: Subtitle text.
    :return: Canonical language name or empty text.
    """

    if importlib.util.find_spec("langdetect") is None:  # Verify text detector package is installed.
        return ""  # Return unknown when detector is unavailable.
    langdetect_module = importlib.import_module("langdetect")  # Import text detector lazily.
    detector_factory = getattr(langdetect_module, "DetectorFactory")  # Read detector factory.
    detector_factory.seed = 0  # Make detector output deterministic.
    try:  # Run text language detection.
        detections = langdetect_module.detect_langs(value)  # Detect candidate languages.
    except Exception:  # Handle weak or invalid text.
        return ""  # Return unknown language.
    if not detections:  # Verify a language candidate exists.
        return ""  # Return unknown language.
    best_detection = detections[0]  # Read strongest language candidate.
    if float(best_detection.prob) < MIN_LANGUAGE_PROBABILITY:  # Verify strong confidence.
        return ""  # Return unknown when confidence is weak.
    normalized_language = normalize_subtitle_language_value(str(best_detection.lang))  # Normalize the generic detector result first.
    if normalized_language == "Portuguese":  # Run PT-BR vs PT-PT heuristics only for Portuguese subtitle text.
        classified_portuguese = classify_portuguese_subtitle_variant(value)  # Refine generic Portuguese into a regional subtitle label when possible.
        if classified_portuguese != "Portuguese":  # Upgrade only when subtitle text actually proves a more specific regional variant.
            return classified_portuguese  # Return region-specific Portuguese label.
    return normalized_language  # Return canonical subtitle language name.


def count_region_marker_hits(normalized_text: str, markers: set[str]) -> int:
    """
    Count conservative region-marker hits inside normalized subtitle text.

    :param normalized_text: Accent-stripped normalized subtitle text.
    :param markers: Region-specific lexical markers.
    :return: Number of distinct region-marker hits.
    """

    return sum(1 for marker in markers if marker in normalized_text)  # Count distinct lexical matches only once per marker.


def classify_portuguese_subtitle_variant(value: str) -> str:
    """
    Distinguish Brazilian Portuguese from European Portuguese subtitle text.

    :param value: Subtitle text region.
    :return: Canonical Portuguese variant or generic Portuguese when uncertain.
    """

    normalized_text = " " + normalize_text(value) + " "  # Normalize accents and whitespace so Portuguese region markers match reliably.
    brazilian_score = count_region_marker_hits(normalized_text, BRAZILIAN_PORTUGUESE_MARKERS)  # Count PT-BR lexical evidence.
    european_score = count_region_marker_hits(normalized_text, EUROPEAN_PORTUGUESE_MARKERS)  # Count PT-PT lexical evidence.
    if brazilian_score >= PORTUGUESE_REGION_MIN_SCORE and brazilian_score >= european_score + PORTUGUESE_REGION_SCORE_MARGIN:  # Require a clear PT-BR winner.
        return "Brazilian Portuguese"  # Return canonical PT-BR label.
    if european_score >= PORTUGUESE_REGION_MIN_SCORE and european_score >= brazilian_score + PORTUGUESE_REGION_SCORE_MARGIN:  # Require a clear PT-PT winner.
        return "Portuguese"  # Return canonical PT-PT label.
    return "Portuguese"  # Fall back to generic Portuguese when evidence is mixed or weak.


def detect_subtitle_language_from_metadata(stream: dict[str, Any]) -> str:
    """
    Detect subtitle language from metadata using subtitle-aware normalization.

    :param stream: Subtitle metadata object.
    :return: Canonical subtitle language name or empty text.
    """

    for value in metadata_language_values(stream):  # Iterate metadata values by reliability.
        language_name = normalize_subtitle_language_value(value)  # Resolve candidate metadata through subtitle-aware aliases.
        if language_name != "":  # Verify a subtitle language was detected.
            return language_name  # Return subtitle metadata language.
    return ""  # Return unknown subtitle language.


def aggregate_region_languages(region_languages: list[str]) -> str:
    """
    Aggregate regional subtitle language detections conservatively.

    :param region_languages: Language detections from timeline regions.
    :return: Canonical language name or empty text.
    """

    useful_languages = [language for language in region_languages if language != ""]  # Remove unknown regions.
    if len(useful_languages) < MIN_VALID_REGIONS:  # Require enough useful regions.
        return ""  # Return unknown when evidence is insufficient.
    counts = Counter(useful_languages)  # Count language votes.
    winning_language, winning_count = counts.most_common(1)[0]  # Read strongest language vote.
    if winning_count / len(useful_languages) < MIN_WINNING_RATIO:  # Require conservative agreement.
        return ""  # Return unknown when regions disagree.
    return winning_language  # Return aggregated language.


def detect_language_from_subtitle_content(file_path: Path, track_id: int, duration_seconds: float) -> str:
    """
    Detect language from extracted embedded subtitle text.

    :param file_path: Matroska file path.
    :param track_id: MKVToolNix subtitle track ID.
    :param duration_seconds: Media duration in seconds.
    :return: Canonical language name or empty text.
    """

    with tempfile.TemporaryDirectory(prefix="subtitle_track_language_") as temp_dir:  # Create cleanup-managed extraction directory.
        subtitle_path = Path(temp_dir) / "subtitle_track.txt"  # Build temporary subtitle path.
        if not extract_subtitle_track(file_path, track_id, subtitle_path):  # Verify embedded subtitle extraction succeeded.
            return ""  # Return unknown language.
        subtitle_text = read_subtitle_text(subtitle_path)  # Read extracted subtitle text.
        cues = parse_text_subtitle_cues(subtitle_text)  # Parse timestamped cues.
        region_texts = collect_region_texts(cues, duration_seconds)  # Collect distributed region text.
        region_languages = [detect_language_from_text(region_text) for region_text in region_texts]  # Detect region languages.
    return aggregate_region_languages(region_languages)  # Return conservative aggregate.


def detect_subtitle_track_language(file_path: Path, stream: dict[str, Any], track_id: int | None, codec_id: str, codec_name: str, duration_seconds: float) -> str:
    """
    Detect one embedded subtitle-track language from metadata or text content.

    :param file_path: Matroska file path.
    :param stream: Subtitle metadata object.
    :param track_id: MKVToolNix track ID.
    :param codec_id: Matroska subtitle codec ID.
    :param codec_name: MKVToolNix subtitle codec name.
    :param duration_seconds: Media duration in seconds.
    :return: Canonical language name or empty text.
    """

    metadata_language = detect_subtitle_language_from_metadata(stream)  # Prefer subtitle-aware metadata normalization first.
    if metadata_language != "" and metadata_language != "Portuguese":  # Keep precise non-Portuguese and explicit PT-BR metadata results.
        return metadata_language  # Return sufficiently specific metadata language.
    if track_id is None:  # Verify content extraction can target the exact track.
        return metadata_language  # Return best metadata language when content cannot be inspected.
    if not subtitle_codec_is_text(codec_id, codec_name):  # Verify subtitle codec contains directly readable text.
        return metadata_language  # Return best metadata language for image-based subtitle content.
    content_language = detect_language_from_subtitle_content(file_path, track_id, duration_seconds)  # Detect subtitle language from actual text when possible.
    if content_language != "":  # Prefer content-based language when extraction succeeded.
        return content_language  # Return text-derived subtitle language.
    return metadata_language  # Fall back to metadata language when content detection is unavailable or inconclusive.
