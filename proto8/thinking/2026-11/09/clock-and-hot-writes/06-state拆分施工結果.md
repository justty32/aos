# 06 state 拆分施工結果：回音欄搬進 state_flux.json，寄 30 封 ping 時 state／procs_state 重寫從 60 次降到 0 次，判準全過

← [README](README.md)｜上一份 [05 續](05-續-衝突方向題與施工.md)

## 做了什麼

照 [05](05-state拆分規劃.md)／[05 續](05-續-衝突方向題與施工.md) 的 S1～S6，名字照使用者裁的 `state_flux`、`responded_at` 三種觸發不縮。

- **aos-loop**：新公開窗 `StateFluxWindow`（key `state_flux`，沒寫＝`state_flux.json`、`null`＝不開；旗標 `--state-flux 檔`）。`state.json` 拿掉 `responded_at`、`ctl_seq`、`ctl_warning`；`state_flux.json`＝`{responded_at, ctl_seq, ctl_warning}`＋子類別的 `flux_more()`，沒有 `updated_at`，第一份必寫、之後有變才寫，寫序 state 先、state_flux 後。起來時 `paused` 從舊 state 接、`ctl_seq` 從舊 state_flux 接。
- **aos-daemon**：`procs_state.json` 拿掉 `ctl_seq`、`ctl_warning`、`mailbox_warning`、`responded_at`；daemon 自己那份 state_flux 多 `procs_ctl_seq`、`procs_ctl_warning`、`mailbox_warning`（一個程式一份）。中途 `flush_table` 也走完整的 state→procs_state→state_flux 寫序（隊員實測發現只補 flux 會讓回音早於 state 落地，已修並加測試）。`stuck.cpp` 改讀子的 ctl mtime＋子 state_flux 的 `responded_at`，不再讀子 state。
- **py／cmd／kernel**：`aos-daemon-ctl` 等回音讀子 state_flux 的 `ctl_seq`；`table.py`、aos-agent `add.py`、llm kernel 讀 `mailbox_warning` 改讀 daemon 的 state_flux（kernel 表照舊讀 procs_state）；`table.state()` 沒人用的 `responded_at` 拿掉。
- **條文與說明**：N-06、N-08、N-09（兩層原則、state_flux 定義、寫序理由、state_flux 沒有 updated_at）、N-11、N-13、N-14、N-16、N-17（要判卡住就要開 state_flux）、N-28、N-32、N-33、N-54、06 命令列、主題、附錄 1～3、C-52 續、03-最高原則、C-54、名詞表、abbr.json；impls、cmd、templates 說明；`stack.gitignore` 檔頭「要留」加 state_flux。
- **範本與試驗場**：三份範本 loop.json、Lua 範例、公司試驗場 `~/code/playground` 兩隻 agent 的 loop.json 補 `"state_flux": "state_flux.json"`（不補也預設開）。桌面 `aos-詳細參考.html` 照新窗改（[桌面頁](#桌面說明頁)）。
- 隊形：codex `gpt-6.1-sol` 寫程式（52 檔）、claude 隊員改條文（27 檔）、codex 改桌面頁；隊長審 diff、建置、實測、commit。

## 過關實測（公司 WSL，試驗場三層複本，假腦；量法同 04：inotify 數重寫、逐次比哪些欄變了）

| 情境 | 04 時 state＋procs_state 重寫 | 現在 state.json | 現在 procs_state.json | 現在 state_flux.json | state／procs_state「只因回音欄」 |
|---|---|---|---|---|---|
| 閒置 10 秒 | 0 | 0 | 0 | 0 | 0 |
| 連問 3 題 | 30（18 只因 `responded_at`） | 6 | 12 | 17 | **0** |
| 寄 30 封 ping | 60（60） | **0** | **0** | 30 | **0** |
| ctl 連發 pause／resume 各 5 | 10（0） | 10 | 0 | 10 | 0 |
| 起收子項 3 輪 | 24（12） | 6 | 9 | 14 | **0** |

- 連問 3 題的 6 次 state.json、起收子項的 6 次，都是新起子 loop 的第一份與結束那份（`code,phase`）；procs_state 的 12／9 次是表列真的變（起收子項，照判準第 4 步算穩定）。
- **P9 卡住列 11／11 過**（`AOS_CLOCK_INTERVAL=300`）：06-11 SIGSTOP＋新 ctl 3.10 秒標 stuck、P7-1 CONT 0.10 秒回 running、P7-5 pause 不誤標、06-06 未來 mtime 不標／換 seq 3.12 秒標／CONT 回、BODY 門檻 10 標而門檻 30 不標、P7-9 kill -9 換 PID、06-17 restart_on_stuck 重起 2 次後 stopped（34.5 秒），加兩列閒置 loop 5 秒 state.json 沒寫、活 loop 收新 ctl 不誤標。父讀的是 state_flux。
- **試驗場三層假腦**：起根→問一題 `FAKE ANSWER`→kill -9 領班 2 秒內換 PID→Ctrl-C 三台 sleeping、殘留 0→再起、再問照答→殘留 0。
- **image**：stop fsm_ann（stopped 列）→Ctrl-C→三個 stack 放 `stack.gitignore`、`git init`＋commit→`git clone` 到第三處醒來：7 份 `state_flux.json` 被追蹤、`.state_flux.json` 0 份；那列照舊 stopped，`aos-agent ctl start` 退 0、回 running、問一題照答，沒被同一道 stop 再停；殘留 0。
- 建置：impls 全建過、0 warning；aos-daemon unittest 45／45、llm kernel `test_nesting` 7／7；`codemap_gen` 無差；`wf-lint` broken 30（開工前 33，沒有新增）。
- grep：程式、範本、測試裡 `responded_at`／`ctl_seq`／`ctl_warning`／`mailbox_warning` 99 處都在 state_flux 語境（或 agent 的 `mailbox_warning.txt`）；`stuck.cpp` 不用 `StateWindow`。
- 量測腳本在 WSL `/tmp/clockhw/`（`hw_watch.py` 加了 state_flux、`hw_img.sh` 是這次新加的 image 來回），不進 repo。

## 代定（可翻案）

1. **一個程式一份 `state_flux.json`**，daemon 不另開 `procs_state_flux.json`；procs_ctl 的回音叫 `procs_ctl_seq`／`procs_ctl_warning`。
2. 條文標題與檔名「兩個手把、兩扇狀態窗」（N-28、aos-daemon docs/04）沒改名：改了會斷錨點與檔名，內文已補 state_flux。要改名再說。
3. 父「不再讀子 state」只限判卡住；接回（adopt）時仍讀子 state 的 pid 三欄與 `phase`（穩定欄），條文照這樣限定。
4. state 的欄位順序照程式：`daemon` 接在 `paused` 後（原條文寫在 `ctl_warning` 後，那欄搬走了）。
5. `aos-daemon-ctl`（Python）只能從 daemon stack 下的 `daemon.json` 取 state_flux 自訂名，拿不到用預設名；明寫 `null`＝不讀。

## 桌面說明頁

`aos-詳細參考.html` 照新窗改（窗的圖、JSON 範例拆成 state 與 state_flux 兩塊、key 表加 `state_flux`、stuck 從「規劃中」改成已實作）。`aos指令與格式參考`、`aos現況地圖`、`aos親手試指南` 是 10 月底舊版（WAIT_USER 已記不再更新），沒改；其他三頁沒提到這幾欄。

## 沒做、留給使用者

- 家機試驗場不用改：state_flux 預設開；要寫齊可以在兩隻 agent 的 loop.json 補 `"state_flux": "state_flux.json"`。
