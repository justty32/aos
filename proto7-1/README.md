# proto7-1 — 照 proto7 核心 spec 一路做到 kernel／agent 的試做

← [proto7](../proto7/README.md)｜要合的：[核心 spec](../proto7/spec/core.md)（條號 S-）

**這是一次嘗試，目的是看看照核心 spec 做下去會遇到哪些問題。** 全部取最簡單的做法，Python 3.11+ 純標準庫。最重要的產出是 **[notes/problems.md](notes/problems.md)**。

## 入口

- **[notes/problems.md](notes/problems.md)**：做下去遇到的問題（分級：要使用者決定／技術選型／默認正常）。
- [spec.md](spec.md)：proto7-1 自己定的檔案格式與行為，每節標 S- 條號。
- **跨 node 靠掛載**（S-23，D-1 的做法）：tasks.json 的 `mounts` 宣告要把哪個資料夾掛進來，tick 在任務資料夾建 `mnt/<名字>` 符號連結；寄信、寫別人的 ctl、寫 daemon 控制檔都只經過它。執行中也能寫 `mount-req/` 請求加掛，下一個 tick 審核（agent 寄給沒掛的對象、kernel 新成員都靠它）。設 `AOS7_AUDIT=1` 時任務的寫入記到 `writes.jsonl`，看得出有沒有寫出範圍（只記不擋）。
- [notes/play/](notes/play/README.md)：試玩紀錄（一輪一列）。
- 示範：`python3 proto7-1/demo/play.py`（一鍵跑完約 8 秒，印出每條時間線每回合發生什麼、kernel 的決定、控制檔、掛載、加掛回條、寫入紀錄、信件，最後逐項檢查；寫入紀錄預設開著）。LLM 預設用離線的假後端；`agent.json` 的 `llm` 改成 `{"url": "http://localhost:1234/v1", "model": "..."}` 就接 OpenAI 相容端點（LM Studio 的 gemma-4-e4b 實測可用）。
- 測試：在 repo 根跑 `python3 -m unittest discover -s proto7-1/tests`（離線、純標準庫，46 項約 10 秒，含示範場景的整合測）。

## 結構

| 位置 | 是什麼 |
|---|---|
| `bin/` | 薄入口：`aos7-daemon`、`aos7-tick`、`aos7-tock`、`aos7-run`、`aos7-ctl`、`aos7-kernel`、`aos7-agent`，與搬來的 `aos-exec` |
| `lib/aos7_*.py` | 本體（每檔開頭一句說明）；掛載在 `aos7_mount.py`，寫入紀錄的檢查在 `aos7_audit.py` |
| `lib/audit_site/` | 寫入紀錄的 audit hook（`sitecustomize.py`，開 `AOS7_AUDIT` 時 tick 放進任務的 `PYTHONPATH`） |
| `lib/aos_*.py` | 搬來的 inst 執行器（見下「來源」） |
| `demo/` | `play.py` 與場景 `scene/`（team＝kernel、amy／bob／carol＝agent、team/sub＝子 daemon） |
| `tests/` | unittest |
| `notes/` | 問題紀錄；`notes/play/` 試玩報告與證據 |

## 來源（複製進來，不 import 外部路徑）

- `lib/aos_inst.py`、`aos_directives*.py`、`aos_dirname.py`、`aos_exec*.py`、`bin/aos-exec`：原樣複製自 proto6 `src/py/lib/` 與 `src/py/bin/`（2026-10-03，commit bb3f151f）。inst JSON 執行器，tasks.json 寫 `inst` 的任務用它跑（S-12）。
- `lib/aos7_llm.py` 的 OpenAI 相容呼叫：參考 proto5 `lib/aos_llm_call.py` 簡化改寫。
- 示範場景仿 proto6 `notes/proposals/2026-10-03-spacetime/05-交叉例子.md` 的 team／amy／bob。
