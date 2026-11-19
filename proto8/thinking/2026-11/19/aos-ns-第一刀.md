# 命名空間第一刀（線 aos-ns-cut1-1119）：agent.py 有了庫 std 與 ag.lib，包在生成時展開進 tools.json，別的庫的工具自動帶「庫名_」、撞名報 SpecBad；只改 agent_spec，執行期一行沒動、沒搬檔

> 11-19 之後 `ag` 改叫 `defs`（`from aos.py.agent import defs`），見 [aos-pylib-1119/07](aos-pylib-1119/07-使用者裁定.md#補寫定義的名字-ag-改叫-defs11-19線-aos-defs-rename-1119)。

← [2026-11-19](README.md)｜設計稿：[aos-ns-1119](aos-ns-1119/README.md)（[03 的 B](aos-ns-1119/03-設計選項.md)、[05](aos-ns-1119/05-邊緣狀況與要拍板的題.md)、[07 使用者裁定](aos-ns-1119/07-使用者裁定.md)）｜前一刀：[庚第三刀](aos-compile-庚-第三刀.md)

使用者 11-19 被問「命名空間第一刀（只改 agent_spec、不搬檔）要現在開工嗎？」答「開工」。照 07 的裁定做：走 B「資料夾即命名空間」、腦看到 std 短名、別的庫加前綴、std 先不搬、照叫 std。**第 6 題（別的庫的路徑在 `agent.py` 明寫）、第 7 題（包改成生成時展開、抄）是「暫照推薦、使用者未單獨裁」，這刀照推薦做，仍是暫定。** 今天已裁的照舊：重生直接蓋、不記帳（「好比C語言和.o之間的關係」）；骨架不帶 hook；hook 組是抄；第二刀（check 順手重生）不做。

## 先講結論

1. `agent.py` 現在寫 `std = ag.std`、`std.pack("look")`、`std.fsm()`、`std.hooks()`；別的庫 `my = ag.lib("my", ag.env("AOS_WS", "/lib/my"))`、`my.pack("look")`、`my.tool("read")`。`ag.pack`、`ag.stock_fsm`、`ag.stock_hooks` 拿掉，不留別名（proto8 當沒有舊版；05「設計者直接定」那條）。
2. **包在生成時讀出、一支支抄進 `tools.json`**，不再寫 `$override`；json 裡只有全路徑（指示詞或絕對路徑），不留庫名。別的庫的工具自動叫 `my_read`，std 照舊 `read`。展開後兩個包給同一個名字、內容又不同＝一行 `SpecBad`，不再悄悄蓋；內容完全相同（菱形）算同一支。
3. 驗收全過（下面逐條），起樹實跑：假腦依序叫 `read` 與 `mylib_read`，前者回 std 那支讀到的字、後者回小庫那支的「mylib read: …」。
4. 執行期（aos-tools、registry、aos-agent、daemon、cpp）一行沒動；沒搬任何檔。代價：跑 `agent.py` 一定要設 `AOS_HOME`（要讀包），骨架的 `tools.json` 從三行 `$override` 變成 19 支工具列出來。

## 改了哪些檔

| 檔 | 改了什麼 |
|---|---|
| `py/aos/agent_spec_lib.py`（新） | 庫：`Lib`（`pack`、`tool`）、`Std`（再加 `hooks`、`fsm`）、`std`、`lib()`；`STOCK_CELLS` 從 `agent_spec.py` 搬來 |
| `py/aos/agent_spec.py` | 拿掉 `pack`、`stock_fsm`、`stock_hooks`；轉出 `std`、`lib`；`ag.tool` 的路徑可給某個庫的 `.tool(...)`；檔頭與 `--help` 補一句「包在跑 agent.py 時讀，要設 AOS_HOME」 |
| `py/aos/agent_spec_parts.py` | `tools_json` 改成疊展開好的包：明寫的工具整格換、`ag.no` 拿掉、撞名報錯、只出 `tools` 表；訊息裡舊名換新名 |
| `templates/agent-python/agent.py` | `std = ag.std`、`std.pack(...)`、`std.fsm()`；註解帶一句別的庫怎麼寫 |
| `templates/agent-python/tools.json` | 用 `python3 agent.py --write-defs` 重生（不手改）；其他生成檔重生後一字未變 |
| `templates/agent-python/README.md` | `TOOLS`、`FSM`、`HOOKS` 改新寫法；加「Libraries」一節（英文） |
| `py/tests/test_agent_spec.py` | 舊寫法全換；eca 那條改成「展開後的工具表＝範本 `$override` 疊出來的那張」；reviewer 改寫版用 `std.tool(...)`；新加 `Namespace` 六支 |
| `py/README.md`、`templates/README.md` | 各補一段第一刀 |

知識庫（`knowledge/`）沒有講 `agent_spec`／`agent.py` 的條目（庚到現在都只給人用），沒改。C-74、C-87 條文照任務書沒改（07 的建議字句仍待使用者點頭）。

## agent.py 現在長怎樣

```python
std = ag.std                # the library that comes with aos; another one: my = ag.lib("my", ag.env("AOS_WS", "/lib/my"))

TOOLS = [std.pack("look"), std.pack("mailbox"), std.pack("json")]   # copied into tools.json tool by tool

LLM = {}

FSM = std.fsm()             # the four cells of the agent-fsm template: idle, think, wait, act
```

驗收那支多兩行：

```python
mylib = ag.lib("mylib", ag.env("AOS_WS", "/lib/mylib"))
TOOLS = [std.pack("look"), mylib.pack("look"), std.pack("mailbox"), std.pack("json")]
```

生出來的 `tools.json` 那兩格：`"read": {"path": {"$env": "AOS_HOME", "$path": "/lib/tools/base/read"}}`、`"mylib_read": {"path": {"$env": "AOS_WS", "$path": "/lib/mylib/tools/read"}}`。

## 驗收

暫存樹 `~/.aos/scratch/aos-ns-cut1-1119/tree`（`start-api` 抄出來），程式在 `git archive` 乾淨複本 `copy/proto8` 疊上改動後 `install.py` 裝的；腳本 `acc.sh`、輸出 `acc.out`。

| # | 驗什麼 | 結果 |
|---|---|---|
| 1 | 工作區放小庫 `lib/mylib`（`tools/read`、`packs/look.json`，包裡寫相對路徑 `../tools/read`），它和 std 都有 `read`；一支 `agent.py` 兩個都用 | `--write-defs` 退 0；`tools.json` 沒有 `$override`，`read` 指 `$AOS_HOME/lib/tools/base/read`、`mylib_read` 指 `$AOS_WS/lib/mylib/tools/read` |
| 2 | 腦看到 `read` 與 `mylib_read` | `aos-tools --file agents/ns/tools.json ls`、掛上後 `aos-agent --target ns tools ls` 都列兩支，說明各是各的；`agent_def check` 回 `{"problems": []}` |
| 3 | 假腦起一隻、兩支各叫得到各自那支 | 劇本假腦（樹裡的 kernel.json 加一組 `fake-ns`）先叫 `read`、再叫 `mylib_read`：history 裡前者回 `hello from note.txt`、後者回 `mylib read: hello from note.txt`；信回「read and mylib_read both answered.」。兩台 daemon 用 shutdown 收掉，收尾 `pgrep -af aos-` 沒有 |
| 4 | 故意撞名 | `mylib.pack("look", prefix="")` → `ns: error: SpecBad tool read comes from both std.pack('look') and mylib.pack('look'), and they differ: rename one (prefix= or rename=), leave one out (exclude=), or pick one with ag.tool('read', ...) (fix the declaration in agent.py)`，退 1、沒寫檔 |
| 5 | 庫根不存在 | 根寫成 `/lib/nolib` → `SpecBad ag.lib('mylib'): the root of library mylib, …/tree/lib/nolib, is not a folder`；`AOS_WS` 沒設 → `SpecBad ag.lib('mylib') reads $AOS_WS/lib/mylib, but AOS_WS is not set (set it when you run agent.py)`，都退 1 |
| 6 | reviewer 改寫版仍與手寫等價（第三刀的驗收） | 改用 `std.tool("aos/…")`、`std.tool("base/…")` 寫，生出來跟 `templates/reviewer` 手寫的逐檔等價（`Reviewer` 那支測試） |

測試（都在乾淨複本 install 後跑）：`test_agent_spec` 33 支全過（原 27 支照新寫法改＋`Namespace` 6 支：兩個 read 各指各的、`std.tool`／`my.tool`／prefix／rename／exclude、撞名與三種解法、菱形、18 種寫錯各一行、經 `agent.py` 撞名一行且不寫檔）；順手跑 `test_install` 11、`test_hooks_engine` 5、`test_tool_spec` 10、`test_declared_files` 7、`tools/aos/defs/tests/test_defs` 19、`templates/tests/test_start` 全過。

## 我自己定的細節（設計稿沒講、又非定不可）

1. **`std` 是 `Lib` 的特例**：根＝`{"$env": "AOS_HOME", "$path": ""}`，包在 `lib/packs`、工具在 `lib/tools`、hook 組與 fsm 格在 `templates/`（Argon A6）。所以 std 生出來的路徑跟今天包裡寫的一字不差（`/lib/tools/base/read`）。
2. **別的庫的長相這刀只認兩個夾**：`<根>/packs/<名>.json`、`<根>/tools/<路徑>/`；`_metainfo.json` 不查。別的庫沒有 `hooks`、`fsm`（03 把 hook 組自己的位置排在搬家那刀）。
3. **`ag.lib` 的根只收絕對路徑或指示詞**（`ag.env`／`ag.home`），相對路徑報錯：相對要嘛從 `agent.py` 那夾算、要嘛從輸出夾算，兩種都會讓 `--write-defs 別的夾` 時意思變掉。庫名只准小寫英數、`_`、`-`（跟包名同一條規矩），不准叫 `std`。
4. **讀不到庫根什麼時候報**：`ag.lib(...)` 當下就查，查不到記成壞的庫，**用到它**（`.pack`／`.tool`）才在生成時報 `SpecBad`；宣告了沒用的壞庫不報。
5. **包裡的相對路徑**照 aos-tools 的算法從包檔那夾算，改寫成庫根底下的全路徑；算出來出了庫根＝報錯。指示詞、絕對路徑原樣抄。`env_file` 同樣處理。包檔帶 `$override`＝報錯（這刀不展開疊在別的包上的包；std 的 18 包都沒有）。包裡值是 `null` 的格不算工具、不抄。
6. **`prefix=`、`rename=`、`exclude=`**：`rename` 給的是最後的名字（不再加前綴）；`rename`、`exclude` 的名字是包裡的原名，包裡沒有＝報錯；兩個都寫同一支＝報錯。前綴只准英數、`_`、`-`；加完超過 64 字＝報錯。
7. **故意與碰巧**：明寫的 `ag.tool(名, …)`、`std.tool(...)`、`my.tool(...)` 整格換掉包裡同名那支（故意，05 第 7 條）；`ag.no(名)` 拿掉那個名字（兩個包都有就兩個一起拿，要只拿一邊用 `exclude=`）；`ag.no` 一個沒有任何包給的名字＝報錯（以前是寫一格 `null`）。兩支明寫的同名照舊「listed twice」。
8. **`std.tool("base/read")` 生成時查工具夾在不在**（不在＝報錯、說出完整位置）；所以 `std.tool` 也要 `AOS_HOME`。`ag.tool("read", my.tool("read"))` 只拿那支的路徑。
9. **`std.fsm(組="agent-fsm")`** 只認 `agent-fsm`（std 今天只有這一組），生成時不讀檔（跟 `stock_fsm` 一樣是借）。`std.hooks(範本)` 就是原本的 `stock_hooks`，行為不變。
10. **`tools.json` 的 description 多一句**「agent.py copied in the tools of std.pack('look'), …」，給人看這張表是從哪幾包抄來的；腦不讀這句。
11. 庫的程式放新檔 `agent_spec_lib.py`（`agent_spec.py` 原本已過 300 行）；它用到 `agent_spec` 的 `tool`、`fsm`、`state` 時在函式裡才 import（避開互相 import）。

## 暫定的兩點（使用者沒單獨裁）

- **第 6 題 a**：別的庫的根在 `agent.py` 明寫（`ag.lib("my", 路徑)`），庫名只在那支檔裡有效。沒有固定庫夾、沒有 `AOS_LIB_<名>` 變數。
- **第 7 題 a**：包在生成時展開、抄進 `tools.json`。包之後多加的工具要重跑 `--write-defs` 才拿得到；工具本身的程式仍是借的（修 bug 不用重生）。

## 沒做的與為什麼

- **std 搬進 `lib/std/`、拍平類夾、hook 組與 fsm 格獨立成夾**：第 4 題裁「先不搬」，03 排在第二刀。
- **`agent_def new` 收 `std/名`、`defs check` 查手寫 json 的同名包**：03 的第三刀。手寫的 `tools.json`、kit、`tools_sub.json`、stack 的 `self_tools` 照舊用 `$override`、照舊悄悄蓋（05 邊緣第 6、23、28 條）。
- **別的庫的 hooks／fsm／範本**：同上，hook 組有自己的位置是搬家那刀。
- **C-74、C-87 加註**：任務書說不要改，07 的建議字句等使用者點頭。
- **知識庫**：沒有給 agent 看的 `agent.py` 條目可改；`agent_def`、知識庫照庚的範圍「先只給人用」。

## 要重建什麼

執行期格式沒變，跑著的 agent 不受影響。用舊寫法（`ag.pack`、`ag.stock_fsm`、`ag.stock_hooks`）的 `agent.py` 會在 `AttributeError` 停下，要改成新寫法；改完重跑 `--write-defs`，`tools.json` 會從 `$override` 變成展開的表（兩種 aos-tools 都讀，結果一樣）。裝好的樹要在那份 proto8 重跑 `install.py` 才吃到新的 `lib/aos/agent_spec*.py`。

## 要使用者拍板的

1. **第 6、7 題要不要正式定**（這刀照推薦做了）：
   - 第 7 題 a 定下（推薦）：撞名報錯、前綴都靠它；代價是 `tools.json` 變長、包加工具要重生。改 b（照舊借 `$override`）＝這刀的前綴與撞名報錯都要拿掉，回到 A 式慣例。
   - 第 6 題 a 定下（推薦）：零新機制；兩台機器路徑不同靠 `ag.env`。改 b（一台一個固定庫夾）或 d（`AOS_LIB_<名>` 變數）＝要加一條固定位置或一族變數，`agent_def new` 才能收 `my/名`。
2. **C-74、C-87 加註**：照 07 的建議字句補（推薦，條文跟現況對得上）；或先不補（條文跟做出來的東西暫時有落差）。
3. （小事，我定的，可改）`ag.lib` 的根要不要准相對路徑：現在不准（理由見細節 3）；准的話要再定「從哪裡算」。

## 使用者親手試（最短）

在裝好這版的 proto8（`AOS_HOME` 指它）與一棵樹裡：

```sh
cd <樹> && source env.sh
mkdir -p lib/my/tools lib/my/packs && cp -r $AOS_HOME/lib/tools/base/read lib/my/tools/read
echo '{"tools": {"read": {"path": "../tools/read"}}}' > lib/my/packs/look.json
cp -r $AOS_HOME/templates/agent-python agents/try && cd agents/try
sed -i 's|^TOOLS = .*|my = ag.lib("my", ag.env("AOS_WS", "/lib/my"))\nTOOLS = [std.pack("look"), my.pack("look")]|' agent.py
AOS_WS=<樹的絕對路徑> python3 agent.py --defs | grep -A3 '"my_read"'      # 看 my_read 指到 lib/my
sed -i 's|my.pack("look")|my.pack("look", prefix="")|' agent.py
AOS_WS=<樹的絕對路徑> python3 agent.py --defs                              # 一行 SpecBad：read 兩邊都有
```
