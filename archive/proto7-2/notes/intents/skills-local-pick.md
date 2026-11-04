# skills 本機挑選 意圖卡（r5，SK1 隊）

← [intents](README.md)｜[skills 卡](skills.md)｜起因 [longtask 問題 5](../play/2026-10-09-longtask/README.md)

**①解決什麼**：本機只算題目與 description 的字詞重疊，「回信」「整理」都挑到 aos-inbox、有「測試」就挑 aos-test。L 的 17 筆裡只有兩筆該挑（06→aos-test、07→wf-lint），其餘 15 筆正解是 **none**，目前錯 12 筆。變準的關鍵是**敢說 none**。

**怎麼變準、不花錢**：SKILL.md frontmatter 加可選 `triggers:`（白話觸發詞）與 `not_for:`；本機只算觸發詞命中（整詞／整句），0 命中或平手＝none；description 只當第二證據；紀錄加 `score`、`why`。沒 triggers 的舊 skill 用舊算法但門檻 ≥2 詞。

**何時該問 AI**：有帳且（平手或信明說「用技能」）才問，每信一次並快取；其餘本機。

**②必要的副作用**：index 多兩欄；library 三本補 `triggers`；紀錄照舊 50 行封頂；不花錢。

**③不做**：不做 embedding；不改 brain（每信記兩筆是 brain 叫兩次，歸 M1 順手修）、llmcall、QUICKSTART。

**④對照現狀多出來的**：frontmatter 兩個新欄 → **保留**（可選，沒寫就舊算法）；快取檔 `.pick/cache.json` → **改成可選**（封頂 50 筆）。

**驗收**：L 跑 2 的 17 筆＋原 10 題當固定題庫：本機 ≥16／17 對、0 筆挑錯本、0 次 AI；開帳時 AI ≤2 次；每信一筆紀錄；README 不變。
