"""Run the local progress board server, detail and answer endpoints, snapshots, and summaries."""
import functools
import datetime as dt
import http.server
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import threading
import time

sys.dont_write_bytecode = True
from answers import AnswerHandlerMixin
from details_api import DetailHandlerMixin
from collect import board_path, collect, copy_assets, load_config, summary_state, write_state
from summarize import maybe_summarize

TEXT_TYPES = {".md": "text/markdown", ".json": "application/json", ".jsonl": "application/x-ndjson",
              ".txt": "text/plain", ".log": "text/plain", ".html": "text/html", ".css": "text/css",
              ".js": "text/javascript"}
USAGE = "python3 dash.py <serve|start|stop|status|collect|summarize> [--port N] [--force]"


def fail(code, reason):
    print(f"dash: error: {code} {str(reason).replace(chr(10), ' ')} (usage: {USAGE})",
          file=sys.stderr)
    return 1


def warning(reason):
    print(f"dash: warning: {str(reason).replace(chr(10), ' ')}", file=sys.stderr)


def arguments(args):
    if not args:
        raise ValueError("ArgumentsBad a command is required")
    if "--help" in args or "-h" in args:
        print(f"Usage: {USAGE}\nserve: run in foreground; start/stop/status: manage the server\n"
              "collect: refresh the static snapshot; summarize: summarize once\n"
              "--port N: override the configured port; --force: force a summary")
        return None
    command, *rest = args
    if command.startswith("-"):
        raise ValueError(f"FlagUnknown {command}")
    if command not in ("serve", "start", "stop", "status", "collect", "summarize"):
        raise ValueError(f"CommandUnknown {command}")
    port, force = None, False
    while rest:
        flag = rest.pop(0)
        if flag == "--port":
            if not rest:
                raise ValueError("ArgumentsBad --port requires an integer")
            try:
                port = int(rest.pop(0))
                if not 1 <= port <= 65535:
                    raise ValueError
            except ValueError:
                raise ValueError("ArgumentsBad port must be between 1 and 65535") from None
        elif flag == "--force" and command == "summarize":
            force = True
        elif flag.startswith("-"):
            raise ValueError(f"FlagUnknown {flag}")
        else:
            raise ValueError(f"ArgumentsBad unexpected argument {flag}")
    return command, port, force


def live(pid):
    if not pid or pid < 1:
        return False
    try:
        os.kill(pid, 0)
        stat = Path(f"/proc/{pid}/stat")
        if stat.exists() and stat.read_text().rsplit(")", 1)[1].split()[0] == "Z":
            return False
        return True
    except (OSError, IndexError):
        return False


def read_pid(path):
    try:
        return int(path.read_text().strip())
    except (OSError, ValueError):
        return None


def snapshot(board, cfg, running=False, summarizing=False):
    state = collect(board, cfg)
    state["server"] = running
    state["summary"]["running"] = summarizing
    write_state(board, state)
    return state


