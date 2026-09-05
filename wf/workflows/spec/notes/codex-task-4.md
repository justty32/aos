# 給 codex 的任務書（第 4 輪：12 條裁決回寫 spec，2026-09-05 晚上）

你在 /home/lorkhan/repo/simple_tools/aos 工作。新規定在 wf/workflows/spec/（先讀 README.md、01-terms.md，還有 notes/README.md、notes/rulings-2026-09-05.md 看前兩批怎麼回寫的、notes/edge-decisions.md 看「邊 XX」是什麼）。構想集在 wf/workflows/ideas/（每章末尾有「待決定」表，README.md 有總表）。

硬規則：
- 不 commit、不 push、不 git add。
- 只准碰：wf/workflows/spec/01～13 各章（含 b 檔）、wf/workflows/spec/schemas/、wf/workflows/spec/notes/rulings-2026-09-05.md、wf/workflows/ideas/ 各章與 README.md。**不准碰** spec/notes/README.md（另一輪 codex 正在改它）、proto/、core/。
- 每個 md 檔 ≤ 12 KB；條款編號 S-章-序 不可改號、不可刪號（要作廢就在原號後寫「作廢，見 S-xx-yy」）；標籤格式照既有：〔裁決 2026-09-05〕／〔預設 2026-09-05，X〕／〔主編補〕。
- 改完跑 `bash wf/tools/wf-lint.sh`，broken 必須是 0。
- 全部大白話中文。

## 使用者今晚的裁決（第三批，12 條，全部「改成再審建議」）

使用者對下面 12 條「AI 建議改」全部點了「改成再審建議」。也就是：每條的定案＝右邊那句「再審建議」，不是原本的預設。

| 編號 | 題目 | 原預設 | **定案（再審建議）** | 依據 |
|---|---|---|---|---|
| E-04 | 源碼 json 的註解放哪 | `_comment` 欄，編譯器一律略過 | 略過，但原樣抄進中間表示 | 邊 L06 |
| F-03 | run 要不要「有變動才動」模式 | 不另立，靠門鈴 | 加 `--until never`；門鈴收件人改成 daemon | 邊 B12、P6 |
| F-04 | 慢指令誰判定 | PATH 沒有就失敗 | 登記表 `slow` 自標，第一版就讀 | 邊 S16 |
| F-07 | 父能不能查子地的鐘還在走 | 查 daemon 登記表 | LLM 請求不是地，要另查請求狀態 | 邊 B03 |
| G-06 | 並行上限誰數 | daemon 看登記表擋 | LLM 併發歸 LLM 世界自己數；daemon 不數 LLM 併發 | 邊 S05 |
| H-03 | agent 限制參數 | 總時限、LLM 次數、token 上限 | 總時限改成格數；token 對自己 `.aos/usage.json` 判 | 邊 L02／B19 |
| I-07 | 環境變數繼承預設 | 預設繼承 | 預設不繼承；另訂保底 PATH | FINDINGS 核心段 |
| I-08 | 足跡宣告 | 宣告但不強制 | 同格兩筆宣告 `footprint.writes` 相交＝整格拒跑退出 3 | 邊 S08 |
| J-05 | 脫節子世界的回寫算不算別人 | 等待中的直接落地 | 可落地，但父每格只在格頭取樣一次 | 邊 S09 |
| K-02 | 迴圈讀登記表哪幾欄 | 一欄不讀 | 只讀 `slow`，其餘保留、無消費者 | 邊 S16 |
| K-04 | `aos llm` 退出碼幾種 | 四種 | 全歸「跑沒跑起來」；可否重試寫封套／狀態檔 | 邊 S18 |
| L-03 | 要不要第一天立正本規範 | 先立薄的 | 已是全套條款，改寫成「這疊就是正本」 | spec 現狀 |

## 要做

1. **逐條找條款**：`grep -n "〔預設 2026-09-05，E-04〕"` 之類，把 12 個編號在 spec 各章（含章末摘要表）的所有出現處都找出來。
2. **逐條對照**：主編之前可能已經把「邊 XX」的建議寫進條款了（notes/edge-decisions.md 標「採」的那些）。兩種情況：
   - 條款內容已經＝定案 → 只把標籤 〔預設 2026-09-05，X〕 改成 〔裁決 2026-09-05〕（章末摘要表那行也改）。
   - 條款內容還是原預設 → 改寫條款成定案，標籤改 〔裁決 2026-09-05〕；牽連到的別條（例如 F-03 的 `--until never` 要進 12 指令面、I-07 的保底 PATH 要有一條寫清楚是哪些路徑、I-08 的 footprint 要在 04 指令格式有欄位、schemas 若有對應 schema 要加欄）一併補，新補的條款標 〔主編補〕。
3. **ideas 回寫**：wf/workflows/ideas/ 對應章的「待決定」表，這 12 條改成「已拍板：<定案一句話>」；README.md 總表同步（照前兩批的寫法）。
4. **rulings 檔**：notes/rulings-2026-09-05.md 末尾加「第三批：12 條 AI 建議改，全部照建議（2026-09-05 晚上）」一節，一張表：編號、定案、動到 spec 哪幾條。
5. `bash wf/tools/wf-lint.sh` broken=0。

回報格式：每條一行「編號：條款已是定案只改標籤／改寫了 S-xx-yy（＋補了 S-xx-zz）」，撞到的事（例如定案跟別條打架），最後 lint 結果。
