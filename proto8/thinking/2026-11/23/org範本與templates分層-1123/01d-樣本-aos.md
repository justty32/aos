樣本四：這個 repo 自己的 `wf/org`（小型工作室，使用者 11-23 定的），一位負責人加四個有活才掛的位子與用到才掛的打雜工。

# 樣本四：aos 這個 repo（小型工作室）

← [入口](README.md)｜[總結與對照](01-四個樣本的總結.md)

## 規模與身體

- **一位負責人加四個位子**：負責人 `eca-aos`、知識庫 `eca-aos-kb`、範本 `eca-aos-templates`、核心程式 `eca-aos-core`、前端 `aos-eca-frontend`（沒掛）；另有打雜工，用到才掛（[wf/org/README.md](../../../../../wf/org/README.md)「成員表」）。
- **主力是 eca claude，打雜工是 agent-fsm 加 gpt**。使用者 11-23（同檔「哪些是使用者說的」，逐字）：「你這邊我預期會是小型工作室，所以主力會是eca claude，人手精簡，fsm gpt則會是打雜工。」
- **位子不等於一直開著的行程**：位子＝一張角色卡加一格地盤與筆記；有活才掛，沒掛時由負責人派 Claude 子 agent 代班，代班先讀角色卡與筆記、收工前把學到的寫回去（七題第 1 題）。
- eca 自己開的 Claude 子 agent 是它的手，不算成員〔提案〕。

## 怎麼切

**照寫入範圍切，不照生產線切**：一個位子管 `proto8/` 底下一個夾（`knowledge/`、`templates/`、`py/` 加 `cpp/`、`frontend/`）。設計、審查、測試、整合都不開位子〔提案〕：驗收是派工的人的事，交件口是 commit-request 的排隊。開位子的條件〔提案〕：有固定的寫入範圍，而且有要跨件留下來的規矩（[wf/org/places.md](../../../../../wf/org/places.md)「開位子」）。

沒有部長（七題第 6 題）：位子在自己範圍內先交後報；跨範圍、`--rm`、`install.py`、動活樹的先問負責人。

## 角色卡

`wf/org/<位子>/README.md`，4～7 KB，四段跟 arena 一樣（職責、讀寫範圍、交接、模型），多三樣：

- 卡頭一段「現況」（掛著沒有、上次做了什麼）。
- 每條註明出處：使用者第幾題定的，還是〔提案〕。
- 「規矩的正本在筆記／原檔，這裡不重抄」（例：[wf/org/kb/README.md](../../../../../wf/org/kb/README.md)）。

打雜工那張卡是**寫給掛它的人看的**，打雜工自己不讀（[wf/org/chore/README.md](../../../../../wf/org/chore/README.md)）。

## 信件與交接

- 信的格式、回報、任務書都在原檔（`wf/workflows/inbox.json`、規矩卡、`wf/public/派線與任務書.md`），org 不重抄；只多要求兩件〔提案〕：任務書寫明範圍與並行的人、回信要短（[places.md](../../../../../wf/org/places.md)「任務書與回信」，註明學自 arena 第一輪回顧）。
- 位子之間可以直接寄信請對方做它範圍內的事〔提案〕。
- 方向題誰碰到都回 `NEEDS-USER` 給負責人。

## 定義、地盤、資產

- **位子直接用出廠範本**：這棵樹的表上，`eca-aos` 與三個位子的定義都是 `$AOS_HOME/templates/eca-claude`（我 11-23 唯讀看了 `.stack/procs_state.json` 裡的定義路徑）。「定義指向角色卡」是〔提案〕，「這種定義現在一份都還沒做」（places.md）。
- **地盤** `wf/ws/<上層>/<名>/`：筆記 `notes.md`、提案、草稿、自己做的定義夾；進 git。任何一層的 `temp/` 不進 git（[wf/ws/README.md](../../../../../wf/ws/README.md)）。stack 裡記 `notes_path`，compact 之後先讀筆記。
- **資產**：`wf/org/` 不另開資產夾，位子的長期產出放它的地盤（places.md）。
- **改進紀錄**：沒有 `improvements.md`；學到的寫進位子的 `notes.md`，坑與做法投 `wf/public`。
- **打雜工的配給包** [wf/workflows/dispatch/kits](../../../../../wf/workflows/dispatch/kits/README.md)：system 文字分四層（通用、站台、角色、任務），通用與角色層以產品版 `proto8/templates/kits/` 為準、要一字不差；站台層（向誰回報、本地規矩）只留在 wf。掛法在 `card.md`。

## 踩到的坑

出處：[wf/org/chore/README.md](../../../../../wf/org/chore/README.md)、places.md。

1. **打雜工卡了四關才掛起來**：真模型端點、端點包的名字、`AOS_LLM_KERNEL` 從哪來、掛的人要有 `subagent` 與 `agent_def` 兩支工具。
2. 一張小蒐集單約 10 分鐘，比 sonnet 的 Claude 子 agent 慢。
3. 它佔掛的人一個 `max_subagents` 名額，位子睡著也佔，四格滿了要先 `rm` 一隻。
4. 任務書要寫知識庫的絕對路徑。
5. **寫入範圍沒有強制力**：全部 agent 同一個 Linux 帳號，commit-request 不查誰交了誰的檔。
6. 舊文件還寫著「部長」，要另外改（當天改了 24 處）。
