# kernel 架構提案 審查（astra，2026-10-02）

## 一段話結論

**A 的骨架可行，但目前不能照提案直接搭。** 現有零件確實能跑政策任務、收摘要、查狀態、改資源上限。主要問題是把「暫停排程」當成「停住程序」，把「廣播寄信」當成「只叫醒指定成員」。多層帳號與收信也還沒接完整。因此「只差一個 PID 小補」說得太滿。以下都是提案問題，沒有要求替 POC 增加當機救援。

## 必修

1. **`pause` 不會停住下層 daemon。**  
   [03-推薦方案.md:92](/home/guanyu/projs/aos/.claude/worktrees/agent-a6247d4f7cb1ddad9/proto6/notes/proposals/2026-10-02-kernel/03-推薦方案.md:92) 說整個 team-a 會停住；但 [aos_daemon_ctl.py:145](../../../../proto6/src/py/lib/aos_daemon_ctl.py) 只設 `paused`、取消待補，正在跑的程序照常。下層 daemon 會繼續叫醒 bob。第 2 階段的整組暫停驗收因此不成立。  
   **改法：** 分清「停止派工」與「殺掉整組」。前者由下層停止派工；後者用現有 `kill`／cgroup，但不能描述成可原地恢復的 pause。

2. **長 `interval_ms` 不等於「不叫不醒」。**  
   [03-推薦方案.md:32](/home/guanyu/projs/aos/.claude/worktrees/agent-a6247d4f7cb1ddad9/proto6/notes/proposals/2026-10-02-kernel/03-推薦方案.md:32) 的說法不符現行行為。[aos_daemon_config.py:43](../../../../proto6/src/py/lib/aos_daemon_config.py) 把首次執行時間設為現在；之後仍按週期跑。bob、amy 開機就會各跑一次。  
   **改法：** 用 state 預置成員為 `paused:true`，再由 kernel `wake` 單跑一格。這個能力已有 [test_ctl_loop.py:118](../../../../proto6/src/py/tests/test_ctl_loop.py) 覆蓋。

3. **共用 MEMBERS 門會繞過 `max_awake`，還可能持續互相叫醒。**  
   [04-agent介面.md:60](/home/guanyu/projs/aos/.claude/worktrees/agent-a6247d4f7cb1ddad9/proto6/notes/proposals/2026-10-02-kernel/04-agent介面.md:60) 要每格寄 grant、成員自己篩 `to`。但 [aos_daemon_mq.py:104](../../../../proto6/src/py/lib/aos_daemon_mq.py) 會把信送給所有訂閱者，並全部叫醒；`to` 只是信件內容。連 paused 成員也會跑，因為 [aos_daemon_run.py:71](../../../../proto6/src/py/lib/aos_daemon_run.py) 先處理待補，再看 paused。grant→summary→kernel 重寄 grant，還會形成互叫循環。  
   **改法：** 最省事是 grant 寫檔，只 wake 獲選者。若用信，就分成員門、只寄獲選者，且寄信本身就是 wake，不能再每格廣播。

4. **範例的 amy 不會切換帳號。**  
   [03-推薦方案.md:21](/home/guanyu/projs/aos/.claude/worktrees/agent-a6247d4f7cb1ddad9/proto6/notes/proposals/2026-10-02-kernel/03-推薦方案.md:21) 沒掛 `modules.account`，卻替 amy 寫 `account.user`。[aos_daemon_config.py:162](../../../../proto6/src/py/lib/aos_daemon_config.py) 在模組未掛時直接忽略該欄位。  
   **改法：** 補 `modules.account` 的預設帳號與白名單，並交代要以 root 啟動；或刪掉這個切帳號示例。

5. **非 root 的下層 daemon 不能直接再分帳號。**  
   [03-推薦方案.md:83](/home/guanyu/projs/aos/.claude/worktrees/agent-a6247d4f7cb1ddad9/proto6/notes/proposals/2026-10-02-kernel/03-推薦方案.md:83) 讓下層以 `aos-a` 執行，第 91 行又說帳號名單往下分。但 [aos_daemon.py:129](../../../../proto6/src/py/lib/aos_daemon.py) 明確拒絕非 root 啟動帳號模組；父層也[禁止用 root 跑成員](../../../../proto6/src/py/lib/aos_daemon_account.py)。  
   **改法：** POC 先讓下層沿用同一帳號。逐層切帳號另列未具備的能力，不能算現有零件已接通。

