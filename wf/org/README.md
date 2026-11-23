工作室的分工入口：eca-aos 這邊有哪些位子、每個位子管什麼、一件事從使用者進來到交件怎麼走、東西放哪裡（使用者 11-23 照推薦答了七題；沒問到的仍標〔提案〕）。

# wf/org：工作室的分工（誰負責什麼、做完交給誰）

← [AGENTS.md](../../AGENTS.md)｜[WORKFLOWS](../WORKFLOWS.md)｜隊形短卡 [aos-teams](../workflows/dispatch/aos-teams.md)｜地盤 [wf/ws](../ws/README.md)

`wf/workflows/` 講「一類事怎麼做」，`wf/ws/` 放每個 agent 自己的東西，這裡只講**這件事歸誰、做完交給誰**。鐵律、使用者偏好、交件、活樹硬規則、地盤規矩都在原檔，這裡不重抄。

**何時用**：要決定一件事派給誰、要開或收一個位子、要掛打雜工、要改交接方式。
**何時不用**：指令怎麼下 → aos-teams；選哪級模型 → [team-model](../workflows/team-model.md)；某類事的做法 → WORKFLOWS。

## 哪些是使用者說的

使用者 11-23 對 eca-aos（逐字；「他那邊」＝他的另一個專案 `/mnt/c/code/mine/arena_cheater`，一隻 eca 加五個 agent-fsm 部門）：

> 他那邊是我的試驗田。那邊現有的aos體系感覺不錯，你這邊也學他吧，在wf/開一個org，但是你這邊我預期會是小型工作室，所以主力會是eca claude，人手精簡，fsm gpt則會是打雜工。

> 然後你也可以開claude subagent fable，去規劃你這邊自己的團隊組織架構

> 蒐集算打雜，但施工這塊，如果是重要的部分，那確實還是得用claude

> 尤其是寫程式

eca-aos 拿 fable 的第一版問了七題，使用者 11-23 答（逐字）：

> 都按照推薦。但py/cpp可以開了，這是aos本體程式庫，是重要對象。舊文件可以更新了。公司體制這塊放著，我就是拿來看看，當參考。

| 題 | 選了什麼 |
|---|---|
| 1 位子常駐還是有活才掛 | 有活才掛；小件派 Claude 子 agent 代班 |
| 2 `aos-eca-frontend` | 定成 `proto8/frontend/` 的位子，前端大修開工才掛 |
| 3 `py`、`cpp` 開不開位子 | **開**（推薦原本是不開，使用者改了） |
| 4 不重要的施工歸誰 | 寫程式一律 Claude；不必判斷的機械式施工可以給 fsm gpt |
| 5 蒐集與雜活先給誰 | 先給 fsm gpt，掛不起來由 sonnet 的 Claude 子 agent 補位 |
| 6 沒有部長，commit 誰放行 | 位子在自己範圍內先交後報；跨範圍、`--rm`、`install.py`、動活樹的先問 eca-aos |
| 7 eca-aos 能不能親手做小件 | 只做活狀態、抄使用者的話進規矩、寫 `wf/org`；其餘照派 |

註「第 N 題」的就是這張表。**標〔提案〕的是 fable 11-23 規劃、七題沒問到的**，不是定案。舊文件（aos-teams、team-model、規矩卡）對不上的地方，使用者說「舊文件可以更新了」，還沒跟上的另外改。

## 工作室的樣子

- **人少、位子固定**：一位負責人加少數專職位子，全是 eca claude。不設部長（第 6 題），不照生產線分部門。
- **位子不等於一直開著的行程**（第 1 題）：位子＝一張角色卡（本夾）加一格地盤與筆記（`wf/ws/`）。有活才掛；沒掛時由負責人派 Claude 子 agent 代班，先讀角色卡與 `notes.md`、收工前把學到的寫回去；代班沒有對話記憶，全靠筆記。
- **eca 自己開的 Claude 子 agent 是它的手，不算成員**〔提案〕：誰開的誰負責、誰驗收；模型照 [user.md「子 agent 模型」](../workflows/common/user.md)。
- **fsm gpt 只打雜**：用到才掛、做完就收，不佔位子、沒有地盤。
- **沒有位子的工作**（條文、wf 整理、環境）由負責人按件派（第 7 題）。

## 成員表

現況是公司 WSL 11-23 的樣子（出處：[eca-aos 筆記](../ws/eca-aos/notes.md)）；家機那棵樹現在掛著誰沒查。

