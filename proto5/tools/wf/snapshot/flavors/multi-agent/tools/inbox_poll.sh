#!/usr/bin/env bash
# Poll personal mail, team mail, subscribed topics, and append-only orders.
# Read state stays below the inbox root so repeated polls remain silent.
set -uo pipefail

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd) || exit 1
default_inbox_root="$script_dir/../inbox"
inbox_root=${WF_INBOX_ROOT:-${AGENT_INBOX_ROOT:-$default_inbox_root}}

usage() {
    printf 'Usage: %s <name> [--topics a,b,c] [--once | --watch | --wait [--timeout N]] [--interval N]\n' "${0##*/}" >&2
}
fail() { printf 'inbox_poll: %s\n' "$1" >&2; exit 1; }
debug() { printf 'inbox_poll: %s\n' "$1" >&2; }

valid_name() {
    case "$1" in ''|*[!A-Za-z0-9._-]*) return 1 ;; *) return 0 ;; esac
}
valid_status() {
    case "$1" in REQUEST|DONE|BLOCKED|NEEDS-USER|FAILED|PROGRESS) return 0 ;; *) return 1 ;; esac
}

[ $# -ge 1 ] || { usage; exit 2; }
member=$1
shift
valid_name "$member" || fail 'name may contain only letters, digits, dot, underscore, hyphen'

topics=()
mode=''
mode_count=0
interval=20
timeout=''
while [ $# -gt 0 ]; do
    case "$1" in
        --topics)
            [ $# -ge 2 ] || { usage; exit 2; }
            IFS=',' read -r -a topics <<< "$2"
            shift 2
            ;;
        --once|--watch|--wait)
            mode=${1#--}
            mode_count=$((mode_count + 1))
            shift
            ;;
        --interval)
            [ $# -ge 2 ] || { usage; exit 2; }
            interval=$2
            shift 2
            ;;
        --timeout)
            [ $# -ge 2 ] || { usage; exit 2; }
            timeout=$2
            shift 2
            ;;
        *) usage; exit 2 ;;
    esac
done

[ "$mode_count" -le 1 ] || { usage; exit 2; }
[ -n "$mode" ] || mode='once'
if [ -n "$timeout" ] && [ "$mode" != wait ]; then usage; exit 2; fi
case "$interval" in ''|*[!0-9]*) fail 'interval must be a positive integer' ;; esac
[ "$interval" -gt 0 ] || fail 'interval must be a positive integer'
if [ -n "$timeout" ]; then
    case "$timeout" in ''|*[!0-9]*) fail 'timeout must be a positive integer' ;; esac
    [ "$timeout" -gt 0 ] || fail 'timeout must be a positive integer'
fi
for topic in "${topics[@]+"${topics[@]}"}"; do
    valid_name "$topic" || fail "topic name may contain only letters, digits, dot, underscore, hyphen: $topic"
done

state_root="$inbox_root/.state/poll/$member"
mail_seen_dir="$state_root/mail-seen"
topic_seen_root="$state_root/topic-seen"
team_seen_root="$state_root/team-seen"
new_seen_dir="$state_root/new-seen"
orders_offset_file="$state_root/orders-offset"
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
                if [ "$in_frontmatter" -eq 0 ]; then in_frontmatter=1; else after_frontmatter=1; fi
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

mark_seen() { touch "$1" 2>/dev/null || debug "cannot persist read marker: $1"; }

scan_mailbox() {
    local dir=$1 seen_dir=$2 label=$3 message filename marker
    [ -d "$dir" ] || return 0
    mkdir -p "$seen_dir" || { debug "cannot create state directory: $seen_dir"; return 0; }
    for message in "$dir"/*.md; do
        [ -f "$message" ] || continue
        filename=${message##*/}
        marker="$seen_dir/$filename"
        [ ! -e "$marker" ] || continue
        parse_message "$message"
        if ! valid_name "$message_from" || ! valid_status "$message_status" || [ -z "$message_headline" ]; then
            debug "malformed message skipped: $message"
            mark_seen "$marker"
            continue
        fi
        printf '[%s] %s %s — %s — %s\n' "$label" "$message_from" "$message_status" "$message_headline" "$message"
        mark_seen "$marker"
    done
}

scan_orders() {
    local orders_file="$inbox_root/orders/$member.md" last_line=0 current_lines heading
    [ -f "$orders_file" ] || return 0
    if [ -r "$orders_offset_file" ]; then
        read -r last_line < "$orders_offset_file" || last_line=0
        case "$last_line" in ''|*[!0-9]*) last_line=0 ;; esac
    fi
    current_lines=$(awk 'END { print NR + 0 }' "$orders_file") || { debug "cannot read orders: $orders_file"; return 0; }
    [ "$current_lines" -ge "$last_line" ] || last_line=0
    if [ "$current_lines" -gt "$last_line" ]; then
        while IFS= read -r heading; do
            case "$heading" in '## '*) printf '[ORDERS] %s — %s\n' "${heading#\#\# }" "$orders_file" ;; esac
        done < <(tail -n "+$((last_line + 1))" "$orders_file")
    fi
    printf '%s\n' "$current_lines" > "$orders_offset_file" || debug "cannot persist orders offset: $orders_offset_file"
}

run_once() {
    local topic members_file team_dir team
    mkdir -p "$mail_seen_dir" "$topic_seen_root" "$team_seen_root" || {
        debug "cannot create state directory: $state_root"; return 0;
    }
    scan_mailbox "$inbox_root/mail/$member" "$mail_seen_dir" 'MAIL'
    for members_file in "$inbox_root"/teams/*/members; do
        [ -f "$members_file" ] || continue
        if grep -Fqx -- "$member" "$members_file"; then
            team_dir=${members_file%/members}
            team=${team_dir##*/}
            scan_mailbox "$team_dir" "$team_seen_root/$team" "TEAM:$team"
        fi
    done
    for topic in "${topics[@]+"${topics[@]}"}"; do
        scan_mailbox "$inbox_root/topics/$topic" "$topic_seen_root/$topic" "TOPIC:$topic"
    done
    scan_orders
    if [ "$member" = dispatcher ]; then
        scan_mailbox "$inbox_root/new" "$new_seen_dir" 'INBOX'
    fi
}

case "$mode" in
    once) run_once ;;
    watch)
        debug "watching name=$member interval=${interval}s"
        while true; do run_once; sleep "$interval" || true; done
        ;;
    wait)
        output=$(run_once)
        if [ -n "$output" ]; then printf '%s\n' "$output"; exit 0; fi
        start_time=$(date '+%s') || fail 'cannot read the current time'
        next_scan=$((start_time + interval))
        while true; do
            now=$(date '+%s') || fail 'cannot read the current time'
            if [ -n "$timeout" ] && [ $((now - start_time)) -ge "$timeout" ]; then exit 3; fi
            if [ "$now" -ge "$next_scan" ]; then
                output=$(run_once)
                if [ -n "$output" ]; then printf '%s\n' "$output"; exit 0; fi
                next_scan=$((now + interval))
            fi
            sleep 1 || true
        done
        ;;
esac
