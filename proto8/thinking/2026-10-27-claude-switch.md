# 2026-10-27 很多 claude 在跑：一個地方看全部、cd 過去接入、收起與叫回（aos-hub）

← [thinking](README.md)｜月份表 [2026-10](months/2026-10.md)｜前情：[10-24 claude／codex 當工具、人可以接進去](2026-10-24-cli-tools.md)（attach、小格、hook）｜程式：[extras/cli_hub](../extras/cli_hub/README.md)，測試 `proto8/tests/test_hub.py`｜後續：[10-28 常駐 aos-kernel、pause 與 stop](2026-10-28-hub-kernel.md)、[10-28 實作（程式已照新方向重寫，下面的指令多半已換）](2026-10-28-hub-adapter.md)

規矩見 [thinking/README](README.md)：只留使用者原文、決定、結論。

## 使用者原文（10-27）

> 除此之外，我也在想，因爲往後搞不好會有很多claude code cli在跑，我不可能每個都開一個shell視窗去看，是否有一些方式，可以讓我方便切換瀏覽呢？並且可以與我們的aos體系匹配，也就是我cd過去某個資料夾，輸入指令，就可以打開正在該資料夾工作的claude code。可以配合tmux，和claude code cli內建的plugin/hook功能？

> 再來，一大堆的claude code cli實例會拖慢速度，我也在想，能不能我輸入指令，就先讓這個已經沒在動作的claude code cli實例結束，下次輸入指令再把他叫回來。我知道有--resume，我是說，能不能接入aos體系，並且統一管理每個實例？

> 都做做看，我去洗澡，二十分鐘後回來。

下面「代定」是頂層照推薦定的（使用者「都做做看」、人不在），**可翻案**。

## 結論

### 1. 延伸 10-24 的小格，不另起一套

10-24 已經讓每個 claude／codex 工具在 stack 裡有一格（`session.txt` 對話 id、`tty.sock` 畫面、hook 接 `turns.jsonl`、`busy.txt`、`lock`），平常非互動、人 attach 時開畫面。這次**全部沿用**，只加三樣：

- **登記**：`cli_session.py` 每用到一格，就在 `$AOS_HUB/cells/`（沒設＝`~/.local/state/aos-hub/cells/`）放一個指過去的捷徑，格裡記 `tool.txt`、`ws.txt`。登記只是一排捷徑；狀態一律當場從格裡的檔讀（N-13：狀態外顯在 stack 的檔），不另存一份會過期的表。
- **一支指令 `aos-hub`**（[extras/cli_hub](../extras/cli_hub/README.md)）：列出、接入、切換、看、收起、叫回。
- **claude 非互動改 `--output-format stream-json`**，每行一邊寫進格裡的 `live.jsonl`，回答取最後的 `result` 那行。

### 2. 六件事各怎麼做

| 要的 | 做法 |
|---|---|
| ① 總覽／切換 | `aos-hub ls` 列全部格（狀態、閒了幾分、工具、工作區、對話 id）；`aos-hub pick` 選一個接進去；**畫面裡按 Ctrl-]**＝跳出並叫 `aos-hub pick` 選另一格（tmux `detach-client -E`；這個鍵是 hub 接進去前加在那格的 tmux 上，cli_session 不知道有 hub） |
| ② cd 過去一個指令接入 | `cd <工作區> && aos-hub`：這裡一格＝直接接、幾格＝選、沒有＝列全部。「資料夾」＝**工作區**（照 10-24：畫面與對話屬於某次跑的 stack，`$AOS_WS/.stack/<工具>/`；同一個 agent 資料夾可以跑在好幾個工作區）；cd 進格本身或它上層也算 |
| ③ 非互動沒有畫面 | **兩者並存**：agent 平常照樣非互動（不開畫面），要看就 `aos-hub watch` 看 `live.jsonl`（讀了哪個檔、說了什麼、花多少）；要插話就等它這次講完再 `aos-hub` 接進去（`--resume` 同一段）。不改成平常就在 tmux 跑互動版，理由見下 |
| ④ 統一管理 | 同 ①：`ls`／`ls --json`。狀態六種：`agent 在叫`（lock 被拿著）、`有人接著`、`畫面在跑`（busy.txt）、`畫面閒著`、`收起了`（沒畫面、有 session.txt）、`還沒對話` |
| ⑤ 收起 | `aos-hub stop 編號`／`stop --idle 分`：`tmux kill-server` 那格（claude 跟著結束，對話邊講邊存），`session.txt` 留著。前三種狀態不收 |
| ⑥ 叫回 | 對收起的格照樣 `aos-hub`／`attach`：10-24 的 `start` 用 `--resume <session.txt>` 開畫面。agent 那邊不用改：畫面沒開走 `-p --resume`、開著從畫面送字（10-24 兩條路） |

**③ 為什麼不改成平常就跑互動版**：互動版開機要等畫面穩（10-24 實測 3 秒門檻、codex 還會卡 Resuming）、可能卡在信任／權限提問沒人回答（10-24 定「只有人開畫面，agent 從不自己開」）、`--max-budget-usd` 只對 `-p` 有效、每格常駐一支 claude 正是使用者說的「拖慢速度」。stream-json 不多一支行程、照樣看得到即時進度。

### 3. 實跑（haiku，總共不到 $0.01）

