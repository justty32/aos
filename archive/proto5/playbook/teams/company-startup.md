# 新創公司編制：八個部門、七個正式員工

← [teams](README.md)｜真東西：[examples/company/](../../examples/company/README.md)｜來源：[notes/2026-09-25-company](../../notes/2026-09-25-company/README.md)

**適合什麼活**：一條產品線（例：arknights 補人物）要有人接單、有人做、有人獨立驗貨、有人造工具，而且名額很緊（正式 ≤10、cpu ≤20、llm cpu ≤5）。

| 部門 | 編法 | 為什麼 |
|---|---|---|
| 總裁辦 | 領隊 1（總裁），兼業務、兼 HR 決策；門房規則管業務 | 董事只對一個人說話；接單的判斷量小，不值得另開人 |
| 製造 | 經理 1（只拆批次）、寫手 1、審查 1；忙時經理 spawn 臨時寫手 | 單件走門房直派寫手，經理大多閒著停車、不佔 cpu |
| 品管 | 檢驗員 1（笨模型）＋機械工具（評分器）；評審是一次性強模型呼叫 | 獨立於製造（不球員兼裁判）；抽查 3 列不用強模型 |
| 研發 | 工具匠 1 | 工具草稿要人批，一個人夠 |
| 圖書館 | 館員 1（笨模型） | 只判「像不像舊條目」 |
| HR、業務 | 併在總裁辦 | 數名額、生臨時工都是程式 |
| 財務 | 不放人 | 帳本＋帳戶全機械 |

**照抄**：`python3 proto5/examples/company/company.py new <資料夾> --prefix c1- --project <專案>`，改 `company.json` 的 `staff`／`departments` 與各 `teams/*/team.json`、`persona/*.md`。
**注意**：經理一律用內建 `lead` 模板（門房落穿只認 `template: lead`），專案規矩寫在 `persona/`，`up` 時接上。
