# index_check 會不會假綠：拿模板 repo 實測到的五種案例來測 aos 這支（11-13，線黃）

← [11-13 README](README.md)｜調度者：頂層 session `repo-aos`｜施工：線黃

## 起因與使用者的話

模板 repo（workflows）的內容要併進 aos，題 6 使用者說「檢查工具，wf/的那邊就完全不留」（[workflows-into-aos「使用者裁定」](workflows-into-aos.md#使用者裁定11-13)）。調度者的讀法：模板那套檢查器不帶進來，aos 留自己的 `wf/tools/index_check.py`。wf-agent 11-13 來信列了它們那套檢查器實測到的五種假綠／崩潰，建議不管留哪支都拿同樣案例測一遍。這份就是測的結果。

## 一句話結論

- aos 這支**本來就不查節點內容裡的引用**（md 連結、json 字串裡的路徑、`$ref`），所以模板那邊最嚴重的幾條（第一段不存在、純文字路徑、`$ref` 遞迴）在這裡是「不適用＝範圍外」，不是 bug。
- 在它自己的範圍（index 跟樹對不對得上）裡實測到 **4 種假綠、1 種崩潰、1 種假紅**，都修了；archive 夾照掃會假紅，使用者 15:18 裁了跳過，也做了（見[已裁](#已裁11-13-1518)）。

## 它查什麼、不查什麼

| 查 | 不查（範圍外） |
|---|---|
| 每份 `_index.json` 的形狀（物件、每項有 description、`index` 是字串） | md 檔裡的連結（那是 wf-lint 的事：`wf/`、`.claude/commands`、AGENTS.md） |
| 列了但不在（EntryGone，含 `檔#/指標` 指得到） | json 字串裡寫的路徑、統一路徑、反引號路徑 |
| 在但沒列（EntryMissing；預設照 `git ls-files`，不在 git 的樹照磁碟） | `$ref`（完全不跟） |
| `index` 欄指得到、指到的是一份 index（LinkBad） | `index` 指到的那份不往下跟（檔內 `_index` 那份會查形狀與鍵） |
| 子夾自己有 `_index.json`、上一層卻沒帶 `index`（LinkMissing） | `archive/` 底下的 index（跳過、印 warning、計入 skipped；15:18 裁定後） |

根：預設是**腳本所在的 repo**（不是 cwd、也不是 git toplevel），`--root` 明給就用給的；`git ls-files` 用 `git -C <root>`，所以 root 是別的 repo 的子夾也只列那個夾裡的檔。

## 五條對照（暫存夾實測，修之前）

| # | 模板那邊的問題 | aos 這支 | 實測（修前） |
|---|---|---|---|
| 1 | 根猜錯就靜默跳過 | **會假綠**（三種擺法），已修 | ① 根外的夾直接當 PATH 給：`EntryMissing` 整個不見，`plain/sub/y.md` 沒列卻 `1 problems`（只剩 EntryGone）。② 解開的快照放在**另一個 git repo 裡、沒 add**：`git ls-files` 回空、不報錯，「在但沒列」全部靜默跳過（`2 index files, 4 entries, 1 problems`，少了 y.md 那條）。③ 叫 `build`／`install`／`node_modules` 的夾裡有 `_index.json`：整份不查也不說（植入壞項 `zzz` → `0 problems`、rc=0）。另外 PATH 底下一份 index 都沒有時 `--quiet` 什麼都不印、rc=0。從 repo 子目錄跑、對 repo 外不在 git 的夾 `--root`、解開的 git archive：都正常（後兩者印 warning 後照磁碟算） |
| 2 | archive 夾照掃 | **照掃，會假紅**（不是假綠）；15:18 裁定後改成跳過 | 整夾封存進 `archive/old/` 後，裡面那份 `_index.json` 的項目或往上指的路徑不再對：`EntryGone archive/old/_index.json: gone.md …`、`live is listed but not there`，rc=1。aos 的 STRUCTURE 也寫 archive「不維護內部連結」；`index_gen` 不在 archive 裡建、`wf-lint` 不下鑽 archive，只有這支照掃。現在 repo 的 archive 裡沒有 `_index.json`，所以還沒撞到 |
| 3 | 不驗的引用種類 | 前三種**不適用**（本來不查引用）；`index` 欄**會假綠**，已修 | `"index": "decisions.json"`（一份普通 json）、`"index": "_description.json"`（一段文字）都 `0 problems`。指到資料夾＝`LinkBad … points to nothing`（本來就抓得到） |
| 4 | 展開 `$ref` 互相引用遞迴崩 | `$ref` **不適用**（不跟）；但**巢太深的 json 會崩**，已修 | `a.json`↔`b.json`、`{"$ref":"#"}`：正常結束。`[`×200000 的檔被 `檔#/0` 列到、或 `_index.json` 本身巢太深：`RecursionError: maximum recursion depth exceeded while decoding a JSON array` 整支 traceback |
| 5 | 轉 json 後 md 的連結沒人查 | **目前不適用** | aos 的 md 還是 md，`wf/`、`.claude/commands`、AGENTS.md 的連結由 wf-lint 查（基準 broken=0）；index_check 列到的 md 裡有壞連結照樣 `0 problems`——那是 wf-lint 的範圍。併進來的內容若是 json，裡面的路徑沒人查＝待裁題 1 |

順帶抓到一個**假紅**：資料夾的 `_metainfo.json#/index` 被 `index` 連到時，舊碼拿 `_metainfo.json` 的根物件去對它列的名字，列的明明是夾裡的檔也報 `EntryGone m/_metainfo.json#/index: n.md is listed but not in that object`。

## 修了什麼（只動 `wf/tools/index_check.py`）

- PATH 解開後在 root 外（絕對路徑、`..`）＝`PathBad`，不再半套照查。
- git 模式下某夾沒有任何檔在 git 裡：印 `warning: <夾> has no files in git, counting what is on disk`、那夾照磁碟算。
- 照名字不走的夾裡有 `_index.json`：印 warning，總數行加 `; N skipped (not walked: …)`。
- PATH 底下一份 `_index.json` 都沒有：印 `warning: no _index.json under <PATH>`（`--quiet` 也印）。warning 都不改退出碼。
- `index` 欄指到的要**是一份 index**：`_index.json` 整份（而且是物件）、檔內 `_index` 鍵、`_metainfo.json#/index` 或 `…/_metainfo/index`（[knowledge/docs/01](../../../knowledge/docs/01-樹長怎樣與多庫.md)），否則 `LinkBad … does not hold an index`。
- json 巢太深讀不了＝當成讀不了（`IndexBad … cannot be read as JSON (JsonTooDeep)`／`EntryGone`），不崩。
- `_metainfo` 的 index：資料夾那份對夾裡的檔、物件那份對物件 P，不再假紅。

測試：新檔 `wf/tools/tests/test_index_check_edges.py` 六例，改前 `FAILED (failures=6)`，改後 `Ran 12 tests OK`（連舊的 test_index_tools）；`wf/tools/tests` 全套 `Ran 30 OK`。本 repo `28 index files, 666 entries, 0 problems`、`proto8/knowledge` `3 index files, 82 entries, 0 problems`，修前修後一樣。

## 沒修、留著的（範圍內但小，或不在領地）

- 檔內 `_index` 那份表裡各項的 `index` 欄不驗（只驗形狀與鍵）；要驗得照 `aos_index.link()` 的「物件當資料夾」算法，沒做。
- `#/` 後面帶 `..` 的 `index`（`a.json#/x/../_index`）這支照字面當鍵，會假紅；`aos_index.link()` 會算 `..`。
- 鍵寫 `_index.json` 自己（docs/01：列夾裡每一個東西、`_index.json` 自己除外）不報。
- symlink 的夾 `os.walk` 不進去、也不說。
- `index_gen.py` 只照 `git ls-files` 列檔，夾沒進 git 時同樣什麼都不生——不在這次領地，只列。

## 已裁（11-13 15:18）

使用者對下面三題（原本是待裁）回：「都按照推薦」。結果：題 1 甲＝不做（判準留著：併進來的 json 裡含路徑的字串超過約 50 處、或稽核線抓到第一個壞引用，再提乙）；題 2 乙＝**已做**（`archive/` 底下每一層的 `_index.json` 不查，各印一行 `warning: archive/…/_index.json is not checked (archive keeps no inner links)`、計入總數行的 skipped；上一層 `archive` 那一項不帶 `index` 也不報 LinkMissing；直接把 archive 裡的夾當 PATH 給仍照查；新測試 `test_archive_is_not_checked_but_told` 改前 `LinkMissing _index.json: archive …` 紅、改後綠）；題 3 甲＝不做。

以下是當時擺給使用者的選項，原樣留著。


**題 1：要不要讓 index_check 也查節點內容裡的引用（json 字串裡的路徑、`$ref`、md 連結）？** 模板那套靠這個抓轉檔殘留；aos 這支從來不做。
- 甲、不做（維持現在）：工作量 0。後果：併進來的 json 內容裡寫錯的路徑沒有工具會抓，靠寫的人與稽核線人工看。
- 乙、只查「明確寫成路徑」的（統一路徑 `檔#/指標`、反引號包住且有副檔名的、`$ref`），跳過的種類各印數字，`$ref` 帶循環偵測：約 150～250 行加測試，要先定「從哪算根」（建議只認 `--root` 明給或 index 所在夾，不猜 git 根）。後果：會出現誤報，要配忽略表（題 3）。
- 丙、連純文字路徑都猜：誤報最多，不建議。
- **建議甲**；等內容真的併進來、第一批 json 出現了再看要不要乙。判準：併進來的 json 裡含路徑的字串超過約 50 處、或稽核線人工抓到第一個壞引用，就做乙。

**題 2：archive 夾要不要跳過？**
- 甲、照掃（現在）：第一次整夾封存帶著 `_index.json` 就可能永遠收不了尾，只能改封存內容（違反「不維護內部連結」）。
- 乙、`archive/` 底下的 `_index.json` 不查，照第 1 條的做法印 warning＋計入 skipped：約 3 行加 1 個測試。跟 `index_gen`、`wf-lint` 一致。
- 丙、掃但只報形狀錯、不報 EntryGone／LinkBad：較複雜，意義不大。
- **建議乙**。

**題 3：要不要有忽略表（設定檔列「這幾處不查」）？**
- 甲、不做：現在沒有需要忽略的誤報。乙、做：只有題 1 選乙才需要。
- **建議甲**，跟題 1 綁在一起決定。
