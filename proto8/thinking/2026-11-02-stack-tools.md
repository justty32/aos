# 2026-11-02 小格改 `$AOS_STACK/tools/<名>/`：使用者選 B，fable 規劃落地

← [thinking README](README.md)｜月份表 [2026-11](months/2026-11.md)｜出發點：[11-02 playground-cathy § 使用者原文第二段](2026-11-02-playground-cathy.md#使用者原文11-02-第二段逐字)（「.stack/<名稱>…這其實不太好，應該要改成.stack/tools/<名稱>…讓fable幫我去研究一下」）｜條文：[P-17、P-25](../docs/CONVENTION/02-題目stack停錯腦.md)、[P-32、P-34、P-38](../docs/CONVENTION/06-巢狀.md)、[N-50](../docs/NORMS/10-基礎設施-定義與工作區.md)、[N-28](../docs/NORMS/04-基礎設施-loop與daemon.md)、[C-54](../docs/CONCEPTS/01-設計理念.md)、[C-52／C-70](../docs/CONCEPTS/01-設計理念.md)、[C-61](../docs/CONCEPTS/05-agent.md)、[附錄1 名詞](../docs/CONCEPTS/附錄1-名詞.md)

本檔只記使用者原文（逐字）、決定、fable 照原則定的規劃（可翻案）、要使用者看的衝突與方向題（[user/03](../../wf/workflows/common/user/03-討論紀錄與規劃.md)）。**還沒動程式、沒動條文**；步驟表在下面。

## 使用者原文（11-02，逐字）

> 未來，搞不好會出現agent+kernel的變體，.stack底下會有一大堆東西。擋名字會擋不過來。所以我覺得最好還是tools/<name>更好。相比於一時方便，我覺得未來的不確定性才是更應該小心處理的

補一句（11-02，逐字）：

> .stack底下就是會有一大堆東西，這個避免不了。

## 決定（11-02，使用者）

- **選 B**：叫別的資料夾程式時給它的小格，從 `$AOS_STACK/<名>/` 改成 **`$AOS_STACK/tools/<名>/`**。選項 A（照舊＋擋名字）不採。
- 研究員原建議等 C-51「後續想法」追究完再動；使用者選**現在就走 B**（知道要改約 10 處程式、25～30 處條文）。

## 規劃（fable，照原則定的細節，可翻案）

### 這次改的理由怎麼寫（照使用者補的那句）

`tools/` **不是**為了讓 stack 頂層變整齊——使用者說了「一大堆東西避免不了」。它是為了**把兩種名字分開放**：

- **固定名**：格自己放的東西，名字是程式寫死的（`queue/`、`history.jsonl`、`compact/`、`history_archive/`、`trace.jsonl`、daemon 的 `loops_ctl.json`…）。以後 agent＋kernel 的變體一多，這種名字只會越來越多，列不完。
- **變動名**：呼叫方給的、跟著外面的設定走的名字（工具叫什麼、daemon 名單上的子項叫什麼、被問的 agent 資料夾叫什麼）。寫程式的人事先不知道會是什麼。

兩種名字放同一層，就得靠「擋名字」一條一條防撞，而固定名的清單還會一直長——擋不過來。**把變動名全收進一個固定名的資料夾底下（`tools/`）**，兩邊就各自一個命名空間，固定名怎麼長都撞不到。代價只有一個：`tools` 這一個字變成 stack 頂層的保留名（下面衝突 3）。

下面每一條連帶細節都用同一把尺量：**那個名字是誰給的？** 呼叫方給的變動名 → 收進一個複數資料夾；程式自己寫死的固定名 → 留在頂層照舊。

### 連帶細節（一行一個：定成什麼｜依據）

1. **工具的小格**＝`$AOS_STACK/tools/<名>/`。涵蓋 act（`lib/agent/act/_entry`）、aos-mcp（`extras/ai_tools/bin/aos-mcp`）、pyfix 的 act（`lib/agent/pyfix/agent/act.py`）、demo 的 shell agent（`demo/agent-bob/act/_entry` 的 `sub=$AOS_STACK/cathy/`、`…/tools/cathy/act/_entry` 的 `sub=$AOS_STACK/stamp/`）。｜使用者這句；工具名是登記檔／tools 資料夾給的變動名。資料夾叫 `tools`（複數）照 C-54「裝同類的資料夾用複數」，而且跟定義那邊的 `tools/<名>/`（P-25、C-61）同一個字——P-38「stack 樹＝呼叫樹＝tools 資料夾樹」反而更貼：`act/tools/cathy/act/tools/stamp/` ⇄ `.stack/tools/cathy/tools/stamp/`。
2. **不分 `agents/`、`kernels/`**：被叫的裡面是工具、另一隻 agent、還是 kernel，一律進 `tools/`。｜C-52「上層不該知道下層是什麼」、C-61「工具一律做成資料夾程式」——呼叫方只知道它叫了一個工具，分資料夾就等於要它知道下層是什麼。
3. **`tools/` 不用誰先 mkdir**：aos-exec 建 stack 是 `mkdir -p`（[impls/aos-exec README 第 3 步](../impls/aos-exec/README.md)），`AOS_STACK=$AOS_STACK/tools/<名>/ aos-exec tools/<名>` 一行照舊、多一層自動長出來。act／aos-mcp 走 `aos-tools call` 也是最後交給 aos-exec，不用自己建。｜N-59「建 stack 只在 aos-exec 做」。
4. **cli_session 的 attach 找畫面**（`lib/agent/cli_session.py:525-540`）：`Cell(os.path.join(stack, t))` → `Cell(os.path.join(stack, "tools", t))`，列表與接進去都一樣。｜它找的是「這隻 agent 叫某個 CLI 工具時開的小格」，就是第 1 條那個位置，跟著走。`lib/agent/claude`、`codex` 兩個工具自己不動：它們拿到的 `$AOS_STACK` 已經是小格。
5. **aos-daemon 的子項小格**＝`$AOS_STACK/loops/<名字>/`（loop 子項與 exec 子項都是，兩種都列在 `loops` 表）。｜同一把尺：子項名字是名單（`daemon.json` 或 `loops_ctl` 的 `loops`）給的變動名，daemon 自己的固定名（`ctl.json`、`state.json`、`loops_ctl.json`、`loops_state.json`、`loops_state_loops/`、信箱、eca-hub 放的 `eca_archive/`）留頂層。資料夾名用 `loops` 不用 `tools`：daemon 不是在「叫工具」（P-17 是 agent 範本的事），它的名單就叫 `loops`、兩扇窗叫 `loops_ctl`／`loops_state`、分頁叫 `loops_state_loops/`，C-54「主題放前面、同一主題同一個字」。連帶：`bin/aos-daemon-ctl` 建的 `<WS>/.stack` symlink 指到 `<D>/loops/<名字>`；eca-hub 從 `loops_state` 讀 `cell` 欄位、不自己拼路徑，跟著變；`AOS_DAEMON` 仍指 daemon 的 stack 頂層。**這條跟 10-22「擋名字」有關，見衝突 1。**
6. **eca-turn 的 `<kind>/`**（`$AOS_STACK/claude/` 或 `codex/`，CLI 的對話小格）**留在頂層不動**。｜`kind` 只有 claude、codex 兩個，是 aos-eca-turn 自己定的封閉集合，不是外面給的變動名——照尺是固定名。它也不是經 P-17 叫工具（在同一個行程裡用 cli_session，沒有 `tools/<kind>/` 這個定義資料夾）。`transcripts/`、`eca.json` 同理照舊。
7. **eca-hub 的 `eca_archive/` 與 `.stack` symlink**：照舊。｜`eca_archive` 是 eca-hub 寫死的固定名，放 daemon 那邊是使用者 10-30「A」定的；B 之後子項進 `loops/`，它跟任何子項名都撞不到。symlink 只是目標路徑多一段（第 5 條）。
8. **pyfix／agent_tool 的 `runs/NNN/`**：照舊。｜`runs/` 本身就是固定名的複數資料夾，裡面的 `001`、`002` 是變動的——它早就是「變動名收進一個固定資料夾」這個形狀，不必再套一層 `tools/`。它刻意每次開新格（不照 P-34 續用），這點不是本題。
9. **ask_round 被問的 agent 的位置**（`lib/aos/ask_round/_entry:116-125`）：沒給 `--ws` 時，被問 agent 的小格＝`$AOS_STACK/tools/<agent 資料夾名>/`，照 P-32 的形：**它的工作區＝那個小格底下的 `ws/`、它的 stack＝那個小格本身**（現行是 `$AOS_STACK/<agent 名>/` 當工作區、`<工作區>/.stack/` 當 stack）。｜agent 資料夾名是 argv 給的變動名，進 `tools/`；工作區與 stack 的擺法 P-32 已寫死「`AOS_STACK=$sub aos-exec --ws "$sub/ws" tools/<名>`」，ask_round 現行寫法是它自己的另一套，趁這次對齊。**最小改法**（若使用者不想一次動兩件）：只把前綴改成 `tools/`、工作區與 `.stack` 的擺法照舊——這點可翻案。
10. **aos-mcp 的 `calls.jsonl`**、act 的 `queue/`、`compact/`、`history_archive/`、`current.txt`、`trace.jsonl` 等：照舊在頂層。｜全是程式寫死的固定名。
11. **用詞**：「小格」的定義改成「`$AOS_STACK/tools/<名>/`」；不新造名詞。daemon 那格叫「子項的小格」照舊，路徑寫 `loops/<名字>/`。

### 實作步驟表

前提：**另一位 Opus 隊長正在改 aos-mcp**（參數改成登記檔路徑 `aos-mcp aos-tools.json`、相關 README／條文／測試、試驗場 cathy）。本表以那一輪**已落地**為前提——**動 aos-mcp 之前先 `git pull` 最新 main**，再在新版的 `call()`（`AOS_STACK=os.path.join(stack, name)`）上改。

驗證方式統一：proto8 的 pytest 全套（11-01 基準 803 OK／8 skip，見 [testing/01-proto8](../../wf/workflows/testing/01-proto8.md)）＋ repo 根 `cmake --build --preset default && ctest --preset default` 全綠（鐵律 1）。各步可以分開 commit，順序建議如下（1 → 2 → 3 → 4 → 5；6 等使用者）。

| 步 | 改哪些檔 | 測試怎麼驗 | 分開 commit？ |
|---|---|---|---|
| 1 工具小格（agent 範本這條線） | `lib/agent/act/_entry:125`（`os.path.join(stack, "tools", name)`）、`lib/agent/pyfix/agent/act.py:79`、`lib/agent/cli_session.py:530、540`、`demo/agent-bob/act/_entry:5`、`demo/agent-bob/act/tools/cathy/act/_entry:7`；測試 `tests/test_exec.py:357`（`.stack/tools/cathy/trace.jsonl`）、`tests/test_lib.py`（agent-liv 那段看小格的斷言）、`tests/test_fay.py`、`tests/test_eca_turn.py`（碰 cli_session 的小格路徑的斷言）；同 commit 補 `lib/README.md`（規則 8、第 84 行 run_python、第 118～119 行）、`demo/README.md`（若有畫樹）、code map [proto8 分冊](../../wf/workflows/common/code-map/proto8/)（鐵律 3） | 全套 pytest；另跑一次 `demo/run.sh`（P-38 說跑完印整棵樹，肉眼看 `.stack/tools/cathy/tools/stamp/`） | 可以，單獨一個 |
| 2 aos-mcp | **先 pull**。`extras/ai_tools/bin/aos-mcp:116`（`os.path.join(stack, "tools", name)`、檔頭第 12 行用法註解）、`tests/test_aos_mcp.py`（看小格位置的斷言）、`extras/ai_tools/README.md:81`（叫一次的那行）與第 40 行（「各 agent 的小格」）、code map [06-周邊工具](../../wf/workflows/common/code-map/proto8/06-周邊工具.md) aos-mcp 那列 | `tests/test_aos_mcp.py`、`tests/test_ai_tools.py`；使用者的試驗場 `~/code/playground` 重跑一次 bob-cathy，確認 `ws/.stack/tools/cathy/` 出現（那份不在 git，由使用者或頂層在 WSL 跑；[playground-cathy 代定 7](2026-11-02-playground-cathy.md) 的路徑要在那份檔加一句「11-02 改 `tools/cathy/`」） | 可以，單獨一個 |
| 3 ask_round | `lib/aos/ask_round/_entry:116-125`（`cell = $AOS_STACK/tools/<agent 名>/`、`ws = cell/ws`、`stack = cell`；最小改法見細節 9）、`lib/README.md:105`、ask_round 自己的用法註解；測試：`tests/` 裡叫 ask_round 的那幾個（grep `ask_round`） | 相關 pytest；手動 `aos-exec lib/aos/ask_round <agent>` 一次看目錄 | 可以，單獨一個 |
| 4 daemon 子項 → `loops/<名字>/` | `impls/aos-daemon/src/`（起子 loop 與 `spawn_exec` 拼小格路徑的那兩處；`loops_state` 的 `cell` 欄位自然跟著）、`bin/aos-daemon-ctl:106-115`（symlink 目標）、`tests/test_daemon.py`（所有 `stack/<名字>` 的斷言）、`tests/test_ai_tools.py:284` 附近與其他用 `dstack/<名字>` 的、eca-hub 測試（若有拼路徑）；文件：[impls/aos-daemon README](../impls/aos-daemon/README.md) 第 16、57、100 行、[bin/README](../bin/README.md) 第 70 行、[extras/eca_hub README](../extras/eca_hub/README.md) 第 26～28 行、[extras/ai_tools README](../extras/ai_tools/README.md) 第 40 行、[demo/daemon*](../demo/README.md) 說明、code map。**這一步先不碰「擋名字」的程式**（`taken_names`／`check_names` 與 `test_daemon.py:296-316`）——留著不會錯，等衝突 1 的答案再動 | root ctest（aos-daemon 的 C++ 測試）＋ `tests/test_daemon.py`、`tests/test_ai_tools.py`、eca-hub 測試；手動起一次 `demo/daemon`，看 `.stack/loops/<名字>/` 與 `<ws>/.stack` symlink 指對 | 可以，單獨一個 |
| 5 條文與名詞（一個 commit） | 見下「條文那步」 | `/wf-lint`（壞連結、錨點） | 可以，單獨一個；放在 1～4 之後，寫「已落地」 |
| 6 擋名字拿掉（**等使用者答衝突 1**） | `impls/aos-daemon/src/` 的 `taken_names`／`check_names` 與 `Conflict`／`CfgBad` 那條錯誤路徑、`tests/test_daemon.py:296-316`、daemon README 第 53～56 行、N-28 那句「子項撞名照 10-22…多擋…」、[10-22 ideas § 5](2026-10-22-ideas/03-5-loop.md) 加一行翻案註 | root ctest、`tests/test_daemon.py` | 可以，單獨一個 |
| 7 收尾 | 本檔「決定」補使用者對衝突／方向題的答案；[months/2026-11](months/2026-11.md) 那列由頂層加；日誌一行 | — | 併入步 5 或單獨 |

### 條文那步（步 5）：改哪幾條、日期註怎麼加

原則：**路徑直接改成新的，後面接一個短的日期註**，只記「這次改了什麼、出處」，不延伸、不改條文其他原意。註的樣子照 C-54 既有的「**10-31 加註**（使用者 10-31「…」，[thinking …]）」格式：

> **11-02 改**（使用者 11-02「未來，搞不好會出現agent+kernel的變體，.stack底下會有一大堆東西。擋名字會擋不過來。所以我覺得最好還是tools/<name>更好」，[thinking 11-02 stack-tools](../../thinking/2026-11-02-stack-tools.md)）：小格由 `$AOS_STACK/<名>/` 改 `$AOS_STACK/tools/<名>/`，呼叫方給的名字跟格自己的固定名分開命名空間。

每條只貼一次完整註；其他條寫短的「（11-02 改 `tools/<名>/`，見 P-17）」就好，別讓每條都長一段。

| 條 | 檔 | 改什麼 |
|---|---|---|
| **P-17** | [CONVENTION/02](../docs/CONVENTION/02-題目stack停錯腦.md) 第 23 行 | `sub=$AOS_STACK/<名>/` → `sub=$AOS_STACK/tools/<名>/`；例子 `$AOS_STACK/stamp/` → `$AOS_STACK/tools/stamp/`；貼完整註（主條） |
| P-15 的小格一詞 | 同檔第 21 行 | 不改字，只是「小格」定義變了，不加註 |
| P-25 | 同檔第 40 行 | 「stack 照 P-17」不用改；若句中出現路徑才改。短註 |
| P-41 介面那行 | 同檔第 47 行 | `AOS_STACK=$AOS_STACK/<名>/ aos-exec tools/<名>` → `…/tools/<名>/ …`；短註 |
| **P-32** | [CONVENTION/06](../docs/CONVENTION/06-巢狀.md) 第 7 行 | `sub=$AOS_STACK/<名>/` → `tools/<名>/`；結尾「cathy 的題目與答案全在 `.stack/cathy/ws/`」→ `.stack/tools/cathy/ws/`；短註 |
| P-34 | 同檔第 10 行 | 路徑沒寫死，只在「不用題名開新小格」處確認用詞；多半不用改 |
| **P-38** | 同檔第 15 行 | 樹的例子 `.stack/{state.txt,trace.jsonl,cathy/{…,stamp/runs.txt}}` → `.stack/{state.txt,trace.jsonl,tools/cathy/{state.txt,trace.jsonl,ws/,tools/stamp/runs.txt}}`；「每層照 P-17 用工具名開小格」補「在 `tools/` 底下」；短註 |
| P-39（N-10 第 66 行提到） | 同檔 | 若有路徑就改，沒有不動 |
| 範例 | [CONVENTION/04](../docs/CONVENTION/04-範例三種寫法.md) 第 26 行、[CONVENTION/01](../docs/CONVENTION/01-保證佈局入口.md) 若有樹 | shell 範例 `sub=$AOS_STACK/cathy/` → `tools/cathy/` |
| **N-50** | [NORMS/10](../docs/NORMS/10-基礎設施-定義與工作區.md) 第 45 行 | `AOS_STACK=$AOS_STACK/<名>/ aos-exec tools/<名>` → `…/tools/<名>/ …`；短註 |
| N-28 | [NORMS/04](../docs/NORMS/04-基礎設施-loop與daemon.md) 第 16～18 行 | 子項小格寫明 `$AOS_STACK/loops/<名字>/`；「子項撞名照 10-22…多擋…」那句**先留**、加一句「11-02 子項改進 `loops/`，撞名已不可能發生；擋不擋待使用者定（衝突 1）」 |
| N-54、N-10 第 76 行 | 同上／NORMS/10 | 提到「小格」的地方若寫了路徑才改 |
| **C-54 用詞** | [CONCEPTS/03](../docs/CONCEPTS/03-基礎設施.md) 第 51 行、[NORMS/10](../docs/NORMS/10-基礎設施-定義與工作區.md) 第 7 行 | 「小格＝…（`$AOS_STACK/<名>/`）」→ `tools/<名>/`；短註 |
| **附錄1 名詞** | [CONCEPTS/附錄1](../docs/CONCEPTS/附錄1-名詞.md) 第 58 行 | 「小格」那列路徑改；日期欄補 11-02 |
| C-52、C-70 | [CONCEPTS/01](../docs/CONCEPTS/01-設計理念.md) | 不改：C-70 引的「AOS_STACK/think, /act」是 agent 自己的格（固定名），不是小格 |
| C-61 | [CONCEPTS/05](../docs/CONCEPTS/05-agent.md) 第 31 行 | 「給它一個小格（P-17）」不用改路徑；不加註 |
| C-51 | — | 不動（使用者的「後續想法」還 open，本次不算它的例子） |

## 要使用者看的衝突與方向題

**衝突 1：daemon 10-22「擋名字」還要不要留？**
10-22 你定的是：子項名字跟 daemon 自己的窗同名（`state.json`、`ctl.json`、`loops_ctl.json`…）就擋掉、退 1；程式有做、也有測試。這次子項改進 `loops/<名字>/` 之後，子項**不可能**再跟那些窗撞——擋名字的程式變成永遠不會跑到的死碼。
- **留**：多幾十行沒用的程式和三個測試，但不改你 10-22 的裁定，以後若又把子項搬回頂層它還在。
- **拿掉**（fable 建議）：照 KISS「最後回頭清掉多餘的」；N-28 那句與 10-22 ideas 加一行翻案註。名字本身仍有的檢查（不能空、不能含 `/`、不能 `.` 開頭）照留，那不是撞名。
例子：以前 `loops: {"state.json": …}` 會被擋；改完它就是 `.stack/loops/state.json/`，跟 `.stack/state.json` 井水不犯河水。

**衝突 2：daemon 子項的路徑會變，牽到人看得見的地方。**
你用 `aos-eca-hub add` 掛的東西，小格從 `$AOS_DAEMON/<名字>/` 變 `$AOS_DAEMON/loops/<名字>/`；工作區裡的 `.stack` 捷徑也會指到新位置。已經掛著、跑著的 daemon 要重起才會用新路徑（舊的小格留在頂層不會自動搬）。這不是原則衝突，是要你知道：改完那天現有的 daemon 要停掉重掛一次。fable 建議照做，順手把舊小格 `rm`。

**衝突 3：`tools` 這個字從此是 stack 頂層的保留名。**
B 的代價：以後任何格都不能在自己 stack 頂層放一個叫 `tools` 的固定東西（檔或資料夾），否則就跟小格撞。目前沒有程式這樣做（grep 過 lib／extras／impls／demo），但要寫進條文當規則（P-17 的註那句就夠）。這跟你說的「tools.json 這個挺常用的、想解放名字」是同一個方向的反面：解放了 `tools.json` 這個檔名，但收走了 stack 裡 `tools/` 這個資料夾名。fable 認為值得，列出來讓你知道。

**方向題 1：ask_round 要不要順便對齊 P-32？**（細節 9）
ask_round 現在把被問的 agent 放成「`$AOS_STACK/<agent 名>/` 是它的工作區、底下 `.stack/` 是它的 stack」；P-32 寫的形是「小格就是它的 stack、工作區在小格底下的 `ws/`」。兩種都能跑。這次一定要把前綴改成 `tools/`；要不要連擺法一起改成 P-32 的形？
- **一起改**（fable 建議）：全 repo 只剩一種「被叫者放哪」的形，看 stack 樹不用記例外。
- **只改前綴**：改動最小，但 ask_round 繼續是例外，lib/README 要多寫一句。
例子：問 agent-dan 一題，一起改之後是 `.stack/tools/agent-dan/{state.txt,queue/,history.jsonl,ws/}`；只改前綴是 `.stack/tools/agent-dan/{out/,.stack/{state.txt,…}}`。

**方向題 2（不急，先記著）：eca-turn 的 `claude/`、`codex/` 留在頂層對不對？**（細節 6）
fable 照「誰給的名字」這把尺把它算成固定名、留頂層。但它確實是「叫別的東西時開的小格」，以後若 kind 不再只有兩個（例如 kind 從設定檔讀），就該搬進一個複數資料夾。現在不改；要是你覺得「反正遲早」想一次搬，fable 建議的名字是 `clis/<kind>/`（它叫的是 CLI，不是 P-17 的工具）。
