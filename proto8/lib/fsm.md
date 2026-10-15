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
  "max_steps": 20                           // 選填正整數
}
```

- 設定從哪來照 `aos_cli`：FSM.json（可接 `#/位置`）、`-`＝stdin；`--start`、`--state`、`--ctl`、`--lock`、`--max-steps` 鏡射；`states`、`end` 不鏡射；`--` 不收。`run(x)` 收路徑或一份設定 dict。相對路徑一律從呼叫者的 cwd 算（格的 TARGET 也是）。
- **一拍**：拿鎖（有 lock）→ 讀 ctl（有 ctl；paused 或 stop＝這拍不起格，只把 seq 回音寫進 state，退出 0）→ 讀 state 窗（檔還沒有＝從 `start` 起）→ 查格 → **先把 `step`＋`running: true` 寫進 state** → 跑格 → 讀格 stdout 最後一份完整 JSON → 換狀態、寫 state → stdout 吐一行 → 放鎖。
- **跑一格**（`aos_methods.run_cell`）：在本行程用 `aos_inst.run()` 跑那張 inst，stdin 蓋成一份暫存檔 `{"state": 現在狀態, "step": 第幾格, "prev": …}`、stdout 蓋成暫存檔（跑完刪掉）；stderr、exit、cwd、`timeout_ms` 照那張 inst 自己寫的。inst 寫了 `stdin_inherit`／`stdout_inherit`＝Conflict（格出錯）。
- **prev**：平常＝上一格回的 `data`（state 窗的 `data`）；上一拍被殺一半（state 的 `running` 還是 true）＝`{"interrupted": true, "data": …}`，重進同狀態、不撿舊結果；進 error 格＝`{"state": 原狀態, "error": "代號: 白話", "data": 原 data}`。
- **下一狀態**：格 stdout 最後一份的 `next` ＞ 表上靜態 `next` ＞ 留原狀態。`data`＝那份的 `data`（沒寫＝null）。`next` 不在表裡：在 `end` 裡＝交給外層（phase 歸位 `start`，那份結果原樣吐成這拍 stdout 最後一份），都不在＝錯。
- **出錯**（格結束碼非 0、aos_inst 自己出錯、查不到格、`next` 不對、走到 `max_steps`）：有 `error` 格＝phase 改 `error`、`step` 歸零，下一拍才跑它；沒有、或 error 格自己出錯＝留原狀態。兩種都記 `last_error`（「代號: 白話」）。代號：`CellFailed`、`UnknownState`、`UnknownNext`、`BadNext`、`MaxSteps`，aos_inst 的照原代號。
- **step**：自上次在 `start` 起跑了幾格；新狀態是 `start` 或進 error 格就歸零。`step` ≥ `max_steps` 時再跑＝`MaxSteps`（不起格）。
- **state 窗**（只有 fsm 寫；不寫時間、pid，N-39）：

```jsonc
{"phase": "thinking", "step": 2, "running": false, "data": {"q": "…"}, "last_error": null, "ctl_seq": 3}
```

- **stdout**：起了格（或查格就出錯）吐一行 `{"step", "from", "to", "code", "ms"}`，出錯多一格 `error`；這行永遠不帶 `next`，所以內層沒到終點時外層留在原格。ctl 擋下的那拍什麼都不吐。
- **巢狀**：某格的 inst 是 `aos_fsm.py 內層.json`。內層有自己的 state 窗、不開 lock 與 ctl（沿用外層）、從自己的 TARGET 拿設定（不讀外層給的 stdin，要外層的東西就 `$ref` 或讀共用檔）；巢狀格不宜寫表上靜態 next。
- **lock**：mkdir 那個資料夾，已經在＝`LockBusy`、不碰 state；退出前 rmdir。被 SIGKILL 的那拍鎖會留著，要人清（基礎實作不處理）。
- **退出碼只說 fsm 自己**：0＝這拍做完（格出錯由表處理也是 0）；125＝設定不對、窗缺（`WindowMissing`）、拿不到鎖、state 讀不懂（`StateBad`）或寫不了，stderr 吐一份 `{"error": {"code", "msg"}}`。
- 格怎麼跑是格的事（N-41）：同步（等 LLM 回覆才結束）或非同步（丟請求、回 `{"next": "waiting"}`）都行，都不自己 setsid／fork；格裡放 loop／daemon 會阻塞一拍，靠那張 inst 的 `timeout_ms` 守。
