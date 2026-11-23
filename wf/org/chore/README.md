打雜工（agent-fsm 身、gpt 腦）的角色卡，寫給要掛它的人看：能派什麼、不能派什麼、怎麼掛怎麼收（提案：fable 規劃，11-23，等使用者定；打雜工自己不讀這張卡）。

# 打雜工 `chore`

← [org](../README.md)｜配給包 [kits](../../workflows/dispatch/kits/README.md)｜掛法 [kits/card](../../workflows/dispatch/kits/card.md)｜心得 [sol-crew](../../public/sol-crew.md)

使用者 11-23：「fsm gpt則會是打雜工」「蒐集算打雜，但施工這塊，如果是重要的部分，那確實還是得用claude」「尤其是寫程式」。

用到才掛、做完就收；不佔位子，沒有地盤與筆記。

**現況：還沒有。** 公司 WSL 11-23 沒掛過，要先過四關：

1. 真模型端點要通（progress `company-wsl-1123-verify`：4000 埠沒在聽、真模型沒驗過）。
2. 端點包的名字要對上（progress `sol-high-pack`：配給包寫 `sol-high`，llm kernel 範本是 `sol` 加 reasoning_effort）。
3. 配給包 `.env` 的 `AOS_LLM_KERNEL` 要改指這台的 llm kernel（[aos-teams/07](../../workflows/dispatch/aos-teams/07-預設流程與agent-fsm.md)「sol 走 agent-fsm」）。
4. 掛的人要有 `subagent`、`agent_def` 兩支工具；`eca-aos` 現在沒有（[它的筆記](../../ws/eca-aos/notes.md)列的工具包裡沒有這兩包）。

## 職責

- **可以派**
  - **蒐集事實**（使用者 11-23「蒐集算打雜」；配給包的蒐集員）：查找、盤點、讀檔整理，每條附出處；不設計、不建議、不改它看的東西。
  - **逐條核對**（配給包的審稿員）：拿任務書或圖紙一條一條對，只指出、不修。
  - **不必判斷的雜活**（照對照表改名、整理格式）：現在沒有現成的包（kits 只做了「看」包），要派得先配包。
- **不能派**
  - **重要的施工，尤其是寫程式**（使用者 11-23）：用 Claude。
  - 設計、架構、判斷對錯（使用者 11-07「gpt 系不做設計決策」，長期，見 [aos-teams](../../workflows/dispatch/aos-teams.md)「誰做什麼」）。
  - 改寫使用者的概念／規範條文（[user.md](../../workflows/common/user.md)：不算簡單工作）。
  - 交件、push、刪檔、問使用者、往下再掛人：題目與產物都交給掛它的人。
  - 要跑指令才知道的事：「看」包沒有 shell，掛的人自己跑好，把輸出給它。
- **還沒定**：不重要的施工歸誰、「重要」怎麼分，使用者沒說。定之前的保守做法（提案）：寫程式不派；只派上面「可以派」那三種。
- **Done when**：`out/answer.md` 或 `out/review.md` 交出來，掛的人逐條對過證據。

## 讀寫範圍

約定，沒有強制力（[org「寫入範圍只是約定」](../README.md)）。

- **可以讀**：任務書點名的路徑、知識庫。
- **可以寫**：只有自己的工作區。這條只靠配給包的 system 文字，沒有 hook 擋（kits「已知限制」）；包裡關掉了改自己的工具，但那仍不是牆。
- **工作區放哪（沒定、沒試過）**：aos-teams 第 3 件寫「`ws` 從你的工作區算，落在 `<線夾>/<agent 名>`」，那是線各有一個線夾時的寫法；11-22 起 eca 的工作區是 repo 根。提案：放掛的人地盤的 `temp/<agent 名>/`（不進 git），要留的結果由掛的人搬出來。
- 活樹、git、刪檔的禁令在配給包的站台層 `site.txt`。

## 交接

| 誰 | 給它什麼 | 它交回什麼 | 之後 |
|---|---|---|---|
| 掛它的人（負責人或任何位子） | 一張單只做一件事：唯一目標、可讀可寫的路徑、交付物、完成條件 | `out/answer.md`、`out/review.md`，或全文放在最後一則回答 | 掛的人逐條對證據、不重跑；要進 repo 的由掛的人整理後交件；`subagent rm` |

- **誰掛誰驗收、誰負責**：它的結果不直接給使用者，也不直接給別的位子。
- 等它不要卡在同一回合（[aos-teams](../../workflows/dispatch/aos-teams.md)第 4 件）。
- 額度用光它不會來信（「看」包沒掛 `brain_notify`），掛的人自己看。
- 任務書不用附必讀清單：配給包只讓它讀知識庫入口加站台層。

## 模型

- **腦**：gpt 的 sol（包名見上面第 2 關）；不用 terra、不走 codex（使用者 11-14）。
- **同時幾隻**：一張單一隻，用到才掛；上限是掛的人的 `max_subagents`（預設 4）。名字 `<掛的人>-sol-<編號>`（aos-teams「命名」）。
- **掛不起來時**：蒐集與雜活由 Claude 子 agent 補位（簡單工作 sonnet，user.md）。
