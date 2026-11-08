#!/bin/sh
# Moderate the local forum (pin, feature, soft delete) and grant or revoke line permissions.
exec python3 "$(dirname "$0")/progress_board/forum.py" admin "$@"
