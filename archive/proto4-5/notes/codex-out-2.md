修改：`README.md`、`llm_cpu_home.py`、`llm_cpu_worker.py`、`llm_cpu_tick.py`、`test/test_worker.py`。
驗證：28 tests；最後一行 `OK`。
自行決定：驗證 `strict_model` 必須為布林值；tick 代寫的失敗結果也補 `model_requested`，無法判定 endpoint 時為 null。
未 commit、未 push；未連真網路。