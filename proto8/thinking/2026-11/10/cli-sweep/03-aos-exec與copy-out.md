aos-exec（含 --stack、入口怎麼找、.env）與 templates/copy-out 照 C-85 掃一遍。

← [入口](README.md)｜上一份 [02-aos-daemon-ctl](02-aos-daemon-ctl.md)｜下一份 [04-aos-llm-eca-mcp](04-aos-llm-eca-mcp.md)

# aos-exec（lv1——這裡的改法一律只動 help／訊息，行為改動全部標「留大修」）

實跑：`/tmp/cli-sweep/ex/`（`prog/_entry` 是一支印出參數、cwd 與 AOS_ 變數的 sh，`prog/.env` 有 `FOO=from-dotenv`）。

## 現況的一段白話

> aos-exec 把一個資料夾（或檔）當程式跑。它先找到入口（資料夾裡的 `_entry`、可執行檔、或 JSON 裡寫的指令），備好兩個位置——工作區（`AOS_WS`，預設你現在站的地方）與 stack（`AOS_STACK`，放它跑出來的狀態，預設工作區下的 `.stack/`）——讀入口旁邊的 `.env`，然後帶著你給的參數跑它，退出碼就是它的退出碼。

## 這段話裝不下的（八樣）

1. **它會把 cwd 換到入口所在的資料夾**。
2. **不給 `--stack` 就在工作區默默建一個 `.stack/`**。
3. **你站在哪＝工作區**（同一行指令換個地方打，`AOS_WS` 就不同）。
4. **`--stack -` 或空字串＝沿用外層的**。
5. **`.env`：外面已經設的贏；`--dotenv-override` 反過來**。
6. **入口四種、`檔#/指標`**。
7. **旗標要寫在 XXX 前面**（後面的全是給程式的參數）。
8. **它另外設了 `AOS_CD／AOS_CF／AOS_CO`**，help 沒提。

## 怪點逐點

**E1　cwd 被換掉，help 只有「set up … cwd」三個字。**（設計如此；補說明）

```
$ cd /tmp/cli-sweep/ex && aos-exec prog a b
args=[a b] cwd=/tmp/cli-sweep/ex/prog WS=/tmp/cli-sweep/ex STACK=/tmp/cli-sweep/ex/.stack/ CD=/tmp/cli-sweep/ex/prog …
```

你打 `aos-exec prog ./input.txt`，程式是站在 `prog/` 裡看 `./input.txt`。這是「資料夾＝程式」的規矩（N-57～N-62），不該改；但 help 要用一句話講出來（例：「runs with cwd = the entry's folder; the folder you started from is $AOS_WS」）。

**E2　隨手試一次就留下 `.stack/`。**（設計如此；補說明。aos-tools-cli 01 第 8 樣已記過 `aos-tools call` 的同一件事）

```
$ aos-exec prog; ls -a                →  .stack  prog  …
$ aos-exec --ws sub prog; ls -a sub   →  .stack
```

`--stack` 指的夾不在會自己建；`--ws` 指的夾不在則報 `WsMissing workspace does not exist: nope`。一個自己建、一個不建，各有道理（stack 是 aos 的、ws 是人的），help 沒講。

**E3　站在哪＝工作區：日常那一行的隱藏輸入。**（設計如此；補說明）

```
$ cd /tmp && aos-exec --stack /tmp/cli-sweep/proj/stacks/root2 /tmp/cli-sweep/proj/defs
（換個地方、給絕對路徑，照樣起得來、睡下的列照醒、排著的信照答）
```

起得來，但這台根的 `AOS_WS` 變成 `/tmp`（`aos-daemon-ctl add` 不給 `-w` 時「default: the daemon's」就會落在那）。daemon-root README 的例子有先 `cd <你的專案>`，沒說為什麼。

**E4　`.env` 的方向**（設計如此）

```
$ FOO=outer aos-exec prog                    → FOO=outer        （外面贏）
$ FOO=outer aos-exec --dotenv-override prog  → FOO=from-dotenv
```

這就是「起之前先 `unset AOS_CLOCK`」的來源：殼裡有舊值，`.env` 就不生效，而且沒有任何提醒。

**E5　錯誤訊息的 usage 跟 help 的 usage 是兩個版本**（小事）：錯誤行印 `aos-exec [--ws WS] [--stack S] [--dotenv-override] XXX [ARGS...]`，help 印 `aos-exec [FLAGS] XXX [ARGS...]`。

