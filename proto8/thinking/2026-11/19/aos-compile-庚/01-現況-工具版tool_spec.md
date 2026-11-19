# 現況一：工具版 tool_spec 今天怎麼宣告、怎麼重生 json、知不知道生成物被手改過

← [README](README.md)｜下一份：[02-現況-定義夾與agent_def](02-現況-定義夾與agent_def.md)

讀的是 repo HEAD `2f7e94d5a` 的程式本身，不是轉述 11-18 的調查稿。

## 先講結論

1. 工具版的寫法是「一支 `tool.py`，最上面幾個大寫常數，最後一行交給 lib」。庚可以整套照抄這個寫法。
2. 重生的時機是 `tools_def check`：它每次都叫 `tool.py --write-defs`，**無條件蓋掉**兩份 json。
3. **工具版完全不知道生成物有沒有被手改過**：沒有雜湊、沒有記號、不比對。手改的字在下一次 check 無聲消失。這在工具那格問題不大（只有兩份檔、很少人手改），搬到 agent 就不夠用了，原因見 [05](05-打架規則-總則.md)。

## 檔在哪

| 東西 | 位置 | 大小 |
|---|---|---|
| lib 本體 | `proto8/py/aos/tool_spec.py` | 291 行，純標準庫 |
| 骨架（給人抄的） | `proto8/templates/tool-python/`：`tool.py`、`_entry.json`、`_tooldef.json`、`_metainfo.json`、`README.md` | 5 檔 |
| 叫它重生的工具 | `proto8/py/tools/agent/tools_def/_entry` 的 `regenerate()` | 第 345～363 行 |

## 怎麼宣告

`tool.py` 分兩段，中間用一行註解 `# ---- your tool: change the lines below ----` 隔開：

- **上半（固定 20 行，不改）**：找 aos 套件。先找自己旁邊，再找 `$AOS_HOME/lib`；找不到印一行錯誤（`ModuleMissing` 或 `HomeMissing`）退 1。
- **下半（使用者改的）**：模組最上層寫 `DESCRIPTION`（字串）、`PARAMS = [ts.param(名, 型別, 說明), …]`、`META`（dict，只寫跟預設不同的）、`def run(args)`，最後一行 `ts.main(run, DESCRIPTION, PARAMS, META)`。

寫錯的處理有一個細節值得照抄：`ts.param()` 發現寫錯時**不在模組最上層丟例外**（那樣會變成一大段 Python traceback），而是先記成「壞的」，等 `main` 再報一行 `SpecBad`，訊息寫成「怎麼改」，結尾附「fix the declaration in tool.py」。

## 怎麼重生

`ts.main` 看命令列的第一個旗標：

| 旗標 | 做什麼 |
|---|---|
| `--tooldef`、`--metainfo` | 把會生成的 json 印出來，不寫檔 |
| `--write-defs [位置]` | 寫檔；位置沒給＝腳本所在的資料夾 |
| 都沒有 | 當工具跑：驗參數、叫 `run`、印結果 |

`tools_def check` 的重生流程：

1. 從入口（`_entry`／`_entry.json`）的 argv 找第一個 `.py`。
2. 讀那支 `.py` 的原始碼，**裡面有 `tool_spec` 這個字串就算「用了 tool_spec」**。
3. 用了就跑 `python3 腳本 --write-defs 位置`（期限 30 秒）。成功印一行 `made  _tooldef and _metainfo from tool.py`；失敗印一行 `bad`，照樣往下查。
4. 沒用 tool_spec 的腳本印一行 `note  … _tooldef and _metainfo are kept by hand`，兩份 json 照舊算手寫的。
5. 重生完再驗內容（`metainfo_problems`、`tooldef_problems`、經 aos-tools 登記試一次、說明裡的例子實跑）。

寫檔的方式（`_write_file`）：先寫同層的暫存檔 `.<名>.tmp-<pid>`，沿用舊檔的權限位，再 `os.replace` 改名。**每一份檔自己是「要嘛舊的、要嘛新的」，兩份合起來不保證**（寫完第一份就當掉，會一新一舊）。

## 知不知道被手改

不知道。讀遍 `tool_spec.py` 與 `tools_def/_entry`，跟「手改」沾得上邊的只有這三處：

| 在哪 | 做了什麼 |
|---|---|
| `tools_def check` | 不比對、不問，直接蓋 |
| `tools_def add_metainfo`／`add_tooldef` | 那份已經在＝`PathExists`，訊息說「for a tool_spec script, change the script and run check」 |
| `templates/tool-python/README.md` | 表格裡寫兩份 json「no, it is generated」（不要改） |

也就是說，工具版的規則是一句話：**Python 贏、每次 check 重生、手改不留也不講**。11-18 晚頂層向使用者解釋庚時說的「照工具那格『Python 贏、重生』」，指的就是這個行為。

## 誰在用、生成物進不進 git

- repo 裡真的用 tool_spec 的只有骨架 `templates/tool-python/tool.py`；`py/tools/` 底下的內建工具都是手寫的 `_entry`（`grep -rl tool_spec py templates` 中的程式只有 lib 自己、它的測試、`tools_def`、與骨架）。所以 tool_spec 的使用者是「之後抄骨架做新工具的人和 agent」。
- 骨架的兩份生成 json **在 git 裡**（`git ls-files templates/tool-python` 列得到）。這是「生成物進 git」在 aos 程式區的現成先例；另一個先例是 `index_gen` 的 `_index.json`。

## 庚可以直接沿用的、與不夠用的

| 沿用 | 不夠用（庚要補） |
|---|---|
| 固定開頭 20 行＋分隔註解 | 手改偵測：工具版沒有 |
| 大寫常數＋最後一行 `main(...)` | 多檔一起寫：工具版只有兩份，沒處理「寫到一半」 |
| 寫錯記起來、`main` 時報 `SpecBad`、訊息寫怎麼改 | 生成物跟別的指令搶同一份檔：工具那格沒有 `agent_def tools` 這種正規的改檔指令 |
| `--write-defs`、印出不寫檔的旗標 | 手寫檔與生成檔混在同一夾：工具夾幾乎全是生成的 |
| 暫存檔＋改名、沿用權限位 | |
| check 時重生、原始碼含 lib 名字就算有用 | |
