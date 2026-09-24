#!/usr/bin/env bash
# Deliver a message to one member, team, topic, or the sender's upstream.
# A temporary file is moved into place for atomic publication.
set -uo pipefail

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd) || exit 1
default_inbox_root="$script_dir/../inbox"
inbox_root=${WF_INBOX_ROOT:-${AGENT_INBOX_ROOT:-$default_inbox_root}}

usage() {
    printf 'Usage:\n' >&2
    printf '  %s <sender> --to <recipient> <STATUS> <headline> [body_file]\n' "${0##*/}" >&2
    printf '  %s <sender> --team <team>    <STATUS> <headline> [body_file]\n' "${0##*/}" >&2
    printf '  %s <sender> --topic <topic>  <STATUS> <headline> [body_file]\n' "${0##*/}" >&2
    printf '  %s <sender> --up             <STATUS> <headline> [body_file]\n' "${0##*/}" >&2
}

fail() { printf 'inbox_mail: %s\n' "$1" >&2; exit 1; }

valid_name() {
    case "$1" in
        ''|*[!A-Za-z0-9._-]*) return 1 ;;
        *) return 0 ;;
    esac
}

[ $# -ge 2 ] || { usage; exit 2; }
sender=$1
mode=$2
valid_name "$sender" || fail 'sender may contain only letters, digits, dot, underscore, hyphen'

field=''
target=''
notice=''
case "$mode" in
    --up)
        [ $# -ge 4 ] && [ $# -le 5 ] || { usage; exit 2; }
        status=$3
        headline=$4
        body_file=${5-}
        matches=0
        leader=''
        for members_file in "$inbox_root"/teams/*/members; do
            [ -f "$members_file" ] || continue
            if grep -Fqx -- "$sender" "$members_file"; then
                matches=$((matches + 1))
                [ "$matches" -le 1 ] || fail "sender belongs to more than one team: $sender"
                IFS= read -r leader < "$members_file" || leader=''
            fi
        done
        if [ "$matches" -eq 1 ] && [ "$sender" != "$leader" ]; then
            valid_name "$leader" || fail 'team leader has an invalid name'
            field='to'
            target=$leader
            dest_dir="$inbox_root/mail/$leader"
            notice=$leader
        else
            dest_dir="$inbox_root/new"
            notice='dispatcher'
        fi
        ;;
    --to|--team|--topic)
        [ $# -ge 5 ] && [ $# -le 6 ] || { usage; exit 2; }
        target=$3
        status=$4
        headline=$5
        body_file=${6-}
        valid_name "$target" || fail 'target name may contain only letters, digits, dot, underscore, hyphen'
        case "$mode" in
            --to)
                if [ "$target" = dispatcher ]; then
                    dest_dir="$inbox_root/new"
                    notice='dispatcher'
                else
                    field='to'
                    dest_dir="$inbox_root/mail/$target"
                fi
                ;;
            --topic) field='topic'; dest_dir="$inbox_root/topics/$target" ;;
            --team)
                members_file="$inbox_root/teams/$target/members"
                [ -f "$members_file" ] || fail "team does not exist: $target"
                if [ "$sender" != dispatcher ] && ! grep -Fqx -- "$sender" "$members_file"; then
                    fail "sender does not belong to team $target: $sender"
                fi
                field='team'
                dest_dir="$inbox_root/teams/$target"
                ;;
        esac
        ;;
    *) usage; exit 2 ;;
esac

case "$status" in
    REQUEST|DONE|BLOCKED|NEEDS-USER|FAILED|PROGRESS) ;;
    *) fail "invalid STATUS '$status' (see PROTOCOL.md)" ;;
esac
if [[ -z $headline || $headline == *$'\n'* || $headline == *$'\r'* ]]; then
    fail 'headline must be one non-empty line'
fi
[ -z "$body_file" ] || [ -r "$body_file" ] || fail "body file is not readable: $body_file"

mkdir -p "$dest_dir" || fail "cannot create inbox directory: $dest_dir"
clock=$(date '+%Y%m%dT%H%M|%Y-%m-%dT%H:%M:%S%:z') || fail 'cannot read the current time'
stamp=${clock%%|*}
at=${clock#*|}
destination="$dest_dir/${stamp}-${sender}-${status}.md"
[ ! -e "$destination" ] || fail "a message already exists for this minute/sender/status: $destination"

tmp=''
cleanup() { [ -z "$tmp" ] || [ ! -e "$tmp" ] || rm -f -- "$tmp" 2>/dev/null || true; }
trap cleanup EXIT
trap 'exit 130' HUP INT TERM
tmp=$(mktemp "$inbox_root/.inbox-mail.XXXXXX") || fail "cannot create a temp file in: $inbox_root"
{
    printf -- '---\n'
    printf 'from: %s\n' "$sender"
    [ -z "$field" ] || printf '%s: %s\n' "$field" "$target"
    printf 'status: %s\n' "$status"
    printf 'at: %s\n' "$at"
    printf -- '---\n'
    printf '# %s\n\n' "$headline"
    if [ -n "$body_file" ]; then cat -- "$body_file"; else cat; fi
} > "$tmp" || fail 'could not write the message body'

mv -n -- "$tmp" "$destination" || fail "cannot publish message to: $destination"
[ ! -e "$tmp" ] || fail "a message already exists for this minute/sender/status: $destination"
tmp=''
trap - EXIT
printf '%s\n' "$destination"
[ -z "$notice" ] || printf 'delivered to %s\n' "$notice" >&2
