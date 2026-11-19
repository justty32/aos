繼承第一刀施工紀錄（線 aos-inherit-cut1-1119）：照 aos-inherit-1119 的乙做了 ag.load（跑底那支 agent.py、它的 ag.main 只交出九個欄位）＋TOOLS／HOOKS／ag.fsm 收「底」（墓碑、帶標記的 hook 組、換格），只動 agent_spec*，生出的 json 整份不記上一層、執行期一行沒動；順手修骨架找套件的兩處小洞；驗收逐條、自己定的細節、收緊的已交行為。

← [aos-inherit-1119 README](aos-inherit-1119/README.md)｜設計：[04 乙修正版](aos-inherit-1119/04-設計選項.md)、[06](aos-inherit-1119/06-邊緣狀況與要拍板的題.md)、[07 採納表](aos-inherit-1119/07-Argon審與採納.md)、[08 使用者裁定](aos-inherit-1119/08-使用者裁定.md)｜規範 N-70（另一條文件線在寫，這條沒動條文）

## 授權與範圍

- 使用者 11-19 選項框：「「一隻 agent 從另一隻衍生」要在哪裡做？」→「乙：加一個 ag.load (Recommended)」；「ag.load 第一刀……要現在開工，還是等整套 Python 庫規劃回來？」→「等規劃回來」。規劃（aos-pylib-1119）回來後頂層派工。
- 同批裁定照守：繼承只在生成時（N-70）；跑著長出來的不收回（連差異頁也不做）；狀態機每隻一層先不做；出處只寫在原始碼（未單獨裁）；「C 與 .o」（重生直接蓋、不記帳）；命名空間 B。
- 範圍＝04「最小可試的一刀」加派工單點名的 HOOKS 帶標記、ag.fsm 換格（04 原分在刀 2，派工單併進這一刀）。讀手寫夾（`ag.from_folder`，04 刀 3）沒做。

## 做了什麼

| 檔 | 改了什麼 |
|---|---|
| `py/aos/agent_spec_load.py`（新） | `ag.load(路徑)`、交回的 `Base`（九個欄位＋`.tools(prefix=, rename=, exclude=)`）、載入隔離、相對路徑換算、一行報錯的 excepthook |
| `py/aos/agent_spec.py` | 轉出 `ag.load`；`ag.main` 被載入時只交欄位、被普通 import 時印一行 warning 不做事；`ag.state` 的 argv／next 可省（只在換格時）；`ag.fsm(底, [...], drop=)` 換格；`defs` 認「底沒宣告 HOOKS」；HELP 多三行 |
| `py/aos/agent_spec_parts.py` | `Hooks`（帶來源標記的 hook 組）；`stack_tools`（墓碑、菱形一邊拿掉一邊留＝SpecBad、說明只列抄進來的包）；`stack_hooks`（兩組同名又不同＝SpecBad、說明裡的範本去重）；`no_hooks` |
| `py/aos/agent_spec_lib.py` | `std.hooks()` 回 `Hooks`（可以 `std.hooks()["timer"]` 取一格） |
| `templates/agent-python/agent.py` | 骨架兩處小洞（pylib 稿 A7）：`$AOS_HOME/lib` 排在自己那夾前面；`except` 也認 `aos.` 開頭的缺模組；錯誤行的程式名改用 agent 夾名（原本 `_found[0]`，排序換了會變成 `lib`）。生出的檔沒變，不用重生（`test_committed_files_match_agent_py` 過） |
| `templates/agent-python/README.md` | 新增「Build on another agent.py」一節；找套件的順序；HOOKS 串列那條補兩組撞名 |
| `py/README.md` | agent_spec 那段補一句繼承第一刀 |
| `py/tests/test_agent_spec.py` | 新增 `Inherit` 八支、`Skeleton` 一支（33 → 42） |

衍生的 `agent.py`（驗收用的那支，骨架開頭照舊）：

```python
base = ag.load("../reviewer")        # runs that agent.py; its ag.main only hands over its fields
std = ag.std

DESCRIPTION = "Review a change and refuse anything without a test."
SYSTEM = base.SYSTEM + "Refuse a change that has no test.\n"
TOOLS = [base.TOOLS,
         ag.no("grep"),                                        # take one tool of the base out
         std.tool("base/peek_now_time", name="now")]           # one tool more
HOOKS = [base.HOOKS, {"timer": {**base.HOOKS["timer"], "every_ms": 60000}}]   # one field of one hook; on_error stays
ag.main(DESCRIPTION, SYSTEM, TOOLS, base.LLM, base.FSM, hooks=HOOKS)
```

## 驗收

實測：`git archive HEAD`（最後一次 `ee96fd190`）抄到 `~/.aos/scratch/aos-inherit-cut1-1119/repo/`、疊上本線的檔，在那份裡 `install.py`；腳本先 unset 所有 `AOS_*`（`mk.sh`、`try1.sh`、`try2.sh`、`live.sh`）。

