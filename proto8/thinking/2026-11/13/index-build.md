# 把 repo 的 index 建好建滿：每個資料夾一份生成的 `_index.json`，從 repo 根用 `index_view` 一路往下都看得到每樣東西是什麼（11-13 公司；階段一文件區已鋪，階段二程式區等停樹後）

← [11-13 日索引](README.md) ・ 前情：[11-12 index](../12/index.md)（格式、天然位置）、[index-link](../12/index-link.md)（`index` 連到下一份）、[index-tools](../12/index-tools/README.md)（`index_view`）、[ops-agent 六點建議](ops-agent-six-suggestions/01-原信.md)（第 2、3 點：沒有索引檢查工具、字串形條目）

## 使用者原文

> 「對了，可以派fable去把index建好建滿，其子agent隨意開」

## 決定（調度者的讀法，照做）

- 對象是這份 repo：repo 頂層、`wf/`、`proto8/`。用 aos 自己的 index 機制（資料夾的 `_index.json`，每項 `名: {"description": …}`，子夾那一項帶 `index` 連到它自己的那一份），讓 agent 用 `index_view` 從 repo 根往下走，每一層都看得到底下每樣東西是什麼。
- 分兩階段：階段一文件區（repo 頂層、`wf/` 整棵、`proto8/` 頂層一份、`proto8/docs`、`proto8/thinking`、`proto8/notes`、`proto8/user-advice`）；階段二程式區（`proto8` 的 lib、cmd、py、templates、kernel、impls、extras、knowledge、cases、feedback）等 11-13 下午停樹重抄之後才放。

## 結論：規格

**放什麼檔**：每個資料夾一份 `_index.json`（獨立那份；不用 `_metainfo.json` 裡的 `index`）。整份由 `wf/tools/index_gen.py` 生成，不手改；要改某一句就改來源（檔頭那一句，或手寫句的檔）再重生。

**一項長什麼樣**：一律物件形 `名: {"description": "一句話"}`；子夾自己也有 `_index.json` 時多一欄 `"index": "子夾/_index.json"`（相對所在的夾，照 index-link 的算法）。鍵＝夾裡的名字（檔名或子夾名），照名字排序；`_index.json` 自己不列。

**列哪些**：`git ls-files` 有的檔，與裡面有這種檔的夾（沒進版控的、被 `.gitignore` 擋掉的不列）。到檔為止，不進檔內（json 檔裡面的節點不建；knowledge 既有的檔內 `_index` 照舊）。

**一句話從哪來**（由上往下，先有的算數）：

1. 手寫句：`wf/tools/index_gen_desc.json`（repo 相對路徑 → 一句話）。子 agent 讀過內容後寫的，用在檔頭取不到或取到的不夠用的地方（只寫「結論」「一覽」、同夾重複、沒有 README 的夾、圖與紀錄檔），與所有往下走的路口（資料夾）。
2. 檔頭那一句（鐵律 3 本來就要求每個檔第一行一句話）：md 取第一個標題，分檔取導航行的「涵蓋：…」；夾取它的 README.md／INDEX.md，工具夾取 `_tooldef.json`／`_metainfo.json`，同名 `x.md` 拆出來的分檔夾取 `x.md` 的；json 取 `description`／`summary`／`$comment`／`title`，`wf-table/1` 資料檔寫出處、列數與欄位；程式檔照 `codemap_gen.py` 的認法（同一個函數）；html 取 `<title>`。markdown 連結與粗體去掉、只留字；超過 200 字截斷。
3. 通用句：`index_gen.json` 的 `usual_dirs`／`usual_files`（`tests`、`src`、`.gitignore` 這類名字就說明用途的）。
4. 都沒有＝`DescMissing`，生成器退 1，要人補。

**一句話怎麼寫**（手寫句的標準）：一句、不換行，先講這是什麼（主題＋性質：條文／討論紀錄／規劃／施工結果／腳本…），有幫助時接什麼時候來看它；20～80 字為宜、最多 120 字；代號（N-69）、日期、檔名、指令名照寫，當檢索詞；不放連結語法、家目錄絕對路徑、帳號名。

