# 第五段：`aos/` 庫最後 5 頁 json 也換成 md；repo 自己 `wf/` 的規矩加上「新寫的預設寫 md、兩種都可以、不做檢查」

← [README](README.md)｜原話：[15](15-使用者原話-續四.md) 第 25 句「1.換。2.好」｜上一段：[16](16-第四段-wf庫換形狀.md)｜對照表：[kb_md_map-aos5.json](kb_md_map-aos5.json)

## 1. `aos/` 庫 5 頁換成 md

| 頁 | 換成 | 怎麼排 |
|---|---|---|
| `aos/packs.json` | `aos/packs.md` | 開頭一句簡介；`# _index`（它自己的 index，18 項「名字: 一句話」）；`# Tool packs`（原本 `about` 那篇，自己有標題，原樣放）；17 個包各一個標題（`# look`、`# change`…）底下一段 |
| `aos/me/_description.json`、`errors/`、`agents/`、`tools/` 的同名檔 | 各自的 `_description.md` | 整份就是那一句話 |

- 用第四段的 `kb_md_shape.py`，加了兩條規則：頂層的值本來就是有 `# 標題` 的文章時原樣放、用它自己的標題；`_index`（每項只有 description）排成 `# _index` 底下的「名字: 一句話」清單，名字用那份 md 裡的標題字（所以 `about` 那一項的名字是 `Tool packs`）。
- **核對**：5 頁共 41 個葉值，換完逐個從新 md 讀回來全對。
- **路徑**：`aos/packs.json#/look` → `aos/packs.md#/look`（鍵就是標題，不變）；`#/about` → `#/Tool packs`；`#/_description` → `#/_`；`#/_index/look/description` → `#/_index/look`。對照表 61 條。
- **誰指到這 5 頁**：只有知識庫裡面（15 處照表改，另手改 5 處：`aos/_index.json` 的 `"index": "packs.md#/_index"`、`index_view` 那頁的例子、`knowledge/README` 的試跑例子與 `aos/`、`wf/` 兩列裡 19 個還寫 `.json` 的頁名、`docs/01` 的樹狀圖）。**程式、工具說明、範本系統文字都沒有指到這 5 頁**（`grep` 過 `py`、`templates`、`cpp`、`frontend`、repo 的 `wf/`、`AGENTS.md`），所以**這批不用為它重裝**。
- 移除 5 份 `.json`，各被同名 `.md` 取代。`aos/` 庫現在只剩 3 份 `_index.json` 是 json；整個知識庫只剩 4 份 `_index.json`。
- **4 份 `_index.json` 沒換**（頂層的讀法，等他確認）：`index` 欄（二次導航）與 `wf/workflows/_index.json` 的 `kind`、`source` 欄放不進「名字: 一句話」。
- 驗（乾淨複本 `s6/`，裝過）：`index_check` 對 `knowledge` 與 `knowledge-zh-md` 8 份 245 項 0 問題（`aos/_index.json` 那一項的 `index` 現在指進 md 的 `# _index`，新規則認得）；`test_knowledge_paths`、`test_hook_points_match`、index_view 兩份過；`wf/tools/tests` 75 過；工具入口實查 `aos/packs.md#/look/_`、`aos/packs.md#/_index/Tool packs`、`aos/me/_description.md` 正確，`index_view aos/packs.md` 印出 18 項。

## 2. repo 自己 `wf/` 的規矩

要求：改得最小，只動講「寫 json 還是 md」的那幾句。六處都是**原字不動、加一句**（四處接在句尾、兩處插在句中），沒有刪字。逐處改前改後在 [19](19-repo規矩六處-改前改後.md)。

1. `AGENTS.md` 鐵律 6。
2. `wf/workflows/common/rules-card.md` 第 6 條（鐵律 6 的濃縮）。
3. `wf/workflows/common/data-files.md` 開頭（資料檔契約）。
4. `wf/STRUCTURE/04-archive與資料檔.md`「資料檔慣例」。
5. `wf/STRUCTURE/02-結構整理原則.md` 觸發 A 第 4 項（條列 > 1024 bytes 抽資料檔）。
6. `proto8/docs/NORMS/00-規範-3-指示詞-組合子-kernel.md` 的 N-45：`$ref` 也可以指到 `.md`。

- **`AGENTS.md` 不是生成的**：找不到生成它的來源，檔尾那行 `wf-kernel v0.5` 只是版本註記；直接改。
- **跟條文綁的檢查**：
  - `wf/tools/find_big_lists.py`（列出 md 裡超過 1 KB 的條列）：只是列清單的工具，沒有接在交件、hook 或任何關卡上（查過 `commit_queue.py`、`commit-request`、`.claude/settings.json`）。沒動它；在 `data-files.md` 寫明它只是列出來參考。
  - `wf/tools/index_check.py`：第二段已整支重寫、不再要求列全；也沒有接在交件上。
  - 交件排隊只跑 `index_gen`（重生索引），不擋「寫 md 還是 json」。
  - 結論：沒有需要關掉的檢查。

## 留給他的題（不擋事）

1. **既有的 repo `wf/` json 資料檔要不要轉成 md？**（`wf/progress.json`、`wf/workflows/inbox.json`、各工作流的 `wf-table` 資料檔、`wf/knowledge/code-map/` 是生成的。）這次照頂層交代只改規矩、沒轉。`progress.json` 有排隊的 `--op` 在寫、code map 是生成器在產、`tabledb.py` 在讀寫資料檔，這三類換了會壞，要換得連工具一起改。
2. **拿不準、沒動的條文**：
   - N-62（統一路徑 `檔#/指標`）與 N-69（index、`_metainfo`、`_description`）：現在 `檔.md#/…` 也是統一路徑、index 不必列全、一項可以是純字串、md 可以自帶 `# index`，條文還是舊的說法。
   - CONCEPTS C-42 續「知識庫存什麼、給人看什麼」。
   - `wf/workflows/tidy/README.md` 第 4 條原則與 `wf/public/整理與拆檔.md`（「用空行把清單切塊躲門檻不算解」）：講的是整理時怎麼抽資料檔，門檻變成建議之後語氣可能要跟著鬆，沒動。
   - `proto8/docs/` 裡指到知識庫舊路徑（`.json`）的 2 處，第三段就列過、沒改。
3. **4 份 `_index.json`** 要不要也換（頂層會問）。
