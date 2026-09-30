你可以開自己的 subagent 平行做事。

你在 /home/guanyu/projs/aos（proto6 設計草案，繁中）。唯讀審稿，不改任何檔。

審的範圍：`proto6/spec/settled/` 整個區域（tick 與 daemon 的基礎，本輪假設沒有 cgroup、沒有 git）。它剛從 spec 其他位置搬過來，區外的 kernel、agent、LLM、CLI 各篇還沒整理，不在審稿範圍，但可以拿來對照連結與依賴。

依據：
- 使用者裁定：`proto6/notes/verdicts/11-tick-as-unit.md`（第二十批，最優先）、`10-tick-minimal-core.md`（第十九批，被第二十批推翻處有註）、`09-special-computing-os.md`（第十八批）。後批優先。
- 原則：主規格是行為正本，協議篇只留欄位、JSON、schema、範例（方案 A）。
- 各篇「下一步納入（git 與 cgroup）」段是草稿，不是現行規則；只審它有沒有被誤當現行規則引用，不審草稿內容本身（另有計畫在做）。

要審：
1. **搬家品質**：整理區能不能自己讀懂（README 的定位、閱讀順序、檔案清單、對外依賴是否正確完整）；有沒有壞連結、指向舊路徑、條號重複或遺失；混合檔拆出來的條目有沒有漏搬或搬了不該搬的；整理區有沒有偷偷依賴 kernel／agent／LLM 的規則。
2. **一致性**：與第二十批裁定是否一致（tick 核心四件事、停格檔只擋本格剩餘任務、擋板檔擋之後的格、結束碼只有 0／1／2／75、AOS_TASK_ID 字串與 AOS_TASK_INDEX、任務帶 user 不同帳號回 125、系統級任務與普通程式的分界、通道是唯一逃生口、時間用格數、group／needs 當陌生 key 等）；篇與篇之間、主規格與協議篇、schema 與範例之間有沒有矛盾；方案 A 殘留（協議篇寫行為規則）。
3. **設計原則**：冗餘（同一件事多處重寫、兩套機制做同一件事）、該考慮卻沒考慮到的狀況（當機復原、併發、權限、人手介入、版本演進、規模、WSL 等）、跟自己宣稱的原則互相違背的弱點。
4. 自動檢查：跑 `python3 proto6/spec/check_ids.py --strict`、`uv run --no-project --with jsonschema python3 proto6/spec/protocol/examples/messages/validate.py`（路徑若已變，找新的）、`wf/tools/wf-lint.sh`，報結果（唯讀沙盒跑不了就說明）。

輸出（最後一則訊息就是報告，繁中大白話）：
- 開頭三行總結。
- 條目分四類：必修／設計問題／建議／要使用者裁定。每條：編號（必-1、設-1、建-1、裁-1）、一句標題、位置（檔案＋條號）、問題、建議改法（裁定題列 2～4 個選項）。
- 最嚴重的放前面。只攤問題，不替使用者改大方向。
