← [入口](../2026-10-30-eca.md)｜涵蓋：A. 兩塊比較：aos agent vs 外部 coding agent、各題結論（每條標照哪條原則／決定）｜上一份 [01-前提](01-前提.md)｜下一份 [03-各題結論](03-各題結論.md)

## A. 兩塊比較：aos agent vs 外部 coding agent

把「射後有理」拆成七件事，兩邊各自現在是怎麼做（或做不到）的對照。「外部 agent」拿 claude code 當代表（codex 同形、pi 的 rpc 模式更順，見 hub-adapter 適配表）。

| 事 | aos agent（已做，P-42） | 外部 coding agent（黑盒子） | 共同點 → 通用介面怎麼對上 |
|---|---|---|---|
| **跑起來** | `aos-exec --ws WS <定義>`；`_entry` 是 aos-loop、每次叫 round | `claude -p`（一答就退）或互動式 `claude`（停著）；都是別人的程式、旗標在它那邊 | 都是「一個資料夾程式跑在一個工作區」。外部 agent 要能 `aos-exec`，就得有一個**定義資料夾**包著它（下面 B） |
| **輸入（塞 prompt）** | `$AOS_STACK/queue/`（N-16 有序投遞），agent 自己的 queue 格認領、接進 history | 非互動：只有啟動那一句（stdin／argv）；要「再說一句」只能再跑一次 `claude -p --resume <id>`。互動式：往畫面打字（tmux paste）。跑到一半不能插（pi rpc 的 `steer` 例外） | 兩邊都是「一則一則、有先後的訊息」。差別只在**誰去 queue 拿**：aos agent 自己拿；外部 agent 不會看資料夾，要**有人替它拿**——那個人就是 adapter（下面叫 `turn` 格）。aos-say 不用改：一律寄進 `<stack>/queue/` |
| **回答（看 reply）** | `$AOS_STACK/history.jsonl` 最新那則 assistant | 非互動：stdout（stream-json）；互動：畫面，另有 `Stop` hook 給最後一句；完整對話在它自己的 session 檔 `~/.claude/projects/<cwd 編碼>/<id>.jsonl` | 兩邊都有「只附加的對話紀錄」。aos 這邊**一律看 history**：外部 agent 的回答由 adapter 抄一則進 history（user 那則認領時抄、assistant 那則答完抄）；它自己的 session 檔用 symlink 掛在小格（決定 35、agent-lifecycle C-15～17）。aos-listen 不用改 |
| **一輪的邊界** | round：認領一則 → 問腦 → 跑工具 → 交卷；格與格之間有 trace | 一輪＝「一句進去、到它不再叫工具、吐出最後一句」（使用者 10-27 筆記）；中間它自己跑工具，外面看不到格 | 兩邊都有「一輪」。aos agent 的一輪拆得開（格），外部 agent 的一輪是一整塊——這是決定 12 說的差別，也是「暫停」粒度不同的根 |
| **停著等** | aos-loop 提供：`ROUND_ON_EMPTY=idle`＋`interval_ms`，queue 空就退 0 等下一次 | `claude -p` 自己不會等（退了）；互動式 `claude` 會等，但等的是鍵盤、不是 queue | 「停著等 queue」兩邊都**不是腦本身的事**：aos agent 交給 aos-loop；外部 agent 的 adapter 也交給 aos-loop（一次＝替它答一則），不自己寫循環（agent-bob 的教訓、agent-lifecycle 衝突 6） |
| **暫停／停** | 寫 `$AOS_STACK/ctl.json` 的 `paused`／`stopped`（N-07），停在輪與輪之間；fsm agent 還能停在格與格之間 | 沒有暫停這回事；只能不給它下一句（互動式畫面開著也一樣）。「停」＝殺行程、關畫面；對話靠 `--resume` 接回 | **`paused` 對外部 agent＝不餵下一則**（新信留在 `queue/new/`、手上那則答完）；**`stopped`＝這則答完 loop 收工**，畫面另外用 hub 的 `close`／`stop` 管。粒度只到「一則訊息」，停不進它的工具呼叫中間——這是黑盒子的天然差異，不補 |
| **誰在管生命週期** | 直接 aos-exec＝Linux 管；掛 daemon＝`loops`／`execs`（N-28 10-30 補） | 同左（決定 34）；多出來的只有**畫面**（tmux、Ctrl-]、信任提問）和**它自己的 session 檔** | 生命週期兩邊**同一套**（aos-exec、aos-daemon、aos-daemon-ctl）。外部 agent 多的那兩樣（畫面、session 檔）就是 aos-eca-hub 要做的全部（下面 C） |

**一句話結論**：兩塊的共同點是「有序的訊息進、只附加的紀錄出、一輪一輪、輪與輪之間才停得下來」——這正好就是 P-42 的三樣（queue、history、ctl／state）。差別只有一個：aos agent 自己去 queue 拿、自己寫 history；外部 agent 不會，**要一個 adapter 替它做，而這個 adapter 跑在 aos-loop 底下就跟一隻 aos agent 一模一樣**。所以通用介面不用新發明：aos-say／listen 照 P-42 一行不改；外部 agent 的 queue 由 adapter 收、history 由 adapter 寫、`paused` 由包著 adapter 的 aos-loop 認。

## 各題結論（每條標照哪條原則／決定）