6. **保存上層門的 `envs` 放錯位置，多層回信也缺收件身分。**  
   [03-推薦方案.md:93](/home/guanyu/projs/aos/.claude/worktrees/agent-a6247d4f7cb1ddad9/proto6/notes/proposals/2026-10-02-kernel/03-推薦方案.md:93) 要在 daemon 設定的 kernel 項寫 `envs`，但 [aos_daemon_config.py:184](../../../../proto6/src/py/lib/aos_daemon_config.py) 根本不讀它。下層還會[覆寫同名門與 `AOS_DAEMON_INST`](../../../../proto6/src/py/lib/aos_daemon_run.py)。子 kernel 用 `"."` 向父端 take，會取父 kernel 的信箱；不是 `"teams/b/daemon-run"`。範例中後者也沒訂 MEMBERS。  
   **改法：** 在啟動下層的真正 `inst.json.envs` 保存父端地址與父端 inst，補上訂閱、取信身分與上報 `from`。第 2 階段要驗 grant／summary 雙向通訊。

7. **政策任務失敗，不會自然讓整格回 1 或停止。**  
   [03-推薦方案.md:97](/home/guanyu/projs/aos/.claude/worktrees/agent-a6247d4f7cb1ddad9/proto6/notes/proposals/2026-10-02-kernel/03-推薦方案.md:97) 混淆了 tick 自己出錯與子任務出錯。[aos_tick.py:178](../../../../proto6/src/py/lib/aos_tick.py) 記完任務非零碼仍繼續，最後回 0；[test_tick_run.py:49](../../../../proto6/src/py/tests/test_tick_run.py) 明確驗證。因此 `decide` 失敗後，`apply` 仍可能執行。  
   **改法：** 修正失敗描述。若需要前一步失敗就不套用，可合成一支順序執行的小程式，或明寫使用 `tasks-blocked`。不必改 tick。

8. **第 0 階段驗的是 A，不能當作 D 的實測。**  
   [05-分階段落地.md:18](/home/guanyu/projs/aos/.claude/worktrees/agent-a6247d4f7cb1ddad9/proto6/notes/proposals/2026-10-02-kernel/05-分階段落地.md:18) 已有 kernel 四項任務，由 kernel wake／pause；但 [02-方案比較.md:48](/home/guanyu/projs/aos/.claude/worktrees/agent-a6247d4f7cb1ddad9/proto6/notes/proposals/2026-10-02-kernel/02-方案比較.md:48) 的 D 明定沒有 kernel、成員自行讀共用額度檔。  
   **改法：** 改稱「A 的 shell 手搭版」。若要判斷 D 夠不夠，另搭真正沒有 kernel 的版本。

9. **方案 B 的比較有不成立的推論。**  
   [02-方案比較.md:34](/home/guanyu/projs/aos/.claude/worktrees/agent-a6247d4f7cb1ddad9/proto6/notes/proposals/2026-10-02-kernel/02-方案比較.md:34) 說 B 讀政策檔，第 37 行卻說政策一變就要改 daemon 程式。改額度參數不必改程式；改演算法時，A 的 `decide` 也可能要改。第 62 行稱 B 可強制 LLM 額度，也缺前提：啟動前檢查整項，管不到一格內多次 LLM 呼叫。  
   **改法：** 分開比較參數與演算法。LLM 強制力改成「需逐次呼叫檢查或池代發」，各方案用相同前提比較。

## 建議

- **同時上限要跨格驗。** [05-分階段落地.md:22](/home/guanyu/projs/aos/.claude/worktrees/agent-a6247d4f7cb1ddad9/proto6/notes/proposals/2026-10-02-kernel/05-分階段落地.md:22) 只驗「一格醒一個」，不能排除前一個未結束、下一格又醒一個。假成員跑得比 kernel 週期久，連驗三格，並包含寄 grant 的流程。