**語言**：repo 的文件區與程式區用繁體中文（照所在區域的文件語言）；`proto8/knowledge` 照它既有的英文（那是給 aos 裡的 agent 讀的出廠內容）。

**多深**：範圍內每一層資料夾都建，不設「夠小就不建」的門檻。大夾不另分冊：資料夾本來就按月、日、主題分層（`thinking/2026-11/13/…`），每層一份、上一層用 `index` 連下去；目前單一夾最多四十幾項，`index_view` 一頁（200 項）放得下。

**不建的地方**（裡面不放 `_index.json`，只在上一層留一項、不帶 `index`）：任何一層叫 `archive` 的夾（封存的當它不存在，要找看它的 README）、`.git`、`.claude`、`.vscode`、`__pycache__`、build／install／vcpkg 產物（本來就不在 git 裡）、`wf/inbox`（信件來來去去，建了馬上過時）。

**跟既有 README／INDEX／code map 生成冊不重複**：一句話取自它們的來源（檔頭），不另抄一份；README 是給人讀的導引，code map 生成冊是「哪個程式檔負責什麼」的 md 表，`_index.json` 是給 agent 用 `index_view` 看的同一句話。來源只有一處，改檔頭、重跑兩支生成器。

## 結論：腳本

- `wf/tools/index_gen.py`：生成。不帶參數＝檢查（跟磁碟上的一致退 0，不一致印 `IndexStale`、退 1）；`--apply` 寫進 repo；`--out DIR` 寫到別處先看；`--stage N` 只做前 N 階段的範圍；`--config FILE` 換一份範圍設定。
- `wf/tools/index_gen.json`：範圍（哪些夾、要不要連底下每層、第幾階段）、不建的夾、通用句。
- `wf/tools/index_gen_desc.json`：手寫句。
- `wf/tools/index_check.py`：查任何一棵樹的 `_index.json` 跟實際對不對得上，不靠生成器：`EntryGone`（列了但不在）、`EntryMissing`（在但沒列；`--view` 關掉）、`LinkBad`（`index` 指不到）、`LinkMissing`（子夾有 index、上一層沒連）、`IndexBad`（形狀不對，含字串形條目）。不在 git 裡的樹（如裝好的 knowledge）自動照磁碟算。這就是 ops-agent 第 2 點要的那種檢查，先做成 repo 的腳本，沒做成 aos 工具。
- 測試：`wf/tools/tests/test_index_tools.py`。
- 維護：新增、刪除、搬檔或改了檔頭那一句之後跑 `python3 wf/tools/index_gen.py --apply`（跟 `codemap_gen.py --apply` 同一個時機），再跑 `python3 wf/tools/index_check.py`。

## 代定（可翻）

- X1 範圍內每個夾都建、不設門檻。使用者 11-12 說過「如果夠小，那其實也不用做看法了，直接讀就是了」；這次照「建好建滿」每層都建，好處是從根往下每一步 `index_view` 都有東西。
- X2 一句話預設跟著檔頭走、不夠用才手寫；手寫句集中放一個檔，`_index.json` 整份是生成物。
- X3 語言照所在區域：repo 繁中、knowledge 英文。
- X4 `archive` 夾裡不建。
- X5 `wf/inbox` 裡不建。
- X6 `proto8/notes`、`proto8/user-advice` 算文件區，放進階段一；`proto8/cases`、`proto8/feedback` 跟程式區一起階段二。
- X7 只列進版控的檔。別條線還沒 commit 的新檔不會出現，等它們進了 git 再重生。
- X8 用獨立的 `_index.json`，不放進 `_metainfo.json` 的 `index`。

## 結論：會不會踩到東西（放之前逐項查過，讀程式碼判斷）

不會壞的：

