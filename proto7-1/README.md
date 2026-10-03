# proto7-1 — 照 proto7 核心 spec 一路做到 kernel／agent 的試做

← [proto7](../proto7/README.md)｜要合的：[核心 spec](../proto7/spec/core.md)（條號 S-）

**這是一次嘗試，目的是看看照核心 spec 做下去會遇到哪些問題。** 全部取最簡單的做法，Python 3.11+ 純標準庫。最重要的產出是 **[notes/problems.md](notes/problems.md)**。

## 入口

- **[notes/problems.md](notes/problems.md)**：做下去遇到的問題（分級：要使用者決定／技術選型／默認正常）。
- [spec.md](spec.md)：proto7-1 自己定的檔案格式與行為，每節標 S- 條號。
- 示範：`python3 proto7-1/demo/play.py`（一鍵跑完約 8 秒，印出每條時間線每回合發生什麼、kernel 的決定、控制檔、信件，最後逐項檢查）。LLM 預設用離線的假後端；`agent.json` 的 `llm` 改成 `{"url": "http://localhost:1234/v1", "model": "..."}` 就接 OpenAI 相容端點（LM Studio 的 gemma-4-e4b 實測可用）。
- 測試：在 repo 根跑 `python3 -m unittest discover -s proto7-1/tests`（離線、純標準庫，34 項約 10 秒，含示範場景的整合測）。

## 結構

| 位置 | 是什麼 |
|---|---|
| `bin/` | 薄入口：`aos7-daemon`、`aos7-tick`、`aos7-tock`、`aos7-run`、`aos7-ctl`、`aos7-kernel`、`aos7-agent`，與搬來的 `aos-exec` |
| `lib/aos7_*.py` | 本體（每檔開頭一句說明） |
| `lib/aos_*.py` | 搬來的 inst 執行器（見下「來源」） |
| `demo/` | `play.py` 與場景 `scene/`（team＝kernel、amy／bob＝agent、team/sub＝子 daemon） |
| `tests/` | unittest |
| `notes/` | 問題紀錄 |

## 來源（複製進來，不 import 外部路徑）

- `lib/aos_inst.py`、`aos_directives*.py`、`aos_dirname.py`、`aos_exec*.py`、`bin/aos-exec`：原樣複製自 proto6 `src/py/lib/` 與 `src/py/bin/`（2026-10-03，commit bb3f151f）。inst JSON 執行器，tasks.json 寫 `inst` 的任務用它跑（S-12）。
- `lib/aos7_llm.py` 的 OpenAI 相容呼叫：參考 proto5 `lib/aos_llm_call.py` 簡化改寫。
- 示範場景仿 proto6 `notes/proposals/2026-10-03-spacetime/05-交叉例子.md` 的 team／amy／bob。
