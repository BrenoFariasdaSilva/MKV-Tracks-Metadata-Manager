"""
Detect audio-track language from metadata first, then sampled audio when needed.
"""

from __future__ import annotations  # Enable modern annotations on supported Python versions.

from collections import Counter  # Aggregate sample language votes.
import importlib  # Load optional Whisper dependency lazily.
import importlib.util  # Detect optional Whisper dependency without hard import errors.
from pathlib import Path  # Represent media and temporary sample paths.
import re  # Normalize metadata text.
import subprocess  # Extract temporary audio samples with ffmpeg.
import tempfile  # Own temporary sample directories.
from typing import Any  # Type dynamic ffprobe and Whisper data.
import unicodedata  # Strip accents from metadata aliases.


WHISPER_MODEL = "base"  # Use smallest practical multilingual Whisper model for fallback detection.
SAMPLE_SECONDS = 25  # Decode short analysis windows only.
SAMPLE_FRACTIONS = (0.22, 0.38, 0.54, 0.70)  # Avoid beginning and ending portions.
MIN_VALID_SAMPLES = 2  # Require more than one useful speech sample.
MIN_WINNING_RATIO = 0.67  # Require conservative sample agreement.
MAX_NO_SPEECH_PROBABILITY = 0.65  # Reject samples Whisper marks as mostly non-speech.

LANGUAGE_ALIASES = {
    "English": ("en", "eng", "english", "ingles", "inglês"),
    "Portuguese": ("pt", "por", "pob", "portuguese", "portugues", "português", "pt br", "pt-br", "brazilian portuguese", "português brasil", "portugues brasil"),
    "Spanish": ("es", "spa", "spanish", "espanol", "español", "castellano", "latam"),
    "French": ("fr", "fre", "fra", "french", "francais", "français"),
    "German": ("de", "ger", "deu", "german", "deutsch"),
    "Italian": ("it", "ita", "italian", "italiano"),
    "Japanese": ("ja", "jpn", "japanese", "nihongo"),
    "Korean": ("ko", "kor", "korean"),
    "Chinese": ("zh", "zh-cn", "zh-tw", "zh-hans", "zh-hant", "zho", "chi", "chinese", "mandarin", "cantonese"),
    "Russian": ("ru", "rus", "russian"),
    "Hindi": ("hi", "hin", "hindi"),
}  # Store common canonical language aliases.

WHISPER_LANGUAGE_CODES = {
    "en": "English",
    "pt": "Portuguese",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "ja": "Japanese",
    "ko": "Korean",
    "zh": "Chinese",
    "ru": "Russian",
    "hi": "Hindi",
}  # Store Whisper language-code mapping.


def normalize_text(value: object) -> str:
    """
    Normalize text for reliable metadata language matching.

    :param value: Raw metadata value.
    :return: Normalized comparable text.
    """

    text = "" if value is None else str(value)  # Convert missing values to empty text.
    text = text.lower()  # Convert text to lowercase.
    text = unicodedata.normalize("NFKD", text)  # Split accents from base characters.
    text = "".join(character for character in text if not unicodedata.combining(character))  # Remove accent marks.
    text = re.sub(r"\b\d+(\.\d+)?\b", " ", text)  # Remove isolated numeric quality markers.
    text = re.sub(r"[\(\)\[\]\{\}_\-\.]+", " ", text)  # Replace separators with spaces.
    text = re.sub(r"\s+", " ", text).strip()  # Collapse whitespace.
    return text  # Return normalized text.


def build_normalized_aliases() -> dict[str, list[str]]:
    """
    Build normalized aliases for configured language names.

    :return: Mapping from canonical language to normalized aliases.
    """

    normalized_aliases: dict[str, list[str]] = {}  # Store normalized aliases by language.
    for language_name, aliases in LANGUAGE_ALIASES.items():  # Iterate configured language groups.
        values = [language_name, *aliases]  # Include canonical name as an alias.
        normalized_aliases[language_name] = sorted({normalize_text(value) for value in values if normalize_text(value)})  # Store deterministic aliases.
    return normalized_aliases  # Return normalized alias mapping.


def normalize_language_value(value: object) -> str:
    """
    Resolve one metadata value into a canonical language name.

    :param value: Raw metadata value.
    :return: Canonical language name or empty text.
    """

    normalized_value = normalize_text(value)  # Normalize raw value.
    if normalized_value == "" or normalized_value in {"und", "undefined", "unknown", "mis", "mul"}:  # Reject unknown metadata markers.
        return ""  # Return unknown language.

    aliases = build_normalized_aliases()  # Build alias mapping.
    for language_name, language_aliases in aliases.items():  # Prefer exact alias matches.
        if normalized_value in language_aliases:  # Verify exact normalized match.
            return language_name  # Return canonical language.

    for language_name, language_aliases in aliases.items():  # Try token matches for longer metadata strings.
        for alias in language_aliases:  # Iterate aliases.
            if len(alias) < 3:  # Avoid unsafe tiny fuzzy aliases.
                continue  # Skip tiny alias.
            if alias in normalized_value.split():  # Verify alias appears as a full token.
                return language_name  # Return canonical language.

    for language_name, language_aliases in aliases.items():  # Try conservative substring matches.
        for alias in language_aliases:  # Iterate aliases.
            if len(alias) < 4:  # Avoid unsafe short substring matches.
                continue  # Skip short alias.
            if alias in normalized_value:  # Verify alias appears inside metadata.
                return language_name  # Return canonical language.

    return ""  # Return unknown language.


