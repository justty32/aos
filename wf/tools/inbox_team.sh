#!/usr/bin/env bash
# Create, extend, and archive inbox teams.
set -uo pipefail

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd) || exit 1
default_inbox_root="$script_dir/../inbox"
inbox_root=${WF_INBOX_ROOT:-${AGENT_INBOX_ROOT:-$default_inbox_root}}
teams_dir="$inbox_root/teams"

usage() {
    printf 'Usage:\n' >&2
    printf '  %s create <team> <leader> [member ...]\n' "${0##*/}" >&2
    printf '  %s add    <team> <session> [session ...]\n' "${0##*/}" >&2
    printf '  %s close  <team>\n' "${0##*/}" >&2
}
fail() { printf 'inbox_team: %s\n' "$1" >&2; exit 1; }
debug() { printf 'inbox_team: %s\n' "$1" >&2; }

valid_name() {
    case "$1" in ''|*[!A-Za-z0-9._-]*) return 1 ;; *) return 0 ;; esac
}

validate_sessions() {
    local session prior
    local -a seen=()
    for session in "$@"; do
        valid_name "$session" || fail 'session may contain only letters, digits, dot, underscore, hyphen'
        for prior in "${seen[@]+"${seen[@]}"}"; do
            [ "$session" != "$prior" ] || fail "duplicate session argument: $session"
        done
        seen+=("$session")
    done
}

session_team() {
    local wanted=$1 members_file
    for members_file in "$teams_dir"/*/members; do
        [ -f "$members_file" ] || continue
        if grep -Fqx -- "$wanted" "$members_file"; then
            printf '%s\n' "${members_file%/members}"
            return 0
        fi
    done
    return 1
}

update_roster() {
    local members_file=$1 closed_date=$2 member heading tmp
    [ -f "$inbox_root/ROSTER.md" ] || return 0
    while IFS= read -r member || [ -n "$member" ]; do
        heading="### \`$member\`"
        if ! grep -Fqx -- "$heading" "$inbox_root/ROSTER.md"; then
            debug "ROSTER entry not found for session: $member"
            continue
        fi
        tmp=$(mktemp "$inbox_root/.inbox-team-roster.XXXXXX") || {
            debug "cannot create temporary ROSTER file for session: $member"; continue;
        }
        if ! awk -v heading="$heading" -v replacement="- **狀態**：已收線（$closed_date）" '
            /^### `/ { active = ($0 == heading) }
            active && !replaced && index($0, "- **狀態**：") == 1 {
                print replacement; replaced = 1; changed = 1; next
            }
            { print }
            END { if (!changed) exit 4 }
        ' "$inbox_root/ROSTER.md" > "$tmp"; then
            debug "ROSTER status line not found for session: $member"
            rm -f -- "$tmp" 2>/dev/null || true
            continue
        fi
        chmod --reference="$inbox_root/ROSTER.md" "$tmp" 2>/dev/null || true
        if ! mv -- "$tmp" "$inbox_root/ROSTER.md"; then
            debug "cannot update ROSTER status for session: $member"
            rm -f -- "$tmp" 2>/dev/null || true
        fi
    done < "$members_file"
}

[ $# -ge 1 ] || { usage; exit 2; }
action=$1
shift
case "$action" in
    create)
        [ $# -ge 2 ] || { usage; exit 2; }
        team=$1
        shift
        valid_name "$team" || fail 'team may contain only letters, digits, dot, underscore, hyphen'
        validate_sessions "$@"
        team_dir="$teams_dir/$team"
        members_file="$team_dir/members"
        [ ! -e "$team_dir" ] || fail "team already exists: $team"
        for session in "$@"; do
            if existing=$(session_team "$session"); then
                fail "session already belongs to team ${existing##*/}: $session"
            fi
        done
        mkdir -p "$teams_dir" || fail "cannot create teams directory: $teams_dir"
        mkdir "$team_dir" || fail "cannot create team directory: $team_dir"
        tmp=''
        cleanup_create() {
            [ -z "$tmp" ] || [ ! -e "$tmp" ] || rm -f -- "$tmp" 2>/dev/null || true
            [ -e "$members_file" ] || rmdir -- "$team_dir" 2>/dev/null || true
        }
        trap cleanup_create EXIT
        trap 'exit 130' HUP INT TERM
        tmp=$(mktemp "$team_dir/.members.XXXXXX") || fail 'cannot create temporary membership file'
        printf '%s\n' "$@" > "$tmp" || fail 'cannot write team membership'
        mv -- "$tmp" "$members_file" || fail "cannot publish team membership: $members_file"
        tmp=''
        trap - EXIT
        printf '%s\n' "$members_file"
        ;;
    add)
        [ $# -ge 2 ] || { usage; exit 2; }
        team=$1
        shift
        valid_name "$team" || fail 'team may contain only letters, digits, dot, underscore, hyphen'
        validate_sessions "$@"
        members_file="$teams_dir/$team/members"
        [ -f "$members_file" ] || fail "team does not exist: $team"
        for session in "$@"; do
            if existing=$(session_team "$session"); then
                fail "session already belongs to team ${existing##*/}: $session"
            fi
        done
        tmp=''
        cleanup_add() { [ -z "$tmp" ] || [ ! -e "$tmp" ] || rm -f -- "$tmp" 2>/dev/null || true; }
        trap cleanup_add EXIT
        trap 'exit 130' HUP INT TERM
        tmp=$(mktemp "$teams_dir/$team/.members.XXXXXX") || fail 'cannot create temporary membership file'
        { cat -- "$members_file"; printf '%s\n' "$@"; } > "$tmp" || fail 'cannot write team membership'
        mv -- "$tmp" "$members_file" || fail "cannot publish team membership: $members_file"
        tmp=''
        trap - EXIT
        printf '%s\n' "$members_file"
        ;;
    close)
        [ $# -eq 1 ] || { usage; exit 2; }
        team=$1
        valid_name "$team" || fail 'team may contain only letters, digits, dot, underscore, hyphen'
        source_dir="$teams_dir/$team"
        [ -f "$source_dir/members" ] || fail "team does not exist: $team"
        close_date=$(date '+%Y-%m-%d') || fail 'cannot read the current date'
        destination="$inbox_root/done/$close_date/teams/$team"
        [ ! -e "$destination" ] || fail "closed team destination already exists: $destination"
        mkdir -p "${destination%/$team}" || fail 'cannot create closed teams directory'
        mv -- "$source_dir" "$destination" || fail "cannot close team into: $destination"
        printf '%s\n' "$destination"
        update_roster "$destination/members" "$close_date"
        ;;
    *) usage; exit 2 ;;
esac
