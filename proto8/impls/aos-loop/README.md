# aos-loop

`aos-loop - 以指定設定，定期執行一個 aos-exec 目標`（NAME，C-54 R1）

**一句話：`aos-loop [FLAGS] loop.json`——一次次跑 `exec`（目標＝`aos-exec -- 目標 參數...`；單子物件＝行程內跑），看它的結束碼決定下一步：0＝下一次、10＝正常停、其他非 0＝失敗。**
一個 lib（`lib/libaos-loop.a`，公開標頭 `aos/loop.hpp`）加一支薄薄的命令列（`bin/aos-loop`）。連 [aos-exec](../aos-exec/README.md) 的公開 API（它又帶進 aos-inst、aos-util、aos-directive）；目標每次在 fork 出來的子行程裡呼叫 aos-exec 的 `run_cli`，單子每次在自己行程內呼叫 aos-exec 的 `run_inst`。全家慣例見 [impls/README.md](../README.md)。

像一個只會看紅綠燈的工讀生：老闆給他一張紙「這件事最多做 20 次」。他每做一次就看結果的燈號——綠（0）就再做一次、
「收工」牌（10）就下班、紅（其他）就停手，在 stderr 留一句「第幾次、做什麼、燈號幾」，帶著那個燈號回去。
做滿 20 次也下班，什麼都不說。老闆中途喊停（SIGTERM），他把話轉給正在做事的人，等那人收好，再帶著「被喊停」的燈號（128＋N）回去。

```sh
cat loop.json              # {"exec": {"argv": ["aos-fsm", "fsm.json"]}, "max": 20}
aos-loop loop.json         # 每次行程內跑單子 `aos-fsm fsm.json`（跑一次 fsm）；格退 10 → loop 以 0 結束
                           # 注意：寫成 "exec": ["aos-fsm", "fsm.json"]＝`aos-exec -- aos-fsm fsm.json`，aos-fsm 被當成路徑＝EntryMissing
echo '{"exec": "idle", "max": 5}' > loop.json
aos-loop --max 2 loop.json # 每次 `aos-exec -- idle`，旗標蓋過 loop.json 的 max：只跑 2 次
```

規範：窗 N-06～N-09、N-17、N-32、N-33 在 [NORMS/05 窗](../../docs/NORMS/05-基礎設施-窗.md)，結束碼 N-43 在 [NORMS/01 總則](../../docs/NORMS/01-總則.md)，loop 的定位在 [NORMS/04 loop 與 daemon](../../docs/NORMS/04-基礎設施-loop與daemon.md)；慣例 CONVENTION P-06、P-19～P-22、P-36。本頁只寫用法與實作細節。
骨架是公開的 `aos::loop::Loop`（aos-daemon 繼承它）。
`aos/loop.hpp` 同時公開 `CtlWindow`／`StateWindow`：`ctl`／`state` 的預設檔名與跨程式讀寫的欄位、指令值只在這裡定義，loop 本身與 daemon 引用同一份（11-06 K-2；[窗](docs/02-窗.md)）。
`exec` 可以直接放單子物件（使用者「不過exec本來就應該要可以直接放內嵌單子吧」「好，就這樣做」，[thinking 10-24](../../thinking/2026-10/24/exec-relative/README.md#10-24-exec-直接放單子)）：物件＝每次行程內 `run_inst`（`src/run/inline.cpp`），見下面「用法」的 `exec`。

**轉交的碼**（11-05 stdio-unify R8、D4）：退非 0 時 stderr 有 `aos-loop: error:` 這行＝我錯（退 1）——只有 `aos-loop: error: RunFailed …` 例外：那是身體那次的碼原樣帶回（碼不是 1）；沒有錯誤行（128＋N）＝收到訊號。`aos-loop --help`＝英文說明印 stdout、退 0。

**state_flux 窗承接 `responded_at`、`ctl_seq`、`ctl_warning`**（11-06 no-pid P2，[thinking no-pid](../../thinking/2026-11/05/no-pid/README.md)）：最近一次有反應的時間——讀到新的一道 ctl（好壞都算，第一道已套用過的不算）才更新；身體跑完一次不更新（11-09），閒著、睡著時都不動，不是心跳。之後給上一層 daemon 判 `stuck` 用。細節在 [docs/02 窗](docs/02-窗.md)。

**讀回自己的狀態**：state／state_flux 不在就安靜重建；在卻讀不了、JSON 壞或根不是物件，先改名成 `<檔名>.bad-<UTC 毫秒時間>` 留證、印一行 warning，再從新狀態開始。好檔仍照常接回有效的 paused／ctl_seq；aos-daemon 等 Loop 子類別也用同一條路。

**跑過幾次要開旗標才寫**（11-09，[N-09 的 11-09 補](../../docs/NORMS/05-基礎設施-窗/02-N-09～N-11.md)）：state 沒有 `counter_runs`；給 `--enable-counters` 而且有 state 窗時，每跑一次寫 state 窗同資料夾的 `counter_runs.txt`（十進位整數＋換行），預設不寫。

**引擎的喚醒掛鉤 `wake_`／`woke`**（11-09，給 aos-daemon 的 poke 用，[thinking daemon-interrupt](../../thinking/2026-11/09/daemon-interrupt/README.md)）：子類別把已擋住的訊號放進 `wake_`，`nap` 睡覺時連它們一起等，收到就呼叫 `woke(sig)`，回 true＝這一圈當作到時間了（提前跑）；不當收工訊號、不轉給身體。aos-loop 自己不設、不接 poke，行為不變。**子行程的訊號遮罩改成還原**：`run_folder` fork 出來的子行程用 aos-util `restore_signals` 把遮罩還原成 `block_signals` 之前的樣子（原本寫死只解三個收工訊號），所以起 aos-loop 的人（例 aos-daemon）多擋的訊號，身體照常收得到。

## 分檔目錄

> 超過 8 KB，依 [STRUCTURE](../../../wf/STRUCTURE.md) 按標題拆開；本檔留前言與表，各段逐字在下列分檔。

| 分檔 | 涵蓋的段 |
|---|---|
| [01-用法](docs/01-用法.md) | 用法：開頭、log、指示詞 |
| [02-窗](docs/02-窗.md) | 用法（續）：窗（ctl、state、state_flux）、結束碼、訊號 |
| [03-元素等](docs/03-元素等.md) | 元素；實作注意；錯誤代號 |
| [04-建置與測試](docs/04-建置與測試.md) | 建置與測試 |

<a id="用法"></a>
<a id="log"></a>
<a id="指示詞"></a>
<a id="窗ctlstate"></a>
<a id="結束碼"></a>
<a id="訊號"></a>
<a id="元素"></a>
<a id="實作注意"></a>
<a id="錯誤代號"></a>
<a id="建置與測試"></a>
