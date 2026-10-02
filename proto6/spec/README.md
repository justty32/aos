# 規格：tick 與 daemon 的基礎

← [proto6](../README.md)｜[裁定](../notes/verdicts/11-tick-as-unit.md)｜[現行程式](../src/py/README.md)｜[舊設計封存](../notes/archive/spec-2026-10-02/README.md)

## 原則：spec 就是唯一事實

〔使用者 2026-10-02，第二十六、二十七批〕行為與格式的正本是**程式**（`proto6/src/py/lib`）加**測試**（`proto6/src/py/tests`）加 **schema 與範例**（[protocol/](protocol/README.md)）。這個資料夾只留**程式看不出來的**：做什麼（幾句）、為什麼與原則、邊界，然後指向程式與測試。欄位表、驗收、歷史註記不寫在這裡；條號（B-、P-、C-、T-）留在標題上，讓舊連結與裁定對得上。

舊設計（node／kernel／agent、LLM 排程、舊協議、CLI、驗收場景…）整批封存在 [notes/archive/spec-2026-10-02/](../notes/archive/spec-2026-10-02/README.md)，不再是規格；碰到衝突，以這裡為準。

## 讀法

| 篇 | 條號 | 內容 |
|---|---|---|
| [terms.md](terms.md) | T-01～T-11 | 核心、系統級任務、普通程式、daemon 模組這些詞，與幾條不寫在程式裡的方向 |
| [conventions.md](conventions.md) | C-01、C-07～C-11 | 時間單位、版本與陌生欄位、結束碼、狀態資料夾名、環境變數、設定檔頂層 |
| [inst.md](inst.md) | inst | 一次 POSIX 執行的描述檔：找檔、解指示詞、怎麼跑、錯誤 |
| [tick.md](tick.md) | B-602、B-620、B-626、B-627、B-633 | tick 核心：互斥鎖、照表跑、每項結束碼紀錄 |
| [tick/hooks.md](tick/hooks.md)、[tick/tasks-blocked.md](tick/tasks-blocked.md) | B-635、B-636 | 外掛掛點與擋板模組 |
| [daemon/README.md](daemon/README.md) | B-640～646 | daemon 與各模組：控制、重讀設定、記住狀態、收屍、訊息、帳號 |
| [protocol/README.md](protocol/README.md) | P-001、P-002、P-007 | 格式篇通則：JSON 規矩、schema 與範例放哪、怎麼驗 |
| [protocol/tick.md](protocol/tick.md)、[protocol/daemon/README.md](protocol/daemon/README.md) | P-120～126、P-200～214 | 檔案與訊息的 JSON 長相 |
| [deferred/](deferred/README.md) | 其餘 | 暫緩區，原文照留；B-625 當機恢復也在這裡 |

## 怎麼驗

從 repo 根目錄：

- 測試：`cd proto6/src/py && PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=lib python3 -m unittest discover -s tests`
- schema 與範例：`cd proto6/spec/protocol/examples && uv run -q --no-project --with jsonschema python messages/validate.py`
- 文檔連結：`bash wf/tools/wf-lint.sh .`
