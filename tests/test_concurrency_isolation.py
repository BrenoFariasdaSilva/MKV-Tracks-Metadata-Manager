from __future__ import annotations  # Enable modern annotations on supported Python versions.

import multiprocessing  # Run true cross-process lock contention tests.
import os  # Read platform behavior for path identity tests.
from pathlib import Path  # Represent temporary media and artifact paths.
import queue  # Detect empty multiprocessing queues without broad exceptions.
import re  # Extract run identifiers from dry-run Makefile commands.
import shutil  # Locate make for Makefile expansion tests.
import subprocess  # Run safe dry-run Makefile commands.
import sys  # Locate the current Python executable for subprocess tests.
import tempfile  # Create isolated temporary directories for tests.
import unittest  # Use standard-library automated tests.
from unittest import mock  # Stub subprocess and executable discovery.

import dependency_lock_runner  # Test dependency lock behavior.
from file_lock import FileLock, release_file_lock  # Test foreign release behavior.
import mkvpropedit_wrapper  # Test media lock behavior.
from mkvpropedit_wrapper import TrackMetadataEdit  # Build safe edit requests.
import report  # Test report and log path isolation.


def run_media_lock_worker(lock_dir_text: str, media_path_text: str, entered_queue: multiprocessing.Queue, release_event: multiprocessing.Event, active_counter: multiprocessing.Value, max_counter: multiprocessing.Value, counter_lock: multiprocessing.Lock) -> None:
    """
    Hold one media lock in a child process until released by the parent.

    :param lock_dir_text: Temporary lock directory path text.
    :param media_path_text: Media file path text.
    :param entered_queue: Queue receiving child entry notifications.
    :param release_event: Event that releases the child critical section.
    :param active_counter: Shared active holder count.
    :param max_counter: Shared maximum holder count.
    :param counter_lock: Shared counter lock.
    :return: None.
    """

    mkvpropedit_wrapper.MEDIA_LOCK_DIR = Path(lock_dir_text)  # Route media locks into the test temp directory.
    lock_handle = mkvpropedit_wrapper.acquire_media_edit_lock(Path(media_path_text))  # Acquire the per-media lock.
    try:  # Hold the lock while the parent observes concurrency state.
        with counter_lock:  # Serialize shared counter updates.
            active_counter.value += 1  # Count active lock holder.
            max_counter.value = max(max_counter.value, active_counter.value)  # Record maximum concurrent holders.
        entered_queue.put(media_path_text)  # Notify parent that this process entered the critical section.
        release_event.wait(5)  # Wait until parent releases this worker.
        with counter_lock:  # Serialize shared counter updates.
            active_counter.value -= 1  # Remove active lock holder.
    finally:  # Release the lock even when the worker is interrupted.
        mkvpropedit_wrapper.release_media_edit_lock(lock_handle)  # Release handle-owned media lock.


def run_dependency_lock_worker(lock_dir_text: str, entered_queue: multiprocessing.Queue, release_event: multiprocessing.Event, active_counter: multiprocessing.Value, max_counter: multiprocessing.Value, counter_lock: multiprocessing.Lock) -> None:
    """
    Hold the dependency lock in a child process until released by the parent.

    :param lock_dir_text: Temporary dependency lock directory path text.
    :param entered_queue: Queue receiving child entry notifications.
    :param release_event: Event that releases the child critical section.
    :param active_counter: Shared active holder count.
    :param max_counter: Shared maximum holder count.
    :param counter_lock: Shared counter lock.
    :return: None.
    """

    dependency_lock_runner.LOCK_DIR = Path(lock_dir_text)  # Route dependency locks into the test temp directory.
    lock_handle = dependency_lock_runner.acquire_dependency_lock()  # Acquire the dependency setup lock.
    try:  # Hold the lock while the parent observes concurrency state.
        with counter_lock:  # Serialize shared counter updates.
            active_counter.value += 1  # Count active lock holder.
            max_counter.value = max(max_counter.value, active_counter.value)  # Record maximum concurrent holders.
        entered_queue.put("entered")  # Notify parent that this process entered the critical section.
        release_event.wait(5)  # Wait until parent releases this worker.
        with counter_lock:  # Serialize shared counter updates.
            active_counter.value -= 1  # Remove active lock holder.
    finally:  # Release the lock even when the worker is interrupted.
        dependency_lock_runner.release_dependency_lock(lock_handle)  # Release handle-owned dependency lock.


