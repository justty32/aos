← [回入口 NORMS.md](../NORMS.md)｜主題：**基礎設施／inst**｜概念：[CONCEPTS 基礎設施 § inst](../CONCEPTS/03-基礎設施.md#inst)｜規範：本檔｜實作：[aos-inst](../bin/README.md)（`bin/aos-inst`、`bin/aos_inst.py`）；impls 線（使用者假日的 C／C++ 參考實作，git 未追蹤）inst 是 C lib、不提供命令列，單子由 aos-exec 行程內跑（[ideas § 20](../thinking/2026-10-19-ideas.md)）

> **兩版實作（10-19 晚，§ 20、§ 21）**：下面講「aos-inst 命令列」「`aos_inst.run()`」的句子是 `proto8/bin` 那版（Python）的樣子。impls 線沒有 aos-inst 命令列（使用者：「aos-inst可以不用，inst和inst json格式，他就是一個C lib，也不提供cli」），單子格式的 JSON 解析不進 C 庫（使用者：「json不要寫進去」）、放在 aos-exec 的 C++ 庫；行程內跑單子的函數是 aos-exec 公開 API 的 `run_inst`，回的東西跟 N-30 的結果同一組欄位（`code`、`signal`、`timed_out`、`pid`、`ms`）。bin 版的 aos-exec 10-19 晚也改成行程內跑單子（呼叫 `aos_inst.run()`），aos-inst 命令列只剩 CONVENTION P-28 的 (A)、(1) 兩種寫法在用。規範本身（單子格式、結果欄位、透明轉交）兩版一樣（指示詞 `$ref` 只有 impls 解得開，[N-45](06-基礎設施-命令列與指示詞.md)）；單子的 `argv[0]` 是 `+x` 但沒 `#!` 的檔，兩版都照 execvp 退回 sh 跑（使用者 § 21「不擋」；10-19 晚使用者選「乙」，aos-exec 自己 exec 的入口也一樣退回 sh，三處一致，N-59 第 6 件、[ideas § 22](../thinking/2026-10-19-ideas.md)）。

同主題：inst｜[loop 與 daemon](04-基礎設施-loop與daemon.md)｜[窗](05-基礎設施-窗.md)｜[命令列與指示詞](06-基礎設施-命令列與指示詞.md)｜[組合子](07-基礎設施-組合子.md)｜[資料夾程式與執行](10-基礎設施-定義與工作區.md)

# 基礎設施／inst

- **N-04** inst 單子裡可以多放東西，inst 不認的別人可以讀（aos-inst 忽略不認的 key）。（3g.13b）
- **N-25**（D-4，草稿；10-19 改）程式內呼叫：`aos_inst.run(x)` 收路徑或一份單子（dict），回 `{"code","signal","timed_out","pid","ms"}`；aos-loop、aos-fsm 在行程內用它跑單子格（P-06、P-07、P-30）。（10-14）impls 線對應的是 aos-exec 公開 API 的 `run_inst(單子, 基準資料夾, args)`，回同一組欄位；之後的 loop／daemon「可以隨意使用指示詞,json schema，還有aos-exec的公開api」（使用者 10-19 晚，[ideas § 20](../thinking/2026-10-19-ideas.md)）。
- **N-27**（D-6，草稿；10-19 改，[CONVENTION P-26](../CONVENTION.md)）子程式的參數：aos-exec 把多的 args 與 stdin 原樣送到入口，怎麼進（args、stdin、或 stack 裡的檔）由工具自己的說明定；單子裡 `stdin: "params.json"` 照舊可以把一個檔交給子程式當 stdin，不加新 key。（10-14；10-16 起 agent 的工具見 [N-50](10-基礎設施-定義與工作區.md)）
- **N-30**（原 h4、h5，草稿；10-19 改）aos-inst 的結果 `{"code","signal","timed_out","pid","ms"}` 回給行程內的呼叫者（aos-loop、aos-fsm）：`code`＝子程式的碼（照實轉交的資料，不是 aos-inst 的退出碼；被訊號停掉時是 128＋N，N-43）、訊號號碼另放 `signal`、被逾時殺掉的 `timed_out: true`。命令列上 aos-inst 的結束碼＝子程式的碼（透明轉交，N-43 例外），不另吐結果 JSON；aos-inst 自己出錯一律退 1、stderr 一行 `aos-inst: 原因`。inst 自己不開窗（沒有 state／ctl）。（10-14 深夜；10-19 改，P-21、P-30）impls 線：沒有 aos-inst 命令列，單子當入口時由 aos-exec 行程內跑、aos-exec 以子程式的碼結束（同樣是透明轉交，N-59 第 6 件）；單子壞＝aos-exec 自己的錯退 1（§ 20）。