| 位子 | 誰 | 一句話 | 現況 |
|---|---|---|---|
| 負責人 [lead](lead/README.md) | `eca-aos` | 使用者的窗口；派工、驗收、管交件與活狀態 | 掛著 |
| 知識庫 [kb](kb/README.md) | `eca-aos-kb` | 專管 `proto8/knowledge/` | 掛著、睡著（11-23 下午掛，做完兩件後 sleep；`subagent wake` 叫醒） |
| 範本 [templates](templates/README.md) | `eca-aos-templates` | 專改 `proto8/templates/` 的定義 | 掛著、睡著（同上） |
| 核心程式 [core](core/README.md) | `eca-aos-core` | 專管 `proto8/py/`、`proto8/cpp/`（第 3 題） | 掛著、睡著（同上）；11-23 新開 |
| 前端 [frontend](frontend/README.md) | `aos-eca-frontend` | 專管 `proto8/frontend/`（第 2 題） | 沒掛，前端大修開工才掛 |
| 打雜工 [chore](chore/README.md) | 用到才掛 | 蒐集、核對、機械式施工 | 還沒有：真模型端點沒驗 |

除了打雜工（agent-fsm＋gpt）全是 eca claude，地盤在 `wf/ws/eca-aos/<名>/`。「位子」「負責人」「代班」這些叫法跟著七題的題目用，使用者照推薦答了，算接受（eca-aos 的判斷）。`eca-aos-core` 這個名字是 eca-aos 取的；`aos-eca-frontend` 要不要改名使用者沒定。

**不開的位子**〔提案〕：設計、審查、測試、整合不開（驗收是派工的人的事，要第二雙眼睛就按件派一隻；交件口是 commit-request 的排隊）。開位子的條件與做法見 [places](places.md#開位子)。

## 標準流程

```
使用者 → eca-aos（聽懂、先講打算）
   ├─ 落在某個位子的範圍 → 那個位子（掛著：寄信；沒掛：派代班）
   ├─ 不屬於任何位子     → 按件派 Claude 子 agent（要規劃的派 fable）
   └─ 過程裡的蒐集與雜活 → 先給打雜工，掛不起來由 sonnet 子 agent 補位
→ 做的人自己驗 → 交件（commit-request）→ 回 eca-aos 終局狀態
→ eca-aos 逐條對證據 → 回報使用者
```

- **沒有部長**：別處寫「寄部長」「部長放行」的，在這裡都是 eca-aos。
- **誰交件**（第 6 題）：照任務書。沒寫就是：掛著的位子（含代班）在自己的範圍內先交後報、回報附雜湊；Claude 子 agent 與打雜工不交，產物給派它的人。跨出範圍、帶 `--rm`、要跑 `install.py`、會動到活樹的先問 eca-aos；push、刪檔照鐵律 2。
- **eca-aos 親手做的**（第 7 題）：活狀態（progress、HANDOFF、筆記）、抄使用者的話進規矩、`wf/org`；其餘照派，要查的也派一隻唯讀的。
- **小事怎麼跳**：照 [WORKFLOWS「可以跳流程」](../WORKFLOWS.md)。位子範圍內一兩句的修正，直接給那個位子或代班，不寫正式任務書，照樣回終局狀態〔提案〕。
- **位子之間可以直接寄信**請對方做它範圍內的事〔提案〕（先例：規矩卡「回報怎麼寫」第 4 條）；接的人照樣回終局狀態，給 eca-aos 的回報裡提一句。
- **方向題**：誰碰到都回 `NEEDS-USER` 給 eca-aos，由它問使用者；沒有人替他選（鐵律 5）。
- **要規劃的大事**：照 [aos-teams「要規劃就走正統流程」](../workflows/dispatch/aos-teams.md)；需求不清先發想。

## 打雜工能做與不能做

- **能做**：蒐集（使用者 11-23「蒐集算打雜」；第 5 題先給它）、照任務書逐條核對、照對照表改名、搬檔、套格式這類不必判斷的機械式施工（第 4 題）。
- **不能做**：寫程式（第 4 題一律 Claude）與其他要判斷的施工；設計與架構判斷（使用者 11-07，長期）；交件、問使用者。細節與掛法在[角色卡](chore/README.md)。

## 東西放哪裡、能寫哪裡

問答表、寫入範圍、定義怎麼寫、怎麼開位子 → [places](places.md)。一句話版：位子的東西放它的地盤，暫存放地盤的 `temp/`，`wf/org/` 只放入口與角色卡；寫入範圍是**約定、沒有強制力**。

## 交接與信件

信的格式與終局狀態 → [inbox.json](../workflows/inbox.json) 的 `local/letter_format`；回報 → [規矩卡](../workflows/common/rules-card.md)；任務書 → [派線與任務書](../public/派線與任務書.md)；派子 agent → [claude子agent](../public/claude子agent.md)。工作室多要求的兩件（任務書寫明範圍、回信要短）〔提案〕在 [places](places.md#任務書與回信)。

## Done when

- 新位子有 `wf/org/<位子>/README.md`，四段都填：職責、讀寫範圍、交接、模型；成員表加一列。
- 職責或現況變了，成員表與角色卡一起改。

## 交接

- 11-22「公司體制」七題（[入口](../../proto8/thinking/2026-11/22/公司體制-1122/README.md)）：使用者 11-23「公司體制這塊放著，我就是拿來看看，當參考。」不答、不追；本夾不照它改。