def run_foreign_release(lock_path_text: str) -> None:
    """
    Attempt to release a lock from a process that never acquired it.

    :param lock_path_text: Existing lock file path text.
    :return: None.
    """

    stream = Path(lock_path_text).open("a+", encoding="utf-8")  # Open the same lock file without acquiring it.
    release_file_lock(FileLock(Path(lock_path_text), stream))  # Attempt release from a non-owner handle.


class ConcurrencyIsolationTests(unittest.TestCase):  # Group concurrency-safety tests.
    @unittest.skipUnless(shutil.which("make"), "make executable is required")  # Skip Makefile assertions when make is absent.
    def test_make_process_uses_one_generated_run_id(self) -> None:  # Verify one generated run id flows through process stages.
        result = subprocess.run(["make", "-n", "process", "REPORT_ARGS=--audio --subtitles", "RENAME_ARGS=--video --audio --subtitles", "INPUT_DIR=G:/Series/"], capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)  # Run dry Makefile expansion without executing media commands.
        self.assertEqual(result.returncode, 0, result.stderr)  # Verify dry-run expansion succeeded.
        run_ids = re.findall(r"--run-id \"([^\"]+)\"", result.stdout)  # Extract propagated run identifiers.
        self.assertGreaterEqual(len(run_ids), 2, result.stdout)  # Verify both report and rename stages contain a run id.
        self.assertEqual(set(run_ids), {run_ids[0]})  # Verify all process stages share one run id.
        self.assertRegex(run_ids[0], r"^[A-Za-z0-9_.-]+$")  # Verify generated run id is filesystem-safe.

    @unittest.skipUnless(shutil.which("make"), "make executable is required")  # Skip Makefile assertions when make is absent.
    def test_make_process_explicit_report_handoff_paths(self) -> None:  # Verify explicit reports are forwarded to both process stages.
        result = subprocess.run(["make", "-n", "process", "RUN_ID=runOne", "REPORT_ARGS=--audio --subtitles", "RENAME_ARGS=--video --audio --subtitles", "INPUT_DIR=E:/Movies/Test Folder", "AUDIO_REPORT=Reports/custom audio.json", "SUBTITLE_REPORT=Reports/custom subs.json", "UNRESOLVED_AUDIO_REPORT=Reports/custom unresolved.json"], capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)  # Run dry Makefile expansion with explicit report paths.
        self.assertEqual(result.returncode, 0, result.stderr)  # Verify dry-run expansion succeeded.
        self.assertIn('--audio-report "Reports/custom audio.json"', result.stdout)  # Verify audio report path appears in generated commands.
        self.assertIn('--subtitle-report "Reports/custom subs.json"', result.stdout)  # Verify subtitle report path appears in generated commands.
        self.assertIn('--unresolved-audio-report "Reports/custom unresolved.json"', result.stdout)  # Verify unresolved report path appears in rename command.
        self.assertEqual(result.stdout.count('--run-id "runOne"'), 2)  # Verify report and rename stages share the explicit run id.

    @unittest.skipUnless(shutil.which("make"), "make executable is required")  # Skip Makefile assertions when make is absent.
    def test_make_dependency_lock_scope_is_limited(self) -> None:  # Verify dependency lock wrapper is not wrapped around media processing.
        result = subprocess.run(["make", "-n", "process", "RUN_ID=runScope", "REPORT_ARGS=--audio", "RENAME_ARGS=--video --audio", "INPUT_DIR=G:/Movies/"], capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)  # Run dry Makefile expansion without executing commands.
        self.assertEqual(result.returncode, 0, result.stderr)  # Verify dry-run expansion succeeded.
        dependency_lines = [line for line in result.stdout.splitlines() if "dependency_lock_runner.py" in line]  # Collect dependency setup commands.
        media_lines = [line for line in result.stdout.splitlines() if "./report.py" in line or "./track_metadata_renamer.py" in line]  # Collect media workflow commands.
        self.assertGreaterEqual(len(dependency_lines), 1, result.stdout)  # Verify dependency setup is still lock wrapped.
        self.assertTrue(all("dependency_lock_runner.py" not in line for line in media_lines), result.stdout)  # Verify media processing remains independently concurrent.

    def test_artifact_paths_are_run_and_input_isolated(self) -> None:  # Verify reports and logs differ across inputs and run ids.
        inputs = ["G:/Series/", "F:/Series/", "G:/Movies/"]  # Define example independent input roots.
        audio_paths = [report.resolve_report_path(input_dir, None, report.AUDIO_REPORT_FILENAME, "runA") for input_dir in inputs]  # Resolve audio reports for different roots.
        subtitle_paths = [report.resolve_report_path(input_dir, None, report.SUBTITLE_REPORT_FILENAME, "runA") for input_dir in inputs]  # Resolve subtitle reports for different roots.
        log_paths = [report.build_log_path(Path("track_metadata_renamer.py"), input_dir, "runA") for input_dir in inputs]  # Resolve logs for different roots.
        self.assertEqual(len(set(audio_paths)), len(inputs))  # Verify different roots do not share audio reports.
        self.assertEqual(len(set(subtitle_paths)), len(inputs))  # Verify different roots do not share subtitle reports.
        self.assertEqual(len(set(log_paths)), len(inputs))  # Verify different roots do not share logs.
        self.assertNotEqual(report.resolve_report_path("G:/Movies/", None, report.AUDIO_REPORT_FILENAME, "runA"), report.resolve_report_path("G:/Movies/", None, report.AUDIO_REPORT_FILENAME, "runB"))  # Verify same root concurrent runs use separate reports.
        self.assertNotEqual(report.build_log_path(Path("report.py"), "G:/Movies/", "runA"), report.build_log_path(Path("report.py"), "G:/Movies/", "runB"))  # Verify same root concurrent runs use separate logs.

    def test_run_id_sanitization_removes_reserved_filename_characters(self) -> None:  # Verify run identifiers are filename safe.
        safe_run_id = report.normalize_run_id("a:b/c\\d*e?f|g<h>")  # Normalize reserved Windows filename characters.
        self.assertNotRegex(safe_run_id, r'[<>:"|?*\\/\x00-\x1f]')  # Verify reserved characters were removed or replaced.
        self.assertNotEqual(safe_run_id, "")  # Verify useful input still produces a non-empty id.

    def test_report_writes_are_unique_only_when_destinations_are_unique(self) -> None:  # Verify atomic replacement does not hide shared destination collisions.
        with tempfile.TemporaryDirectory() as temp_dir:  # Create isolated report output root.
            original_reports_dir = report.REPORTS_DIR  # Preserve global report directory.
            report.REPORTS_DIR = Path(temp_dir)  # Route reports into the test temp directory.
            try:  # Restore the global report directory after assertions.
                first_path = report.resolve_report_path("G:/Movies/", None, report.AUDIO_REPORT_FILENAME, "runA")  # Resolve first run report.
                second_path = report.resolve_report_path("G:/Movies/", None, report.AUDIO_REPORT_FILENAME, "runB")  # Resolve second run report.
                shared_path = report.resolve_report_path("G:/Movies/", None, report.AUDIO_REPORT_FILENAME, None)  # Resolve legacy shared destination.
                self.assertNotEqual(first_path, second_path)  # Verify run ids isolate destinations.
                self.assertEqual(shared_path, report.resolve_report_path("G:/Movies/", None, report.AUDIO_REPORT_FILENAME, None))  # Verify identical destinations would still collide without run ids.
                self.assertTrue(report.write_report(first_path, {"Audio (1)": {"desired_new_name": "English"}}))  # Write first isolated report.
                self.assertTrue(report.write_report(second_path, {"Audio (1)": {"desired_new_name": "Portuguese"}}))  # Write second isolated report.
                self.assertIn("English", first_path.read_text(encoding="utf-8"))  # Verify first report retained its data.
                self.assertIn("Portuguese", second_path.read_text(encoding="utf-8"))  # Verify second report retained its data.
            finally:  # Restore module global.
                report.REPORTS_DIR = original_reports_dir  # Restore original report directory.

    def test_equivalent_media_paths_share_lock_identity(self) -> None:  # Verify equivalent path spellings map to one lock file.
        with tempfile.TemporaryDirectory() as temp_dir:  # Create isolated media root.
            media_path = Path(temp_dir) / "Movies" / "Film.mkv"  # Build target media path.
            media_path.parent.mkdir(parents=True)  # Create target directory.
            media_path.write_bytes(b"not real media")  # Create harmless placeholder file.
            original_lock_dir = mkvpropedit_wrapper.MEDIA_LOCK_DIR  # Preserve global media lock directory.
            mkvpropedit_wrapper.MEDIA_LOCK_DIR = Path(temp_dir) / "locks"  # Route media locks into the test temp directory.
            try:  # Restore the global lock directory after assertions.
                first_lock = mkvpropedit_wrapper.build_media_lock_path(media_path)  # Resolve lock from direct path.
                second_lock = mkvpropedit_wrapper.build_media_lock_path(media_path.parent / "." / ".." / "Movies" / "Film.mkv")  # Resolve lock from normalized path.
                slash_lock = mkvpropedit_wrapper.build_media_lock_path(Path(str(media_path).replace("\\", "/")))  # Resolve lock from alternate separators.
                self.assertEqual(first_lock, second_lock)  # Verify normalized equivalent path shares the lock.
                self.assertEqual(first_lock, slash_lock)  # Verify separator spelling shares the lock.
                if os.name == "nt":  # Verify Windows case-insensitive identity when on Windows.
                    self.assertEqual(first_lock, mkvpropedit_wrapper.build_media_lock_path(Path(str(media_path).upper())))  # Verify casing changes share the lock on Windows.
            finally:  # Restore module global.
                mkvpropedit_wrapper.MEDIA_LOCK_DIR = original_lock_dir  # Restore original media lock directory.

    def test_same_media_lock_serializes_processes_and_releases(self) -> None:  # Verify same media file cannot be edited by two processes at once.
        with tempfile.TemporaryDirectory() as temp_dir:  # Create isolated media and lock roots.
            context = multiprocessing.get_context("spawn")  # Use spawn for cross-platform process behavior.
            media_path = Path(temp_dir) / "Movie.mkv"  # Build harmless placeholder path.
            media_path.write_bytes(b"not real media")  # Create harmless placeholder file.
            release_event = context.Event()  # Create parent-controlled release event.
            entered_queue = context.Queue()  # Create entry notification queue.
            active_counter = context.Value("i", 0)  # Create shared active holder count.
            max_counter = context.Value("i", 0)  # Create shared maximum holder count.
            counter_lock = context.Lock()  # Create shared counter lock.
            first = context.Process(target=run_media_lock_worker, args=(str(Path(temp_dir) / "locks"), str(media_path), entered_queue, release_event, active_counter, max_counter, counter_lock))  # Build first same-file worker.
            second = context.Process(target=run_media_lock_worker, args=(str(Path(temp_dir) / "locks"), str(media_path), entered_queue, release_event, active_counter, max_counter, counter_lock))  # Build second same-file worker.
            first.start()  # Start first contender.
            second.start()  # Start second contender.
            self.assertEqual(entered_queue.get(timeout=5), str(media_path))  # Verify one contender entered.
            with self.assertRaises(queue.Empty):  # Verify the other contender cannot enter while the lock is held.
                entered_queue.get(timeout=0.5)  # Attempt to read a second entry before release.
            release_event.set()  # Release current holder and allow completion.
            first.join(5)  # Wait for first worker.
            second.join(5)  # Wait for second worker.
            self.assertFalse(first.is_alive())  # Verify first worker exited.
            self.assertFalse(second.is_alive())  # Verify second worker exited.
            self.assertEqual(first.exitcode, 0)  # Verify first worker succeeded.
            self.assertEqual(second.exitcode, 0)  # Verify second worker succeeded.
            self.assertEqual(max_counter.value, 1)  # Verify at most one process held the same media lock.

    def test_different_media_files_can_hold_locks_together(self) -> None:  # Verify independent media files are not globally serialized.
        with tempfile.TemporaryDirectory() as temp_dir:  # Create isolated media and lock roots.
            context = multiprocessing.get_context("spawn")  # Use spawn for cross-platform process behavior.
            first_media = Path(temp_dir) / "A.mkv"  # Build first harmless placeholder path.
            second_media = Path(temp_dir) / "B.mkv"  # Build second harmless placeholder path.
            first_media.write_bytes(b"not real media")  # Create first placeholder file.
            second_media.write_bytes(b"not real media")  # Create second placeholder file.
            release_event = context.Event()  # Create parent-controlled release event.
            entered_queue = context.Queue()  # Create entry notification queue.
            active_counter = context.Value("i", 0)  # Create shared active holder count.
            max_counter = context.Value("i", 0)  # Create shared maximum holder count.
            counter_lock = context.Lock()  # Create shared counter lock.
            first = context.Process(target=run_media_lock_worker, args=(str(Path(temp_dir) / "locks"), str(first_media), entered_queue, release_event, active_counter, max_counter, counter_lock))  # Build first file worker.
            second = context.Process(target=run_media_lock_worker, args=(str(Path(temp_dir) / "locks"), str(second_media), entered_queue, release_event, active_counter, max_counter, counter_lock))  # Build second file worker.
            first.start()  # Start first independent worker.
            second.start()  # Start second independent worker.
            entries = {entered_queue.get(timeout=5), entered_queue.get(timeout=5)}  # Read both entries while workers are still held.
            self.assertEqual(entries, {str(first_media), str(second_media)})  # Verify both independent locks were acquired concurrently.
            self.assertEqual(max_counter.value, 2)  # Verify independent media files can overlap.
            release_event.set()  # Release both holders.
            first.join(5)  # Wait for first worker.
            second.join(5)  # Wait for second worker.
            self.assertEqual(first.exitcode, 0)  # Verify first worker succeeded.
            self.assertEqual(second.exitcode, 0)  # Verify second worker succeeded.

    def test_foreign_release_cannot_release_owner_lock(self) -> None:  # Verify another process cannot release a lock it never acquired.
        with tempfile.TemporaryDirectory() as temp_dir:  # Create isolated lock root.
            original_lock_dir = mkvpropedit_wrapper.MEDIA_LOCK_DIR  # Preserve global media lock directory.
            mkvpropedit_wrapper.MEDIA_LOCK_DIR = Path(temp_dir) / "locks"  # Route media locks into the test temp directory.
            context = multiprocessing.get_context("spawn")  # Use spawn for cross-platform process behavior.
            media_path = Path(temp_dir) / "Movie.mkv"  # Build harmless placeholder path.
            media_path.write_bytes(b"not real media")  # Create harmless placeholder file.
            owner_lock = mkvpropedit_wrapper.acquire_media_edit_lock(media_path)  # Acquire parent-owned lock.
            try:  # Keep parent lock held while foreign release runs.
                foreign = context.Process(target=run_foreign_release, args=(str(owner_lock.path),))  # Build foreign release process.
                foreign.start()  # Start non-owner release attempt.
                foreign.join(5)  # Wait for foreign release attempt.
                self.assertEqual(foreign.exitcode, 0)  # Verify foreign release process exited cleanly.
                release_event = context.Event()  # Create probe release event.
                entered_queue = context.Queue()  # Create probe entry queue.
                active_counter = context.Value("i", 0)  # Create shared active holder count.
                max_counter = context.Value("i", 0)  # Create shared maximum holder count.
                counter_lock = context.Lock()  # Create shared counter lock.
                probe = context.Process(target=run_media_lock_worker, args=(str(Path(temp_dir) / "locks"), str(media_path), entered_queue, release_event, active_counter, max_counter, counter_lock))  # Build probe contender.
                probe.start()  # Start probe while parent lock remains held.
                with self.assertRaises(queue.Empty):  # Verify probe cannot enter after foreign release.
                    entered_queue.get(timeout=0.5)  # Attempt to read probe entry before owner release.
            finally:  # Release parent lock before joining probe.
                mkvpropedit_wrapper.release_media_edit_lock(owner_lock)  # Release parent-owned media lock.
                mkvpropedit_wrapper.MEDIA_LOCK_DIR = original_lock_dir  # Restore original media lock directory.
            self.assertEqual(entered_queue.get(timeout=5), str(media_path))  # Verify probe enters after real owner release.
            release_event.set()  # Release probe holder.
            probe.join(5)  # Wait for probe worker.
            self.assertEqual(probe.exitcode, 0)  # Verify probe worker succeeded.

    def test_dependency_lock_serializes_only_shared_setup(self) -> None:  # Verify shared venv mutation lock admits one holder at a time.
        with tempfile.TemporaryDirectory() as temp_dir:  # Create isolated dependency lock root.
            context = multiprocessing.get_context("spawn")  # Use spawn for cross-platform process behavior.
            release_event = context.Event()  # Create parent-controlled release event.
            entered_queue = context.Queue()  # Create entry notification queue.
            active_counter = context.Value("i", 0)  # Create shared active holder count.
            max_counter = context.Value("i", 0)  # Create shared maximum holder count.
            counter_lock = context.Lock()  # Create shared counter lock.
            first = context.Process(target=run_dependency_lock_worker, args=(temp_dir, entered_queue, release_event, active_counter, max_counter, counter_lock))  # Build first dependency worker.
            second = context.Process(target=run_dependency_lock_worker, args=(temp_dir, entered_queue, release_event, active_counter, max_counter, counter_lock))  # Build second dependency worker.
            first.start()  # Start first dependency contender.
            second.start()  # Start second dependency contender.
            self.assertEqual(entered_queue.get(timeout=5), "entered")  # Verify one dependency setup entered.
            with self.assertRaises(queue.Empty):  # Verify second setup cannot enter while lock is held.
                entered_queue.get(timeout=0.5)  # Attempt to read second entry before release.
            release_event.set()  # Release current holder and allow completion.
            first.join(5)  # Wait for first worker.
            second.join(5)  # Wait for second worker.
            self.assertEqual(first.exitcode, 0)  # Verify first worker succeeded.
            self.assertEqual(second.exitcode, 0)  # Verify second worker succeeded.
            self.assertEqual(max_counter.value, 1)  # Verify only one dependency mutation holder existed.

    def test_lock_release_after_exception_and_no_nested_self_deadlock(self) -> None:  # Verify cleanup paths and caller-held lock behavior.
        with tempfile.TemporaryDirectory() as temp_dir:  # Create isolated media and lock roots.
            original_lock_dir = mkvpropedit_wrapper.MEDIA_LOCK_DIR  # Preserve global media lock directory.
            mkvpropedit_wrapper.MEDIA_LOCK_DIR = Path(temp_dir) / "locks"  # Route media locks into the test temp directory.
            media_path = Path(temp_dir) / "Movie.mkv"  # Build harmless placeholder path.
            media_path.write_bytes(b"not real media")  # Create non-empty placeholder file.
            first_lock = mkvpropedit_wrapper.acquire_media_edit_lock(media_path)  # Acquire first lock.
            try:  # Simulate exception cleanup path.
                raise RuntimeError("planned failure")  # Raise a controlled exception.
            except RuntimeError:  # Handle controlled exception.
                mkvpropedit_wrapper.release_media_edit_lock(first_lock)  # Release lock after exception.
            second_lock = mkvpropedit_wrapper.acquire_media_edit_lock(media_path)  # Reacquire after exception release.
            try:  # Exercise nested caller-held edit path without reacquiring.
                edit = TrackMetadataEdit("track:v1", "old", "new")  # Build one safe edit operation.
                completed = subprocess.CompletedProcess(["mkvpropedit"], 0, "", "")  # Build successful fake subprocess result.
                with mock.patch("mkvpropedit_wrapper.find_executable", return_value=sys.executable):  # Stub executable discovery.
                    with mock.patch("mkvpropedit_wrapper.subprocess.run", return_value=completed) as run_mock:  # Stub external edit command.
                        result = mkvpropedit_wrapper.apply_track_metadata_edits(media_path, [edit], media_lock_held=True)  # Apply edit while caller owns lock.
                self.assertTrue(result.success)  # Verify caller-held lock path succeeds.
                self.assertEqual(run_mock.call_count, 1)  # Verify no deadlock prevented subprocess execution.
            finally:  # Restore global state and release lock.
                mkvpropedit_wrapper.release_media_edit_lock(second_lock)  # Release reacquired lock.
                mkvpropedit_wrapper.MEDIA_LOCK_DIR = original_lock_dir  # Restore original media lock directory.

    def test_cli_process_reports_match_rename_resolution(self) -> None:  # Verify report creation paths equal rename consumption paths.
        parsed_report = report.build_report_argument_parser().parse_args(["--audio", "--subtitles", "--input-dir", "G:/Series/", "--run-id", "runSame"])  # Parse report stage arguments.
        from track_metadata_renamer import build_process_argument_parser  # Import process parser after report module setup.
        parsed_rename = build_process_argument_parser().parse_args(["--video", "--audio", "--subtitles", "--input-dir", "G:/Series/", "--run-id", "runSame"])  # Parse rename stage arguments.
        report_audio_path = report.resolve_report_path(parsed_report.input_dir, parsed_report.audio_report, report.AUDIO_REPORT_FILENAME, parsed_report.run_id)  # Resolve generated audio report path.
        report_subtitle_path = report.resolve_report_path(parsed_report.input_dir, parsed_report.subtitle_report, report.SUBTITLE_REPORT_FILENAME, parsed_report.run_id)  # Resolve generated subtitle report path.
        rename_audio_path = report.resolve_report_path(parsed_rename.input_dir, parsed_rename.audio_report, report.AUDIO_REPORT_FILENAME, parsed_rename.run_id)  # Resolve consumed audio report path.
        rename_subtitle_path = report.resolve_report_path(parsed_rename.input_dir, parsed_rename.subtitle_report, report.SUBTITLE_REPORT_FILENAME, parsed_rename.run_id)  # Resolve consumed subtitle report path.
        self.assertEqual(report_audio_path, rename_audio_path)  # Verify audio report handoff is exact.
        self.assertEqual(report_subtitle_path, rename_subtitle_path)  # Verify subtitle report handoff is exact.


if __name__ == "__main__":  # Run tests when invoked as a script.
    unittest.main()  # Execute standard-library tests.