| 條 | 結果 |
|---|---|
| `reviewer` → `strict-reviewer`：多一支、system 加一句、hook 改一欄不丟 `on_error`、拿掉一支 | 過。工具差 `-grep +now`；`system.txt` 多一行；`timer` 只有 `every_ms` 300000→60000，`on_error: continue`、`timeout_ms` 留著；其他 hook 與底一樣 |
| 生成後 json 完整、沒有上一層痕跡 | 過。`fsm.json`、`loop.json`、`llm.json`、`_entry`、`body.json` 與底逐位元相同；全夾找不到 `reviewer/`、`ag.load`、暫存夾路徑、`$override`、`extends`；`tools.json` 說明列的是 `std.pack('look')…`（底抄進來的包），不提底 |
| `agent_def check` | `{"problems": []}`、退 0 |
| 假腦起一隻實跑 | start-api 樹、root＋llm daemon、`ctl add` 衍生那夾：生效工具 18 支有 `now` 沒 `grep`；生效 `timer` 是 60000＋`on_error: continue`；送一封、腦請求的 system 是兩句合起來的；假腦回「FAKE ANSWER to: hello inherit…」。收尾兩個 daemon 各 `shutdown`，`pgrep -af aos-` 空 |
| 底改了 → 下游重生才跟上 | 過（`test_upstream_change_follows_at_regeneration_only`）：底的 agent.py 多一個包，下游夾不變；下游重生後有了，底自己的 json 從沒寫過 |
| 菱形（兩條路到同一底、一邊 `ag.no`）→ 報錯 | 過：`tool grep is taken out in ag.load('…/d1') but kept in ag.load('…/d2')`；hook 一邊 `None` 一邊有也報；明寫 `ag.no`／`ag.tool`／`{"timer": None}` 就過。經 agent.py 是一行、夾裡不寫 |
| 直接 `import` 另一支 agent.py 的舊坑 | 被取代：被 import 的那支 `ag.main` 印一行 `reviewer: warning: … was imported, not run, so its ag.main(...) does nothing; to build on another agent.py, use base = ag.load("its folder")`、不做事；底那夾沒被寫、衍生那夾照常寫、退 0 |
| 既有 33 支 `test_agent_spec` 不退步 | 過；連新的共 42 支過，`test_aos_py`（別線剛交的入口）13 支一起跑也過 |

另驗：載入錯誤（夾不在、夾裡沒 agent.py、底有 NameError（帶行號）、底沒叫 ag.main、底的宣告寫錯、a 載 b 載 a、用到底手寫的欄位、取底沒有的 hook、路徑不是字串）`--write-defs`／`--defs` 都是一行 `derived: error: SpecBad …`、退 1、夾裡不寫；`sys.path` 與底 import 的模組載完還原（底與衍生各有一支 `helper.py`，各拿各的）；底的相對路徑（工具 path／env_file、hook handler、狀態格 argv 裡底那夾真有的檔）換算成底那夾的路徑，底用 `ag.env` 指時寫成指示詞；README 那段例子原樣貼進 agent.py 跑得通。`from aos.py.agent import defs` 之後 `defs.load` 就是 `ag.load`（入口轉匯出整個 agent_spec，本線不用做事）。

## 自己定的細節（設計稿沒講、又非定不可）