**E6　`aos-exec help`＝`EntryMissing entry not found: help`**：全家都不收 `help` 這個字（[06](06-跨指令不一致.md) X10），只是 aos-exec 的訊息最不像在講 help。

**只是不熟**：四種入口與 `檔#/指標`（實跑 `one.json`、`multi.json#/a`、`multi.json#/b z` 都如文件）；`--stack=st` 的等號寫法可用；`--` 可用。

**已知、不重報**：設計-43（JSON 入口加 `+x` 又寫 `#!/usr/bin/env aos-exec` 無限 exec）、設計-45（`.env` 改 `AOS_WS` 時 stack 不跟）、B08（`EntryMissing` 只印字面值）。

## 照推薦改完後的一段白話

行為不動，所以白話同上；help 多三句：cwd 會換、沒給 `--stack` 會建 `.stack/`、`.env` 蓋不過殼裡已有的值。裝不下的八樣裡 1、2、5、8 從「要另外解釋」變成「help 第一屏就看得到」。

---

# copy-out（templates/ 底下的 Python 腳本；範本屬 lv5）

實跑：`/tmp/cli-sweep/co/`。

## 現況的一段白話

> copy-out 把 repo 裡的一份範本整夾抄到你指定的新資料夾，順便把範本裡指回 repo 的路徑改寫成換台也能用的寫法（預設靠環境變數 `AOS_PROTO8`，也可選相對或絕對）。

## 這段話裝不下的（七樣）

1. **只給一個參數時，那個參數是目的地，範本用預設的 agent-fsm**。
2. **三種 MODE 的差別**（已是使用者裁定，留）。
3. **捷徑（symlink）會變成複本或絕對捷徑，各印一行 warning**。
4. **不需要 `AOS_PROTO8` 的範本也印「needs AOS_PROTO8」**。
5. **沒有辦法列出有哪些範本**。
6. **名字沒有 `aos-` 前綴；旗標叫 `--proto8`**。
7. **TEMPLATE 只認 repo 裡的名字，不能拿自己的資料夾當來源**。

## 怪點逐點

**C1　一個參數＝目的地：打錯就默默抄一份。**（真問題）

```
$ copy-out help
copied agent-fsm -> /tmp/cli-sweep/help/help (6 paths written as env)
$ copy-out agent-fsm
copied agent-fsm -> /tmp/cli-sweep/co/agent-fsm (6 paths written as env)     ← 以為在指定範本，其實是目的地
```

`usage: copy-out [--proto8 MODE] [TEMPLATE] DEST`（`templates/copy-out:34` `DEFAULT = "agent-fsm"`）。可省略的參數排在必填的前面，是全家唯一一處。

**C2　「0 paths written」之後還說需要 AOS_PROTO8。**（真問題，小）

```
$ copy-out daemon-root defs
copied daemon-root -> …/defs (0 paths written as env)
needs AOS_PROTO8 set to this machine's proto8 folder (now: …)
```

daemon-root README 自己寫「本範本自己沒有指進 repo 的路徑」。

**C3　沒有 `--list`；範本名打錯時的訊息也不列有哪些。**

```
$ copy-out nosuch dest1
copy-out: error: TemplateMissing no template folder nosuch under …/proto8/templates (or kernel/NAME under …/proto8/kernel)
$ copy-out --list
copy-out: error: FlagUnknown unknown flag --list
```

**C4　旗標只能在前**：`copy-out daemon-root r2 --proto8 env` → `ArgumentsBad too many arguments`（訊息沒講是位置問題；aos-tools 今天修過同型的）。

**C5　名字**：PATH 上叫 `copy-out`（`~/.local/bin/copy-out`），是全家唯一沒有 `aos-` 的；在 [指令樹](07-指令樹.md) 上沒有位置。`--proto8` 是拿「原型第八版」這個資料夾名當旗標名。兩個都是命名題，列給使用者，不代定。

**設計如此**：三種 MODE（使用者 11-10「要用相對位置、絕對位置、環境變數指定都可」）；symlink 的四行 warning（B12 已記「env 模式的 tooldef／metainfo 是快照複本」）；`kernel/NAME`；目的地已存在就拒絕（`DestExists … nothing is overwritten`）。

## 照推薦改完後的一段白話

> copy-out 把 repo 裡的一份範本整夾抄到你指定的新資料夾（`copy-out 範本 目的地`，兩個都要寫；`--list` 看有哪些範本），順便把指回 repo 的路徑改寫成換台也能用的寫法；抄完告訴你這份在別台需要備好什麼——不需要就不說。

少掉 1、4、5；2、3、7 留著；6 看使用者。
