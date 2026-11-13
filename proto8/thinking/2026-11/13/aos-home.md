# 公司 WSL 改住 `~/aos-home`（11-13 早）：repo 換成 `~/repo/aos`、重 build＋install、全套測試，`~/aos-home` 從零重搭一隻 opus eca，遊樂場與舊 repo 刪掉

← [11-13 日索引](README.md)｜搭法十七步：[ops-notes-to-aos § 從零搭一棵小樹](../12/ops-notes-to-aos.md#從零搭一棵小樹一個-daemon一隻懂-aos-的-opus-eca使用者自己做)｜桌面手冊原稿：[aos-home-手冊.html](aos-home-手冊.html)

## 使用者原文

- 「幫我把現有的WSL遊樂場重刷一次，包括裡面的知識庫。」
- 頂層問要不要 pull、重 build、重裝、跑全套測試：「要的，整個重弄好」
- 「等等，應該說，我要遷移到WSL那邊去。所以WSL那邊，可能就不會是遊樂場了。可能...~/aos-home？」
- 問住哪：「住~/aos-home，我自己搭的都清掉，我們整個重新來過。然後~/repo/simple_tools/aos就是最新的。」
- 問用哪份 repo：「直接~/repo/aos好了」
- 「好了之後弄一分我可以照著做的手冊到桌面」
- 舊的 aos-home、`~/repo/aos-tools`、`~/repo/simple_tools/aos`：「這些舊的都直接刪」；接著「連同~/repo/simple tools一起刪掉。遊樂場也都刪掉」
- （頂層轉述）下個 session 會是 aos 體系：他要搬進 WSL 用 aos 裡的 agent 工作。

## 結論

- **公司 WSL 的工作 repo 是 `~/repo/aos`**：`git clone ~/repo/aos-tools ~/repo/aos`（`2e8eb6736`），origin 改回 `https://github.com/justty32/aos.git`，`main...origin/main` 對齊；推拉照舊加 `-c 'url.git@github.com:.insteadOf=https://github.com/'` 走 SSH。
- **impls 在 `~/repo/aos` 全部重 build**（08:22～08:23，十支 bin 都新）。`install.sh` 第一次全部 skip（`~/.local/bin` 25 條 `aos-*` 連結與 `aos-proto8.pth` 都指 `~/repo/aos-tools`，install 不覆蓋別份 repo 的連結）：刪掉那 25 條連結、`.pth` 改名成 `aos-proto8.pth.bak-1113-aos-tools`，重跑＝linked 25、寫新 `.pth`；現在 25 條全指 `~/repo/aos`，`readlink -f $(which aos-exec)`＝`~/repo/aos/proto8/impls/aos-exec/bin/aos-exec`，Python 模組從 `~/repo/aos/proto8/py` 讀。
- `~/.cache/aos-mcp-*/tools.json`：公司 WSL 沒有（不用清）。
- **全套測試（`~/repo/aos`）**：在 `~/repo/aos`（`2e8eb6736`，08:24～08:36）proto8 底下直接放 `test_*.py` 的 66 夾（archive、build 除外）各跑 `python3 -m unittest discover`，從空的短暫存目錄 `/tmp/ftb/t` 起跑：**66 夾 1354 例，只紅既有 4 支**（aos-agent `test_daemon_down` 的 test_add、test_stop；box_check `test_acceptance` 的 test_measure_boxed_passes、test_real_boxed_whitelist_and_writes），skip 2，沒有新的紅、沒有逾時；aos-eca 92 例全綠（短路徑沒撞 AF_UNIX 上限）。輸出在 `/tmp/ftb/`（之後連 /tmp 一起清了）
- **`~/aos-home` 從零重搭**（舊的使用者自己搭的那棵：樹停著、沒有行程，直接刪，沒留備份）：照十七步 ①～⑦，路徑換 `~/repo/aos`。陣容：根（`_clock`、`_sweeper`、`foreman`）＋領班（`_sweeper`）＋一隻 `eca_main`（eca-claude 範本、opus、`print_flags []`＝不設花費上限、`system.txt` 指 `../knowledge`）；沒有問腦總機。
- **實驗一輪都過**：起樹三列 running；`eca_main` 掛上 running；aos 工具 **26 支**（子 agent 那台照 `tools_sub.json` 是唯讀 9 支，沒另外數）；hooks `mail_notify`、`timer`；opus 一句（index_view 看 `../knowledge/aos` 答 **20 項**、`json_get` 讀 `_description.json` 答出第一句）16 秒；`aos-agent chat` 用管線送一句答 `ok`；停樹 `3 procs asleep`、沒有殘留行程；存檔 `~/aos-saves/aos-home-1113-0825`（4.7M）；讀檔（`rm -rf ~/aos-home && cp -a 存檔 ~/aos-home`）後起樹，`eca_main` 照樣 running、history 4 行在；再試手冊第 ⑦⑧ 段：`git pull`（已最新）、重抄 lib／knowledge、加 `eca_two`（26 支）再 `rm --purge` 拿掉。驗完樹停著。
- **信任**：`~/.claude.json` 對 `~/aos-home/ws` 已是 `hasTrustDialogAccepted: true`（同路徑之前信任過），chat 不用；畫面沒驗。
- **刪掉的**（使用者授權）：舊 `~/aos-home`；`~/code/` 底下 `playground` 開頭的八夾（`playground`〔11-13 08:16 照 HEAD 重抄一半、沒起樹的半成品〕、`playground-fsm_ann.bak-1110-toolscli`、`playground-lib.bak-1110-toolscli`、`playground.bak-1110`、`playground.bak-1111-1024`、`playground.bak-1111-1306`、`playground.bak-1113-0816`〔11-12 12:45 那份原樣，含 eca_opus 自己寫的 `ws/notes`、`ws/new_tools/aos_cache`〕、`playground.bak-anchor-20261110`；刪前各自 stopped、沒有行程）；`~/repo/aos-tools`（刪前查過：沒有未推 commit、沒有 stash、只有一條 worktree、未追蹤的只有頂層那封過時交接信、ignored 的全是 build／bin／`__pycache__`；沒有連結或行程指著它）；`~/repo/simple_tools/aos`（自己有 `.git` 的獨立 repo、在上層 repo 是未追蹤的 `aos/`，刪了上層不會多刪除變更；查法同上，乾淨）。
- **沒刪的**：`~/repo/simple_tools` 這個上層 repo（它的 `main` 有 **8 個沒推的 commit**，全是 `freepy/` 的：`57da41f`～`14a0a8f`，遠端沒有），等使用者看過再定；舊 `.pth` 改名檔；`~/aos-saves/aos-home-1113-0825`。

- **`/tmp` 清了**（使用者「/tmp可以清掉，別占用記憶體」）：先確認沒有 aos 行程、沒有行程開著要刪的檔；刪了 guanyu 名下的 `aos-daemon-b.*`、`aos-review-round-*`、`aos-impls-build.lock`、`judge-test.*`（50 夾）、`ft1113`、`ftb`、`pg1113-*`；40M → 572K。留著：`claude-1000`（Claude Code 自己的暫存，可能有 session 在用）、`node-compile-cache`（node 的快取）、root 擁有的系統夾。`/tmp/line*`、`/tmp/fulltest_*`、`/tmp/aos-home-dryrun` 早就不在了。

## 十七步跟 11-13 main 對不上的地方（已改進 ops-notes-to-aos）

- repo 路徑 `~/repo/aos-tools` → `~/repo/aos`（先要有的、②、③ 的提示句、⑯）。
- ⑥ 範本 flags 多了 `Agent,Skill`、`cli.json` 帶 `tools_sub`；⑩、⑫ 工具支數 25 → 26。
- 其他步照抄就過；系統提示 `system.txt`、`knowledge/aos/_description.json`、`index_view` 都還對。

## 沒驗

- `aos-agent open`（畫面）：從程式叫沒有終端機。
- opus 那句花多少錢：transcript 裡沒找到 cost 欄位，沒記到。
- 子 agent（Agent 工具）實叫一次、外部 MCP（⑰）。

## 代定

- 新 aos-home 不建問腦總機（eca 用不到；十七步本來就沒有）。
- 舊 `.pth` 改名留著（`~/.local/lib/python3.12/site-packages/aos-proto8.pth.bak-1113-aos-tools`），不刪。
- 讀檔那步照手冊寫法實跑（會蓋掉當下的 aos-home；當下那份跟存檔一樣）。
- 手冊背景起樹的 log 放 `/tmp/aos-home-root.log`。

## 早上先做的遊樂場重刷（被叫停、之後整個刪了）

- 08:16 把 `~/code/playground` 整份 `mv` 成 `.bak-1113-0816`，照 HEAD 重抄 `lib py templates knowledge`、總機、四隻定義、fsm_ann 外部 MCP 示範，帶回 `ws/notes`、`ws/new_tools`；起樹前被叫停，後來使用者說遊樂場都刪，兩份一起刪了。
- 同時在 `~/repo/aos-tools`（同一個 `2e8eb6736`）先 build 過一次、跑了 47 夾全套就停（改到 `~/repo/aos` 重跑）：那 47 夾只紅既有 4 支。
