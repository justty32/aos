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


# claude's input box (2.1.325, seen 11-16 ok-small): the lines between the last two full-width rules, the first starting with ❯.
# Empty = nothing after ❯ but its dim (SGR 2) placeholder, like 'Try "create a util..."'. Anything else = someone typed (or it cannot be read).
RULE, INPUT_MARK = "\u2500", "\u276f"
ESC_TOKEN = re.compile(r"\x1b\[([0-9:;]*)m|\x1b(?:\[[0-9:;<=>?]*[ -/]*[@-~]|\][^\x07\x1b]*(?:\x07|\x1b\\)|.)|([^\x1b]+)")
FOOTER_MAX = 3            # non-empty lines allowed under the box (the mode / hint footer); more = not claude's live input box


def _dim_after(params, dim):
    """SGR parameters -> dim state; the colour parameters of 38/48/58 (;5;N or ;2;R;G;B) are skipped, not read as 2 = dim."""
    parts = params.replace(":", ";").split(";") if params else ["0"]
    i = 0
    while i < len(parts):
        p = parts[i]
        if p in ("38", "48", "58"):
            kind = parts[i + 1] if i + 1 < len(parts) else ""
            i += 5 if kind == "2" else 3 if kind == "5" else 2
            continue
        if p in ("", "0", "22"):
            dim = False
        elif p == "2":
            dim = True
        i += 1
    return dim


def _text(line, dim_too=True):
    """One capture-pane -e line without escapes; dim_too=False also drops the dim (SGR 2) runs."""
    out, dim = [], False
    for m in ESC_TOKEN.finditer(line):
        if m.group(2) is not None:
            if dim_too or not dim:
                out.append(m.group(2))
        elif m.group(1) is not None:
            dim = _dim_after(m.group(1), dim)
    return "".join(out)


def input_state(screen):
    """'empty', 'typed' or 'unknown' for claude's input box in capture-pane -p -e text."""
    lines = screen.split("\n")
    rules = [i for i, line in enumerate(lines) if len(_text(line).strip()) >= 10 and set(_text(line).strip()) == {RULE}]
    if len(rules) < 2 or rules[-1] - rules[-2] < 2:
        return "unknown"
    if len([line for line in lines[rules[-1] + 1:] if _text(line).strip()]) > FOOTER_MAX:
        return "unknown"                                       # an old box further up (the CLI left, a dialog below it)
    box = lines[rules[-2] + 1:rules[-1]]
    if not _text(box[0]).startswith(INPUT_MARK):
        return "unknown"
    if len(box) > 1:
        return "typed"                                         # a second line (Shift+Enter, or long text wrapped)
    typed = _text(box[0], dim_too=False).replace(INPUT_MARK, "", 1)
    return "typed" if typed.replace("\xa0", " ").strip() else "empty"


def input_clear(cell):
    """True only when claude's input box on the open screen is empty, so aos may type into it without joining someone's half-typed words.
    Known limit: a key pressed between this look and the typing can still be joined (repo-aos 11-16: noted, not fixed)."""
    r = cell.tmux("capture-pane", "-p", "-e", "-t", cli_base.TMUX_SESSION)
    return getattr(r, "returncode", 1) == 0 and input_state(r.stdout or "") == "empty"


def typed_warning(command):
    aos_flags.warn("aos-eca", "%s not typed into the open screen: its input box has text (or cannot be read); "
                   "the letter stays queued and is tried again next round" % command)


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
    if not input_clear(cell):
        typed_warning(command)
        return None                                           # someone's words in the input box: not typed, the letter stays

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
