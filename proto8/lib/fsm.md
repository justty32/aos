# fsm（`aos_fsm.py`＋方法表 `aos_methods.py`）

← [proto8/lib](README.md)｜規範：[NORMS 組合子 § fsm](../NORMS/07-基礎設施-組合子.md#fsm)（N-20、N-36～N-41）｜demo：[demo/fsm](../demo/fsm/README.md)

一拍跑一格的狀態機：讀回現在狀態、查表跑那一格、換狀態、寫 state 窗、退出。壽命一拍，要一直跑就讓 loop 拍它。基礎實作（N-18，10-15）。

```
python3 proto8/lib/aos_fsm.py [--key 值 ...] [FSM.json | -]
```

```jsonc
{
  "start": "idle",                          // 必填，要在 states 裡
  "states": {                               // 必填：狀態名 → 格
    "idle": "idle.json",                    //   aos-inst TARGET（檔、資料夾、可接 #/位置）
    "thinking": "think/",                   //   資料夾＝aos-inst 的找法；裡面可以是另一個 aos_fsm（巢狀）
    "tool": {"argv": ["python3", "tool.py"]},          //   內嵌一張 inst
    "done": {"target": "done.json", "next": "idle"},   //   帶表上靜態 next
    "error": "on-error.json"                //   選填：出錯時跳去的格
  },
  "end": ["tool", "idle"],                  // 選填：出口名單（巢狀的內層用）
  "state": "fsm-state.json",                // 必填（N-19）
  "ctl": "fsm-ctl.json",                    // 選填
  "lock": "fsm.lock/",                      // 選填：一個資料夾
  "max_steps": 20,                          // 選填正整數
  "max_fails": 3                            // 選填正整數，預設 3：連續出錯幾次就停住
}
```

- 設定從哪來照 `aos_cli`：FSM.json（可接 `#/位置`）、`-`＝stdin；給了 FSM.json 而 stdin 是一般檔（被外層 fsm 當格跑時就是）＝stdin 第一份物件當預設（N-40，見「巢狀」）；`--start`、`--state`、`--ctl`、`--lock`、`--max-steps`、`--max-fails` 鏡射；`states`、`end` 不鏡射；`--` 不收。`run(x, ident=None, defaults=None)` 收路徑或一份設定 dict。相對路徑一律從呼叫者的 cwd 算（格的 TARGET 也是）。
- **一拍**：拿鎖（有 lock）→ 讀 ctl（有 ctl；paused 或 stop＝這拍不起格，只把 seq 回音寫進 state，退出 0）→ 讀 state 窗（檔還沒有＝從 `start` 起）→ 查格 → **先把 `step`＋`running: true` 寫進 state** → 跑格 → 讀格 stdout 最後一份完整 JSON → 換狀態、寫 state → stdout 吐一行 → 放鎖。
- **跑一格**（`aos_methods.run_cell`）：在本行程用 `aos_inst.run()` 跑那張 inst，stdin 蓋成一份暫存檔＝**這份 fsm 設定本身＋`fsm_state`（這拍起格前讀到的 state 窗整份）**、stdout 蓋成暫存檔（跑完刪掉）；stderr、exit、cwd、`timeout_ms` 照那張 inst 自己寫的。inst 寫了 `stdin_inherit`／`stdout_inherit`＝Conflict（格出錯）。
- **設定**（N-37，10-15 使用者選乙；同日依 C-48 改成「設定本身＋一個 key」）：就是這拍拿到的設定（旗標併進去；有用指示詞的話先解好；fsm 不認得的 key 也照帶），路徑原樣、不轉絕對——格照自己的 cwd 算（沒寫 `cwd` 的格＝跟 fsm 同一個 cwd）。格要的設定（例：agent 的 `brain`、`history`）就從這裡拿，不必再在 argv 指一次設定檔。
- **`fsm_state`**（取代原本的 `state`／`step`／`prev` 與 prev 的三種形狀，10-15 使用者「都照建議」）：格要的都在窗裡——`data`＝上一格回的；`running: true`＝上一拍被殺一半（重進同狀態、不撿舊結果）；進 error 格時 `phase`＝`error`、`last_error`＝「代號: 白話」、`error_from`＝原狀態、`data` 照留；這格是第幾格＝`step`＋1。key 名 `fsm_state` 不叫 `state`：設定裡 `state` 已經是窗的路徑。
- **下一狀態**：格 stdout 最後一份的 `next` ＞ 表上靜態 `next` ＞ 留原狀態。`data`＝那份的 `data`（沒寫＝null）。`next` 不在表裡：在 `end` 裡＝交給外層（phase 歸位 `start`，那份結果原樣吐成這拍 stdout 最後一份），都不在＝錯。
- **出錯**（格結束碼非 0、aos_inst 自己出錯、查不到格、`next` 不對、走到 `max_steps`）：有 `error` 格＝phase 改 `error`、`step` 歸零，下一拍才跑它；沒有、或 error 格自己出錯＝留原狀態。兩種都記 `last_error`（「代號: 白話」，截 300 字）。代號：`CellFailed`、`UnknownState`、`UnknownNext`、`BadNext`、`MaxSteps`，aos_inst 的照原代號。
- **真正原因**（10-15 146 試跑後補）：`CellFailed` 的白話＝格自己 stderr 最後一份 N-29 錯誤（`代號: 白話`），例 `CellFailed: BrainFailed: HttpError: http://…/api/chat 回 400：{"error":"… does not support tools"}`；格沒吐就寫「格 X 結束碼 N」。怎麼撿：沒寫 stderr 的格（本來接 /dev/null）由 `run_cell` 改接暫存檔；格自己寫了 stderr 檔就讀那個檔；`stderr_inherit`／`stderr_merge` 的撿不到。
- **連續出錯就停住**（10-15 146 試跑後補）：state 的 `fails`＝連續出錯幾次，成功一拍就歸零；到 `max_fails`（預設 3）就寫 `halted: true`，之後的拍不起格、不吐東西、退 0（ctl 的 seq 回音照寫），等人。有 `error` 格時照舊跳去，error 格也一直錯就同樣累計到停。**人怎麼接手**：把 state 窗的 `halted` 刪掉或改 `false`（`fails` 不用動：再錯一次就馬上又停，成功就歸零），或刪掉整份 state＝從 `start` 重來。這是「state 只有 fsm 寫」（N-09）的例外，跟 SIGKILL 留下的鎖要人清同類。巢狀時各層各算：內層停住後外層照拍，但內層不再起格（不再叫腦）。
- **step**：自上次在 `start` 起跑了幾格；新狀態是 `start` 或進 error 格就歸零。`step` ≥ `max_steps` 時再跑＝`MaxSteps`（不起格）。
- **state 窗**（只有 fsm 寫；不寫時間、pid，N-39）：

```jsonc
{"phase": "thinking", "step": 2, "running": false, "data": {"q": "…"}, "last_error": null, "error_from": null, "ctl_seq": 3, "fails": 0, "halted": false}
```

- **stdout**：起了格（或查格就出錯）吐一行＝那格的 aos_inst 結果（N-30：`id`、`code`、`signal`、`timed_out`、`pid`、`ms`、`exit_file`；沒起成格＝這些是 null）＋`step`、`from`、`to`，出錯多一格 `error`: `{"code", "msg"}`（N-29 形狀）；這行永遠不帶 `next`，所以內層沒到終點時外層留在原格。ctl 擋下、停住（`halted`）的那拍什麼都不吐。
- **巢狀**：某格的 inst 是 `aos_fsm.py 內層.json`。內層有自己的 state 窗、不開 lock 與 ctl（沿用外層）、從自己的 TARGET 拿設定，**外層餵的 stdin（外層 cfg）當預設**：內層沒寫的 key 才用外層的（N-40，10-15 使用者「都照建議」）；fsm 自己的 key（`start`、`states`、`end`、`state`、`ctl`、`lock`、`max_steps`、`max_fails`）與 `fsm_state` 不繼承（動工自定：繼承外層的 lock 會撞鎖、state 會撞窗）。給自己格的就是合起來那份。只在 stdin 是一般檔時讀（終端機、pipe、/dev/null 不讀，不會卡住）——這是 N-21「給 TARGET 就不讀 stdin」對內層 fsm 的例外。巢狀格不宜寫表上靜態 next。
- **lock**：mkdir 那個資料夾，已經在＝`LockBusy`、不碰 state；退出前 rmdir。被 SIGKILL 的那拍鎖會留著，要人清（基礎實作不處理）。
- **退出碼只說 fsm 自己**：0＝這拍做完（格出錯由表處理也是 0）；125＝設定不對、窗缺（`WindowMissing`）、拿不到鎖、state 讀不懂（`StateBad`）或寫不了，stderr 吐一份 `{"error": {"code", "msg"}}`。
- 格怎麼跑是格的事（N-41）：同步（等 LLM 回覆才結束）或非同步（丟請求、回 `{"next": "waiting"}`）都行，都不自己 setsid／fork；格裡放 loop／daemon 會阻塞一拍，靠那張 inst 的 `timeout_ms` 守。
