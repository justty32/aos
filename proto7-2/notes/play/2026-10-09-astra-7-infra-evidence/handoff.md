# astra-7 QA 分工

授權：頂層 2026-10-09 開 R 隊（plan-2026-10-09 §3），最多四條子線；全部禁止修改既有程式、測試與文件，禁止 commit/push、LLM。工人 `codex exec -m gpt-6-astra -c model_reasoning_effort="high"`，跑在 main 的 worktree 複本（ad1dfa25）；測試與長跑一律包 `systemd-run --user --scope -p TasksMax=800 -p RuntimeMaxSec=1800`。任務書原文在 [tasks/](tasks/)（[共同規則](tasks/common.md)＋各線一份）。

| 線 | 唯一可寫領地 | 驗收 |
|---|---|---|
| core3 | core3/ 與自己 /tmp | §7 第 3 組：R8-01、R8-03 前半、C8-01／C8-02 各 3／3＋對照、K-04 ×10、R8-29；K1／K2 新邊角 |
| pack4 | pack4/ 與自己 /tmp | §7 第 4 組 11 項、astra-5／6 budget 50 案與獨立核帳、C8-03 槽外 tmp |
| group5 | group5/ 與自己 /tmp | §7 第 5 組每條一案、`test_interval_huge_int` 搬回、T8-01～08 拿掉注入轉紅、§7 文件項 |
| longrun | longrun/ 與自己 /tmp | 全套一次、step 450、adapt 320、核心行數與 lib 歷史 |

每線保存可重跑探針、精簡 JSON、summary.md、ps 前後與 cleanup.json；大量快照 tar.gz。隊長收線時親自重跑 NEW-core3-1（[lead-rerun-new-core3-1.log](core3/lead-rerun-new-core3-1.log)，3／3 重現），並核對各線原始 JSON。
