# proto8 討論紀錄：2026-10

← [thinking](../README.md)

規矩見 [thinking/README](../README.md)。這個月的每天一份，一列一句：定了什麼、還有什麼未決。

| 日期 | 份數 | 一句話 |
|---|---|---|
| [2026-10-11](11/README.md) | 1 | 重來的理由與 aos 基本概念；未決：kernel 資源與排程格式、agent 與工具的引用協議 |
| [2026-10-12](12/README.md) | 4 | tasks 只做 seq／par／if／not、tick-tock 只是時鐘、loop 包 inst、daemon 管 loop 表；未決：監工參數、限時算不算出錯等 |
| [2026-10-13](13/README.md) | 2 | TARGET 吃 `檔#/位置`、`_metainfo` 給 kernel 參考、kernel 基於 daemon、agent＝狀態機；未決：agent 資料夾怎麼放 |
| [2026-10-14](14/README.md) | 1 | 統一入口 stdin／stdout JSON、窗一族、aos-fsm 抽成通用 |
| [2026-10-15](15/README.md) | 20 | 條文按主題分、kernel 截流與 LLM／通用 kernel、JSON 格式族與同像性、兩條總原則與 KISS、命名 C-54、inst／aos-exec 第四版（指示詞以現行 N-45 為準：`$env`、`$ref`，`$ref` 可帶 `$at`） |
| [2026-10-16](16/README.md) | 4 | KISS 也是最後原則、重審五件拍板（批次 2～6 暫停）、agent 當函數是概念上的、結束碼只是參考 |
| [2026-10-19](19/README.md) | 2 | 資料夾＝程式、aos 只訂環境變數、proto8-2 併進 proto8；重寫順序（tasks、通用 kernel 未決） |
| [2026-10-20](20/README.md) | 1 | argv 可放指示詞、argv[0] 帶 `/` 就插 aos-exec、`$path`／`$prefix`；未決：`$fmt`、D15 |
| [2026-10-21](21/README.md) | 2 | aos-exec 旗標放前面、`.env` 的讀法；loop／daemon／fsm／tick 計畫已做 |
| [2026-10-22](22/README.md) | 1 | Python 版向 C++ 看齊、分層（基礎層 → 標準庫 → agent／kernel） |
| [2026-10-23](23/README.md) | 6 | 命名統合與命名方法（R1～R12）、daemon 壓測修正、ctl 只寫變動與 `$ref` 陣列、aos-agent＝範本、腦的工具呼叫；未決：kernel 怎麼做 |
| [2026-10-24](24/README.md) | 20 | 二十份嘗試（多是 demo、代定可翻案）：`exec` 收內嵌單子、`_metainfo`、工具＝函式庫三層、LLM kernel 第一版、沙箱等；未決在各份 |
| [2026-10-25](25/README.md) | 1 | 兩隊由上而下拆 galtxt；沒有人評、量測沒做完 |
| [2026-10-26](26/README.md) | 1 | claude code cli 節點一步步做、經 aos-mcp 接 aos 工具 |
| [2026-10-27](27/README.md) | 1 | 很多 claude 的小格登記與 aos-hub 接入／收起／叫回 |
| [2026-10-28](28/README.md) | 6 | aos-hub 常駐 kernel（10-30 起改做 aos-eca-hub）、工具註冊檔 aos-tools、各單位都是 aos 函數、round 設計（11-03 晚整條刪）、介質概念收線 |
| [2026-10-29](29/README.md) | 3 | 介質細節規劃（都照建議、已實作）、看信箱 tool 解錯題、bob 兩隻實跑與決定 33～35 |
| [2026-10-30](30/README.md) | 4 | agent 的 queue 與外部 agent 生命週期、地圖各點的去向、eca 規劃（都照建議、已做）、aos-round（11-01 刪） |
| [2026-10-31](31/README.md) | 2 | aos-var 收回、parts 退成約定（11-01 裁、aos-parts 刪）、round 不重切（使用者要深思） |
