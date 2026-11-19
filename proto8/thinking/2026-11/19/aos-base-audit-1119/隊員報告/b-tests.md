# b-tests 報告：現有測試全跑一次＋涵蓋表

隊員 b-tests；乾淨複本 `~/.aos/scratch/aos-base-audit-1119/src`（HEAD 3c4cc4c52），全程經 `../bin/clean`；`TMPDIR=b-tests/tmp`；4 條並行；每支 `timeout 600 python3 -B <檔> -v`；逐支 log 在 `b-tests/logs/`，原始結果 `results.txt`、`summ.txt`，表 `table.md`（本檔第 6 節同內容）。

## 1. 總表摘要

- 找到 293 支 `test_*.py`（不含 `proto8/archive/` 那支舊檔）。全跑完，約 2877 個 test case（unittest 的 Ran 加總）。
- 第一次跑：284 支綠、9 支非 0。逐支追根後**這 9 支全是環境／跑法問題，沒有一支是基底真壞**（第 3 節，調整後重跑都綠）。
- skip 共 36 個 case（11 支檔），原因見第 4 節。**值得注意：`test_subuid` 的 4 個「真換身分」測試在這台全 skip，sub:N 的真行為在現有測試裡沒被驗到；cgroup 整類也沒驗。**
- 最長：test_daily 368s、test_gdb_live 168s、test_paths_move 137s、test_do_task_fold 106s、test_lifecycle 95s。沒有 hang、沒有 timeout。
- 沒有 pytest；全用 unittest（檔案當腳本跑）。`cpp/aos-llm/tests/test_ls_backend.py` 是無輸出的腳本（退 0 即過）。

## 3. 9 支非 0 的判斷（全為環境／跑法，非真壞）

| 測試 | 第一次錯誤 | 判斷 | 重跑 |
|---|---|---|---|
| frontend/tests/{test_phase1,test_delivery,test_v2,test_compact_quiet,test_slash}（5 支） | `AOS_* variables are set; run through tests/run.sh` | 這幾支拒絕在有 `AOS_*` 的環境跑，而 `clean` 必設 `AOS_HOME`，與任務書規定衝突；不是壞 | `env -i … bash run.sh <名>`（PATH 帶複本 bin、`VIEW_TEST_TMP` 設好）：phase1 9（7 skip）、delivery 3、v2 7、compact_quiet 3、slash 28，全 OK |
| py/tests/apps/eca/test_switch.py（3 FAIL＋1 ERROR，class `TtySocket`） | 期望 sock 路徑在 `$XDG_RUNTIME_DIR/aos-tty-<uid>/`，實際在 `/tmp/aos-tty-1000/` | `py/aos/agentlib/cli_cell.py:24` 設計：XDG 路徑「太長」就退回 /tmp。我的 TMPDIR 在 `~/.aos/scratch/…/b-tests/tmp` 太長。環境 | `TMPDIR=/tmp/bt-b`：50 test 全 OK |
| py/tests/apps/feedback/test_feedback.py（1 FAIL） | `first['cwd']` 被縮成 `~/.aos/...`，測試期望絕對路徑 | 暫存夾在 HOME 下時程式縮寫成 `~`，測試沒預期。**測試對「暫存夾在 HOME 下」不穩**，與基底無關 | `TMPDIR=/tmp/bt-b`：11 OK |
| templates/tests/reviewer/test_reviewer.py（1 FAIL） | `AnswerMissing waited 35 s`（假腦 35s 內沒回） | 4 條並行負載下時間敏感；單獨重跑 21s OK。**flaky（35s 寫死）** | 單獨跑 OK |
| py/tools/aos/review_round/tests/test_suggestions.py | `ModuleNotFoundError: No module named 'aos'` | 當腳本跑時 `lib` 不在 sys.path，其他 review_round 測試卻能跑；這支依賴 `PYTHONPATH=proto8/lib`。跑法問題 | 加 `PYTHONPATH=$AOS_HOME/lib`：3 OK |

附帶發現（只是醜／不穩）：
- **測試殘留**：`cpp/aos-daemon/tests/support.py:13` 寫死 `mktemp -d /tmp/aos-daemon-b.XXXXXX`（不吃 TMPDIR）。我跑完 `/tmp/aos-daemon-b.*` 留 12 個夾（3zw26x、5UZQlj、9dn5La、ErVI5n、FRfi8k、HnL17y、PqmKVf、QRDj7h、ZIUhg2、xPdqKx、yyYISX、z5Sb5F；建立 12:46–12:48，是我這輪 daemon 測試留的，沒有行程在裡面，我沒刪）。這也是 test_subuid 真換身分被 skip 的原因。
- **無孤兒行程**：全跑完以 `/proc/*/cwd` 檢查，沒有 aos 行程的 cwd 在我的子夾、`src/` 或 `/tmp/aos-daemon-b.*`。機器上其他 aos 行程屬別的隊員（e-upper、d-mailkern、inherit-cut1），沒碰。我沒起任何需要收的行程。

## 4. skip 的原因（這台環境限制）

