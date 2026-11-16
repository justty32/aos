# screen_slash sends allowlisted commands to an open CLI screen and returns masked output without opening a screen.
import os
import re
import time

import aos_flags

from .common import cli_ask, cli_base

SCREEN_ONLY = {"/context": ("claude",)}
SHELLS = {"bash", "zsh", "sh", "fish", "dash"}
SCREEN_LIMIT = 3800
SCREEN_WAIT = 8

# Copied from extras/aos-view/aos-view SECRET_RES, with the reviewed AWS access-key addition.
SECRET_RES = [
    re.compile(r"\b(sk-[A-Za-z0-9_\-]{12,}|ghp_[A-Za-z0-9]{20,}|gho_[A-Za-z0-9]{20,}|AIza[A-Za-z0-9_\-]{20,}"
               r"|xox[baprs]-[A-Za-z0-9\-]{10,}|AKIA[0-9A-Z]{16})"),
    re.compile(r"(Bearer\s+)[A-Za-z0-9._\-]{12,}"),
    re.compile(r"\b([A-Z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD)[A-Z0-9_]*\s*=\s*)\S+"),
]
FOOTER_STARTS = "\u256d\u256e\u2570\u256f\u2502\u2500>\u276f"


def note(text):
    return aos_flags.aos_note("slash", text)


def screen_output(screen, command):
    """Discard the bottom input box before locating the final command echo."""
    lines = screen.splitlines()
    while lines:
        tail = lines[-1].strip()
        if tail and not tail.startswith(tuple(FOOTER_STARTS)) and "for shortcuts" not in tail:
            break
        lines.pop()
    for i in range(len(lines) - 1, -1, -1):
        if command in lines[i]:
            return "\n".join(lines[i + 1:]).rstrip()
    return None


def screen_slash(command, cfg, cell, stack):
    """Return a slash note, or None while busy so the caller can leave its letter queued."""
    allowed = SCREEN_ONLY.get(command)
    if not allowed:
        return note("screen command is not supported")
    # Resolve back to the allowlist's key: never type message text or appended arguments.
    command = next(key for key in SCREEN_ONLY if key == command)
    if cfg["kind"] not in allowed:
        return note(command + ": only claude's screen has this command")
    if not cell.alive():
        return note(command + ": a screen must be open (aos-agent open); aos does not open one for you")
    if os.path.exists(cell.file("busy.txt")):
        return None
    pane = cell.tmux("display-message", "-p", "-t", cli_base.TMUX_SESSION, "#{pane_current_command}")
    if pane.returncode != 0 or pane.stdout.strip() in SHELLS:
        return note(command + ": the screen is not running claude; nothing was typed")

    def capture():
        return cell.tmux("capture-pane", "-p", "-J", "-S", "-300", "-t", cli_base.TMUX_SESSION).stdout

    before = capture()
    cli_ask.type_line(cell, command)
    start = time.monotonic()
    previous, current, output = before, before, None
    while time.monotonic() - start < SCREEN_WAIT:
        time.sleep(0.5)
        current = capture()
        output = screen_output(current, command)
        if time.monotonic() - start >= 1.5 and current != before and current == previous and output:
            break
        previous = current
    if output is None:
        return note(command + ": the command was not seen returning on the screen; no screen text was copied")
    if "PRIVATE KEY" in output:
        return note(command + ": the screen contains PRIVATE KEY text; no screen text was copied")
    output = SECRET_RES[0].sub("[secret hidden]", output)
    output = SECRET_RES[1].sub(r"\1[secret hidden]", output)
    output = SECRET_RES[2].sub(r"\1[secret hidden]", output)
    if len(output) > SCREEN_LIMIT:
        output = output[:SCREEN_LIMIT] + "\u2026(cut)"
    return note(command + ": typed into the open screen; it printed:\n" + output)
