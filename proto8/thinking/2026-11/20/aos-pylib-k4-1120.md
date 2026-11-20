編譯程式庫第 4 刀（`defs.extern` 換意思＝編譯成連結）與 `loop=` 宣告的施工紀錄（11-20，線 aos-pylib-k4-1120，兩筆 commit）：做了什麼、實測、驗收、舊寫法的行為差異、跟設計稿對不上處、替使用者做的選擇。

← [2026-11-20](README.md)｜設計稿：[aos-pylib-plan-1120](aos-pylib-plan-1120/README.md)（[05 extern 連結版](aos-pylib-plan-1120/05-extern-symlink.md)、[07c 第 4 刀](aos-pylib-plan-1120/07c-施工計劃-第3到5刀.md#第-4-刀-extern-連結版)、[08 第 1、6、8 題](aos-pylib-plan-1120/08-待裁題.md)、[11 採納表](aos-pylib-plan-1120/11-採納表.md)）｜使用者答案：[12-使用者已答](aos-pylib-plan-1120/12-使用者已答.md)｜上一刀：[第 3 刀](aos-pylib-k3-1120.md)

## 依據（使用者原話）

- extern：「啊，那這樣的話，extern還是有作用的，也就是創建一個symlink，指向我們要的檔案路徑，編譯的時候就是只生成symlink。喔老天...我雖然不太喜歡symlink，但這...好吧，加上這個功能，但註釋要說別濫用。」
- 待裁第 6 題（連結被 `agent_def llm set`／`tools add` 寫穿）：「接受，寫進「別濫用」」→ 不改那些指令，寫進說明。
- 待裁第 1 題（`defs.main()` 收設定檔列不產出的檔）：「先不定」→ 不做。
- 待裁第 8 題（`loop.json` 從 agent.py 改不到）：「加一個宣告」。
- 開工：「開工吧」。

## 一句話

**第一筆**：`defs.extern(路徑)` 那一欄編成一個連結（symlink）放在那一欄平常的檔名上、照字面存你寫的路徑，編譯只重做連結、永遠不碰目標；`--dry-run` 印 `{"$symlink": 路徑}`、`--compile` 印 `wrote 夾/system.txt -> 路徑`；目標不在、是資料夾、繞回自己、fsm 指到別夾、extern 放在串列裡都是 `SpecBad`；`defs.load` 的底連到夾外的照樣交出（衍生那支編譯時換算），連到夾內的接不上；`agent_def check` 報斷掉的連結（一個一條）。說明（docstring、`--help`、骨架 README、教學）寫明別濫用與會被指令寫穿。**沒用 extern 的骨架與六隻例子重新編譯產物逐 byte 相同。**

**第二筆**：見末節「第二筆：loop=」。

## 第一步：實測（改程式前，用 HEAD 裝好的複本、暫存樹、假腦）

`exp_links.py`（`~/.aos/scratch/aos-pylib-k4-1120/`）：抄 start-api、總機加一個假腦（先叫 probe 工具，再回「收到的 system 開頭＋工具回的字」）；編兩隻正常的 agent，再手動把檔換成指到 `../../shared/` 的連結：

| 連結 | 結果 | 結論 |
|---|---|---|
| a 的 `system.txt` → shared | 腦收到 `SYSTEM OF SHARED (the linked one)`；改 shared 那份、不重新編譯，下一封信就是 `SYSTEM OF SHARED, EDITED` | 讀得到、改了就生效 |
| a 的 `tools.json` → shared（裡面 `"path": "probe"`） | 叫到的是 `probe of agent a` | 工具的相對路徑從**連結所在的定義夾**算（05 讀程式推的，對） |
| a 的 `hooks.json` → shared（`"handler": "hk.sh"`） | 跑的是 `hook of agent a` | handler 的相對路徑也從連結所在的定義夾算 |
| b 的 `fsm.json` → `../../shared/fsm.json` | 回 `FAKE ANSWER to: hello`：b 的 `llm.json`（假腦 fakesys）沒被讀到，格程式用的是 shared 那夾 | **fsm 指到夾外會找錯夾**（`aos-loop` 先 `canonical`），05 的限制照留：fsm 只能指同一夾 |

暫存樹留在 `/tmp/k4-links-wqedxsjm`（沒刪）。行程用 daemon shutdown 收掉。

## 寫起來

```python
bob = defs.Agent(
    "Like ann, with a system text written by hand.",
    system=defs.extern("system.hand.txt"),        # system.txt 編成連結 → system.hand.txt（同夾手寫，編譯永遠不碰）
    tools=[...], llm={...},
    fsm=defs.extern("fsm.hand.json"),             # fsm 只能連同一夾
)
# 或連到夾外：system=defs.extern("../shared/system.txt")（別濫用）
```

## 動了哪些檔（第一筆）

| 檔 | 做什麼 |
|---|---|
| `py/aos/agent_spec.py` | `extern(目標)`：一個參數、普通字串、照字面存（`{"kind": "extern", "target": …}`）；指示詞 `defs.env`／`defs.home`＝bad；docstring 用 05 的「別濫用」英文稿（加了「fsm 只能同一夾」「同夾手寫換個名字連過去」兩句）；`HELP` 加 05 那兩行；`defs.fsm(底是 extern, …)`＝bad；檔頭一行 |
| `py/aos/agent_spec_agent.py` | `_names` 不再讓 extern 改檔名（interfaces.json 一律寫預設名；eca 版用 interfaces.json 宣告的名字），拿掉舊的「撞名」檢查；新 `_links`：沒給夾、繞回自己、目標不在、是資料夾、fsm 不在同一夾＝SpecBad；`defs.load` 帶 `from` 的在這裡換算；產物是 `spec_base.Link`（不經 `_plain`）；`_write` 寫連結那行加 ` -> 目標`；load 交回的夾內 extern 訊息改寫；pick 訊息裡的 extern 例子改成新意思 |
| `py/aos/agent_spec_load.py` | 新 `_anchored`：底的 extern 目標（照它的 `from` 或底那夾算）在底那夾外面＝帶 `from` 照樣交出；裡面＝`_hand`（用到才 SpecBad，同今天）；欄位處理改用 `skip` |
| `py/aos/agent_spec_parts.py`、`agent_spec_hooks.py` | tools／hooks 串列裡放 extern＝專門的 SpecBad（`stands for the whole field`）；HOOKS_SHAPE 的例子、兩處註解 |
| `py/aos/spec_unit.py` | `--dry-run` 把 `Link` 印成 `{"$symlink": 目標}` |
| `py/tools/aos/defs/links_check.py`（新）、`catalog.py` | check 最先查定義夾最上層的斷鏈，一個一條；有斷鏈就不再往下查那份（Argon A9） |
| 測試 | 新 `test_agent_spec_extern.py`（7 條：05 逐項表每列、連編兩次、`defs.load` 夾外換算兩層＋夾內接不上）、新 `test_agent_spec_extern_live.py`（3 條實掛）；`test_agent_spec.py`（拿掉舊意思的 extern：`test_spec_bad` 6 個案例、`extern("agent.py")` 那段、`test_extern_hooks`；`test_extern_meta_and_interfaces` 改成不帶 extern）、`test_agent_spec_load.py`（reviewer 範本那支改連 `system.hand.txt`、夾內 extern 訊息）、`test_agent_spec_script.py`（手寫檔不被碰改成連結版、連編兩次；eca 版連結坐在宣告的名字上、繞回自己）；`py/tools/aos/defs/tests/test_defs.py` 加斷鏈一條 |
| 文件 | 骨架 README 新一節「extern: a link to a file you write (do not overuse it)」、另三處改說法；教學 06-2 的 bob 改用 `system.hand.txt` 並加「別濫用」一點；`py/tools/aos/defs/README.md` 斷鏈一條；`knowledge/aos/agents.json` check 那句加斷鏈；`templates/README.md` 那句 extern 舊說明；`py/README.md`、`py/docs/01`、`py/docs/04`（連第 3 刀紀錄列的字一起補） |

## 驗收（第一筆）

環境：`git archive` 抄 `60c0a6d28`（HEAD，含第 0～3 刀）到 `~/.aos/scratch/aos-pylib-k4-1120/base`、`install.py`；同一個 commit 再抄 `new`，只疊本線的檔（工作樹裡別線沒交的改動沒抄）、`install.py`。腳本一律先 unset 所有 `AOS_*`、`env -i PATH=<複本>/bin:/usr/bin:/bin HOME=… AOS_HOME=<複本>`。

**1. 沒用 extern 的產物逐 byte 相同**（做法同第 2、3 刀：骨架 12 種旗標＋八隻例子各 `--dry-run`、`--dry-run --dynamic`、`--compile`，bob 另編到別夾）。

- 舊寫法（`cases/old.py`，bob 與 revtpl 寫 `defs.extern("system.txt")`）餵新程式：111 份輸出 89 份相同；不同的 22 份＝`--help`（多兩行，預期）＋bob、revtpl 各 `--dry-run`／`--dry-run --dynamic`／`--compile`（＋bob 編到別夾）全部變成一行 `SpecBad … links system.txt to itself …`、退 1、什麼都沒寫。
- 新寫法（`cases/new.py`：那兩隻改 `defs.extern("system.hand.txt")`、手寫檔改名 `system.hand.txt`）：111 份 **101 份相同**；不同的 10 份見下表。寫出的樹 `diff -r` 只差骨架 `README.md`（文件改了，編譯時夾裡已有、不寫）與 bob／revtpl 多一份 `system.hand.txt`；`system.txt` 讀出來的內容兩邊相同（連結指到同樣的字），`interfaces.json` 兩邊相同。骨架重新編譯跟提交的那份無差。
- 骨架、ann04、ann、reviewer、eca、strict-reviewer、renamed（六隻沒用 extern 的）每份輸出與寫出的檔都相同。

**原本用 `defs.extern` 的例子改成新意思後，行為差異逐項**：

| 例子 | 改動前（extern＝手寫檔，interfaces.json 指到它） | 改動後（寫法照搬 `extern("system.txt")`） | 改動後（改寫成 `extern("system.hand.txt")`） |
|---|---|---|---|
| 教學 06-2 的 bob、`--compile` | 不寫 `system.txt`、留著手寫那份 | SpecBad「links system.txt to itself」、什麼都不寫 | `system.txt` 是連結 → `system.hand.txt`；輸出多一行 `wrote …/system.txt -> system.hand.txt`（排在最後） |
| bob、`--dry-run`（含 `--dynamic`） | 印出的 JSON 沒有 `system.txt` | 同上 SpecBad | JSON 多一格 `"system.txt": {"$symlink": "system.hand.txt"}` |
| bob、`--compile 別的夾` | 成功：別的夾裡**沒有** `system.txt`（interfaces.json 指著它，執行時就是沒有 system 文字） | 同上 SpecBad | SpecBad「system.hand.txt does not exist (seen from …/bob-out)」：相對路徑從編譯進去的那一夾算，那裡沒有手寫檔（要編到別夾就連到絕對路徑或兩邊都放） |
| revtpl（`templates/reviewer` 寫成一支）| 同 bob 前兩列 | 同上 SpecBad | 同 bob 前兩列 |
| `defs.load` 一個用 extern 的底 | 用到那欄＝SpecBad「a file written by hand」 | 底連到夾內＝同樣 SpecBad（訊息改說 link to a file inside that folder）；底連到夾外＝照樣交出、衍生那支也編成連結 | 同左 |
| 不給 fsm（eca 版）、extern 的名字 | 要跟 interfaces.json 宣告的名字一樣，否則 SpecBad | 連結坐在宣告的名字上；`extern(宣告的名字)`＝繞回自己 | — |
| `extern("../x")`、絕對路徑 | SpecBad（只收夾內相對名） | 收（連到那裡；目標要在） | — |

**2. 實掛**（`test_agent_spec_extern_live.py`，`new` 複本；抄 start-api、總機加一個「回收到的 system 文字」的假腦）：`system=defs.extern("../../shared/system.txt")`、`fsm=defs.extern("fsm.hand.json")`：

- 編出 `system.txt -> ../../shared/system.txt`、`fsm.json -> fsm.hand.json`；`agent_def check` 回 `{"problems": []}`；腦收到 `first words`。
- 改 `shared/system.txt` 成 `second words`、**不重新編譯**，下一封信腦收到 `second words`。
- 重新編譯：`fsm.hand.json`、`shared/system.txt` 一個 byte 都沒變，輸出有 `system.txt -> ../../shared/system.txt`，連結還在。
- `agent_def new` 抄一份（照搬，純粹 cp）：抄到同一層 `agents/bob2`：兩個連結的字一樣、還通，check 無 problem，`fsm.json` 指的是 bob2 自己那份 `fsm.hand.json`；抄到深一層 `agents/deep/bob3`：連結的字還是 `../../shared/system.txt`、**斷了**，check 恰好一條 problem `system.txt is a link to ../../shared/system.txt, which is not there …`。
- 3 條 OK（約 8 秒）；行程由 daemon shutdown 收掉。

**3. 報錯情況**：`test_agent_spec_extern.py` 的 `test_spec_bad` 13 個（指示詞兩種、不是字串、空字串、不在、是資料夾、繞回自己三種寫法、tools／hooks 串列裡、fsm 到別夾、fsm 到子夾），每個都確認夾裡什麼都沒寫、原本的手寫檔沒被動；`.dry_run()` 沒給夾、從別夾看不到目標各一條；`defs.fsm(extern…)`；夾內 extern 用到時；check 斷鏈。

**4. 全套測試逐夾**（同一份 commit，base／new，各自 install，一夾一夾跑）：

| 夾 | base | new（第一筆） |
|---|---|---|
| `py/tests` | 690 OK（skip 1、expected failure 1） | 699 OK（同；多 9＝extern 7＋live 3－拿掉的 `test_extern_hooks` 1） |
| `py/tools/aos/defs/tests` | 27 OK | 28 OK（多斷鏈一條） |
| `templates/tests/tool-python`、`tools_def`、`agent_def` | 5／12／32 OK | 同 |
| `py/tests/apps/*`（feedback 以外十七夾，含 gdb 66、agent 213、eca 223） | 全 OK | 同，每夾條數相同 |
| `py/tests/apps/feedback` | 18 error | 18 error（讀不到 `wf/`，已知） |
| `templates/tests` agent-fsm、reviewer、judge-llm、kits、image-move-check | 209／1／4／8 OK、0 條 | 同 |

這一輪兩邊沒有紅的。

## 跟設計稿對不上、或設計稿沒寫到的（都選最小的做法）

1. **繞回自己的判法多一種**：05／Argon A7 寫「目標的真實路徑」跟「定義夾真實路徑＋連結檔名」比。照字面做，`system.txt` 已經是連到 shared 的連結時寫 `extern("system.txt")` 會判不出（真實路徑解到 shared 去），編出一個連到自己的連結。所以兩種都比：目標的**上一層解開、檔名不解**的路徑，或目標整個解開的路徑，任一個等於連結自己＝繞回自己。第二次編譯不誤判（有測試）。
2. **那句特別的訊息不寫「now」**：05 草稿是 `defs.extern now takes the file to link to; "system.txt" is the link itself`。「now」是在講舊版，照「proto8 當沒有舊版、不留舊名提示」改成 `extern('system.txt') for system links system.txt to itself: give the file to link to, like defs.extern("system.hand.txt") for a file of this folder kept by hand`。
3. **連結在 `--compile` 輸出排最後**：連結跟函數程式一樣不經 `_plain`，加在最後；寫檔改名時照 `RENAME_LAST`（沒列＝0），在索引檔之前換上。沒用 extern 的輸出順序不受影響。
4. **`defs.load` 的底連到夾外的相對路徑「從底那支 agent.py 的夾算」**：設計稿說「目標在底那夾外面＝照樣交出、到知道編譯進哪一夾才換算」，沒說底的相對路徑從哪算。底被 `defs.load` 時沒有在編譯，取它預設會編進的那一夾（`agent.py` 所在的夾）。底自己也是衍生來的（記號已帶 `from`）照它的 `from` 算，兩層也對（有測試）。「在不在底那夾裡面」用真實路徑判。
5. **`agent_def check` 的斷鏈只看定義夾最上層、不管是不是 interfaces.json 宣告的檔**：設計稿寫「宣告的檔是斷掉的連結」。宣告的檔都在最上層，而 interfaces.json 自己也可能是斷鏈，先讀它再判會繞圈；所以最上層任何斷鏈都報。有斷鏈時**那份定義其餘的檢查先不做**（訊息寫了「the other checks of this definition wait until it is fixed」）——這是做到「一個斷鏈只報一條」最小的方法；設計稿說「先判」，沒說後面要不要照查。
6. **斷鏈檢查放進 `py/tools/aos/defs/`**：任務書的領地清單沒點名這夾，但 07c 第 4 刀與 05 的「別濫用」說明都要它（說明寫「agent_def check reports a broken link, nothing else does」）；沒有別線動這夾，claim 得到才改。
7. **骨架 README 的「extern」一節用英文**：05 說「用上面那段的中文版」，但骨架 README 整份是英文（給抄出去的人與腦看），照檔的語言寫英文；中文說明寫在教學 06-2。
8. **目標是不是本來就會被編譯寫掉的檔不擋**：例如 `system=defs.extern("tools.json")` 讓 `system.txt` 連到同夾編出來的 `tools.json`。照「目標內容不驗」，不擋（第一次編譯時 `tools.json` 還不在才會報不在）。
9. **`spec_base.py` 檔頭那句「程式檔、連結今天還沒人用」沒改**：那支不在領地（第 0 刀的檔），交頂層：第 3、4 刀已經用上，可改成「程式檔給第 3 刀的 fn/<名>.py、連結給第 4 刀的 defs.extern」。

## 替使用者做的選擇（第一筆）

- **第 1 題「先不定」**：`defs.main()` 不收設定檔；同夾手寫的檔換個名字連過去（`defs.extern("system.hand.txt")`）就是今天的做法，寫進 README 與教學。
- **第 6 題「接受，寫進「別濫用」」**：`agent_def`、`aos-tools` 一行沒動；docstring、README、教學都寫了「`agent_def llm`／`tools`、`aos-tools add --file` 會順著連結改到共用檔；`agent_def system` 會把連結換成普通檔」。
- **`agent_def new` 照搬連結**（aos-defnew-cp-1120 已定純粹 cp）：沒動 `agent_def`；實測寫在上面（同層通、不同深度斷、check 報）；README 的「別濫用」寫了一句。
- **編譯時不另外印提醒**（05 的定法）：只有 `wrote … -> 目標` 那行看得出是連結。

## 要頂層或別線補的字（本線不碰）

- `wf/HANDOFF.md` 名字那段（:37 一帶）：「`defs.extern`：留著但換意思＝編譯成 symlink」可補「已交（第 4 刀，線 aos-pylib-k4-1120）：同夾手寫換名連過去 `defs.extern("system.hand.txt")`；fsm 只能連同一夾；`agent_def check` 報斷鏈」。
- `py/aos/spec_base.py` 檔頭第 4 行（見上「對不上」第 9 條）。
- 改的是 `py/`：**活樹要在 `~/repo/aos/proto8` 跑 `install.py` 才吃到**（要使用者點頭）；本線沒跑。已經用舊意思寫 `defs.extern("system.txt")` 的 `agent.py`（使用者教學夾 `~/code/aos-tut` 的 bob 若照 06-2 做過）要改成 `defs.extern("system.hand.txt")`、手寫檔改名才能再編譯；已編好的定義夾不受影響（執行期沒動）。
