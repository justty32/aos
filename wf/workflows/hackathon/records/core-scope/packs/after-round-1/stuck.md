# 下一輪的資料包 — 這輪卡住的清單

← [本份索引](README.md)｜[資料包](../README.md)｜[本場索引](../../README.md)｜[hackathon](../../../../README.md)｜[同一塊：R2 後 →](../after-round-2/stuck.md)

第 1 輪之後，四位各自卡在哪裡，每條都附原始整理或現場檔案的路徑。

## 1. 這輪卡住的清單

- **p1（Carmack persona）**卡在第一個數字沒有唯一口徑：同一份現場同時可數成 1 份 helper、6 個可重跑發布位置或含人工復原的 9 次交易；原始整理在 `/home/guanyu/aos-hack/core-scope/p1/wf/workflows/experiments/core-scope-r1/report-r1.md` 的〈三個數字〉。
- **p1（Carmack persona）**卡在 SIGINT 後孤兒行程與 `.runi` 並存，且 provider accepted／dropped 的本機 snapshot 相同，復原仍靠人工殺行程、判斷 temp 與外部 oracle；完整現場在 `/home/guanyu/aos-hack/core-scope/p1/wf/workflows/experiments/core-scope-r1/transcript.txt`。
- **p2（Armstrong persona）**卡在 Publish rename 前中止後仍要人工 `mv`，Ctrl-C 後仍要搬走 `.runi` 並重造只含未啟動 instruction 的半批；整理與各 evidence 路徑在 `/home/guanyu/aos-hack/core-scope/p2/p2-agent-loop/ROUND-1.md`。
- **p2（Armstrong persona）**卡在無 query provider 的 effect unknown：盲重試已把 ledger 從 1 筆變 2 筆，現有狀態還沒有可直接操作的 `adopt | retry | abandon` transition；現場在 `/home/guanyu/aos-hack/core-scope/p2/p2-agent-loop/evidence/kill-9.log`。
- **p3（Cantrill persona）**卡在 crash harness 沒有為每刀留下獨立的 `aos` exit：PTY 的 `^C` 連 wrapper 一起終止；同一輪也遇到合法性藏在檔名裡、錯名被安靜忽略，以及同 target 重投／雙 producer 尚未測，整理在 `/home/guanyu/aos-hack/core-scope/p3/experiment-round1/ROUND1.md`。
- **p4（Thompson persona）**卡在 no-aos 對照只跑 happy path，還沒承受與 aos 版本相同的 SIGINT、SIGKILL、rename 前中止與重開驗收；對照腳本在 `/home/guanyu/aos-hack/core-scope/p4/round1/run-no-aos.sh`。
- **p4（Thompson persona）**卡在三行 delivery helper 的多 producer 主張尚無壓力資料；目前實作只有 `/home/guanyu/aos-hack/core-scope/p4/round1/deliver.sh`，尚未有兩個 producer 各投 1,000 個唯一 ID 的結果。