- `wf-lint`：只查 md 與帶 `"contract": "wf-table/` 的 json，`_index.json` 整份略過。鋪完後 wf `broken=0`、proto8 `broken=11`，都沒變多。
- `extras/gitignore-check`：查的是它自己臨時建的假專案，不查 repo。
- 工具夾、agent 定義的辨認：只看 `_entry`、`_tooldef.json`、`_metainfo.json`、`interfaces.json`，不列夾內容；`aos-tools`、`aos-exec` 不受影響。工具夾的 `_metainfo.json` 現在都沒有 `index` 鍵，`index_view` 只會看到 `_index.json` 這一層。
- C++：CMake 只 glob `src/*.cpp`／`*.c`；程式列目錄的地方都是跑起來才有的夾。
- `install.sh`：只連結 `bin/` 裡可執行的檔。
- wf 的腳本（inbox、progress_board、decide_page、metainfo_migrate）：都按名字或 `*.md`、`decide_*.json` 找，不受影響。

會改變輸出、不會壞的：

- code map 生成冊：原本每份 `_index.json` 會在生成冊多一列「設定（鍵：…）」；調度者同意後 `codemap_gen.py` 的略過名單加了 `_index.json`（a993379be），生成冊不再列 index（knowledge 既有三份的列也拿掉了）。
- 腦用的 `ls`、`glob` 等看到的子項多一個。

放了會壞、所以不放的（階段二照這張表避開）：

| 夾 | 原因 |
|---|---|
| `templates/tool-python/` | 兩支測試寫死夾裡剛好五個檔；`tools_def new` 還會把它抄進每個新工具 |
| 範本與 kernel 的定義夾（有 `interfaces.json` 的夾，連裡面的格夾） | `agent_def new` 整夾抄出去，新定義會帶著這份；`aos-grow down` 會把 index 的鍵當成「別處還在叫這個名字」而拒收，只有 `_entry` 的格夾多一個檔會報 `TargetBad` |
| `cases/<套>/<案例>/expect/`、`ws/` | `expect/` 底下每個檔都算一份預期輸出，多一個檔比對就不過；`ws/` 整夾抄進工作區 |
| `lib/packs/` | 一支測試讀這夾每份 json、斷言不含 `mcp_tool` 字樣 |
| 各 `bin/` | 只該放那一支指令 |
| `wf/inbox/` | 放信處只放信 |

## 階段一結果（文件區，已鋪）

- 305 份 `_index.json`、1915 項：repo 根 1 份 10 項、`proto8/` 頂層 1 份 17 項、`proto8/docs` 22 份 158 項、`proto8/thinking` 206 份 1220 項、`proto8/notes` 5 份 21 項、`proto8/user-advice` 2 份 11 項、`wf/` 68 份 478 項。
- 一句話的來源：手寫 528 句（七個 opus 子 agent 分區讀內容後寫：所有資料夾，與檔頭取到的太短、同夾重複、取不到的檔），其餘跟著檔頭走。
- `index_check.py`：`0 problems`（含 knowledge 既有三份：82 項，沒有列了不在、在了沒列、連結指不到的）。
- `index_view` 從 repo 根往下走：`{"path": "."}` → `proto8`、`wf` 兩項帶 `index:`；`{"path": "proto8/thinking/2026-11", "key": "13"}` → 當天主題一句話與下一份的路徑；`{"path": "wf/workflows/dispatch"}`、`{"path": "proto8/docs/NORMS"}` 都看得到每一項。
- 子 agent 順手看到、沒動的：幾份 thinking README 的標題還寫舊狀態（「未施工」「沒改程式」，夾裡其實已施工），手寫句照夾裡後來的結果寫；`proto8/user-advice/2026-09/aos-tools.md` 只有標題；`wf/session_logs/2026-11/README.md` 的 11-06 那一列有一段重複貼了兩次。

## 給使用者看的

- **「建滿」的其他讀法**（這次先照「這份 repo」做）：一是也包含裝好的那棵樹自己長出來的東西（`~/aos-home` 的 ws、agents、stack；那裡的 lib、templates、knowledge 是從 repo 抄過去的，repo 鋪好、重抄就有）；二是只指 `proto8/knowledge` 這棵出廠內容樹（已有三份，缺的階段二補）；三是連 json 檔裡面的節點也建（檔內 `_index`）；四是 `archive/` 與 `impl_cpp/` 裡面也建。
- **`impl_cpp/` 裡面不建**（調度者同意）：那是使用者親手寫的夾，只在 repo 根留一項。
- **範本與 kernel 的定義夾裡面不放**（原因見上表）：這些夾只在上一層有一句話，`index_view` 走不進去。
- **維護要不要掛進規矩**：兩個方案在下面「維護」，待使用者裁；裁之前靠記得跑。