def serve(board, port):
    data = board / "data"
    data.mkdir(parents=True, exist_ok=True)
    copy_assets(board)
    stopped = threading.Event()
    state_lock = threading.Lock()
    summary_thread = None

    class Handler(DetailHandlerMixin, AnswerHandlerMixin, http.server.SimpleHTTPRequestHandler):
        def refresh_answers(self):
            with state_lock:
                busy = summary_thread is not None and summary_thread.is_alive()
                snapshot(board, load_config(), True, busy)

        extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map,
                          **{ext: f"{kind}; charset=utf-8" for ext, kind in TEXT_TYPES.items()}}

        def end_headers(self):
            self.send_header("Cache-Control", "no-store")
            super().end_headers()

        def log_message(self, fmt, *values):
            with (data / "server.log").open("a", encoding="utf-8") as log:
                log.write(f"dash: request {self.log_date_time_string()} {fmt % values}\n")

    Handler.board = board

    class Server(http.server.ThreadingHTTPServer):
        def handle_error(self, request, client_address):
            warning("HTTP request handling failed")

    server = Server(("127.0.0.1", port), functools.partial(Handler, directory=str(board)))
    server.timeout = 0.25

    def summarize(cfg):
        try:
            maybe_summarize(board, cfg)
        except Exception as exc:
            warning(f"Summary worker failed: {exc}")
        finally:
            with state_lock:
                if not stopped.is_set():
                    try:
                        state = json.loads((data / "state.json").read_text(encoding="utf-8"))
                        now = dt.datetime.now().astimezone()
                        state["summary"] = summary_state(board, cfg, now, state["warnings"])
                        state["generated_at"] = now.isoformat()
                        write_state(board, state)
                    except Exception as exc:
                        warning(f"Summary state refresh failed: {exc}")

    def loop():
        nonlocal summary_thread
        while not stopped.is_set():
            interval = 15
            try:
                cfg = load_config()
                interval = max(0.1, float(cfg["collect_interval_sec"]))
                busy = summary_thread is not None and summary_thread.is_alive()
                with state_lock:
                    state = snapshot(board, cfg, True, busy)
                    if not busy and not stopped.is_set():
                        summary_thread = threading.Thread(target=summarize, args=(cfg,), daemon=True)
                        state["summary"]["running"] = True
                        write_state(board, state)
                        summary_thread.start()
            except Exception as exc:
                warning(f"Collection loop failed: {exc}")
            stopped.wait(interval)

    def shutdown(signum, frame):
        stopped.set()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    worker = None
    try:
        snapshot(board, load_config(), True)
        worker = threading.Thread(target=loop, daemon=True)
        worker.start()
        while not stopped.is_set():
            server.handle_request()
    finally:
        stopped.set()
        server.server_close()
        if worker:
            worker.join()
        snapshot(board, load_config(), False, False)
        pidfile = data / "server.pid"
        if read_pid(pidfile) == os.getpid():
            pidfile.unlink(missing_ok=True)
    return 0


def start(board, port):
    data = board / "data"
    data.mkdir(parents=True, exist_ok=True)
    pidfile = data / "server.pid"
    url = f"http://127.0.0.1:{port}/"
    if live(read_pid(pidfile)):
        print(f"dash: already running {url}")
        return 0
    with (data / "server.log").open("ab") as log:
        child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "serve",
                                  "--port", str(port)], stdin=subprocess.DEVNULL,
                                 stdout=log, stderr=log, start_new_session=True)
    pidfile.write_text(f"{child.pid}\n", encoding="utf-8")
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and child.poll() is None:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                print(f"dash: started {url} (pid {child.pid})")
                return 0
        except OSError:
            time.sleep(0.1)
    if child.poll() is None:
        child.terminate()
    pidfile.unlink(missing_ok=True)
    return fail("StartFailed", f"server did not become ready; see {data / 'server.log'}")


def stop(board):
    pidfile = board / "data/server.pid"
    pid = read_pid(pidfile)
    if not live(pid):
        pidfile.unlink(missing_ok=True)
        print("dash: not running")
        return 0
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    deadline = time.monotonic() + 5
    while live(pid) and time.monotonic() < deadline:
        time.sleep(0.1)
    pidfile.unlink(missing_ok=True)
    print("dash: stopped")
    return 0


def main():
    try:
        parsed = arguments(sys.argv[1:])
        if parsed is None:
            return 0
    except ValueError as exc:
        code, reason = str(exc).split(" ", 1)
        return fail(code, reason)
    try:
        command, requested_port, force = parsed
        board, cfg = board_path(), load_config()
        port = requested_port if requested_port is not None else int(cfg["port"])
        if command == "serve":
            return serve(board, port)
        if command == "start":
            return start(board, port)
        if command == "stop":
            return stop(board)
        if command == "status":
            state = {}
            try:
                state = json.loads((board / "data/state.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                pass
            print(f"dash: {'running' if live(read_pid(board / 'data/server.pid')) else 'not running'}\n"
                  f"URL: http://127.0.0.1:{port}/\nBoard dir: {board}\n"
                  f"Last generated_at: {state.get('generated_at', 'none')}")
        elif command == "collect":
            copy_assets(board)
            snapshot(board, cfg)
            print(board / "index.html")
        elif command == "summarize":
            result = maybe_summarize(board, cfg, force)
            print(result)
            return int(result == "error")
        return 0
    except Exception as exc:
        return fail("OperationFailed", exc)


if __name__ == "__main__":
    sys.exit(main())
