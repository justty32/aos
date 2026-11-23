`proto8/templates/` 要不要分成 `agents`／`kernels`／`orgs`：現有每一夾歸哪一類、三個選項各自的好處與代價、規劃員的推薦（推薦只是建議，由使用者定）。

# 03 templates 要不要分成 agents／kernels／orgs

← [入口](README.md)｜數字的出處：[03a 搬動代價的盤點](03a-搬動代價的盤點.md)

使用者 11-23（逐字，出處 [eca-aos 筆記](../../../../../wf/ws/eca-aos/notes.md)「2026-11-23 16:10」）：

> template這邊你看看，是不是考慮把它分成templates/agents, templates/kernels, templates/orgs

## 結論

1. **`orgs` 該開**：org 範本是一夾文件，跟 agent 範本擺同一層會混；開一個類別夾放它，什麼都不會斷。
2. **`kernels` 其實已經有了**，叫 `templates/kernel/`（單數；11-17 從 proto8 頂層併進來，裡面五個 kernel 範本加自己的 `docs/`、`tests/`）。差的只是名字。
3. **`agents` 最貴**：`agent-fsm`、`eca-claude` 的路徑是執行期的位址（03a 第六節）。搬了，這個 repo 這棵樹的四隻、arena_cheater 的七份定義、每一棵照 README 掛出來的樹，都要停下來改。
4. **三類收不下全部**：現有 14 個範本夾，歸得進三類的是 7 個，另外 7 個歸不進。
5. **推薦選項甲**：現在只新增 `templates/orgs/`，其餘不動。這是推薦，由使用者定（[04](04-要問使用者的題目.md) 第 1 題）。

## 現有每一夾歸哪一類

| 夾 | 是什麼 | 歸哪 |
|---|---|---|
| `agent-fsm` | aos 自己的 agent；**同時是執行期的格程式與 hook 宣告放的地方** | agents |
| `agent-python` | 用一支 `agent.py` 寫的 agent 定義骨架 | agents |
| `eca-claude`、`eca-claude-alt`、`eca-pi` | 外部 coding agent | agents |
| `reviewer` | 重用 agent-fsm 的格的一隻 agent | agents |
| `kernel/`（`daemon-kernel`、`procs-kernel`、`llm-kernel`、`llm-team`、`kernel-python`） | kernel 範本 | kernels（已經是一層） |
| （新）org 範本 | 一夾文件 | orgs |
| `daemon-root`、`daemon-sub` | daemon 的定義 | **歸不進**：不是 agent，也不是 kernel |
| `start-api`、`start-eca` | 起手範本，一包抄好一棵樹（根、kernel、agent 都有） | **歸不進**：橫跨三類 |
| `tool-python` | 一支工具的骨架（README 自己寫「不是 agent 範本」） | **歸不進** |
| `judge-llm` | 同步的裁判比對器，帶 `_tooldef.json`，是一支工具 | **歸不進** |
| `kits` | 配給包，蓋在 agent-fsm 上的系統文字加工具（README 寫「不是範本」） | **歸不進**：勉強算 agents 的附件 |
| `docs`、`tests`、`README.md`、`_index.json` | 跨範本的說明、測試、入口 | 留頂層 |

歸不進的七夾，分層之後只有兩條路：留在頂層（頂層變成三個類別夾加七個散夾），或再開幾類（例：`daemons`、`starts`、`tools`，共六類）。

## 三個選項

### 甲：只新增 `templates/orgs/`，其餘不動

- **好處**：使用者要的 org 範本馬上有地方放；org 不跟 agent 範本混；沒有東西會斷。
- **代價**：頂層還是 16 夾混著；`kernel` 是單數、`orgs` 是複數，名字不一致（要一致又不想改舊的，新夾可以叫 `org`）。
- **要動的檔**：新增範本 13 個檔、測試 1 個；改 `templates/README.md` 一段、`wf/tools/index_gen.json` 加一個路徑、`index_gen_desc.json` 加一兩個鍵；知識庫新一頁、`aos/_index.json` 一列、`kits.md` 一句。
- **活樹**：不用動。

