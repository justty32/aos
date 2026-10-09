# kernel 進階

← [README](README.md)｜[spec.md](spec.md)｜[藍圖 kernel1](../../notes/blueprint-kernel1.md)｜[意圖卡](../../notes/intents/kernel.md)

## 一覽與契約卡

| 項目 | 內容 |
|---|---|
| 分類 | 上層任務包；普通 keep 任務（`max_live: 1`），替別的任務做決策 |
| 第一版範圍 | 觀測＋綁 run 的 kill＋通知；規則只有內建 `supervise-brain`（與測試用 `noop`） |
| 職責 | 每個自己的 tock：讀來源公開事實→快照→純函式規則→整份驗證→**先存意圖再送控制**→核對回條；被殺接續 |
| 前置條件 | 心跳在跑；`<node>/kernel/kernel.json` 合法；別的 node 的來源／目標要在 kernel 的 tasks 項目 `mounts` 掛上 |
| 保證 | state 一次 rename；決定 id 提交時給定、重送重起同一個；kill 綁原 run，絕不轉向新 run；同目標同時最多一份 kill；一個 run 最多 kill 一次；同信只通知一次，同一步 kill 等待加倍、最多 3 次（可設） |
| 不保證 | kill 之後 keep 會不會重起、重起後好不好；brain 業務上算不算完成 |
| 寫的檔 | 自己槽 `state.json`（唯一恢復真相）、`decisions.json`（只留上一次、給人看）；目標槽 `ctl.json`；有設 `mail` 才寄 NEEDS-USER |
| 只讀 | 來源槽 `birth.json`、來源 node 的 `brain/task.json`、`round.json`、inbox 與 done 的信件標題；不呼叫會收程序的判定 |
| 依賴 | 標準庫、核心 `aos7_fs`；寄信用 `modules/mail`（可選）；不改核心、不碰 step／budget／adapt |
| 程式 | `aos7_kernel_state.py`（設定、state、快照）、`aos7_kernel.py`（驗證、送出與核對、主迴圈、status）、`aos7_kernel_rules.py`（規則）、`bin/aos7-kernel`（薄入口） |
| 範例 | `examples/supervise-brain/`（`run.py`、`kernel.json`） |
| 測試 | `tests/test_kernel_core.py`、`test_kernel_crash.py`（骨架、崩潰矩陣）、`test_kernel_rules.py`（規則純函式）、`test_kernel_example.py`（範例整圈） |

## 裝到自己的 node

kernel 不跟 `aos7-up` 一起裝。在 repo 根、node 是 `/tmp/aos/bob`（aos7-up 起的，房子 `/tmp/aos`）時：

```sh
mkdir -p /tmp/aos/bob/kernel && cp proto7-2/packs/kernel/examples/supervise-brain/kernel.json /tmp/aos/bob/kernel/
python3 proto7-2/bin/aos7-ctl add /tmp/aos/bob "{\"name\":\"kernel\",\"mode\":\"keep\",\"argv\":[\"python3\",\"$PWD/proto7-2/packs/kernel/bin/aos7-kernel\",\"run\"]}"
```

keep 任務的 argv 要寫 aos7-kernel 的**完整路徑**（任務的工作目錄是 node，不是 repo 根）。第一次 `run` 會自己初始化 state，不用另外 init。範例的 `kernel.json` 把 node 寫成 `bob`（相對心跳的房子）；別的名字要改成自己的。

看它在做什麼：`python3 proto7-2/packs/kernel/bin/aos7-kernel status /tmp/aos/bob`，一行白話，例如「監督 1 件：都在動，沒有要處理的」「監督 1 件：已寄信 you」「監督 1 件：kill brain#16 等回條（可能晚一點才生效）」。

## 設定 `kernel.json`

完整規則見 [spec §2](spec.md)。要點：

- `sources`：要看的 brain（`node`＋`slot`＋`kind: "brain"`）；`targets`：可以 kill 的槽，每個都要在 sources 裡，否則退 2；sources 最多 10 個。
- `node` 是相對心跳根（aos7-up 的房子）的 node id；寫 `.` 也代表自己，但通知信裡會照字印成「. 卡住了」，所以範例寫 `bob`。
- `rules`：`supervise-brain` 的 `no_progress_rounds`（預設 6，到了寄信）、`kill_after_rounds`（預設 12，第一次到了 kill）、`max_kills`（正整數，預設 3）、`notify`（收件人，預設 `you`）。
- `mail`：可選。`{"root": "..", "from": "kernel"}`＝寄到 node 的上一層（aos7-up 的房子）的信箱；不寫就不寄，通知只記在 state 的 `done`（status 看得到「提醒已記下」）。
- 監督門檻與 max_kills 有寫就要是正整數（bool 不算）；補齊預設後，kill 門檻必須大於通知門檻，初始化前就驗證。
- `events` 第一版只收 `false`。
- **改設定**：設定雜湊不合時 kernel 不再提交、退 1（改回原樣即接續）。要換設定，先等在途清空，再刪 state.json 與 decisions.json。

