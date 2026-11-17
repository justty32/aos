#!/bin/sh
# Append a forum post or reply for a line to the local forum event file.
exec python3 "$(dirname "$0")/progress_board/forum.py" post "$@"
