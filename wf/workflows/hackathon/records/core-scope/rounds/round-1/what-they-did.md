# 第 1 輪紀錄 — 各人做了什麼

← [本輪索引](README.md)｜[書記每輪紀錄](../README.md)｜[本場索引](../../README.md)｜[hackathon](../../../../README.md)｜[同一塊：R2 →](../round-2/what-they-did.md)

四位第一次把三回合 loop 跑完，各自的路線與撞到的第一手現場，逐人一段。

## 1. 各人做了什麼

**Carmack persona。** 這一路用現成的 `./build/bin/aos` 跑一個 world，把三回合固定成「假模型產生具名 tool call → 固定 argv 工具呼叫假 provider → 假模型讀回結果」。基線三回合全到 final，三次 `aos exec` 都回 0。之後在同一條 loop 內測了 SIGINT、SIGKILL，以及 tool result rename 前 SIGTERM；三種事故最後都靠人工處理現場走回 final。SIGKILL 另做了 provider accepted／dropped 兩個外部結果不同、但本機 snapshot 相同的對照。

**Armstrong persona。** 這一路用 POSIX shell、假模型和現成 `aos` 做串行 loop，工具是 allowlist 限制的 `append_once`。所有本機狀態共用一支 `atomic-publish.sh`，`deliver.sh` 只改投遞 target。基線完整跑完；rename 前 SIGKILL、單次 exec 的 SIGINT、provider effect 後 `kill -9` 三個正式事故場也都經人工修復走到 final。Ctrl-C 案封存 `.runi` 後只重投未啟動的 schedule；`kill -9` 案則刻意做了一次盲重試，外部 ledger 由一筆變成兩筆。第一次 baseline 本身成功，但外層 `tee` 因 evidence 目錄尚不存在而沒有保存 transcript，之後另開 fresh world 重跑留證。

**Cantrill persona。** 這一路也是單一 world 的串行三回合 loop，工具是 allowlist 限制的 `write_marker`；本機結果共用 `atomic-publish.sh`，外部效果先進 world 外的假 provider ledger，故障點用 phase marker 定位。基線到 final。Ctrl-C 在 model response 尚未提交時發生，靠 provider query 補回；`kill -9` 在 tool effect 已發生而 result 尚未提交時發生，也靠 provider query 補回；delivery rename 前殺 publisher 後，人工驗 JSON、補 rename 才繼續。第一版 delivery 檔名多了一個點，`aos exec` 三次都回 0 卻完全不取件，失敗 world 保留下來。

**Thompson persona。** 這一路做最小串行鏈：假模型輸出 JSON instruction，三行 `deliver.sh` 投進 inbox，`aos exec` 執行，工具結果再回給假模型。基線三回合閉環，接著測 SIGINT、確認 child 已開始後的 `kill -9`、rename 前停住再殺，以及不可對帳 provider 的 accepted／rejected 對照；前三種靠人工搬開 `.runi` 或補 rename 繼續。最後完全拿掉 `aos`，以三行 shell 跑過同一條因果鏈。第一次 `kill -9` 太早，沒有打中預定切點，因此保留現場後重跑；SIGINT 現場起初以 `wc -l` 把沒有換行的 effect 檔誤報為 0，後以原始 bytes 更正。
