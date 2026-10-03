# proto7-1 — 照 proto7 核心 spec 一路做到 kernel／agent 的試做

← [proto7](../proto7/README.md)｜要合的：[核心 spec](../proto7/spec/core.md)（條號 S-）

**這是一次嘗試，目的是看看照核心 spec 做下去會遇到哪些問題。** 全部取最簡單的做法，Python 3.11+ 純標準庫。最重要的產出是 **[notes/problems.md](notes/problems.md)**。

## 入口

- **[notes/problems.md](notes/problems.md)**：做下去遇到的問題（分級：要使用者決定／技術選型／默認正常）。
- [spec.md](spec.md)：proto7-1 自己定的檔案格式與行為，每節標 S- 條號。
- **跨 node 靠掛載**（S-23，D-1 的做法）：tasks.json 的 `mounts` 宣告要把哪個資料夾掛進來，tick 在任務資料夾建 `mnt/<名字>` 符號連結；寄信、寫別人的 ctl、寫 daemon 控制檔都只經過它。執行中也能寫 `mount-req/` 請求加掛，下一個 tick 審核（agent 寄給沒掛的對象、kernel 新成員都靠它）。設 `AOS7_AUDIT=1` 時任務的寫入記到 `writes.jsonl`，看得出有沒有寫出範圍（只記不擋）。
- [notes/play/](notes/play/README.md)：試玩紀錄（一輪一列）。
- 示範：`python3 proto7-1/demo/play.py`（一鍵跑完約 8 秒，自己開的暫存根全 OK 就刪掉、有失敗留著並印路徑，印出每條時間線每回合發生什麼、kernel 的決定、控制檔、掛載、加掛回條、寫入紀錄、信件，最後逐項檢查；寫入紀錄預設開著）。LLM 預設用離線的假後端；`agent.json` 的 `llm` 改成 `{"url": "http://localhost:1234/v1", "model": "..."}` 就接 OpenAI 相容端點（LM Studio 的 gemma-4-e4b 實測可用）。
- **真模型場景**：`python3 proto7-1/demo/real.py`。lead（luna）、coder（deepseek）、中途加入的 rita（haiku）只靠信件合寫兩個小模組，由不用 LLM 的 ci 機器人跑隱藏測試驗收；kernel 管卡住和預算，並給每個成員寫名冊（`.aos/roster.json`）；總額上限 `cap_tokens` 這個場景沒設。ci 不測不回非程式碼與重複的程式碼，PASS 直接寄 lead（附程式碼）。`--model lead=deepseek-chat` 之類可換模型組合；跑完會報 lead 交的檔是 ci 第幾次測的那份。只打 LiteLLM 代理 `127.0.0.1:4000`，每輪 ≤ 400 次呼叫、≤ 900 秒，不放進 unittest。紀錄與發現：[real-1](notes/runs/2026-10-03-real-1.md)、[real-2](notes/runs/2026-10-03-real-2.md)（兩模組三次都寫出 DONE.md，一次交付的檔不合格）、[notes/problems-real.md](notes/problems-real.md)。
- **發散探針**（[probes/](probes/README.md)）：十二個刻意彼此不同的 kernel／agent 探針（群體、子時間線、排程、多 daemon、三層巢狀、事件驅動、長任務、重試／自我 restart、改自己任務表、150 條時間線、sh／inst 任務、node 搬家），只用來逼出 daemon／tick 缺什麼。`python3 proto7-1/probes/run_all.py` 一鍵跑（約 100 秒）。逼出來的需求清單：**[notes/infra-needs.md](notes/infra-needs.md)**（併了 astra-4 的 R1～R18）。
- 測試：在 repo 根跑 `python3 -m unittest discover -s proto7-1/tests`（離線、純標準庫，87 項約 14 秒，含示範場景的整合測）。

## 結構

| 位置 | 是什麼 |
|---|---|
| `bin/` | 薄入口：`aos7-daemon`、`aos7-tick`、`aos7-tock`、`aos7-run`、`aos7-ctl`、`aos7-wait-tock`、`aos7-kernel`、`aos7-agent`，與搬來的 `aos-exec` |
| `lib/aos7_*.py` | 本體（每檔開頭一句說明）；掛載在 `aos7_mount.py`，寫入紀錄的檢查在 `aos7_audit.py` |
| `lib/audit_site/` | 寫入紀錄的 audit hook（`sitecustomize.py`，開 `AOS7_AUDIT` 時 tick 放進任務的 `PYTHONPATH`） |
| `lib/aos_*.py` | 搬來的 inst 執行器（見下「來源」） |
| `demo/` | `play.py` 與場景 `scene/`（team＝kernel、amy／bob／carol＝agent、team/sub＝子 daemon）；`real.py` 與真模型場景 `real_scene/`（lead／coder／ci）、`real_later/rita/`（中途加入） |
| `tests/` | unittest（`test_infra.py`＝探針與 astra-4 逼出來的基礎設施修補） |
| `probes/` | 發散探針：`probelib.py`（開暫存根、起 daemon、收乾淨）、`run_all.py`、每個探針一個資料夾（`probe.py`＋任務腳本＋README） |
| `notes/` | 問題紀錄；`notes/play/` 試玩報告與證據；`notes/runs/` 真模型場景跑的紀錄 |

## 來源（複製進來，不 import 外部路徑）

- `lib/aos_inst.py`、`aos_directives*.py`、`aos_dirname.py`、`aos_exec*.py`、`bin/aos-exec`：原樣複製自 proto6 `src/py/lib/` 與 `src/py/bin/`（2026-10-03，commit bb3f151f）。inst JSON 執行器，tasks.json 寫 `inst` 的任務用它跑（S-12）。
- `lib/aos7_llm.py` 的 OpenAI 相容呼叫：參考 proto5 `lib/aos_llm_call.py` 簡化改寫。
- 示範場景仿 proto6 `notes/proposals/2026-10-03-spacetime/05-交叉例子.md` 的 team／amy／bob。
