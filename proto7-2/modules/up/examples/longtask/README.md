← [up examples](../multiround/README.md)｜意圖卡 [longtask](../../../../notes/intents/longtask.md)｜實跑報告 [2026-10-09-longtask](../../../../notes/play/2026-10-09-longtask/README.md)

12 封需求信（`letters/*.txt`，第一行是標題；用 .txt 是因為 05 號故意放了壞連結）：01 是一份 12 節週報、要分 13 回合做；02～10 是小件（有的指定分 2～3 回合）；11 問「你前面交的週報第 5 節」（看 brain 跨信記不記得）；12 故意缺人數又有兩份對不上的數字（逼出要你決定）。

從 repo 根跑（包在 systemd scope 裡）：

```sh
systemd-run --user --scope -p TasksMax=300 python3 -B proto7-2/modules/up/examples/longtask/run.py /tmp/lt-out              # 假 AI，約 30 秒
systemd-run --user --scope -p TasksMax=300 python3 -B proto7-2/modules/up/examples/longtask/run.py /tmp/lt-out --model chatgpt-gpt-6-sol-high --kill-mode brain
systemd-run --user --scope -p TasksMax=300 python3 -B proto7-2/modules/up/examples/longtask/run.py /tmp/lt-out --fake-delay 2 --deadline 8 --kill-mode tree --kill-step 3   # 假 AI 重現殺整棵樹，約 1 分鐘
python3 -B proto7-2/modules/up/examples/longtask/analyze.py /tmp/lt-out                                                    # 印燈號數字，寫 summary.json、calls.csv、replies.md
```

`run.py` 起 node、把 `compact.json` 門檻改成 6000 bytes／留 3 則、依序寄 12 封、01 號做到第 `--kill-step` 回合時 SIGKILL 一次，12 封都有終局回信（或 `--stuck-minutes` 沒變化、`--max-calls`、`--max-minutes`）就停心跳，房子打包成 `OUT/house.tar.gz`（暫存房子留在 /tmp，看完自己刪）。`--kill-mode`：`tree` 連同正在問 AI 的 llmcall 一起殺（2026-10-09 實跑會卡死，見報告；修好後那封在 deadline 秒後回卡住、後面照常辦）、`brain` 只殺 brain、`idle` 等 brain 沒在問 AI 時殺。`--fake-delay`（只對假 AI）讓假 AI 每次回覆前等幾秒，才殺得到傳輸中途；`--deadline` 寫進 up.json，就是「不確定」等多久回卡住。真 AI 一次約 29 次呼叫、2.5 分鐘。