1. **載入方式**：`runpy.run_path(檔, run_name="__main__")`——底那支有沒有寫 `if __name__ == "__main__":` 都能載；載入期間把底那夾排在 `sys.path` 第一（跟 python3 跑一支檔一樣），載完還原。
2. **一行報錯**：在 `ag.load` 第一次被叫時裝一個 `sys.excepthook`，只把沒人接的 `SpecBad`／`DefBad` 印成 `名: error: SpecBad …`（其他例外照舊 traceback）。這樣載入錯、用到手寫欄位、取不存在的 hook 都在 agent.py 最外層一行報；REPL 裡也是一行、不殺行程；測試裡是普通例外。
3. **手寫（by_hand）欄位＝用到才報**：07 A7 說「by_hand 欄報 SpecBad」，這裡做成「讀那個欄位才報」，衍生那支自己寫 SYSTEM 時，底的 SYSTEM 是手寫檔也能衍生。
4. **底沒宣告 HOOKS**：交回一個空的組、標「沒宣告」；單獨給、或串列裡只有這種＝當作沒宣告，不生 `hooks.json`（跟底一樣）。
5. **相對路徑換算的範圍**：工具的 path、env_file 與 hook 的 handler 一律換（它們本來就從定義夾算）；狀態格 argv 只換「底那夾裡真有這個檔」的那幾個字（`python3` 這種指令不動；aos-fsm 本身是從 cwd 算、不轉）。換成絕對路徑會把底那夾的路徑寫進 json——只在底用了相對路徑時發生，README 照舊勸用 `ag.home`／`ag.env`。
6. **hook 兩組撞名怎麼解**：兩組（Hooks）之間同名又不同＝SpecBad，**除非自己寫的 dict 在兩組之後明寫了那一格**（＝選好了）；寫在兩組中間的不算。自己寫的 dict 照舊「後面的蓋前面」整格換。
7. **json 不留上一層**：`tools.json`／`hooks.json` 的說明只列抄進來的包與範本（從底那裡一路帶上來、去重），不寫 `ag.load(...)`；04 原寫「tools.json 的 description 有一句從哪抄的」，照派工單「不留上一層」改成不寫底。
8. **`ag.state` 可省的欄位**：`argv`、`next` 省了只在 `ag.fsm(底, …)` 換底的同名格時合法；`timeout_ms` 省了＝沿用底的（沒辦法用省略來「拿掉」底的 timeout）。換格不提供改起點（`drop` 掉起點＝SpecBad）。
9. **`ag.load` 的路徑**：資料夾（找裡面的 agent.py）或直接給 `.py` 檔；相對路徑從叫它那支 agent.py 的夾算，REPL 從 cwd；也收 `ag.env(...)`。
10. **普通 import**：04 寫「什麼都不做直接回」；這裡多印一行 warning 指向 `ag.load`，免得悄悄沒作用。
11. 載入的程式放新檔 `agent_spec_load.py`（agent_spec.py 已過 300 行，照第三刀拆檔的理由）。

## 收緊了哪些已交行為（要告訴使用者）

1. **06「設計者直接定」第 4 條：兩個帶標記的 hook 組互撞改成報錯。** 以前 `HOOKS = [std.hooks(), std.hooks("eca-claude")]` 是後面那組悄悄蓋掉前面的同名 hook；現在 `brain_notify`、`context_wrap` 這兩格內容不同，會報 `SpecBad hook brain_notify comes from both std.hooks('agent-fsm') and std.hooks('eca-claude')…`，要在後面自己寫一個 dict 選一格。`agent-fsm` 配 `eca-pi` 同名的兩格內容一樣，不受影響。repo 裡（範本、測試）沒有人這樣寫。
2. 被普通 `import` 的 agent.py，`ag.main` 不再照 argv 寫檔與退出（改成一行 warning、不做事）——這是修 02 結論 5 的坑，算修 bug。
3. 骨架找套件改成 `$AOS_HOME/lib` 優先：同時有 `$AOS_HOME/lib/aos` 與 agent.py 旁邊的 `aos/` 夾時，以前用旁邊那份、現在用 `$AOS_HOME` 那份。README 原寫的順序跟著改。
4. `std.hooks()` 的回傳從 `{"kind": "stock_hooks", "template", "hooks"}` 換成一個 dict（就是那張 hook 表、帶標記）。只有 agent_spec 自己讀它，對外沒有人用那個形狀。

## 沒做的與為什麼

- `ag.from_folder`（把手寫的 json 夾讀成底，04 刀 3）：不在第一刀。沒有 agent.py 的定義（`templates/reviewer` 這種）仍只能 `agent_def new` 抄。
- 改起點、工具「只改一欄」：04／07 A9 定了工具不提供；起點沒人提，先不做。
- 出處另記一個鍵：照第 5 題暫定 a，只在原始碼（`grep 'ag.load('`）。`lineage` 沒碰。
- 規範條文（N-70）沒動：另一條文件線在寫。
- `gdb_` 前綴不擋（06 直接定第 7 條）。

## 要使用者拍板的

- 收緊第 1 條（兩個範本的 hook 組互撞改報錯）照 06 直接定做了；不喜歡可改回「後面的蓋前面」只對範本、留報錯給 `ag.load` 的底。
- 其他照推薦先走，沒有新題。

## 使用者親手試的最短步驟

```sh
mkdir -p ~/t/reviewer ~/t/strict && cd ~/t
cp $AOS_HOME/templates/agent-python/agent.py reviewer/
head -22 reviewer/agent.py > strict/agent.py
cat >> strict/agent.py <<'EOF'
base = ag.load("../reviewer")
SYSTEM = base.SYSTEM + "Refuse a change that has no test.\n"
ag.main("Strict one.", SYSTEM, [base.TOOLS, ag.no("grep")], base.LLM, base.FSM)
EOF
python3 strict/agent.py --defs | head -40      # 看一眼：整份、沒有 reviewer 字樣
python3 strict/agent.py --write-defs           # reviewer/ 那夾一個檔都不會多
```

（`$AOS_HOME` 要是裝過這一刀的那份；家機／公司機的活樹今天沒裝。）