`~/code/try/claude-switch/`：三個工作區各叫一次 → `ls` 三格都「收起了」→ `attach -d 1` 叫回 ws-a（畫面上看得到 agent 問過的那句）→ agent 再問一句（從畫面送字，答 6）→ `stop --idle 0` 收起 → agent 再問（非互動 `--resume`，答 7）→ 再叫回，畫面上三輪都在。`watch` 看到 ws-b 那次 Glob、Read 四個檔、花 $0.0014。外層 tmux 裡按 Ctrl-] 出現選單、選 2 接進 ws-b。`aos-loop --max 1 reap.json` 跑得動。

### 4. Claude Code 內建的背景 session（查過、沒選）

v2.1.311 有 `claude --bg`（背景開）、`claude agents`（列出所有互動與背景 session，`--json` 給程式讀，`--cwd` 篩資料夾）、`claude attach <id>`、`claude logs`、`claude stop`（停掉、對話留著，`attach` 或不帶旗標的 `claude --bg --resume <id>` 會用原本的選項叫醒）。實測：停掉再叫醒接得上同一段；叫醒時帶了旗標＝另開一份拷貝。幾乎就是 ④⑤⑥ 的現成版，**但沒選它當主路**：

- 沒有「往背景 session 送一句、拿回答」的指令，agent 那邊的兩條路接不上（只能先 stop 再 `-p --resume`）；
- 看不出有沒有人接著；狀態存在 `~/.claude/jobs/`，不在 aos 的 stack 裡（N-13）；
- 只有 claude，codex 沒有；背景 session 預設跟著使用者設定開（實測顯示 auto mode），權限要另外顧。

10-24「未決」那條（兩家都有穩定的背景 API 就改走 CLI 自家機制）仍然成立；現在 claude 這邊只差「送一句」。你自己在終端機開的 claude 不在 hub 裡，用 `claude agents` 看。

## 10-27 晚：用起來的疑問（先不改）

使用者問：「我能不能走到某個資料夾，然後打aos-hub確認這個房間的狀況？ctrl-]換房是怎麽實現的？aos-hub stop指令，後面接啥？還是說我要cd過去打？ctrl-]是否應該是直接退出(但不結束)，而不是還要換下一間？」聽完現況與改法建議後：「Hmmm，沒事，反正這只是demo，以後再完善就好，先這樣。」

結論：aos-hub 是 demo，介面先不改。之後完善時的候選（頂層建議、使用者沒定）：退出鍵只留一個（只跳出不結束）；`aos-hub ls` 在工作區裡只列這一格、`-a` 列全部；`aos-hub stop` 不帶編號＝收這一格。

## 代定（可翻案）

- **自動收起：閒 30 分**，用 aos-loop 每分鐘跑一次 `aos-hub stop --idle 30`（`extras/cli_hub/reap.json`），不另寫常駐程式。要不要開、要不要掛進 aos-daemon 或 tick 的定期事務，由使用者決定；目前要手動 `aos-loop reap.json` 才會跑。30 分的理由：一輪對話少有停超過 30 分還要馬上接著講的，收錯了叫回也只要幾秒。
- **登記位置 `~/.local/state/aos-hub/`**（XDG 的「狀態」資料夾），可用 `AOS_HUB` 換（測試用）。
- **指令名 `aos-hub`**、換一格的鍵 **Ctrl-]**（Ctrl-\ 跳出照 10-24；Ctrl-b 留給 Claude Code）。
- **收起用 `tmux kill-server`**，不先在畫面打 `/exit`（打字可能卡在別的提問上）。
- 「閒了多久」看格裡檔案最後被動的時間，不另寫時間戳。

## 跟原則的衝突與方向題

- **C-52 巢狀只管自己這一層**：hub 要知道格裡的檔（`busy.txt`、`lock`、`tty.sock`）才判得出狀態，等於讀了 cli_session 那層的內部。現在的做法是 hub 直接 import cli_session（同一份程式碼讀自己的格），算「同一層的兩個入口」；若要嚴格分層，得讓 cli_session 自己出一個 `status` 指令、hub 只叫它。
- **N-13 狀態外顯在 stack／C-67 位置由叫的人給**：登記放在全機一份的 `~/.local/state/aos-hub/`，不屬於任何工作區或 stack；aos 現在沒有「全機一份」的地方（像 `AOS_HEAP` 那樣由叫的人給是最接近的先例）。後果：不同使用情境（測試、別的試驗場）會混在同一份清單，除非各自設 `AOS_HUB`。
- **自動收起該掛哪裡（方向題）**：proto8 的 aos-loop（現在的做法，最小）、aos-daemon 的一個子 loop（跟其他常駐的一起管）、core/tick 的定期事務登記（`wf-tick` 那套）。原則推不出唯一答案。
- **playground 的節點不在裡面**：它直接 `claude -p --no-session-persistence`，沒有格、對話不留。要進 hub，就得改走 lib/agent 的 claude 工具（或至少照小格慣例存 `session.txt`、`live.jsonl`）。這是 user-advice「節點從 claude code cli 長成樹」那條路要不要統一用 cli_session 的問題。

## 已知限制

見 [cli_hub/README 已知限制](../extras/cli_hub/README.md#已知限制)。另：試的時候自己開的 tmux 一定要 `-f /dev/null`——使用者的 `~/.tmux.conf` 開了 tmux-continuum 自動復原，任何新開的 tmux server 都會把他存的 session 搬進來（10-27 試 Ctrl-] 時踩到；格的畫面有自己的 `tmux.conf`，不受影響）。
