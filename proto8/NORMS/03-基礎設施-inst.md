← [回入口 NORMS.md](../NORMS.md)｜主題：**基礎設施／inst**｜概念：[CONCEPTS 基礎設施 § inst](../CONCEPTS/03-基礎設施.md#inst)｜規範：本檔｜實作：[aos-inst](../bin/README.md)（`bin/aos-inst`、`bin/aos_inst.py`）

同主題：inst｜[loop 與 daemon](04-基礎設施-loop與daemon.md)｜[窗](05-基礎設施-窗.md)｜[命令列與指示詞](06-基礎設施-命令列與指示詞.md)｜[組合子](07-基礎設施-組合子.md)｜[資料夾程式與執行](10-基礎設施-定義與工作區.md)

# 基礎設施／inst

- **N-04** inst 單子裡可以多放東西，inst 不認的別人可以讀（aos-inst 忽略不認的 key）。（3g.13b）
- **N-25**（D-4，草稿；10-19 改）程式內呼叫：`aos_inst.run(x)` 收路徑或一份單子（dict），回 `{"code","signal","timed_out","pid","ms"}`；aos-loop、aos-fsm 在行程內用它跑單子格（P-06、P-07、P-30）。（10-14）
- **N-27**（D-6，草稿；10-19 改，[CONVENTION P-26](../CONVENTION.md)）子程式的參數：aos-exec 把多的 args 與 stdin 原樣送到入口，怎麼進（args、stdin、或 stack 裡的檔）由工具自己的說明定；單子裡 `stdin: "params.json"` 照舊可以把一個檔交給子程式當 stdin，不加新 key。（10-14；10-16 起 agent 的工具見 [N-50](10-基礎設施-定義與工作區.md)）
- **N-30**（原 h4、h5，草稿；10-19 改）aos-inst 的結果 `{"code","signal","timed_out","pid","ms"}` 回給行程內的呼叫者（aos-loop、aos-fsm）：`code`＝子程式的碼（照實轉交的資料，不是 aos-inst 的退出碼；被訊號停掉時是 128＋N，N-43）、訊號號碼另放 `signal`、被逾時殺掉的 `timed_out: true`。命令列上 aos-inst 的結束碼＝子程式的碼（透明轉交，N-43 例外），不另吐結果 JSON；aos-inst 自己出錯一律退 1、stderr 一行 `aos-inst: 原因`。inst 自己不開窗（沒有 state／ctl）。（10-14 深夜；10-19 改，P-21、P-30）
