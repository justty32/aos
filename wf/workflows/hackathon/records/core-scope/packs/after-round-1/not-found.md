# 下一輪的資料包 — 還是查不到的

← [本份索引](README.md)｜[資料包](../README.md)｜[本場索引](../../README.md)｜[hackathon](../../../../README.md)｜[同一塊：R2 後 →](../after-round-2/not-found.md)

repo 與兄弟專案都翻過、確認沒有現成資料的那幾條。

## 4. 還是查不到的

- `wf/workflows/hackathon/records/core-scope.md`〈5. 仍然不知道的〉只確認第一個數字口徑不一；在 `docs/`、`wf/workflows/workshop/`、`wf/workflows/experiments/t5-agent-loop.md` 與四個兄弟專案中都沒有一份既定的「實作份數／靜態呼叫點／實際 commit／人工 rename」統一計數表，**這條沒有現成資料**。
- `wf/workflows/experiments/t5-agent-loop.md`〈3. 投遞：原子 rename、壞 JSON 與檔名碰撞〉只有同一 producer 連投兩次的覆蓋證據；`/mnt/c/code/mine/simple_tools/agent-machine/workbench/2026-08-14/p1a2-process-python/PHASE2-EVIDENCE.md`〈明確未驗，不可外推〉也明列未涵蓋 multiwriter，因此兩個 producer 各投 1,000 個 ID 的遺失／重複／覆蓋數，**這條沒有現成資料**。
- `/home/guanyu/aos-hack/core-scope/p4/round1/run-no-aos.sh` 只有 happy path；repo 的 crash 證據都在 `wf/workflows/experiments/t5-agent-loop.md`〈4. Ctrl-C、`.runi` 與「續跑」〉與〈7. reliability 題的補充實驗〉且都包含 aos 或另一套假 loop，沒有 no-aos 三行鏈承受同一組三刀後的重開結果，**這條沒有現成資料**。
- `/home/guanyu/aos-hack/core-scope/p3/experiment-round1/ROUND1.md` 記錄 PTY wrapper 與 `aos` 一起被 `^C` 終止；`core/inst/tests/test_run_loop.cpp` 有 loop signal tests，`wf/workflows/experiments/t5-agent-loop.md`〈4. Ctrl-C、`.runi` 與「續跑」〉有 `timeout` 現場，但都不是「PTY 真送 `^C` 且 wrapper 存活、獨立取得 aos exit」的 harness，**這條沒有現成資料**。
- `wf/workflows/workshop/background/questions-reliability.md`〈Deliver／Publish 只保證 rename 的可見性原子，還是提供 `--durable` 承諾斷電後仍存在？〉只有測試方法與選項；`/mnt/c/code/mine/simple_tools/agent-machine/workbench/2026-08-14/p1a2-process-python/PHASE2-EVIDENCE.md`〈明確未驗，不可外推〉也排除 power loss，故斷電後 file data／directory entry 是否仍在，**這條沒有現成資料**。
- `/mnt/c/code/mine/simple_tools/dcap/README.md`〈唯一指令〉至〈給 agent 用〉與 `/mnt/c/code/mine/simple_tools/dcap/tool/README.md`〈失敗時會怎樣〉只有 scaffold CLI、模板與一般退出碼；`/mnt/c/code/mine/simple_tools/freepy/agentloop/CONTROLLER.md`〈明確不負責〉排除持久化與副作用 recovery，兩者都沒有 Publish receipt、Effect resolve 或多 producer delivery 可抄，**這條沒有現成資料**。
