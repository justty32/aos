# Preserve declared child observation trees and hand their location to the caller.
import json
import os
from pathlib import Path
import shutil

MARKER = '.observed_child.json'


def clear_child(stack):
    try:
        (Path(stack) / MARKER).unlink(missing_ok=True)
    except OSError:
        pass


def take_child(stack):
    marker = Path(stack) / MARKER
    try:
        value = json.loads(marker.read_text()).get('child')
        return value if isinstance(value, str) else None
    except (OSError, ValueError, AttributeError):
        return None
    finally:
        clear_child(stack)


def _warn_skipped(interface, error):
    """One warning line per skipped child account (open-16); same program name as observed.append."""
    import observed
    import tool_io
    if isinstance(error, AttributeError):
        error = 'aos-observed is not an object'
    tool_io.warn('skipped child observations declared in %s: %s' % (interface, error), prog=observed.program())


def copy_child(stack, name, child_stack, publish=True):
    """Copy only publicly declared accounts, preserving relative interface paths."""
    source = Path(child_stack)
    destination = Path(stack) / 'observed' / name
    copied = False
    for directory, _, files in os.walk(source):
        if 'interfaces.json' not in files:
            continue
        interface = Path(directory) / 'interfaces.json'
        try:
            declarations = json.loads(interface.read_text())
            if 'aos-observed' not in declarations:
                continue
            declared = declarations['aos-observed'].get('file')
            if not isinstance(declared, str) or not declared:
                raise ValueError('aos-observed.file is not a non-empty string')
            account = Path(directory) / declared
            relative = account.relative_to(source)
            # Public output paths must remain within the child's stack.
            try:
                account.resolve().relative_to(source.resolve())
            except ValueError:
                raise ValueError('%s points outside the child stack' % declared) from None
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(account, target)
            public = destination / interface.relative_to(source)
            public.parent.mkdir(parents=True, exist_ok=True)
            # Retain the observation declaration without exposing unrelated interfaces.
            public.write_text(json.dumps({'aos-observed': {'file': declared}}) + '\n')
            copied = True
        except (OSError, ValueError, TypeError, AttributeError) as error:
            _warn_skipped(interface, error)
            continue
    if not copied:
        return None
    relative = destination.relative_to(Path(stack)).as_posix()
    if publish:
        try:
            (Path(stack) / MARKER).write_text(json.dumps({'child': relative}) + '\n')
        except OSError:
            pass
    return relative