## supervise-brain 怎麼判

- 進度＝`<node>/brain/task.json` 的 `(id, step)`（信、步數），綁來源槽 `birth.json` 的 `run`。沒有 task.json＝閒置或已結案，不看。
- 老化＝來源 node 的回合數（`round.json`）距基準建立過了幾回合；心跳停了就不老化。讀不到、run 對不上＝不知道，不計老化、恢復後重建基準。
- 滿 `no_progress_rounds`：同一封信只寄一次 NEEDS-USER，換 run 或 step 都不重寄。
- kill 綁當時 run，每 run 最多一次；同一封信同一步，第 1／2／3 次要停滿 12／24／48 回合（門檻可設），最多 `max_kills` 次，到上限就停止；換信或 step 改變才歸零。新 run、未知恢復重建計時，通知與次數保留，舊 state 可直接接上。
- brain 每次回「繼續」都會往下一步，自己連續 3 回合沒進展會先回信問你（NEEDS-USER），所以預設 6／12 只是**保底**：brain 程序還活著、卻不再寫 task.json（例如卡在等 AI）才會走到 kernel 寄信與 kill。

## 範例在做什麼

`examples/supervise-brain/run.py`（門檻用預設 6／12，心跳 1 秒一回合，全程約 30 秒）：

1. `aos7-up -d` 起 bob（假 AI），照上面兩行裝 kernel。
2. 寄「做 5 回合的整理」；bob 做到第 2 步，把 `.aos/up.json` 的 `fake_delay` 設 3600——假 AI 不再回，brain 卡在等 AI。
3. 停滿 6 回合，kernel 寄 NEEDS-USER 給 you；停滿 12 回合，kill brain 當時的 run，回條 ok。kill 收的是整個程序群組，正在等 AI 的 llmcall 子程序一起收掉。
4. keep 重起 brain：從 task.json 的同一步接續，同一筆 call 不重送（`llmcall/fake-remote.json` 的受理次數仍是 1），只說「AI 還沒確定回沒回」。範例這時把 up.json 的 `deadline` 調成 1 秒，brain 就不再等、回你 BLOCKED 結案。不調的話 brain 會照 up 的規則等滿 `deadline`（假 AI 預設 60 秒、範例設 600），這段期間同信不重寄；下一次 kill 會等 24 回合，同一步最多收掉 3 次。
5. 還原 up.json；SIGKILL kernel 一次（keep 重起它，brain 不受影響），再寄「做 4 回合的介紹」：一回合一步、回信 DONE，kernel 零動作。

`--keep` 留下房子，可以看 `you/inbox/` 的三封信（kernel 的 NEEDS-USER、bob 的 BLOCKED 與 DONE）、`bob/.aos/tasks/kernel/state.json` 的 `done`。旁觀者不用懂 kernel：`aos7-up status` 的「信」那行會算到「1 封要你決定」。

## state、快照、規則介面

都在 spec，不重抄：state 形狀與初始化 → [spec §3](spec.md)；快照四態 → [spec §4](spec.md)；規則簽名 `rule(ctx, snap, rstate) -> (rstate2, candidates)` 與整份驗證 → [spec §5](spec.md)；執行順序與四個崩潰點 → [spec §6](spec.md)；kill／notify 的送出與核對 → [spec §7](spec.md)。

## 退出碼與錯誤

| 碼 | 意思 | 例 |
|---|---|---|
| 0 | 做到 | `run` 收到 SIGTERM；`status` 印出一行 |
| 1 | 做不到 | 設定雜湊和 state 不合；state.json 不見了但 decisions.json 在 |
| 2 | 你給的不對 | kernel.json 不合（target 不在 sources、未知規則）；`status` 給的 node 沒有 kernel.json |
| 3 | 不知道 | state 讀寫故障、tasks.json 讀不到；證據都留著，照原樣再跑會接續 |

stderr 一行 `aos7-kernel: 發生什麼。怎麼辦`，3 以「不確定：」開頭。

## 測試

`systemd-run --user --scope -p TasksMax=300 python3 proto7-2/tests/run_all.py packs/kernel/tests`
