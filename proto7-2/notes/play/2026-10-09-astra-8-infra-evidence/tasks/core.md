# 子線 core：核心＋daemon＋核心旁的模組，以及 kernel 的接點

線名 `core`。範圍：
- 核心 `proto7-2/lib/aos7_*.py` 今天的改動（`git diff cbc67a3d^ HEAD -- proto7-2/lib proto7-2/spec.md`）：L1 的 N-06 `owe`、A9-01 reaping→missing、K1～K4 的收尾、timeline。對照 `proto7-2/spec.md`、`proto7-2/notes/component-contracts.md`。
- 核心旁的模組：`modules/events/`（今天新進，保存端／發布／讀者／取樣器）、`modules/history.py`（A9-02 封存 `.v1`）、`modules/subd/`、`modules/control/`、`modules/audit/`、`modules/once_retry/`、`modules/tools/`（aos7-ctl、wait-tock）、`lib/aos_inst.py`（A9-03）。
- kernel 的接點（不審 kernel 內部）：kernel 寫目標槽 `ctl.json` kill（綁 run）、讀 brain 的 `task.json`、keep 任務身分——與核心 spec §5／§6 的 ctl 契約、tools 的 aos7-ctl、up 怎麼裝 kernel 是否一致；kernel 與 control／subd／once_retry 同時作用在一個 node 時會不會互相打架。
- daemon 視角的副作用：events 的 12 檔上限、history 的封存、up 裝的三個 keep 任務，各自寫哪些檔，有沒有違反「核心不每回合長檔」。

挑最可能壞的地方深挖：重起／被殺後的恢復、兩個寫者搶同一檔、鎖的順序、錯誤時有沒有走 Unknown／退 3。
