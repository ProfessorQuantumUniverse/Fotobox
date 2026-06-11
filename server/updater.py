"""Self-update via git when the Fotobox comes online over Ethernet.

When a cable is plugged in, the box fetches the newest version from its git
remote and fast-forwards the working tree. Real progress is parsed from
``git``'s own ``--progress`` output (the "Receiving objects: NN%" / "Resolving
deltas: NN%" lines) and reported through a callback so the UI can show a live
percentage bar.

If the network drops mid-update the partial fetch is rolled back
(``git merge --abort`` / clean fetch state) so the previously working version
keeps running – we never leave the box on a half-pulled tree.
"""

import logging
import os
import re
import subprocess
import threading
from typing import Callable, Optional

logger = logging.getLogger(__name__)

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# git prints progress like "Receiving objects:  73% (1234/1690)" on stderr.
_PROGRESS_RE = re.compile(r"(Receiving objects|Resolving deltas|Counting objects|Compressing objects):\s+(\d+)%")

# Phasen-Gewichtung: das Empfangen der Objekte ist der lange Teil.
_PHASE_WEIGHTS = {
    "Counting objects": (0, 5),
    "Compressing objects": (5, 10),
    "Receiving objects": (10, 85),
    "Resolving deltas": (85, 98),
}

ProgressCallback = Callable[[int, str], None]

_update_lock = threading.Lock()
_cancel_event = threading.Event()


def _run_git(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", REPO_DIR, *args],
        capture_output=True, text=True, timeout=kwargs.pop("timeout", 30), **kwargs
    )


def is_git_repo() -> bool:
    try:
        res = _run_git(["rev-parse", "--is-inside-work-tree"])
        return res.returncode == 0 and res.stdout.strip() == "true"
    except (FileNotFoundError, subprocess.SubprocessError):
        return False


def current_revision() -> str:
    try:
        return _run_git(["rev-parse", "--short", "HEAD"]).stdout.strip()
    except (FileNotFoundError, subprocess.SubprocessError):
        return "?"


def cancel_update() -> None:
    """Signal a running update to stop and roll back (e.g. cable unplugged)."""
    _cancel_event.set()


def _phase_percent(phase: str, percent: int) -> int:
    lo, hi = _PHASE_WEIGHTS.get(phase, (0, 100))
    return int(lo + (hi - lo) * percent / 100)


def _abort_partial(branch_backup: Optional[str]) -> None:
    """Roll back to the previously working tree, discard partial fetch state."""
    try:
        _run_git(["merge", "--abort"])
    except subprocess.SubprocessError:
        pass
    if branch_backup:
        try:
            _run_git(["reset", "--hard", branch_backup])
        except subprocess.SubprocessError:
            pass
    logger.info("Update rolled back – previous version kept")


def run_update(progress: ProgressCallback) -> None:
    """Fetch + fast-forward the repo, reporting progress 0..100.

    ``progress(percent, message)`` is called repeatedly. A final call with
    percent == 100 (success) or a status message is always emitted by the
    caller in ``app.py``; here we only drive 0..99 plus the merge.
    """
    if not is_git_repo():
        raise RuntimeError("Kein git-Repository – Update nicht möglich")

    # Aktuellen Stand sichern, um bei Abbruch zurückrollen zu können.
    before = _run_git(["rev-parse", "HEAD"]).stdout.strip()
    progress(2, "Verbinde mit Server …")

    proc = subprocess.Popen(
        ["git", "-C", REPO_DIR, "fetch", "--progress", "origin"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
    )

    last_pct = 2
    assert proc.stdout is not None
    for line in proc.stdout:
        if _cancel_event.is_set():
            proc.terminate()
            _abort_partial(before)
            raise RuntimeError("Update abgebrochen (Netzwerk getrennt)")
        m = _PROGRESS_RE.search(line)
        if m:
            pct = _phase_percent(m.group(1), int(m.group(2)))
            if pct > last_pct:
                last_pct = pct
                progress(pct, "Lade Update herunter …")
    proc.wait()

    if proc.returncode != 0:
        _abort_partial(before)
        raise RuntimeError("git fetch fehlgeschlagen")

    if _cancel_event.is_set():
        _abort_partial(before)
        raise RuntimeError("Update abgebrochen (Netzwerk getrennt)")

    progress(max(last_pct, 90), "Wende Update an …")

    # Branch bestimmen und fast-forward-only mergen (keine Merge-Commits/Konflikte).
    branch = _run_git(["rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip() or "HEAD"
    merge = _run_git(["merge", "--ff-only", f"origin/{branch}"])
    if merge.returncode != 0:
        _abort_partial(before)
        raise RuntimeError("Update konnte nicht angewendet werden (kein Fast-Forward)")

    after = _run_git(["rev-parse", "HEAD"]).stdout.strip()
    progress(99, "Aufräumen …")
    if before == after:
        logger.info("Already up to date (%s)", current_revision())
    else:
        logger.info("Updated %s → %s", before[:7], after[:7])


def start_update_async(progress: ProgressCallback, done: Callable[[bool, str], None]) -> None:
    """Run :func:`run_update` in a daemon thread.

    ``done(success, message)`` is invoked when finished. Only one update runs
    at a time; concurrent calls are ignored.
    """
    def worker():
        if not _update_lock.acquire(blocking=False):
            logger.info("Update already running – ignoring duplicate trigger")
            return
        _cancel_event.clear()
        changed_from = current_revision()
        try:
            run_update(progress)
            new_rev = current_revision()
            if new_rev == changed_from:
                done(True, "Bereits aktuell")
            else:
                done(True, f"Aktualisiert auf {new_rev}")
        except Exception as exc:  # noqa: BLE001 – report any failure to the UI
            logger.error("Update failed: %s", exc)
            done(False, str(exc))
        finally:
            _update_lock.release()

    threading.Thread(target=worker, daemon=True).start()