### 乙：甲，再把 `kernel/` 改名成 `kernels/`

- **好處**：兩個類別夾的名字都照使用者說的。kernel 範本是抄的來源，樹裡的是抄本（`start-api/llm`、`cp -r … llms/def`），我沒找到執行期指回 `templates/kernel` 的地方。
- **代價**：95 行、51 個檔的字要改（`py` 12 檔、`templates` 15、`wf` 14、條文 8、知識庫 2、`proto8/README.md`），另有 14 個程式與測試檔用路徑找它，加 `test_start.py` 那張表與 `wf/tools` 的生成設定。純改名，功能上沒有好處。
- **活樹**：這棵樹最上層那張表沒有指到 `templates/kernel` 的列（我看過）；這台的 llm kernel 在 `~/aos-home/llm`，那邊與別棵都沒查。照理不用動。
- **做法**：要在同一個 commit 裡改完，中間狀態測試會紅。

### 丙：照原話三分，agent 範本搬進 `templates/agents/`

- **好處**：頂層乾淨，一眼看得出有哪幾類。
- **代價**（03a 全部）：
  - 程式六處：`agent_def new` 的找法（現在只收不帶 `/` 的名字）、`std.hooks()` 與 `std.fsm()`、`agent_spec_parts.py`、`refs_check.py`、`aos-frontend`、兩支工具的說明；改完要 `install.py`。
  - 64 個程式與測試檔用路徑找這六個範本；文字 276 行、152 個檔；範本之間互相連結的 `fsm.json`、`interfaces.json`。
  - 歸不進的七夾要另外決定（上一節）。
- **活樹與別的專案**：沒有過渡期（proto8 當成沒有舊版，不留舊名）。每一棵樹停下來，把表上指 `templates/eca-claude` 這類的列改掉或重掛；這棵樹是四列，`eca-aos` 自己也在裡面。arena_cheater 的七份定義重做。`AOS_HOME` 是抄本的機器重抄。別棵樹有幾列，沒查。
- **為什麼這麼貴**：大頭是 `agent-fsm` 這一夾身兼兩職，既是給人抄的範本，又是所有動態連結的 agent 執行時去拿程式的地方。程式自己也寫著這是暫時寄放（`py/aos/agent_spec_lib.py` 的 `Std`：「hook 組與 fsm 格今天寄在範本名底下」）。要不要先把這部分搬出 `templates/` 是另一個方向題，這裡不提案；只是照實說：那件事沒做之前，搬 `agent-fsm` 就是搬執行期的位址。

## 對照

| | 甲 | 乙 | 丙 |
|---|---|---|---|
| 要改的既有檔 | 約 6 個 | 約 60 個 | 200 個以上，含程式 |
| 要跑 `install.py` | 不用 | 不急（`py` 裡只有註解與一句說明文字） | 要 |
| 這棵活樹 | 不動 | 不動 | 停下來改四列 |
| 別的專案 | 不動 | 不動 | arena_cheater 重做七份定義；別棵樹沒查 |
| 頂層的夾 | 現有 16 個＋`orgs` | 同甲 | 3 類＋7 個散夾＋`docs`、`tests`（或 6 類） |

## 推薦與理由

**推薦甲。** 這是規劃員的建議，由使用者定。

1. **org 範本不必等分層**：兩件事可以分開，先把「去做」的那件做掉。
2. **三類裡有兩類甲就到位了**：`orgs` 新開，`kernels` 已經存在（只是叫 `kernel`）。
3. **剩下那一類換來的是資料夾好看，付出的是活樹與別的專案停工**。這四個專案現在都靠 `templates/agent-fsm`、`templates/eca-claude` 這兩個位址在跑。
4. **三類只收得下一半**，真要分乾淨得六類，那是比原話更大的一件事。

名字要不要一致（乙）是口味問題：便宜、可以跟甲一起做，也可以不做。使用者如果還是要丙，建議等一個各棵樹都能停的時段一次做完，清單在 [05](05-施工清單.md)。
