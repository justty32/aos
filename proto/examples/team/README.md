# team — 指揮一隊

跑這個會看到**一個主 agent（lead）派兩個子 agent，各住自己的資料夾、各自在登記表上有一顆
自己的鐘**，子做完把結果寫回主指定的落點，主等兩邊都好了才合併寫總結——全程用 LLM 世界的
假後端 `echo:`，不打任何網路。

這是 ideas 13「先玩清單」的**第二級劇本**（第一級是單人 coding agent，見
[`examples/agent`](../agent/README.md)）。撞到的東西記在
[`FINDINGS-team.md`](FINDINGS-team.md)。

## 怎麼跑

```sh
proto/play-team.sh
```

它會：起一個暫存家（`examples/team/.home`，不碰你的 `~`）→ init 三塊地 → 起 LLM 世界
（`aos llm serve`，假後端）→ 起 daemon → `aos daemon add lead` 讓 daemon 去起主那支
`aos run` → 每 3 秒印一次 `aos daemon ls` 與三塊地的 `aos status`，直到主閒著或滿五分鐘 →
印「主幾圈、子各幾圈、誰先好、有沒有人卡住、為什麼停」→ 把三塊地的接力棒與狀態檔收進
`proto/play-logs/team-<時間>/`。

實測一趟大概 **4～6 秒**：主走 11～12 格、子 A 與子 B 各走 5 格各跑 1 圈，子 A 先寫回落點。

## 劇本

任務：把主地上 `work/` 的兩支小 Python 檔各加一句檔頭 docstring。子 A 管 `a.py`，子 B 管
`b.py`，主最後列出兩邊改了什麼。

```
主 lead                                    子 A（workers/a）        子 B（workers/b）
 dispatch_a ─ call async ─ 登記子 A 的鐘 ──► （daemon 起 aos run --register）
 dispatch_b ─ call async ─ 登記子 B 的鐘 ──────────────────────────► （同上）
 wait_a ─ await out/a.done.json               prep  讀主派的 work/a.py，組 prompt
 wait_b ─ await out/b.done.json               ask   aos deliver 投給 LLM 世界
 prep_report  把兩份結果組成 prompt           wait  await state/answer.txt
 ask          投給 LLM 世界                   apply 挑出 DOC: 那行，寫回 $AOS_RESULT
 wait_sum     await state/answer.txt                └ 沒挑到就再繞一圈（最多 3 圈）
 report       貼 docstring、寫 report.md
```

- **子自己有鐘**：主的 `call` 步 `mode:"async"` 只把子登進 `$AOS_HOME/.aos/registry.json`
  就算成功（裁決 P-01：沒有 daemon 在跑就當場失敗）；真正起 `aos run <子> --register` 的是
  daemon（G-01）。所以 `aos daemon ls` 看得到三塊地各自的鐘，`aos stop <子>` 停得掉單一個子。
- **子怎麼知道要做什麼**：`AOS_RESULT`（主指定的落點）、`AOS_CALLER`（主那塊地）、
  `AOS_ARG_FILE`／`AOS_ARG_WHO`（主在 `call` 步的 `args` 寫的），由 `aos run` 從登記表那筆重建。
- **子只往落點寫**：子不改主地上的檔，只把想到的 docstring 寫進 `$AOS_RESULT`；貼上去是主在
  `report` 那步做的。落點是主開給子的唯一寫入洞（spec 07b）。
- 假後端 `echo:` 把 prompt 原樣回，所以 prompt 裡放了一行「想不到就照抄」的備用答案，
  子挑最後一行 `DOC:`——換真後端挑到的就是模型自己那行。

## 三塊地有什麼

| 檔 | 幹嘛的 |
|---|---|
| `lead/main.aos.json` | 主的八步：派兩個、等兩個、組總結、投 LLM、等回話、寫報告 |
| `lead/lead.py` | 主的腦：組總結 prompt、把兩邊的 docstring 貼進 `work/`、寫 `report.md` |
| `lead/agent.json` | 主的限制參數＋隊員名單（誰負責哪個檔、落點在哪） |
| `lead/work/a.py`、`b.py` | 要加 docstring 的兩支小檔（跑完會被改，`play-team.sh` 每次會從 `.pristine/` 還原） |
| `workers/a`、`workers/b` | 兩個子，各一塊地；`worker.py`／`main.aos.json`／`system.md` 兩邊一模一樣，只有 `agent.json` 的 `who` 不同 |

跑完才會生出來的（都不進 git）：三塊地的 `.aos/`、`lead/out/`（兩個落點）、各地的 `state/`、
`lead/report.md`、`examples/team/.home/`（暫存家）。

## 想看壞掉長什麼樣

- **子壞掉**：把 `lead/main.aos.json` 裡 `dispatch_a` 的 `args.file` 改成 `work/missing.py`，
  再把 `wait_a` 的 `max_ticks` 改小（例如 8）。你會看到主等到 `await_timeout` 才知道出事，
  而且登記表上子 A 那筆跟「做完了」長得一模一樣（FINDINGS-team T-02）。
- **兩個子撞同一個落點**：把兩個 `call` 步的 `result` 都改成 `out/shared.done.json`。
  沒有任何一層擋，後寫的蓋掉先寫的（T-03）。
- **落點沒清就重跑**：只刪三塊地的 `.aos/` 與 `state/`、留著 `lead/out/`，主第 1 格就會撿到
  上一輪的舊結果。