| 檔 | skip 數 | 原因 | 屬性 |
|---|---|---|---|
| daemon/test_cgroup | 整類 | 沒有 systemd user manager | 環境；**cgroup 限額（cpu/mem/pids 的 cgroup 路徑）這台完全沒驗到** |
| daemon/test_subuid | 4（test_real_switch、test_real_cpu_hit、test_real_procs_counts_the_subuid、test_real_cannot_reach） | fixture 在 `/tmp/aos-daemon-b.XXXX`（mktemp 預設 700），daemon 報 `LimitBad user sub:N: cannot reach … Permission denied`，測試把它當「走不進」而 skip | 環境＋fixture：**sub:N 真換身分（Uid、檔擁有者、清得掉、cpu_s 命中、procs 只數自己）0 驗證**；另 5 個用假 newuidmap 的有過 |
| agent/test_daemon_down | 2 | 不在初始 pid namespace（WSL2） | 環境 |
| share/test_share、test_check_reset | 9＋10 | 沒裝 setfacl | 環境（ACL 共享沒驗） |
| sandbox/test_sandbox | 3 | 沒裝 s6-setuidgid | 環境 |
| box_check/test_acceptance | 2 | 沒裝 s6-softlimit | 環境 |
| reply_match ×3（agent、aos_ws、subagent） | 各 1 | 複本不是 git repo（要 `REPLY_MATCH_REPO`） | 跑法 |
| templates/test_daily | 2 | 要 `AOS_TEST_MNTC=1`＋/mnt/c 暫存夾 | 刻意沒開 |

## 5. 涵蓋表（基底行為 → 現有測試）

「有」＝有測試直接驗該行為；「部分」＝只驗了一半；「沒測」＝我 grep 全部測試名與內容找不到。以下是**讀測試名與抽查內容**的結果（推測成分：我沒逐行審每支斷言是否夠強）。

| # | 基底行為 | 涵蓋 | 對應測試 |
|---|---|---|---|
| 1 | 起 | 有 | daemon/test_lifecycle `test_body_matrix`、`test_normal_start_sleep_wake_and_restart_have_no_bad_files_or_warning`、`test_launch_failure_is_one_stopped_row` |
| 2 | 停 | 有 | test_stop_cause（sleep/rm/stop/shutdown 各原因）、test_lifecycle `test_signal_exit_stays_stopped`、test_ctl `test_agent_sleep_*` |
| 3 | sleep／wake | 有 | test_lifecycle `test_sleep_escalates_cooperative_stop…`、`test_pending_loop_can_wake_after_daemon_restart`、test_stale_stop；test_poke（喚醒延遲） |
| 4 | 重起 | 有 | test_lifecycle `test_never_started_stopped_row_starts_after_daemon_restart`、`test_flux_ack_follows_stable_state_and_restart_deduplicates_stop` |
| 5 | auto-restart 連環重起上限 | 有 | test_lifecycle `test_auto_restart_still_stops_after_three_quick_exits`；daemon_ctl/test_auto_restart 只測旗標型別 |
| 6 | daemon 被殺再起後表與 proc 接回 | 有 | test_lifecycle 一整組 `test_adopt_*`（invalid json、stopping、alive/dead）、`test_unknown_adopted_exit_leaves_table`；test_stop_cause `test_adopt_does_not_rewrite`；test_two_machines `test_restarted_daemon_still_adopts_its_own_children` |
| 7 | 孤兒行程 | 部分 | `test_unknown_adopted_exit_leaves_table`、sweeper/test_sweep（有 orphan 字樣）；沒有「daemon 沒了、子行程還活著、重起後不會多開一份」的明確測試 |
| 8 | 同名 proc | 部分 | daemon_ctl/test_add_rm_checks `test_add_same_name_is_refused`（ctl 層）；daemon 層同名列沒測 |
| 9 | 同時多支 ctl | 部分 | comm/test_comm `test_concurrent_writers_use_flock`（只是 comm 板）；test_poke `test_twenty_pokes…`；**同時多支 `aos-daemon-ctl` 改表／起停沒測** |
| 10 | 信箱：收件人沒起／正在停 | 部分 | agent-fsm/test_selfheal（`lost_letter_is_sent_again`、`missing_kernel_waits…`）、kernel/test_runner `stopped_row_waits_then_gives_up…`、kernel_llm/test_stopped_slot；**寄給 daemon 內剛 stopping 的 proc 本身沒測** |
| 11 | 信箱：滿 | **沒測** | grep full／ENOSPC／too large 全無 |
| 12 | 信的順序與不丟 | 部分 | kernel/test_kernel_cut（01–13：切在送出前後不重不丟）、test_kernel_route `04_keep_ordered…`；**多寄件人 FIFO 順序沒直接測** |
| 13 | 大信 | **沒測** | 無 |
| 14 | 壞信 | 有 | daemon/test_bad_letter、kernel/test_kernel `invalid_json_reply_is_dropped…`、`reply_without_body…`、aos-llm test_full `*_error_body_*` |
| 15 | aos-exec 錯誤路徑 | 有 | exec/test_entry_missing、test_classify（`script_without_x_keeps_old_error`、`timeout_ms_rejects_invalid_values`）、test_ref_hash `pointer_not_found_is_directive_bad` |
| 16 | loop／fsm 一格掛掉 | 有（loop）／部分（fsm） | loop/test_on_start_stop（`body_10_and_failure`、`failing_on_start_only_warns`、`on_stop_timeout`、cause_*）；fsm 只有 test_stack_make／ref_hash，**aos-fsm 表一格失敗的行為只靠 agent-fsm 整合測試間接測** |
| 17 | hook 掛掉 | 有 | agent-fsm/test_hooks（`on_fail_stop…`、`on_fail_continue_warns…`、`timeout_kills_and_fails`）、kernel/test_kernel_hooks `06_hook_failures_stop_or_continue`、test_kernel_route `08_broken_route_hook…` |
| 18 | 時鐘 | 有 | clock_register 兩支、agent-fsm/test_clock_hook(+_daemon)、daemon/test_lifecycle `test_frozen_clock_stuck_deadlines…`、`test_clock_key_is_ignored…`、py/tests/test_clock_when |
| 19 | limits：cpu、files | 有 | test_limits `test_cpu_hit`、`test_file_hit`、`test_cpu_soft_and_hard` |
| 20 | limits：mem、procs | 部分 | test_limits `test_memory_suspect`（只到「懷疑」）、`test_procs_warning_once…`；真 OOM／pids 在 test_cgroup（**本機 skip**）；fork 炸彈類沒測 |
| 21 | sub:N | 部分 | test_subuid 5 個假 newuidmap 的有過；**4 個真換身分全 skip**；kernel/test_limits_rule `subuid_and_group_boundaries`；asuser、share、sandbox 部分 skip |
| 22 | kernel 站掛掉（daemon 側） | 部分 | agent/test_ls_health、aos-llm test_recv_hint（`kernel_not_running`、`kernel_cannot_write_box`）、subagent/test_daemon `requests_go_to_aos_kernel_without_aos_daemon`；**kernel 站行程被殺後信的下場沒測** |
| 23 | llm kernel 逾時 | 有 | kernel_llm/test_nesting（`timeout_precedes_transparent_error`）、test_nesting_live（`kernel_timeout_wins`、`letter_deadline_wins…`） |
| 24 | llm kernel 失敗 | 有 | kernel_llm/test_retry_flag（9 條）、test_nesting `zero_exit_error_is_reply_bad`、`non_timeout_term_can_forward…` |
| 25 | llm kernel 冷卻 | 有 | agent-fsm/test_cooldown（brain_failed cools…、temporary retries、retry_after）、agent-fsm/test_hook_retry_later、kernel_llm/test_hook_retry_later |
| 26 | hold | 有 | kernel/test_kernel_hold（12 條）、kernel_gate/test_kernel_gate、test_triage、test_query_daemon |
| 27 | 額度記帳 | 有 | kernel_llm/test_budget_fields、test_ledger（`write_failure_warns_and_finishes`）、test_two_machines `sender_budget_missing_names_the_key` |
| 28 | 兩個 kernel | 有 | kernel/test_kernel `two_stations_relay_reply_back…`、test_kernel_route（兩站路由）、kernel_llm/test_batch8_live（`two_daemons…`、兩個 pack） |
| 29 | kernel 重起後在途請求 | 有 | kernel/test_kernel_cut（01–13）、test_kernel `restart_finishes_original_before_relaying…`、`ordered_request_without_reply_to_is_not_resent…`、kernel_llm/test_nesting `remount_preserves_first_request…` |
| 30 | set-def | 有 | agent/test_set_def（14 條：運行／停／睡／重啟 daemon／無 slot／舊 def 工具警告） |
| 31 | agent.py 重生（regen） | 部分 | py/tests/test_agent_spec（SpecBad、覆寫規則、std 庫、範本 agent.py 與已提交檔一致）；**「重生時丟掉手改／hook」之類沒測**（grep "regen" 無） |
| 32 | aos.gdb 斷點卡住 | 有 | gdb/test_gdb_live（13 條：held、skip、sleep while held、resume、watcher、broken condition）、test_gdb_trigger（26 條）；全 pass（168s） |

