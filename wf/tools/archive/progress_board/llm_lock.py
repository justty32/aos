"""Serialize board model requests across processes with bounded optional waiting."""
import contextlib
import fcntl
from pathlib import Path
import sys
import time


@contextlib.contextmanager
def llm_lock(board, wait_timeout=0):
    """Yield ownership; workers skip immediately and CLI callers wait at most 120s."""
    path = Path(board) / 'data/llm.lock'
    path.parent.mkdir(parents=True, exist_ok=True)
    timeout = min(120, max(0, wait_timeout))
    deadline = time.monotonic() + timeout
    acquired = False
    with path.open('a') as stream:
        try:
            while True:
                try:
                    fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    acquired = True
                    break
                except BlockingIOError:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        if timeout:
                            print('dash: warning: busy, skipped', file=sys.stderr)
                        break
                    time.sleep(min(0.05, remaining))
            yield acquired
        finally:
            if acquired:
                fcntl.flock(stream, fcntl.LOCK_UN)
