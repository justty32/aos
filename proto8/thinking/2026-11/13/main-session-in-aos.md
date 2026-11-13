# 主 session 接 aos 的四題（11-13 早，公司 WSL）：主 session 已經是樹裡的一隻 eca proc「repo-aos」，四題照現況與原則各自定案；留兩題給使用者裁（只規劃、沒施工）

← [11-13 日索引](README.md)｜前情：[wf-to-aos 02 § 明天主 session 開始：現在卡在三點](../12/wf-to-aos/02-寄信給人與主session.md#明天主-session-開始現在卡在三點)、[wf-to-aos](../12/wf-to-aos.md)、[linux-user § 人的行程算樹外還是樹內](../12/linux-user.md#續c-64-以今晚為準人的行程算樹外還是樹內不是問題)、[aos-home](aos-home.md)

## 使用者原文（引自既有文件，逐字）

- 11-12 晚（[wf-to-aos](../12/wf-to-aos.md)）：「.json比markdown好，有需要的話再做一些輔助工具和程式幫助人看json就好。2.先放着，這是後面一邊玩一邊自然會要做的。3.後續玩一玩，自然會想到怎麽做，反正有hook。4.把人類這個linux user作爲agent，寄信過去就是了。5.對，這個明天開始。」
- 11-12 晚（[wf-to-aos 02](../12/wf-to-aos/02-寄信給人與主session.md)）：「好，這些都不是問題。只是主session接mcp這個要處理。邊緣狀況這邊就先這樣，之後踩坑再說。」
- 11-12 晚（[linux-user](../12/linux-user.md)）：「這個問題...不是問題，我開claude code做事，如果這個是claude code eca，那一切都被收在claude code eca中，對於其他proc來說，他們面對的就是這個eca proc。」
- 11-12 晚（[linux-user](../12/linux-user.md)）：「user是哪個proc...對，就是aos眼中一個能收信的對象。」
- 11-11（[P-43](../../../docs/CONVENTION/02-題目stack停錯腦/03-P-43-本文.md)）：「eca基本都有goal，所以goal不用給eca。todo也不用。」
- 11-04（[P-43](../../../docs/CONVENTION/02-題目stack停錯腦/03-P-43-本文.md) 末段）：「.claude調查這塊。全部都是自己要承擔的風險」
- 11-10（[P-48](../../../docs/CONVENTION/02-題目stack停錯腦/10-P-48.md)）：「5.對。使用者這邊需要把自己當agent，自己指定自己的stack」

## 一句話

昨晚四題的前提是「主 session 是一個不在任何 daemon 表上的 Claude Code」。今天早上這個前提沒了：公司 WSL 的主 session 就是 `~/aos-home` 那棵樹裡的一隻 eca proc，名字 `repo-aos`。所以四題有三題已經被事實回答，剩下的照原則定得出來；真正要使用者裁的只有兩題（見[最後一節](#要使用者裁的)）。

## 現況總覽（11-13 09:30 前後實查）

查法都是唯讀：讀 `~/aos-home/ws/.stack/procs_state.json`、各 proc 的 stack 資料夾、定義資料夾，`ps` 與 `/proc/<pid>/cmdline`、`/proc/<pid>/environ` 看正在跑的那隻 claude。

- 那棵樹的 daemon 表（`~/aos-home/ws/.stack/procs_state.json`）上有六隻：`_sweeper`、`eca_main`（opus）、`ops-agent`、`me-agent`、`gpt-price`（codex 身）、`repo-aos`，全部 `running`。
- `repo-aos` 那一列：定義 `~/aos-home/ws/defs/agent`（跟 `me-agent` 共用同一份定義）、工作區 `~/repo/aos`、stack `~/aos-home/ws/.stack/procs/repo-aos`、`auto_restart: true`。
- 正在跑的 claude（畫面那條路，tmux 裡）：`--model fable`、`--tools default`、`--permission-mode dontAsk`、`--strict-mcp-config`、`--mcp-config` 指 stack 裡的 `claude/mcp.json`（一台 `aos`，`aos-mcp --ws ~/repo/aos --stack …/procs/repo-aos`）、`--append-system-prompt-file ~/aos-home/ws/defs/agent/system.txt`、`--settings` 帶 aos 自己的畫面 hook、`--resume <對話 id>`；cwd 是 `~/repo/aos`。環境變數有 `AOS_DAEMON`、`AOS_STACK`、`AOS_WS`、`AOS_HOME=~/aos-home`。
- 它的 `history.jsonl` 第一則是 `eca_main` 寄進 queue 的自我介紹（角色是 user），不是人打的。
- `eca_main` 自己的筆記（`~/aos-home/ws/notes/agents.md`）寫：它是「使用者處理公司工作的中心」，`repo-aos` 的用途是「使用者拿它來繼續改進 aos」，它打算把手上的 aos 問題「之後可以交給它」。

## 第一題：Skill 放哪

### 現況事實

- repo 裡沒有 `.claude/skills/`，只有 `.claude/commands/wf-lint.md` 與 `.claude/settings.json`（`find .claude -type f`）。
- `wf-lint` 這支在今天的 session 裡已經以 skill 的樣子出現（本線隊長是 `repo-aos` 叫出來的子 agent，可用 skill 清單裡有 `wf-lint`，說明文字就是那份 command 的）；也就是說 `.claude/commands/` 的東西 CLI 自己就當 skill 用，不必搬。
- `--strict-mcp-config` 只擋 MCP，不擋 skill：帳號層的 skill 與外掛照樣載入（今天的清單裡看得到三十幾支；跟 [eca-task-subagent § 全域設定帶進來的東西](../12/eca-task-subagent.md#全域設定帶進來的東西) 實測一致）。
- `repo-aos` 的定義 `ws/defs/agent` 是跟 `me-agent`（工作區是別的專案）共用的；`~/aos-home` 與 `~/aos-home/ws` 底下都沒有 `.claude/`。

### 結論

- **講這個 repo 怎麼做事的 skill，放 repo 的 `.claude/skills/<名>/SKILL.md`**（現有的 `.claude/commands/wf-lint.md` 不搬）。理由：P-43「eca 照吃工作區設定」——skill 跟著工作區走，誰在這個工作區開工（樹裡的 eca、人直接開的 Claude Code、家機的 session）拿到的都是同一份，而且進 git、兩台機器同步。
- **不放定義資料夾**（定義是好幾隻 agent 共用的，`me-agent` 用不到 wf 的 skill）、**不放帳號層 `~/.claude/skills/`**（那會進這個 linux 帳號底下所有 claude 身的 agent，包括做公司工作的那幾隻）。
- **跨 agent 共用的 aos 知識不是 skill**，照 C-88 放共用知識庫（`~/aos-home/knowledge`），system.txt 已經指過去了。
- 昨晚擔心的「skill 兩套」不存在了：昨晚是「主 session 一套、eca 一套」，現在主 session 就是那隻 eca，只有一套。
- codex 身讀的是 `.agents/skills/`（[eca-task-subagent § codex 身](../12/eca-task-subagent.md#codex-身)）；這個 repo 現在沒有 codex 身的常駐 agent，不預先做（C-56）。

### 還缺什麼要施工

- 沒有必做的。哪些 wf 工作流要改寫成 skill，屬於「wf 往 aos 走」那條線（使用者：先玩一玩），這裡不排。
- 文件一處可補：`AGENTS.md` 第 17 行「唯一的例外是 `.claude/`」那句現在只提 slash 指令與 hook；之後真的新增第一支 `.claude/skills/` 時，在同一句補「skill 也放這裡」即可。

## 第二題：主 session 的身分（連帶 mailbox 能不能掛）

### 現況事實

- 主 session 在 daemon 表上、名字 `repo-aos`（見上面總覽）。昨晚的 `DaemonMissing` 是因為不在表上，現在這個原因沒了。
- mailbox 三支已經掛著：定義的 `tools.json` 疊了 `lib/packs/mailbox.json`；`mail_notify` hook 在跑（stack 裡有 `hooks/mail_notify/notified.json`、`on_clock.json`）。頂層自己也回報工具清單裡有 `mailbox_peek／read／send`。
- 它的信箱資料夾 `…/procs/repo-aos/mailbox/` 現在還不存在（`ls` 沒有）；照 P-48，別人用名字寄來或它自己第一次用時才建。別人回信的 `reply_to` 就是這個路徑。
- 人的信箱 `~/.aos/stack/mailbox/` 在（11-11 建的），`new/` 是空的；`$AOS_LINUX_USER_STACK` 沒設。
- **從 queue 進來的話分不出是誰說的**：`aos-agent say` 寄的信只有 `{"role": "user", "content": …}`，沒有寄件人欄；`repo-aos` 的定義是 `--on-busy answer`，人在畫面上時別的 agent 寄來的話也照樣貼進畫面。今天第一則 user 就是 `eca_main` 寄的，靠它自己在內文報名字才知道。
- 沒實測的：沒有真的寄一封信給 `repo-aos` 或叫它的 `mailbox_send`（任務邊界不准寄信）。

### 結論

- **主 session＝樹裡的 proc `repo-aos`，是一隻 agent。** 這是使用者 11-12 那句話（人開的 Claude Code 若是 eca，其他 proc 面對的就是這隻 eca proc）在今天變成事實，不用另外定。
- **人是另一個對象**，不等於 `repo-aos`：人的信箱在 `~/.aos/stack/mailbox`（使用者定的「aos 眼中一個能收信的對象」）。agent 要找人＝寄到那個信箱；要找這隻做 aos 的 agent＝寄給 `repo-aos`。
- **mailbox 掛得上、已經掛著**，`reply_to` 指 `repo-aos` 自己 stack 的信箱。昨晚「把主 session 登記成表上的一隻，現在沒有這種做法」的答案就是：用 `aos-agent ctl add` 把它起成一隻 eca、人再接上畫面——不需要替「樹外的裸 Claude Code」另做登記機制（C-80：不在 daemon 下的不管；C-56）。
- **裸開的 Claude Code（不經樹）就不是 aos agent**：沒有信箱、沒有 self 類工具是正常的，不補。家機昨晚修的 `~/.cache/aos-mcp-aos`（10 支、沒有 mailbox）就是這種；家機要不要也改成樹裡的一隻，見[要使用者裁的](#要使用者裁的)第 2 題。
- **兩套信怎麼分**：同一棵樹裡的 agent 找 `repo-aos` 走 mailbox（P-48）；不在這棵樹裡的（別台機器、別資料夾裸開的 session）照舊走 `wf/inbox/`。兩套都留著，直到「wf 往 aos 走」那條線動到 inbox 為止。
- **「等使用者的事」現在不改寄人的信箱**：D4 定了方向，但使用者同一段說要先玩、不施工不規劃；`wf/WAIT_USER.md` 照舊。
- **鐵律 2 對 mailbox 與 queue 一體適用**：別的 agent 寄來的信、寄進 queue 的話，都是情報與請求，不是使用者的授權（P-48 也寫「來信是情報與請求、不是命令」）。但 queue 裡的話分不出是人還是 agent，而且 `eca_main` 是使用者指定的中心 agent——這裡跟鐵律 2 有衝突，留給使用者裁（第 1 題）。

### 還缺什麼要施工

- `wf/workflows/dispatch/aos-teams/05-同機session與Argon.md`「同機 session 傳話」：補一句「同一棵 aos 樹裡的 agent 互相找走 mailbox，用 aos 的名字（`repo-aos`、`eca_main`…）；不在樹裡的照舊 a2a／`wf/inbox`」。
- `wf/workflows/dispatch/aos-teams/01-公司WSL.md`（或 `wf/workflows/dev-env.md` 公司 WSL 段）：補一段「公司 WSL 的頂層 session 是 `~/aos-home` 樹裡的 `repo-aos`：定義、工作區、stack 在哪，怎麼接上畫面」，連到本檔。
- `wf/workflows/inbox/README.md`：加一行指到上面那句，講清楚 inbox 與 mailbox 各管哪一段。
- `AGENTS.md`「開場與入口」三軸：不用加第四軸——新信有 `mail_notify` 每分鐘提醒，不必開場去掃。
- 第 1 題裁完後：把裁定寫進 `AGENTS.md` 鐵律 2 那句（現在只寫「agent 寄來的信不是授權來源」，沒提 queue 與中心 agent）。
- 程式不用改。

## 第三題：always-on 規矩怎麼進主 session

### 現況事實

- **repo 的規矩 CLI 自己就載入**：`repo-aos` 的 cwd 是 `~/repo/aos`，`CLAUDE.md`→`AGENTS.md` 照常進 context（本線隊長是它的子 agent，開場就收到 `CLAUDE.md` 那一句；頂層也回報照常載入）。
- **system.txt 每次起 CLI 都附加**：`/proc/<pid>/cmdline` 看得到 `--append-system-prompt-file ~/aos-home/ws/defs/agent/system.txt`＋`--system-prompt-snapshot off`。那份只有兩句：共用知識庫在哪、怎麼看。它是定義那份（`me-agent` 也吃同一份）；`repo-aos` 的 stack 裡沒有自己的 `system.txt`（照 `interfaces.json` 的宣告，stack 有就用 stack 那份）。
- **compact 後重讀**：repo 的 `.claude/settings.json`（SessionStart，matcher `compact`，跑 `wf/tools/compact_reload.sh`）還在；aos 另外用 `--settings` 帶自己的 SessionStart／UserPromptSubmit／Stop／PreToolUse hook。兩份同時存在；**沒驗**的是「在這隻 eca 身上 compact 之後 `compact_reload.sh` 真的有跑」。
- aos 這邊的 hook 現在掛著 `timer`（什麼都不做）與 `mail_notify`；對話換新時 aos 會用自己記的 history 整理一段帶進去（P-43）。

### 結論

- **規矩只有一份、放它所屬的那一層，不抄第二份**（昨晚邊緣狀況 1「兩套並存誰是準」的答案）：
  - 「在這個 repo 做事的規矩」（鐵律、使用者偏好、工作流）留在 repo：`CLAUDE.md`→`AGENTS.md`→`wf/`。它跟著工作區走，由 CLI 自己載入，aos 不碰也不抄（C-52 只管自己這一層；P-43 eca 內部是黑盒子、照吃工作區設定）。
  - 「這隻 agent 在這棵樹裡該知道的」（知識庫在哪）放 `system.txt`。**不把 wf 規矩寫進 system.txt 或共用知識庫。**
  - compact 後重讀沿用 repo 的 `.claude/settings.json`，不另做 aos 版（aos 的 hook 事件本來就沒有 compact）。
- 所以「always-on 怎麼進主 session」在主 session 是 claude 身 eca 的前提下**已經進了，不用新機制**；這也符合使用者 D3「之後玩一玩自然會想到，反正有 hook」——現在不預先設計。
- 之後若有「只給 `repo-aos`、不給同定義其他 agent」的常駐提醒，放它 stack 那份 system（`aos-agent system`／`self_system`），不改共用定義。現在沒有這種內容，不做。
- agent-fsm 身不讀 `CLAUDE.md`、codex 身讀的是 `AGENTS.md`：這個 repo 目前沒有這兩種身的常駐 agent，不處理。

### 還缺什麼要施工

- 沒有必做的程式或設定。
- 要補驗一次（頂層自己下次 compact 時順手看）：compact 後有沒有印出 `compact_reload.sh` 的內容；沒有的話再查兩份 SessionStart 是不是互蓋，那時才是施工題（落點 `proto8/lib/agent/cli_session.py` 組 `--settings` 的地方）。
- `wf/workflows/common/user/02-交接與收工.md`「compact 前先寫交接」：補一句「頂層是 eca 時照舊；aos 那邊 `/compact` 後 history 會換成摘要」，等上面那次補驗有結果再寫。

## 第四題：`todo` 歸誰

### 現況事實

- `todo` 工具在 `proto8/lib/packs/todo.json`、本體 `lib/agent/todo/`；清單存在叫它的那隻 agent 自己 stack 的小格（`<stack>/tools/todo/todo.json`，第一次寫才建）——讀 `lib/agent/todo/_entry` 檔頭確認。
- `repo-aos` 的定義沒掛 `todo`（`tools.json` 七包：gadgets、events、self、def、mailbox、json、index）（11-13 下午註：七包是樹裡 `ws/defs/agent` 這份定義的實況——它是今早 08:24 從當時的範本抄的；repo 的 `templates/eca-claude/tools.json` 同一天 `2e1e69de2` 加了 `jsonx`、現在八包，樹裡的定義與 `~/aos-home/templates` 的複本都還是七包，定義不會自己跟著範本變）；`--tools default`＝CLI 自己的工具全開（CLI 自帶的待辦工具有沒有真的出現在頂層的清單裡，本線看不到頂層的工具表，沒查）。
- 昨晚的顧慮是「經 `~/.cache/aos-mcp-aos` 用時，這台機器所有主 session 共用一張、會互蓋」；公司 WSL 沒有那個 cache 夾（[aos-home](aos-home.md)），主 session 也不走那條路了。

### 結論

- **`todo` 歸每隻 proc 自己**（C-91：清單放自己小格、各自獨立）。主 session 現在有自己的 stack，要掛的話那張清單就只屬於 `repo-aos`，昨晚「共用一張互蓋」的問題在樹裡不存在。
- **但不掛**：主 session 是 eca，照使用者 11-11「eca基本都有goal，所以goal不用給eca。todo也不用。」與 P-43「CLI 自己就有、而且更順手的不給」，手上的小步驟用 CLI 自己的待辦。
- **跨 session 還沒做完的事不是 todo**，照舊記 `wf/SESSION-LOG.md`（進 git、兩台機器看得到）；todo 只是一段對話裡的小抄。
- 哪天真的要用 aos 的 `todo`：`repo-aos` 自己 `self_tools` 加到自己 stack 的覆蓋層即可，不動共用定義、隨時可拿掉。

### 還缺什麼要施工

- 沒有。

## 交給頂層的施工清單（彙總，都沒動手）

| 檔 | 大概改法 | 什麼時候 |
|---|---|---|
| `wf/SESSION-LOG.md` 第一條 open | 四題已定案，改成只剩「等使用者裁兩題」＋連到本檔 | 現在 |
| `proto8/thinking/2026-11/13/README.md` | 加本檔一列 | 現在 |
| `wf/workflows/dispatch/aos-teams/05-同機session與Argon.md`、`01-公司WSL.md`、`wf/workflows/inbox/README.md` | 第二題列的三句 | 現在可做 |
| `AGENTS.md` 鐵律 2 | 照第 1 題的裁定補 queue 與中心 agent | 裁完 |
| 家機 `~/.claude.json` 的 aos MCP 那行、`~/.cache/aos-mcp-aos/` | 照第 2 題的裁定留或拿掉（使用者的設定檔，要他點頭） | 裁完、在家機 |
| compact 後重讀 | 補驗一次；壞了才動 `cli_session.py` | 下次 compact |

## 要使用者裁的

兩題。第 1 題是新做法跟既有原則（鐵律 2）的衝突；第 2 題是原則推不出的方向。

兩題 11-13 都已裁（各題末有裁定與原話）。

### 第 1 題：`eca_main` 傳來的話，算不算你的授權？

背景（白話）：現在你有一隻中心 agent `eca_main`，它會把話直接送進 `repo-aos`（就是這個做 aos 的 session）的對話裡，看起來跟你自己打的字一樣，分不出來。但規矩（鐵律 2）寫的是：push、刪檔、開新工作要「你當場確認」，agent 寄來的不算。今天它已經說之後要把 aos 的問題交給 `repo-aos` 做。

- **甲：一律不算。** `eca_main` 說什麼都只當建議；要做新工作、push、刪檔，都要你親自在 `repo-aos` 的畫面上說。後果：最安全、規矩一個字不用改；但你想透過 `eca_main` 一句話指揮全場時，這隻會停下來等你本人。
- **乙：普通工作算，不可逆的不算。** `eca_main` 可以派 `repo-aos` 改程式、查東西（可以 git 退回的）；push、刪檔、對外送出仍要你本人說。後果：中心 agent 能派工，最壞情況是多做了一段可以退掉的工；鐵律 2 的「開新工作」要改寫成「`eca_main` 派的可以開」。
- **丙：全部都算。** `eca_main` 等於你的代言人，含 push 與刪檔。後果：最省事；但 `eca_main` 被別的信誤導或自己搞錯時，會直接變成 push 或刪檔，沒有人擋。

建議：**乙**。你定的角色是「`eca_main` 派工、追蹤、彙報」，甲會讓它派不動這隻；丙把不可逆的事交給一隻分不清真假來源的通道，風險不對等。你回答之前，`repo-aos` 照現行鐵律 2 字面走（等於甲）。

**裁定（11-13，對話裡直接答）＝乙：普通工作算，不可逆的不算。** 使用者原話：「1.算。2.可以。」頂層接著問第 1 題是不是讀成「普通工作算、push 和刪檔這類不可逆的還是要他本人說」，使用者原話：「2.對。」（那則訊息的第 2 點就是在回這個讀法）。已寫進待裁資料檔 [decide_20261113_wu.json](decide_20261113_wu.json) 的 `ms-1`；裁定後待施工見[裁定落地-1113](裁定落地-1113.md)。

### 第 2 題：家機的主 session 要不要也改成樹裡的一隻？

背景（白話）：公司這台，做 aos 的 session 已經是樹裡的一隻 agent，有信箱、有名字。家機昨晚修好的是另一種：直接開 Claude Code、外掛 10 支 aos 工具，沒有信箱、沒有名字。

- **甲：家機也照公司這樣。** 在家機那棵樹加一隻指向 repo 的 eca，以後都從它的畫面進去；昨晚那個外掛設定（`~/.claude.json` 的 aos 那行）拿掉。後果：兩台一樣、只有一種做法；要你在家機花幾分鐘照手冊加一隻（或回家後叫頂層做）。
- **乙：家機維持直接開。** 後果：不用動；但家機的 session 收不到其他 agent 的信，兩台的 wf 規矩要一直寫「有信箱時…沒信箱時…」兩種情況。
- **丙：兩種都留，看當天心情。** 後果：最自由；文件與規矩要兩種都顧，昨晚「todo 共用一張」那類問題在直接開的那種仍然存在。

建議：**甲**。一種做法最簡單（KISS），昨晚剩的問題全是「不在樹裡」造成的。

**裁定（11-13，對話裡直接答）＝甲：家機也照公司這樣。** 使用者原話：「1.算。2.可以。」（第 2 點回這題；「可以」對到甲是頂層的讀法）。已寫進待裁資料檔的 `ms-2`；在家機才做得了，見[裁定落地-1113](裁定落地-1113.md)。

## 順帶看到的（只記一行，不展開）

- `repo-aos` 用的指令（`~/.local/bin/aos-*`）與畫面 hook 直接指向 `~/repo/aos/proto8` 的原始碼，而它的工作就是改這份原始碼：改壞一支 Python 會立刻影響整棵正在跑公司工作的樹（頂層已知，今天的任務書有寫「每次存檔都要是能跑的完整狀態」）；`AOS_HOME` 那邊的 `lib/` 則是 `~/aos-home/lib` 的複本，repo 改了不會自動跟上。
- `ws/defs/agent` 是 `repo-aos` 與 `me-agent` 共用的定義，`eca_main` 的筆記也寫「改它會影響所有用它的 agent」。
- `aos-agent say` 的信沒有寄件人欄，收的那隻只能靠對方在內文自報名字（第 1 題的根源）。
- `gpt-price`（codex 身）底下同時有五隻 `aos-mcp` 行程在跑，其他幾隻 claude 身都只有一兩隻；沒查原因。
- `wf/SESSION-LOG.md`「試驗場」那行與 [aos-home](aos-home.md) 還寫「驗完樹停著」「一隻 opus `eca_main`」，現況是樹開著、六隻。