### 最大涵蓋缺口

1. **信箱滿／大信**：完全沒測。
2. **sub:N 真換身分**、**cgroup 限額**：在這台全 skip，現有測試實質 0 驗證（而且 sub:N 的 skip 是 fixture 放 `/tmp` 700 夾造成，換 fixture 位置也許就能跑）。
3. **同時多支 ctl／同名 proc（daemon 層）／孤兒行程重起不重複**：只有間接或 ctl 層測試。
4. **kernel 站行程被殺／整個掛掉後，在途與新寄的信怎麼處理**：只有 kernel_cut（重起後接回）與 hint 層，沒有「站一直不回來」的長時間行為測。
5. aos-fsm 單格掛掉只靠整合測試；agent.py 重生丟東西沒測。

## 6. 逐支結果表（293 支）

結果欄「pass N」＝通過的 case 數（不含 skip）；耗時為 4 條並行下的牆鐘秒數。

| 測試檔 | 層 | 結果 | 耗時 |
|---|---|---|---|
| py/tools/aos/box_check/tests/test_acceptance.py | aos 工具 | pass 3／skip 2 | 1s |
| py/tools/aos/llm_forward/tests/test_forward.py | aos 工具 | pass 6 | 3s |
| py/tools/aos/measure/tests/test_acceptance.py | aos 工具 | pass 4 | 3s |
| py/tools/aos/measure/tests/test_compare.py | aos 工具 | pass 3 | 0s |
| py/tools/aos/measure/tests/test_fake_agent.py | aos 工具 | pass 1 | 40s |
| py/tools/aos/measure/tests/test_ledger.py | aos 工具 | pass 10 | 0s |
| py/tools/aos/measure/tests/test_runner.py | aos 工具 | pass 8 | 0s |
| py/tools/aos/metainfo_check/tests/test_metainfo_check.py | aos 工具 | pass 14 | 0s |
| py/tools/aos/promote/tests/test_recovery.py | aos 工具 | pass 3 | 0s |
| py/tools/aos/promote/tests/test_swap.py | aos 工具 | pass 8 | 6s |
| py/tools/aos/review_round/tests/test_policy.py | aos 工具 | pass 4 | 1s |
| py/tools/aos/review_round/tests/test_round.py | aos 工具 | pass 5 | 75s |
| py/tools/aos/review_round/tests/test_suggestions.py | aos 工具 | FAIL→重跑 OK（見 3） | 1s |
| py/tools/aos/rollback/tests/test_rollback.py | aos 工具 | pass 1 | 0s |
| py/tools/aos/shell_report/tests/test_report.py | aos 工具 | pass 6 | 7s |
| py/tools/aos/watch/tests/test_watch.py | aos 工具 | pass 11 | 6s |
| py/tests/apps/asuser/test_asuser.py | asuser/sub:N | pass 20 | 5s |
| py/tools/base/glob/tests/test_glob.py | base 工具 | pass 7 | 3s |
| py/tools/base/grep/tests/test_grep.py | base 工具 | pass 12 | 3s |
| py/tools/base/llm_http/tests/test_llm_http.py | base 工具 | pass 39 | 31s |
| py/tools/base/mcp_tool/tests/test_mcp_tool.py | base 工具 | pass 23 | 19s |
| py/tools/base/peek_now_time/tests/test_peek_now_time.py | base 工具 | pass 3 | 0s |
| py/tools/base/remove/tests/test_remove.py | base 工具 | pass 4 | 1s |
| py/tools/base/run_python/tests/test_observed.py | base 工具 | pass 6 | 1s |
| py/tools/base/shell/tests/test_observed.py | base 工具 | pass 5 | 0s |
| py/tests/apps/comm/test_comm.py | comm 板 | pass 17 | 19s |
| cpp/aos-daemon/tests/test_bad_letter.py | daemon | pass 3 | 1s |
| cpp/aos-daemon/tests/test_cgroup.py | daemon | 0（setUpClass 整類 skip） | 0s |
| cpp/aos-daemon/tests/test_ctl.py | daemon | pass 19 | 8s |
| cpp/aos-daemon/tests/test_lifecycle.py | daemon | pass 40 | 95s |
| cpp/aos-daemon/tests/test_limits.py | daemon | pass 12 | 8s |
| cpp/aos-daemon/tests/test_poke.py | daemon | pass 10 | 14s |
| cpp/aos-daemon/tests/test_ref_hash.py | daemon | pass 1 | 0s |
| cpp/aos-daemon/tests/test_stack_make.py | daemon | pass 5 | 0s |
| cpp/aos-daemon/tests/test_stale_stop.py | daemon | pass 1 | 4s |
| cpp/aos-daemon/tests/test_state_path.py | daemon | pass 4 | 1s |
| cpp/aos-daemon/tests/test_stop_cause.py | daemon | pass 11 | 24s |
| cpp/aos-daemon/tests/test_subuid.py | daemon | pass 5／skip 4 | 2s |
| cpp/aos-daemon/tests/test_two_machines.py | daemon | pass 9 | 3s |
| py/tests/apps/daemon_ctl/test_add_rm_checks.py | daemon ctl | pass 2 | 1s |
| py/tests/apps/daemon_ctl/test_already.py | daemon ctl | pass 2 | 1s |
| py/tests/apps/daemon_ctl/test_auto_restart.py | daemon ctl | pass 7 | 2s |
| py/tests/apps/daemon_ctl/test_envs_portable.py | daemon ctl | pass 10 | 0s |
| py/tests/apps/daemon_ctl/test_limits_keys.py | daemon ctl | pass 3 | 1s |
| py/tests/apps/daemon_ctl/test_path_json.py | daemon ctl | pass 9 | 0s |
| py/tests/apps/daemon_ctl/test_registered_envs.py | daemon ctl | pass 9 | 1s |
| py/tests/apps/daemon_ctl/test_shutdown_timeout.py | daemon ctl | pass 2 | 1s |
| cpp/aos-directive/tests/test_ref_hash.py | directive | pass 9 | 1s |
| cpp/aos-directive/tests/test_ref_spot.py | directive | pass 10 | 1s |
| cpp/aos-exec/tests/test_classify.py | exec | pass 8 | 1s |
| cpp/aos-exec/tests/test_entry_missing.py | exec | pass 3 | 1s |
| cpp/aos-exec/tests/test_ref_hash.py | exec | pass 4 | 0s |
| cpp/aos-exec/tests/test_stack_lazy.py | exec | pass 4 | 0s |
| frontend/tests/test_compact_quiet.py | frontend | FAIL→重跑 OK（見 3） | 1s |
| frontend/tests/test_delivery.py | frontend | FAIL→重跑 OK（見 3） | 0s |
| frontend/tests/test_phase1.py | frontend | FAIL→重跑 OK（見 3） | 1s |
| frontend/tests/test_slash.py | frontend | FAIL→重跑 OK（見 3） | 1s |
| frontend/tests/test_v2.py | frontend | FAIL→重跑 OK（見 3） | 0s |
| cpp/aos-fsm/tests/test_ref_hash.py | fsm | pass 1 | 0s |
| cpp/aos-fsm/tests/test_stack_make.py | fsm | pass 3 | 0s |
| py/tests/apps/gdb/test_gdb_live.py | gdb | pass 13 | 168s |
| py/tests/apps/gdb/test_gdb_trigger.py | gdb | pass 26 | 6s |
| py/tests/apps/mcp/test_hooks.py | hook | pass 7 | 2s |
| py/tests/test_cli_hook_follow.py | hook | pass 15 | 1s |
| py/tests/test_hook_run.py | hook | pass 16 | 3s |
| py/tests/test_hooks_engine.py | hook | pass 5 | 1s |
| py/tools/agent/self_hook/tests/test_self_hook.py | hook | pass 6 | 3s |
| cpp/aos-json/tests/test_add_ls_search.py | json 工具 | pass 22 | 1s |
| cpp/aos-json/tests/test_ref_hash.py | json 工具 | pass 9 | 1s |
| cpp/aos-json/tests/test_ref_rel.py | json 工具 | pass 5 | 0s |
| py/tools/agent/kernel_gate/tests/test_kernel_gate.py | kernel hold 閘 | pass 11 | 7s |
| py/tools/agent/kernel_gate/tests/test_query_daemon.py | kernel hold 閘 | pass 1 | 2s |
| py/tools/agent/kernel_gate/tests/test_triage.py | kernel hold 閘 | pass 8 | 3s |
| py/tools/aos/kernel/tests/test_hook_retry_later.py | kernel 站 | pass 3 | 7s |
| py/tools/aos/kernel/tests/test_kernel.py | kernel 站 | pass 21 | 7s |
| py/tools/aos/kernel/tests/test_kernel_cut.py | kernel 站 | pass 13 | 22s |
| py/tools/aos/kernel/tests/test_kernel_hold.py | kernel 站 | pass 12 | 5s |
| py/tools/aos/kernel/tests/test_kernel_hooks.py | kernel 站 | pass 11 | 5s |
| py/tools/aos/kernel/tests/test_kernel_route.py | kernel 站 | pass 15 | 7s |
| py/tools/aos/kernel/tests/test_limits_rule.py | kernel 站 | pass 27 | 1s |
| py/tools/aos/kernel/tests/test_refuse_extra.py | kernel 站 | pass 12 | 0s |
| py/tools/aos/kernel/tests/test_runner.py | kernel 站 | pass 8 | 2s |
| py/tools/aos/kernel_llm/tests/test_backends.py | llm kernel | pass 10 | 7s |
| py/tools/aos/kernel_llm/tests/test_batch8_live.py | llm kernel | pass 3 | 17s |
| py/tools/aos/kernel_llm/tests/test_budget_fields.py | llm kernel | pass 14 | 2s |
| py/tools/aos/kernel_llm/tests/test_hook_retry_later.py | llm kernel | pass 2 | 1s |
| py/tools/aos/kernel_llm/tests/test_hooks.py | llm kernel | pass 5 | 3s |
| py/tools/aos/kernel_llm/tests/test_ledger.py | llm kernel | pass 4 | 1s |
| py/tools/aos/kernel_llm/tests/test_nesting.py | llm kernel | pass 8 | 6s |
| py/tools/aos/kernel_llm/tests/test_nesting_live.py | llm kernel | pass 6 | 7s |
| py/tools/aos/kernel_llm/tests/test_retry_flag.py | llm kernel | pass 9 | 4s |
| py/tools/aos/kernel_llm/tests/test_session_key.py | llm kernel | pass 6 | 0s |
| py/tools/aos/kernel_llm/tests/test_stopped_slot.py | llm kernel | pass 2 | 1s |
| py/tools/aos/kernel_llm/tests/test_two_machines.py | llm kernel | pass 7 | 2s |
| cpp/aos-lock/tests/test_owner.py | lock | pass 3 | 0s |
| cpp/aos-lock/tests/test_release.py | lock | pass 2 | 2s |
| cpp/aos-loop/tests/test_on_start_stop.py | loop | pass 27 | 3s |
| cpp/aos-loop/tests/test_ref_hash.py | loop | pass 2 | 0s |
| cpp/aos-loop/tests/test_stack_make.py | loop | pass 4 | 0s |
| py/tests/test_aos_lib_missing.py | py 共用模組 | pass 1 | 2s |
| py/tests/test_aos_ws_reply_match.py | py 共用模組 | pass 11／skip 1 | 0s |
| py/tests/test_cli_a2a.py | py 共用模組 | pass 19 | 12s |
| py/tests/test_cli_codex_mcp.py | py 共用模組 | pass 3 | 0s |
| py/tests/test_cli_external_mcp.py | py 共用模組 | pass 20 | 6s |
| py/tests/test_cli_fault.py | py 共用模組 | pass 20 | 0s |
| py/tests/test_cli_linger.py | py 共用模組 | pass 19 | 11s |
| py/tests/test_cli_print_mid.py | py 共用模組 | pass 6 | 1s |
| py/tests/test_cli_reserved_flags.py | py 共用模組 | pass 7 | 0s |
| py/tests/test_cli_screen_env.py | py 共用模組 | pass 5 | 0s |
| py/tests/test_cli_settings.py | py 共用模組 | pass 8 | 0s |
| py/tests/test_cli_stream.py | py 共用模組 | pass 23 | 14s |
| py/tests/test_cli_system.py | py 共用模組 | pass 3 | 0s |
| py/tests/test_cli_tools_directive.py | py 共用模組 | pass 11 | 1s |
| py/tests/test_cli_tools_sub.py | py 共用模組 | pass 14 | 1s |
| py/tests/test_context_wrap.py | py 共用模組 | pass 34 | 4s |
| py/tests/test_declared_files.py | py 共用模組 | pass 7 | 0s |
| py/tests/test_directive_value.py | py 共用模組 | pass 12 | 0s |
| py/tests/test_env_file.py | py 共用模組 | pass 8 | 0s |
| py/tests/test_env_sh.py | py 共用模組 | pass 8 | 1s |
| py/tests/test_file_tools_paths.py | py 共用模組 | pass 3 | 1s |
| py/tests/test_flags_anywhere.py | py 共用模組 | pass 8 | 1s |
| py/tests/test_index_extra_keys.py | py 共用模組 | pass 2 | 0s |
| py/tests/test_index_link.py | py 共用模組 | pass 3 | 0s |
| py/tests/test_index_view.py | py 共用模組 | pass 14 | 8s |
| py/tests/test_install.py | py 共用模組 | pass 15 | 4s |
| py/tests/test_json_tools.py | py 共用模組 | pass 18 | 14s |
| py/tests/test_kill_group.py | py 共用模組 | pass 5 | 5s |
| py/tests/test_mail_notify.py | py 共用模組 | pass 9 | 9s |
| py/tests/test_mcp_client.py | py 共用模組 | pass 45 | 7s |
| py/tests/test_mcp_freeze.py | py 共用模組 | pass 21 | 0s |
| py/tests/test_metainfo.py | py 共用模組 | pass 9 | 0s |
| py/tests/test_observed.py | py 共用模組 | pass 6 | 0s |
| py/tests/test_observed_children.py | py 共用模組 | pass 2 | 0s |
| py/tests/test_quiet.py | py 共用模組 | pass 8 | 4s |
| py/tests/test_ref_path.py | py 共用模組 | pass 5 | 0s |
| py/tests/test_state_path.py | py 共用模組 | pass 18 | 1s |
| py/tests/test_state_path_fresh.py | py 共用模組 | pass 3 | 0s |
| py/tests/test_tool_io_keys.py | py 共用模組 | pass 7 | 0s |
| py/tests/test_tool_io_metainfo.py | py 共用模組 | pass 6 | 0s |
| py/tests/test_tool_io_place.py | py 共用模組 | pass 6 | 0s |
| py/tests/test_tool_spec.py | py 共用模組 | pass 10 | 2s |
| py/tests/test_user_zone_guard.py | py 共用模組 | pass 3 | 1s |
| py/tests/test_ws_write.py | py 共用模組 | pass 20 | 4s |
| py/tests/apps/sandbox/test_sandbox.py | sandbox | pass 29／skip 3 | 5s |
| py/tests/apps/share/test_check_reset.py | share/ACL | pass 0／skip 10 | 2s |
| py/tests/apps/share/test_share.py | share/ACL | pass 10／skip 9 | 5s |
| py/tests/apps/sweeper/test_releasing.py | sweeper | pass 1 | 0s |
| py/tests/apps/sweeper/test_sweep.py | sweeper | pass 47 | 7s |
| cpp/aos-util/tests/test_parse_cli.py | util | pass 8 | 1s |
| wf/public/tools/fsm-guard/tests/test_guard.py | wf 工具 | pass 34 | 8s |
| wf/tools/tests/test_autoreply.py | wf 工具 | pass 10 | 9s |
| wf/tools/tests/test_codemap_deps.py | wf 工具 | pass 8 | 1s |
| wf/tools/tests/test_codemap_json.py | wf 工具 | pass 4 | 0s |
| wf/tools/tests/test_index_check_edges.py | wf 工具 | pass 7 | 0s |
| wf/tools/tests/test_index_tools.py | wf 工具 | pass 7 | 1s |
| wf/tools/tests/test_json_text.py | wf 工具 | pass 12 | 1s |
| wf/tools/tests/test_json_text_git.py | wf 工具 | pass 3 | 1s |
| wf/tools/tests/test_metainfo_migrate.py | wf 工具 | pass 3 | 0s |
| wf/tools/tests/test_quiet.py | wf 工具 | pass 7 | 3s |
| py/tools/agent/agents_ctl/tests/test_agents_ctl.py | 上層 agent 工具 | pass 4 | 3s |
| py/tools/agent/board_set/tests/test_board_tools.py | 上層 agent 工具 | pass 5 | 3s |
| py/tools/agent/do_task/tests/test_do_task.py | 上層 agent 工具 | pass 21 | 32s |
| py/tools/agent/fork/tests/test_fork.py | 上層 agent 工具 | pass 14 | 6s |
| py/tools/agent/goal/tests/test_goal.py | 上層 agent 工具 | pass 3 | 2s |
| py/tools/agent/guard/tests/test_guard.py | 上層 agent 工具 | pass 144 | 36s |
| py/tools/agent/guard/tests/test_scope.py | 上層 agent 工具 | pass 25 | 0s |
| py/tools/agent/mailbox_send/tests/test_mailbox_tools.py | 上層 agent 工具 | pass 6 | 6s |
| py/tools/agent/self_ctl/tests/test_self_ctl.py | 上層 agent 工具 | pass 3 | 1s |
| py/tools/agent/self_history/tests/test_self_history.py | 上層 agent 工具 | pass 6 | 4s |
| py/tools/agent/self_llm/tests/test_self_llm.py | 上層 agent 工具 | pass 4 | 1s |
| py/tools/agent/self_state/tests/test_self_state.py | 上層 agent 工具 | pass 3 | 2s |
| py/tools/agent/self_system/tests/test_self_system.py | 上層 agent 工具 | pass 5 | 3s |
| py/tools/agent/self_tools/tests/test_broken_entry.py | 上層 agent 工具 | pass 1 | 4s |
| py/tools/agent/self_tools/tests/test_self_tools.py | 上層 agent 工具 | pass 4 | 1s |
| py/tools/agent/todo/tests/test_todo.py | 上層 agent 工具 | pass 15 | 4s |
| py/tools/agent/tools_def/tests/test_tools_def.py | 上層 agent 工具 | pass 12 | 12s |
| py/tools/agent/user_send/tests/test_user_send.py | 上層 agent 工具 | pass 5 | 2s |
| py/tools/agent/user_verify/tests/test_user_verify.py | 上層 agent 工具 | pass 6 | 2s |
| templates/tests/agent-fsm/test_batch3.py | 上層 agent-fsm | pass 1 | 14s |
| templates/tests/agent-fsm/test_brain_notify.py | 上層 agent-fsm | pass 29 | 12s |
| templates/tests/agent-fsm/test_brain_wait_file.py | 上層 agent-fsm | pass 3 | 0s |
| templates/tests/agent-fsm/test_cells.py | 上層 agent-fsm | pass 12 | 15s |
| templates/tests/agent-fsm/test_clock_hook.py | 上層 agent-fsm | pass 13 | 5s |
| templates/tests/agent-fsm/test_clock_hook_daemon.py | 上層 agent-fsm | pass 1 | 9s |
| templates/tests/agent-fsm/test_compact.py | 上層 agent-fsm | pass 19 | 57s |
| templates/tests/agent-fsm/test_cooldown.py | 上層 agent-fsm | pass 37 | 59s |
| templates/tests/agent-fsm/test_do_task_fold.py | 上層 agent-fsm | pass 5 | 106s |
| templates/tests/agent-fsm/test_fork.py | 上層 agent-fsm | pass 1 | 34s |
| templates/tests/agent-fsm/test_goal.py | 上層 agent-fsm | pass 27 | 89s |
| templates/tests/agent-fsm/test_home_rule.py | 上層 agent-fsm | pass 2 | 3s |
| templates/tests/agent-fsm/test_hook_retry_later.py | 上層 agent-fsm | pass 1 | 1s |
| templates/tests/agent-fsm/test_hooks.py | 上層 agent-fsm | pass 21 | 18s |
| templates/tests/agent-fsm/test_integration.py | 上層 agent-fsm | pass 1 | 6s |
| templates/tests/agent-fsm/test_mail_notify_daemon.py | 上層 agent-fsm | pass 1 | 65s |
| templates/tests/agent-fsm/test_own_system.py | 上層 agent-fsm | pass 3 | 9s |
| templates/tests/agent-fsm/test_own_tools.py | 上層 agent-fsm | pass 2 | 2s |
| templates/tests/agent-fsm/test_reply_match.py | 上層 agent-fsm | pass 9 | 21s |
| templates/tests/agent-fsm/test_same_turn_tools.py | 上層 agent-fsm | pass 1 | 5s |
| templates/tests/agent-fsm/test_selfheal.py | 上層 agent-fsm | pass 20 | 25s |
| py/tools/agent/agent_def/tests/test_agent_def.py | 上層 agent_def | pass 18 | 3s |
| py/tools/agent/agent_def/tests/test_def_edit.py | 上層 agent_def | pass 11 | 4s |
| py/tests/test_agent_spec.py | 上層 agent_spec | pass 33 | 7s |
| py/tests/apps/agent/test_add_dotenv.py | 上層 aos-agent | pass 10 | 5s |
| py/tests/apps/agent/test_add_parent_daemon.py | 上層 aos-agent | pass 8 | 74s |
| py/tests/apps/agent/test_ask.py | 上層 aos-agent | pass 10 | 3s |
| py/tests/apps/agent/test_brain_hint.py | 上層 aos-agent | pass 16 | 31s |
| py/tests/apps/agent/test_chat_read_line.py | 上層 aos-agent | pass 7 | 6s |
| py/tests/apps/agent/test_ctl_kit.py | 上層 aos-agent | pass 11 | 20s |
| py/tests/apps/agent/test_daemon_down.py | 上層 aos-agent | pass 0／skip 2 | 1s |
| py/tests/apps/agent/test_goal.py | 上層 aos-agent | pass 6 | 22s |
| py/tests/apps/agent/test_history.py | 上層 aos-agent | pass 11 | 23s |
| py/tests/apps/agent/test_hook.py | 上層 aos-agent | pass 12 | 28s |
| py/tests/apps/agent/test_kernel_screen.py | 上層 aos-agent | pass 8 | 0s |
| py/tests/apps/agent/test_kernel_state_path.py | 上層 aos-agent | pass 12 | 26s |
| py/tests/apps/agent/test_listen_brain_failure.py | 上層 aos-agent | pass 9 | 14s |
| py/tests/apps/agent/test_listen_timeout.py | 上層 aos-agent | pass 2 | 2s |
| py/tests/apps/agent/test_llm.py | 上層 aos-agent | pass 3 | 7s |
| py/tests/apps/agent/test_ls_health.py | 上層 aos-agent | pass 6 | 5s |
| py/tests/apps/agent/test_peek.py | 上層 aos-agent | pass 2 | 2s |
| py/tests/apps/agent/test_reply_match.py | 上層 aos-agent | pass 16／skip 1 | 20s |
| py/tests/apps/agent/test_rm_keep.py | 上層 aos-agent | pass 6 | 8s |
| py/tests/apps/agent/test_say_from.py | 上層 aos-agent | pass 5 | 1s |
| py/tests/apps/agent/test_set_def.py | 上層 aos-agent | pass 14 | 43s |
| py/tests/apps/agent/test_state_parts.py | 上層 aos-agent | pass 9 | 16s |
| py/tests/apps/agent/test_stop_linger.py | 上層 aos-agent | pass 4 | 3s |
| py/tests/apps/agent/test_system.py | 上層 aos-agent | pass 7 | 5s |
| py/tests/apps/agent/test_tools_override.py | 上層 aos-agent | pass 13 | 7s |
| py/tests/apps/agent/test_who_registered_daemon.py | 上層 aos-agent | pass 3 | 3s |
| py/tools/aos/defs/tests/test_defs.py | 上層 defs | pass 19 | 5s |
| py/tests/apps/eca/test_compact_wrap.py | 上層 eca | pass 11 | 11s |
| py/tests/apps/eca/test_goal.py | 上層 eca | pass 14 | 10s |
| py/tests/apps/eca/test_goal_replace.py | 上層 eca | pass 4 | 0s |
| py/tests/apps/eca/test_history_edit.py | 上層 eca | pass 3 | 2s |
| py/tests/apps/eca/test_hooks.py | 上層 eca | pass 14 | 5s |
| py/tests/apps/eca/test_kernel_watch.py | 上層 eca | pass 9 | 1s |
| py/tests/apps/eca/test_letter_name.py | 上層 eca | pass 4 | 1s |
| py/tests/apps/eca/test_live_mail.py | 上層 eca | pass 3 | 13s |
| py/tests/apps/eca/test_long_turn.py | 上層 eca | pass 2 | 3s |
| py/tests/apps/eca/test_peek.py | 上層 eca | pass 5 | 2s |
| py/tests/apps/eca/test_pi.py | 上層 eca | pass 14 | 7s |
| py/tests/apps/eca/test_pi_screen.py | 上層 eca | pass 7 | 5s |
| py/tests/apps/eca/test_reply_match.py | 上層 eca | pass 13 | 7s |
| py/tests/apps/eca/test_retry.py | 上層 eca | pass 21 | 12s |
| py/tests/apps/eca/test_retry_file.py | 上層 eca | pass 13 | 0s |
| py/tests/apps/eca/test_screen_hook.py | 上層 eca | pass 3 | 0s |
| py/tests/apps/eca/test_screen_slash.py | 上層 eca | pass 16 | 0s |
| py/tests/apps/eca/test_slash.py | 上層 eca | pass 17 | 11s |
| py/tests/apps/eca/test_switch.py | 上層 eca | FAIL→重跑 OK（見 3） | 14s |
| py/tools/agent/subagent/tests/test_daemon.py | 上層 subagent | pass 2 | 27s |
| py/tools/agent/subagent/tests/test_reply_match.py | 上層 subagent | pass 4／skip 1 | 6s |
| py/tools/agent/subagent/tests/test_subagent.py | 上層 subagent | pass 16 | 19s |
| py/tools/agent/subagent/tests/test_wait.py | 上層 subagent | pass 8 | 6s |
| cpp/aos-llm/tests/test_full.py | 信箱/llm CLI | pass 6 | 1s |
| cpp/aos-llm/tests/test_ls_backend.py | 信箱/llm CLI | pass（非 unittest 腳本，無統計） | 1s |
| cpp/aos-llm/tests/test_ls_kernel.py | 信箱/llm CLI | pass 17 | 1s |
| cpp/aos-llm/tests/test_recv_hint.py | 信箱/llm CLI | pass 6 | 1s |
| cpp/aos-llm/tests/test_send_hint.py | 信箱/llm CLI | pass 2 | 0s |
| cpp/aos-llm/tests/test_sender_stack.py | 信箱/llm CLI | pass 4 | 0s |
| py/tests/apps/feedback/test_boundaries.py | 其他指令 | pass 7 | 3s |
| py/tests/apps/feedback/test_feedback.py | 其他指令 | FAIL→重跑 OK（見 3） | 4s |
| py/tests/apps/json_view/test_json_view.py | 其他指令 | pass 20 | 1s |
| py/tests/apps/mailbox/test_mailbox.py | 其他指令 | pass 12 | 6s |
| py/tests/apps/mcp/test_broken_entry.py | 其他指令 | pass 1 | 0s |
| py/tests/apps/mcp/test_list_changed.py | 其他指令 | pass 2 | 3s |
| py/tests/apps/mcp/test_own_registry.py | 其他指令 | pass 3 | 1s |
| py/tests/apps/mcp/test_timeout.py | 其他指令 | pass 4 | 4s |
| py/tests/apps/mcp_import/test_import.py | 其他指令 | pass 23 | 13s |
| py/tests/apps/tools/test_broken_entry.py | 其他指令 | pass 7 | 3s |
| py/tests/apps/tools/test_cache.py | 其他指令 | pass 8 | 2s |
| py/tests/apps/tools/test_cell_lazy.py | 其他指令 | pass 2 | 1s |
| py/tests/apps/tools/test_cli.py | 其他指令 | pass 27 | 8s |
| py/tests/apps/tools/test_env_file.py | 其他指令 | pass 14 | 4s |
| py/tests/apps/tools/test_metainfo_tooldef.py | 其他指令 | pass 10 | 3s |
| py/tests/apps/tools/test_override.py | 其他指令 | pass 34 | 7s |
| py/tests/apps/tools/test_paths.py | 其他指令 | pass 15 | 3s |
| py/tests/apps/tools/test_pointer.py | 其他指令 | pass 4 | 1s |
| py/tests/apps/tools/test_stack_in_caller.py | 其他指令 | pass 3 | 1s |
| py/tests/apps/clock_register/test_clock_once_cron.py | 時鐘 | pass 7 | 3s |
| py/tests/apps/clock_register/test_clock_register.py | 時鐘 | pass 8 | 5s |
| py/tests/test_clock_when.py | 時鐘 | pass 8 | 0s |
| py/tests/test_on_clock_kernel.py | 時鐘 | pass 2 | 2s |
| py/tools/agent/clock_register/tests/test_clock_register_tool.py | 時鐘 | pass 4 | 3s |
| py/tools/base/peek_clock/tests/test_peek_clock.py | 時鐘 | pass 4 | 1s |
| templates/tests/judge-llm/test_judge.py | 範本/整合 | pass 4 | 9s |
| templates/tests/kits/test_kits.py | 範本/整合 | pass 8 | 0s |
| templates/tests/reviewer/test_reviewer.py | 範本/整合 | FAIL→重跑 OK（見 3） | 39s |
| templates/tests/test_daily.py | 範本/整合 | pass 14／skip 2 | 368s |
| templates/tests/test_eca_pi.py | 範本/整合 | pass 3 | 1s |
| templates/tests/test_fake_slow.py | 範本/整合 | pass 1 | 0s |
| templates/tests/test_paths_move.py | 範本/整合 | pass 4 | 137s |
| templates/tests/test_screen_linger.py | 範本/整合 | pass 1 | 1s |
| templates/tests/test_start.py | 範本/整合 | pass 4 | 0s |
| templates/tests/tool-python/test_skeleton.py | 範本/整合 | pass 4 | 2s |