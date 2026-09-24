#!/usr/bin/env bash
# Continuously announce new dispatcher-facing messages once. This watcher is
# terminal-neutral and only observes the inbox new/ directory.
set -uo pipefail

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd) || exit 1
default_inbox_root="$script_dir/../inbox"
inbox_root=${WF_INBOX_ROOT:-${AGENT_INBOX_ROOT:-$default_inbox_root}}

poll_seconds=${WF_INBOX_POLL_SECONDS:-${AGENT_INBOX_POLL_SECONDS:-20}}
new_dir="$inbox_root/new"
announced_dir="$inbox_root/.state/announced"

debug() { printf 'notify_watch: %s\n' "$1" >&2; }

valid_name() {
    case "$1" in
        ''|*[!A-Za-z0-9._-]*) return 1 ;;
        *) return 0 ;;
    esac
}

valid_status() {
    case "$1" in
        REQUEST|DONE|BLOCKED|NEEDS-USER|FAILED|PROGRESS) return 0 ;;
        *) return 1 ;;
    esac
}

case "$poll_seconds" in
    ''|*[!0-9]*) debug 'poll interval must be a positive integer'; exit 1 ;;
esac
[ "$poll_seconds" -gt 0 ] || { debug 'poll interval must be a positive integer'; exit 1; }

message_from=''
message_status=''
message_headline=''

parse_message() {
    local path=$1 line in_frontmatter=0 after_frontmatter=0
    message_from=''
    message_status=''
    message_headline=''
    while IFS= read -r line || [ -n "$line" ]; do
        if [ "$after_frontmatter" -eq 0 ]; then
            if [ "$line" = '---' ]; then
                if [ "$in_frontmatter" -eq 0 ]; then
                    in_frontmatter=1
                else
                    after_frontmatter=1
                fi
            elif [ "$in_frontmatter" -eq 1 ]; then
                case "$line" in
                    'from: '*) message_from=${line#from: } ;;
                    'status: '*) message_status=${line#status: } ;;
                esac
            fi
        elif [ -n "$line" ]; then
            case "$line" in '# '*) message_headline=${line#\# } ;; esac
            break
        fi
    done < "$path"
}

announce_once() {
    local message filename marker
    mkdir -p "$new_dir" "$announced_dir" || { debug "cannot create inbox state under: $inbox_root"; return 0; }
    for message in "$new_dir"/*.md; do
        [ -f "$message" ] || continue
        filename=${message##*/}
        marker="$announced_dir/$filename"
        [ ! -e "$marker" ] || continue
        parse_message "$message"
        if ! valid_name "$message_from" || ! valid_status "$message_status" || [ -z "$message_headline" ]; then
            debug "malformed message skipped: $message"
        else
            printf '[INBOX] %s %s — %s\n' "$message_from" "$message_status" "$message_headline"
        fi
        touch "$marker" 2>/dev/null || debug "cannot persist announcement marker: $marker"
    done
}

while true; do
    announce_once
    sleep "$poll_seconds" || true
done