## 維護

- **什麼時候跑**：新增、刪除、搬動、改名任何進版控的檔或夾，或改了某個檔的檔頭那一句（md 的第一個標題、README 標題、json 的 `description`、程式檔第一行）之後，commit 前跑 `python3 wf/tools/index_gen.py --apply`，改到的 `_index.json` 跟著同一個 commit。新檔要先 `git add` 才列得到（只列進版控的）。
- **取不到一句話**：生成器印 `index_gen: error: DescMissing 路徑`、退 1。補檔頭那一句；檔頭放不了的（圖、紀錄檔、沒有 README 的夾）在 `wf/tools/index_gen_desc.json` 加一筆 `"路徑": "一句話"`。搬檔、刪檔後手寫句的舊路徑也會報 `DescMissing …(in index_gen_desc.json but not in the repo)`，把那筆改成新路徑或刪掉。
- **只想檢查**：`python3 wf/tools/index_gen.py`（不寫檔）：每份該改的印一行 `IndexStale 哪一份 is missing／differs from the file headers`，退 1；都一致退 0。
- **`index_check.py` 報什麼**（`python3 wf/tools/index_check.py [夾…]`，不靠生成器、任何一棵樹都能查）：`EntryMissing 哪一份: 名 is there but not listed`（加了檔沒重生）、`EntryGone …: 名 is listed but not there`（刪了或搬了沒重生）、`LinkBad …: 名: index 路徑 points to nothing`（子夾的 index 不見了）、`LinkMissing`（子夾有 index、上一層沒連）、`IndexBad`（形狀不對，例如條目寫成字串）。最後一行總數，有問題退 1。
- **新開一個要建 index 的區域、或某個夾裡面不能放**：改 `wf/tools/index_gen.json` 的 `scopes`、`skip_dirs`／`skip_dir_names`；手寫維護、不要生成器碰的那幾份寫進 `hand_indexes`。

**掛進規矩的兩個方案（待使用者裁，hub 檔沒動）**：

- （甲）改鐵律 3。`AGENTS.md` 鐵律 3 的粗體句「**新檔第一行（腳本跳過 shebang 的第一行）寫一句話；commit 前跑 `python3 wf/tools/codemap_gen.py --apply`**」改成「**新檔第一行（腳本跳過 shebang 的第一行）寫一句話；commit 前跑 `python3 wf/tools/codemap_gen.py --apply`，並跑 `python3 wf/tools/index_gen.py --apply`**」；同一條後段「改檔頭那一句、重生，跟程式同一個 commit」不用改。後果：每個 commit 多跑一支（約一秒），index 永遠跟得上；文件區的 commit 也要跑（code map 那支原本只管程式）。
- （乙）不改鐵律，`wf/tools/wf-lint.sh` 多查一項。在 CODEMAP 那一關後面加一關 `INDEX`：repo 根有 `wf/tools/index_gen.py` 時跑 `python3 wf/tools/index_gen.py --quiet` 與 `python3 wf/tools/index_check.py --quiet`，任一支退非 0 就印 `INDEX <那支印的錯誤行>`、計入 `broken`（SUMMARY 多一欄 `index=N`）；`.claude/commands/wf-lint.md` 補一句「`INDEX` 表示資料夾的 `_index.json` 跟實際的檔對不上，修法是跑 `python3 wf/tools/index_gen.py --apply`」。後果：平常不用記，跑 wf-lint 時才發現過期、那時再重生；兩次 wf-lint 之間 index 可能缺幾項。注意現在 `/wf-lint` 照慣例只掃 `wf` 與 `.claude/commands`，CODEMAP 那關的條件是掃的根底下有 `proto8/`，所以平常沒跑到；`INDEX` 這關要寫成不看掃哪個根、每次都跑，才有用。
- 兩個可以都做。
