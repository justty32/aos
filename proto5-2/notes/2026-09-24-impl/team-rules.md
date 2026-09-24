# 各隊共用守則（proto5-2 實作隊，2026-09-24）

← [進度](progress.md)｜[決定](decisions.md)

隊長把這份當每隊任務書的前言。

## 地方與規矩

- worktree：`/home/lorkhan/repo/simple_tools/aos/.claude/worktrees/agent-a8418312913acf899`（下稱 W）。幾隊**同時**在這個 worktree 改不同的檔。
- **不准 commit、不准任何改 git 狀態的指令**（commit／stash／checkout／reset／add 都不行）；隊長收齊後自己 commit。`git diff`／`git status` 看可以。
- **只准改自己那隊名下的檔**（任務書會列）。要動別隊的檔，寫進回報、讓隊長協調。`aos_home.py`／`aos_client.py` 只准**加**新函式，不改既有函式的行為。
- **`proto5/`、`wf/` 一個字都不准動**；proto5-2 的 `spec/` 也不准改（規範是定稿）。規範沒寫或矛盾：自己選最保守的做法，寫進 `proto5-2/notes/2026-09-24-impl/decisions.md` 自己那隊的編號段（每條：撞到什麼、選了什麼、為什麼保守、翻案要改哪裡），**不要停下來問**。
- 用繁體中文寫註解、文件、回報；程式照 proto5/lib 既有風格（只用標準庫、Python 3.12）。
- 測試指令（在 W 下）：`cd proto5-2/lib && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s test -p '<你的檔>.py'`。
  全套會被別隊改到一半的東西弄紅，**只跑自己的檔**；全套由隊長跑。
- 行程衛生：測試拉起來的 daemon／cpu 一律要在 tearDown 收乾淨。收尾時 `pgrep -fa <你測試用的暫存目錄前綴>` 要空。**只殺自己拉的行程**（其他隊也在跑）。
- **絕對不要碰 LM Studio／`lms`／localhost:1234／ollama**（使用者在打遊戲搶 GPU）。要真的問模型只准用 LiteLLM `http://localhost:4000/v1`、model `deepseek-chat`、不用 api_key。

## 兩邊的約定（kernel 隊與 daemon 隊都要照這張做；規範原文優先）

| 項目 | 約定 |
|---|---|
| scale 單 | 放在 `D/requests/<name>`，`id`＝檔名去掉 `.json`；params 照 [protocol §1](../../spec/protocol.md)；kernel 的檔名 `k-<chain>-<seq>-scale-<P>.json`，boot 的 `k-<chain>-boot-scale-<P>.json`（縮到 0 加 `-down`） |
| 錯誤回音 | `{"error": {"code": -32000, "message": …, "data": {"code": "NameTaken"}}}`（`aos_home.error_response`）；`-32602` 走 `aos_home.params_error`。kernel 只看 `data.code` |
| 成功回音 | `{"pool": P, "count": N, "ver": V}` |
| daemon 活不活 | `aos_daemon.is_alive(D)`（flock 探測，proto5 原函式，不改名不改行為） |
| 池摘要 | `D/pools/<dpool>/summary.json`，欄位照 [daemon-home §4](../../spec/daemon-home.md)；「檔不在」＝池已完全拿掉 |
| 一顆的檔 | `D/pools/<dpool>/kids/<i>.json`，欄位照 daemon-home §3；沒檔＝還沒拉過（`pending`） |
| 給 kernel 讀的小函式 | daemon 隊在 `aos_daemon.py` 提供 `pool_summary(D, dpool)`（讀 summary.json，不在或壞了回 `None`）與 `pool_kid(D, dpool, i)`（讀 kids 檔，不在回 `None`）。kernel 隊只用這兩個＋`is_alive`，不自己拼路徑 |
| cpu 通知 | 工作 cpu 的 `info.json` 有 `notify`＝`/abs/K/requests`；通知檔 `resp-<digest>.json`，內容與 digest 照 [cpu-notify §2](../../spec/cpu-notify.md) |
| cpu 入口 | `proto5-2/cli/aos-cpu`（絕對路徑；kernel 建池模板時用它） |
