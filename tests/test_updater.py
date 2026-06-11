"""Tests for the git self-updater (all git calls mocked)."""

import subprocess
from unittest.mock import MagicMock, patch

import server.updater as updater


def _completed(stdout="", returncode=0):
    return MagicMock(stdout=stdout, returncode=returncode, stderr="")


class TestPhasePercent:
    def test_receiving_objects_maps_into_band(self):
        # Receiving objects band is 10..85
        assert updater._phase_percent("Receiving objects", 0) == 10
        assert updater._phase_percent("Receiving objects", 100) == 85
        mid = updater._phase_percent("Receiving objects", 50)
        assert 10 < mid < 85

    def test_resolving_deltas_band(self):
        assert updater._phase_percent("Resolving deltas", 100) == 98


class TestIsGitRepo:
    def test_true(self):
        with patch.object(updater, "_run_git", return_value=_completed("true\n")):
            assert updater.is_git_repo() is True

    def test_false_when_git_missing(self):
        with patch.object(updater, "_run_git", side_effect=FileNotFoundError):
            assert updater.is_git_repo() is False


class TestRunUpdate:
    def _fake_popen(self, lines):
        proc = MagicMock()
        proc.stdout = iter(lines)
        proc.returncode = 0
        proc.wait.return_value = 0
        return proc

    def test_reports_increasing_progress_and_succeeds(self):
        updater._cancel_event.clear()
        progress_calls = []

        git_results = {
            "rev-parse_HEAD": _completed("oldsha\n"),
            "branch": _completed("dev\n"),
            "merge": _completed("Updating\n"),
        }

        def fake_run_git(args, **kw):
            if args[:2] == ["rev-parse", "--abbrev-ref"]:
                return git_results["branch"]
            if args[:1] == ["merge"]:
                return git_results["merge"]
            if args[:1] == ["rev-parse"]:
                return git_results["rev-parse_HEAD"]
            return _completed()

        lines = [
            "Counting objects:  50% (5/10)\n",
            "Receiving objects:  20% (2/10)\n",
            "Receiving objects: 100% (10/10)\n",
            "Resolving deltas: 100% (3/3)\n",
        ]

        with patch.object(updater, "is_git_repo", return_value=True), \
             patch.object(updater, "_run_git", side_effect=fake_run_git), \
             patch.object(updater.subprocess, "Popen", return_value=self._fake_popen(lines)):
            updater.run_update(lambda pct, msg: progress_calls.append((pct, msg)))

        percents = [p for p, _ in progress_calls]
        assert percents == sorted(percents)  # monotonically increasing
        assert max(percents) >= 90

    def test_cancel_midway_rolls_back(self):
        updater._cancel_event.clear()

        def fake_run_git(args, **kw):
            return _completed("oldsha\n")

        proc = MagicMock()
        # First line triggers the cancel check
        proc.stdout = iter(["Receiving objects:  10% (1/10)\n"])
        proc.returncode = 0

        def progress(pct, msg):
            updater._cancel_event.set()  # simulate cable unplugged

        with patch.object(updater, "is_git_repo", return_value=True), \
             patch.object(updater, "_run_git", side_effect=fake_run_git) as mock_git, \
             patch.object(updater.subprocess, "Popen", return_value=proc):
            try:
                updater.run_update(progress)
            except RuntimeError as exc:
                assert "abgebrochen" in str(exc).lower()
            else:
                raise AssertionError("expected RuntimeError on cancel")

        proc.terminate.assert_called_once()
        # Rollback uses reset --hard
        assert any(c.args[0][:1] == ["reset"] for c in mock_git.call_args_list)
        updater._cancel_event.clear()

    def test_fetch_failure_raises(self):
        updater._cancel_event.clear()
        proc = MagicMock()
        proc.stdout = iter([])
        proc.returncode = 1
        proc.wait.return_value = 1

        with patch.object(updater, "is_git_repo", return_value=True), \
             patch.object(updater, "_run_git", return_value=_completed("oldsha\n")), \
             patch.object(updater.subprocess, "Popen", return_value=proc):
            try:
                updater.run_update(lambda p, m: None)
            except RuntimeError as exc:
                assert "fetch" in str(exc).lower()
            else:
                raise AssertionError("expected RuntimeError on fetch failure")

    def test_not_a_repo_raises(self):
        with patch.object(updater, "is_git_repo", return_value=False):
            try:
                updater.run_update(lambda p, m: None)
            except RuntimeError as exc:
                assert "git" in str(exc).lower()
            else:
                raise AssertionError("expected RuntimeError")


class TestStartUpdateAsync:
    def test_done_called_on_success(self):
        results = []
        with patch.object(updater, "run_update") as mock_run, \
             patch.object(updater, "current_revision", side_effect=["old", "new"]):
            updater.start_update_async(
                lambda p, m: None,
                lambda ok, msg: results.append((ok, msg)),
            )
            # The worker runs in a thread; join via the lock
            with updater._update_lock:
                pass
        mock_run.assert_called_once()
        assert results and results[0][0] is True

    def test_done_called_on_failure(self):
        results = []
        with patch.object(updater, "run_update", side_effect=RuntimeError("boom")), \
             patch.object(updater, "current_revision", return_value="old"):
            updater.start_update_async(
                lambda p, m: None,
                lambda ok, msg: results.append((ok, msg)),
            )
            with updater._update_lock:
                pass
        assert results and results[0][0] is False
        assert "boom" in results[0][1]