- **跨帳號巢狀 cgroup 要補委派前提。** [03-推薦方案.md:91](/home/guanyu/projs/aos/.claude/worktrees/agent-a6247d4f7cb1ddad9/proto6/notes/proposals/2026-10-02-kernel/03-推薦方案.md:91) 說下層可再分，但現行只把整棵框[交給父 daemon 的預設帳號](../../../../proto6/src/py/lib/aos_daemon.py)。建議先驗同帳號巢狀；不同帳號要寫清楚如何取得子框管理權。

- **收信只取一次，再依 `type` 分流。** [04-agent介面.md:60](/home/guanyu/projs/aos/.claude/worktrees/agent-a6247d4f7cb1ddad9/proto6/notes/proposals/2026-10-02-kernel/04-agent介面.md:60) 的 grant reader 與第 85 行的成員通訊共用信箱。[take 會清空整個信箱](../../../../proto6/src/py/lib/aos_daemon_mq.py)，不能篩完 grant 就丟掉其餘信。

- **把驗收前提補完整。** [05-分階段落地.md:45](/home/guanyu/projs/aos/.claude/worktrees/agent-a6247d4f7cb1ddad9/proto6/notes/proposals/2026-10-02-kernel/05-分階段落地.md:45) 可明寫由人手送 SIGHUP；第 4 階段才驗 kernel 自己通知。第 68 行測試指令則沿用 [spec/README.md:29](../../../../proto6/spec/README.md)，補上 `PYTHONPATH=lib`。

## 疑問

- **grant 是窗口總額，還是剩餘額度？**  
  [04-agent介面.md:63](/home/guanyu/projs/aos/.claude/worktrees/agent-a6247d4f7cb1ddad9/proto6/notes/proposals/2026-10-02-kernel/04-agent介面.md:63) 寫 `calls:20`，文字卻說剩 17 次；每格重寄也沒說是否重置。建議採固定窗口總額，加同窗口不變的 `window_start_seq`。驗「同窗口寄兩封，合計仍只能用三次」。

- **整組暫停想要哪種效果？**  
  [05-分階段落地.md:43](/home/guanyu/projs/aos/.claude/worktrees/agent-a6247d4f7cb1ddad9/proto6/notes/proposals/2026-10-02-kernel/05-分階段落地.md:43) 沒分清停止派新工作、立即終止、原地凍結。建議 POC 先做「不派新工作，正在跑的做完」；最貼近現有能力。

- **`due_seq` 是格號還是等待長度？**  
  [04-agent介面.md:56](/home/guanyu/projs/aos/.claude/worktrees/agent-a6247d4f7cb1ddad9/proto6/notes/proposals/2026-10-02-kernel/04-agent介面.md:56) 寫「幾格後」，但 [C-01](../../../../proto6/spec/conventions.md) 規定 `_seq` 是第幾格。建議 POC 統一用 `after_ticks`，從 kernel 收到那格起算，與 `wake_me` 一致。

## 看過的範圍

完整讀過提案七份文件。對照主工作樹的現行 spec、相關 schema、Python 程式與測試；封存設計未當作現行保證。

確認成立的主要能力：

| 能力 | 零件、欄位與程式證據 |
|---|---|
| 四項政策任務、hooks、`kind` | `tasks`／`hooks`；[aos_tick.py:156](../../../../proto6/src/py/lib/aos_tick.py) |
| 查正在跑、暫停、上次碼 | `status` 的 `running`／`paused`／`last_exit`；[aos_daemon_ctl.py:178](../../../../proto6/src/py/lib/aos_daemon_ctl.py) |
| 改名單、套新資源上限 | SIGHUP、`insts`／`cgroup`；[aos_daemon_reload.py:75](../../../../proto6/src/py/lib/aos_daemon_reload.py) |
| 重開後保留暫停狀態 | `modules.state`，只保存 `paused`／`stopped`；[aos_daemon_state.py:25](../../../../proto6/src/py/lib/aos_daemon_state.py) |
| 原樣送三種信、跨 daemon 寄信 | `modules.mq`＋每項 `mq` 訂閱；[aos_daemon_mq.py:104](../../../../proto6/src/py/lib/aos_daemon_mq.py)、[跨 daemon 測試](../../../../proto6/src/py/tests/test_mq_doors.py) |

全程唯讀。未改檔、未 commit、未執行測試。