def read_string_tags(stream: dict[str, Any]) -> dict[str, str]:
    """
    Read string tags from an ffprobe stream.

    :param stream: ffprobe stream object.
    :return: String tag mapping.
    """

    raw_tags = stream.get("tags")  # Read raw tags.
    if not isinstance(raw_tags, dict):  # Verify tags are object-shaped.
        return {}  # Return empty tags.
    return {str(key): str(value) for key, value in raw_tags.items() if value is not None}  # Return stringified tags.


def metadata_language_values(stream: dict[str, Any]) -> list[object]:
    """
    Collect language-related metadata values in priority order.

    :param stream: ffprobe stream object.
    :return: Ordered metadata values.
    """

    tags = read_string_tags(stream)  # Read stream tags.
    values: list[object] = []  # Store prioritized values.
    values.extend([tags.get("language"), tags.get("LANGUAGE"), tags.get("lang"), tags.get("LANG")])  # Prefer standardized language tags.
    values.extend([stream.get("language"), stream.get("LANGUAGE")])  # Include direct stream fields when present.
    values.extend([tags.get("title"), tags.get("TITLE"), tags.get("name"), tags.get("NAME"), tags.get("handler_name")])  # Add name-like tags as fallback.
    values.extend(tags.values())  # Add all tags as final metadata fallback.
    return values  # Return ordered metadata values.


def detect_language_from_metadata(stream: dict[str, Any]) -> str:
    """
    Detect language from reliable metadata values.

    :param stream: ffprobe stream object.
    :return: Canonical language name or empty text.
    """

    for value in metadata_language_values(stream):  # Iterate metadata values by reliability.
        language_name = normalize_language_value(value)  # Resolve candidate metadata value.
        if language_name != "":  # Verify a language was detected.
            return language_name  # Return metadata language.
    return ""  # Return unknown language.


def choose_sample_offsets(duration_seconds: float) -> list[float]:
    """
    Choose intermediate sample offsets across useful duration.

    :param duration_seconds: Media or stream duration in seconds.
    :return: Sample start offsets in seconds.
    """

    if duration_seconds <= SAMPLE_SECONDS * 3:  # Verify duration is long enough for distributed samples.
        return [max(0.0, duration_seconds * 0.5 - SAMPLE_SECONDS * 0.5)] if duration_seconds > 0.0 else [0.0]  # Return centered fallback sample.
    max_start = max(0.0, duration_seconds - SAMPLE_SECONDS - 10.0)  # Avoid final credits or padding.
    offsets = [min(max_start, max(10.0, duration_seconds * fraction)) for fraction in SAMPLE_FRACTIONS]  # Build intermediate offsets.
    return sorted({round(offset, 2) for offset in offsets})  # Return unique deterministic offsets.


def extract_audio_sample(file_path: Path, audio_position: int, start_time: float, sample_path: Path) -> bool:
    """
    Extract a decoded temporary audio sample for one specific audio stream.

    :param file_path: Media file path.
    :param audio_position: Zero-based audio stream position.
    :param start_time: Sample start time in seconds.
    :param sample_path: Temporary WAV output path.
    :return: True when sample extraction succeeds.
    """

    command = ["ffmpeg", "-v", "error", "-ss", f"{start_time:.2f}", "-i", str(file_path), "-map", f"0:a:{audio_position}", "-t", str(SAMPLE_SECONDS), "-vn", "-ac", "1", "-ar", "16000", "-f", "wav", str(sample_path), "-y"]  # Build stream-specific decode command.
    try:  # Run ffmpeg extraction.
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)  # Execute ffmpeg.
    except OSError as error:  # Handle unavailable ffmpeg.
        print(f"ffmpeg unavailable for language sample: {error}")  # Report extraction failure.
        return False  # Return failed extraction.
    if result.returncode != 0:  # Verify extraction succeeded.
        print(f"ffmpeg sample extraction failed for {file_path}: {result.stderr.strip()}")  # Report extraction error.
        return False  # Return failed extraction.
    return sample_path.exists() and sample_path.stat().st_size > 0  # Return whether sample file exists with content.


