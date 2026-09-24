#!/usr/bin/env bash
set -uo pipefail

tools_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd) || exit 1
team="$tools_dir/inbox_team.sh"
mail="$tools_dir/inbox_mail.sh"
poll="$tools_dir/inbox_poll.sh"
pass_count=0
fail_count=0

run_test() {
    local name=$1 function=$2
    if (
        test_root=$(mktemp -d /tmp/inbox-test.XXXXXX) || exit 1
        trap 'rm -rf -- "$test_root"' EXIT
        export test_root AGENT_INBOX_ROOT="$test_root"
        "$function"
    ); then
        printf 'ok - %s\n' "$name"
        pass_count=$((pass_count + 1))
    else
        printf 'not ok - %s\n' "$name"
        fail_count=$((fail_count + 1))
    fi
}

member_routes() {
    local path
    "$team" create alpha lead-a work-a >/dev/null || return 1
    path=$("$mail" work-a --up PROGRESS 'member update' </dev/null 2>"$test_root/stderr") || return 1
    [ -f "$path" ] && [[ $path == "$test_root"/mail/lead-a/*.md ]] || return 1
    grep -Fqx 'to: lead-a' "$path" && grep -Fq 'delivered to lead-a' "$test_root/stderr"
}
leader_routes() {
    local path
    "$team" create alpha lead-a work-a >/dev/null || return 1
    path=$("$mail" lead-a --up DONE 'leader update' </dev/null 2>"$test_root/stderr") || return 1
    [ -f "$path" ] && [[ $path == "$test_root"/new/*.md ]] || return 1
    ! grep -q '^to:' "$path" && grep -Fq 'delivered to dispatcher' "$test_root/stderr"
}
unaffiliated_routes() {
    local path
    path=$("$mail" solo --up DONE 'solo update' </dev/null 2>"$test_root/stderr") || return 1
    [ -f "$path" ] && [[ $path == "$test_root"/new/*.md ]] && ! grep -q '^to:' "$path"
}
explicit_recipient() {
    local path
    "$team" create alpha lead-a work-a >/dev/null || return 1
    path=$("$mail" work-a --to peer-z PROGRESS 'direct update' </dev/null) || return 1
    [ -f "$path" ] && [[ $path == "$test_root"/mail/peer-z/*.md ]] && grep -Fqx 'to: peer-z' "$path"
}
explicit_dispatcher() {
    local path
    "$team" create alpha lead-a work-a >/dev/null || return 1
    path=$("$mail" work-a --to dispatcher PROGRESS 'escalated update' </dev/null 2>"$test_root/stderr") || return 1
    [ -f "$path" ] && [[ $path == "$test_root"/new/*.md ]] || return 1
    ! grep -q '^to:' "$path" && grep -Fq 'delivered to dispatcher' "$test_root/stderr"
}
ambiguous_fails() {
    mkdir -p "$test_root/teams/one" "$test_root/teams/two" || return 1
    printf '%s\n' lead-one shared > "$test_root/teams/one/members"
    printf '%s\n' lead-two shared > "$test_root/teams/two/members"
    ! "$mail" shared --up DONE ambiguous </dev/null >/dev/null 2>&1
}
team_rejects() {
    "$team" create alpha lead-a work-a >/dev/null || return 1
    ! "$mail" stranger --team alpha PROGRESS rejected </dev/null >/dev/null 2>&1
}
team_accepts() {
    local path
    "$team" create alpha lead-a work-a >/dev/null || return 1
    path=$("$mail" work-a --team alpha PROGRESS 'team update' </dev/null) || return 1
    [ -f "$path" ] && [[ $path == "$test_root"/teams/alpha/*.md ]] && grep -Fqx 'team: alpha' "$path"
}
wait_team_message() {
    local output
    "$team" create alpha lead-a work-a >/dev/null || return 1
    "$mail" lead-a --team alpha PROGRESS 'wake member' </dev/null >/dev/null || return 1
    output=$("$poll" work-a --wait --timeout 5) || return 1
    [[ $output == *'[TEAM:alpha]'* && $output == *'wake member'* ]]
}
wait_silent_timeout() {
    local rc
    "$poll" nobody --wait --timeout 2 > "$test_root/stdout"
    rc=$?
    [ "$rc" -eq 3 ] && [ ! -s "$test_root/stdout" ]
}
close_archives() {
    local today destination
    today=$(date '+%Y-%m-%d') || return 1
    "$team" create alpha lead-a work-a >/dev/null || return 1
    destination=$("$team" close alpha) || return 1
    [ "$destination" = "$test_root/done/$today/teams/alpha" ] &&
        [ -f "$destination/members" ] && [ ! -e "$test_root/teams/alpha" ]
}
create_existing_fails() {
    "$team" create alpha lead-a >/dev/null || return 1
    ! "$team" create alpha lead-b >/dev/null 2>&1
}
cross_team_fails() {
    "$team" create alpha lead-a work-a >/dev/null || return 1
    ! "$team" create beta lead-b work-a >/dev/null 2>&1
}
once_discovers_team() {
    local output
    "$team" create alpha lead-a work-a >/dev/null || return 1
    "$mail" lead-a --team alpha PROGRESS 'auto discovery' </dev/null >/dev/null || return 1
    output=$("$poll" work-a --once) || return 1
    [[ $output == *'[TEAM:alpha]'* && $output == *'auto discovery'* ]]
}

run_test 'member send routes to leader mail' member_routes
run_test 'leader send routes to new' leader_routes
run_test 'unaffiliated send routes to new' unaffiliated_routes
run_test 'explicit recipient overrides team route' explicit_recipient
run_test 'explicit dispatcher routes to new' explicit_dispatcher
run_test 'ambiguous team membership fails' ambiguous_fails
run_test 'team mail rejects nonmember' team_rejects
run_test 'team mail accepts member' team_accepts
run_test 'wait returns existing team message' wait_team_message
run_test 'wait timeout is silent' wait_silent_timeout
run_test 'close archives team' close_archives
run_test 'create rejects existing team' create_existing_fails
run_test 'create rejects cross-team member' cross_team_fails
run_test 'once auto-discovers team' once_discovers_team
printf 'ok %d fail %d\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