def read_whisper_language_result(result: Any) -> str:
    """
    Read a conservative language result from Whisper transcription data.

    :param result: Whisper transcription result.
    :return: Canonical language name or empty text.
    """

    if not isinstance(result, dict):  # Verify result has expected mapping shape.
        return ""  # Return unknown language.
    segments = result.get("segments")  # Read speech segments.
    useful_segments = segments if isinstance(segments, list) else []  # Normalize segment list.
    text_value = str(result.get("text") or "").strip()  # Read transcribed text.
    if text_value == "":  # Verify sample contains text.
        return ""  # Return unknown language.
    if useful_segments:  # Verify Whisper returned segment diagnostics.
        no_speech_values = [float(segment.get("no_speech_prob", 1.0)) for segment in useful_segments if isinstance(segment, dict) and isinstance(segment.get("no_speech_prob"), (int, float))]  # Collect no-speech probabilities.
        average_no_speech = sum(no_speech_values) / len(no_speech_values) if no_speech_values else 1.0  # Compute no-speech mean.
        if average_no_speech > MAX_NO_SPEECH_PROBABILITY:  # Reject likely non-speech samples.
            return ""  # Return unknown language.
    language_code = str(result.get("language") or "").lower().strip()  # Read Whisper language code.
    return WHISPER_LANGUAGE_CODES.get(language_code, "")  # Return mapped language.


def detect_language_with_whisper(sample_path: Path) -> str:
    """
    Detect language for one temporary sample with optional Whisper dependency.

    :param sample_path: Temporary WAV sample path.
    :return: Canonical language name or empty text.
    """

    if importlib.util.find_spec("whisper") is None:  # Verify optional Whisper package is installed.
        return ""  # Return unknown when fallback detector is unavailable.
    whisper_module = importlib.import_module("whisper")  # Import Whisper lazily.
    model = whisper_module.load_model(WHISPER_MODEL)  # Load configured multilingual model.
    result = model.transcribe(str(sample_path), task="transcribe", fp16=False, verbose=False)  # Transcribe sample for language detection.
    return read_whisper_language_result(result)  # Return conservative language result.


def aggregate_sample_languages(sample_languages: list[str]) -> str:
    """
    Aggregate sampled language detections conservatively.

    :param sample_languages: Language detections from sampled audio.
    :return: Canonical language name or empty text.
    """

    useful_languages = [language for language in sample_languages if language != ""]  # Remove unknown samples.
    if len(useful_languages) < MIN_VALID_SAMPLES:  # Require enough speech-containing samples.
        return ""  # Return unknown when evidence is insufficient.
    counts = Counter(useful_languages)  # Count language votes.
    winning_language, winning_count = counts.most_common(1)[0]  # Read strongest language vote.
    if winning_count / len(useful_languages) < MIN_WINNING_RATIO:  # Require conservative agreement.
        return ""  # Return unknown when samples disagree.
    return winning_language  # Return aggregated language.


def detect_language_from_audio_samples(file_path: Path, audio_position: int, duration_seconds: float) -> str:
    """
    Detect language from multiple intermediate samples of one audio stream.

    :param file_path: Media file path.
    :param audio_position: Zero-based audio stream position.
    :param duration_seconds: Media or stream duration in seconds.
    :return: Canonical language name or empty text.
    """

    sample_languages: list[str] = []  # Store per-sample language detections.
    with tempfile.TemporaryDirectory(prefix="audio_track_language_") as temp_dir:  # Create cleanup-managed sample directory.
        temp_root = Path(temp_dir)  # Convert temporary directory to Path.
        for sample_number, start_time in enumerate(choose_sample_offsets(duration_seconds), start=1):  # Iterate distributed sample offsets.
            sample_path = temp_root / f"sample_{sample_number}.wav"  # Build temporary sample path.
            if not extract_audio_sample(file_path, audio_position, start_time, sample_path):  # Verify sample extraction succeeded.
                continue  # Skip failed sample.
            try:  # Run optional audio language detection.
                sample_languages.append(detect_language_with_whisper(sample_path))  # Store sample detection result.
            except Exception as error:  # Handle detector failures without stopping report generation.
                print(f"Whisper language detection failed for {file_path}: {error}")  # Report detector failure.
                sample_languages.append("")  # Store unknown sample result.

    return aggregate_sample_languages(sample_languages)  # Return conservative aggregate.


def detect_audio_track_language(file_path: Path, stream: dict[str, Any], audio_position: int, duration_seconds: float) -> str:
    """
    Detect one audio-track language from metadata or sampled audio.

    :param file_path: Media file path.
    :param stream: ffprobe audio stream object.
    :param audio_position: Zero-based audio stream position.
    :param duration_seconds: Media or stream duration in seconds.
    :return: Canonical language name or empty text.
    """

    metadata_language = detect_language_from_metadata(stream)  # Prefer reliable metadata.
    if metadata_language != "":  # Verify metadata resolved a language.
        return metadata_language  # Return metadata language.
    return detect_language_from_audio_samples(file_path, audio_position, duration_seconds)  # Return sampled audio language.
