# 撈遺產：proto2 的 aos-agent 有哪些決定值得帶進 proto4-7

你在 repo `/home/lorkhan/repo/simple_tools/aos`。**只讀，不改任何檔**，不 commit、不開 agent。

## 背景

使用者 2026-09-13 說：「在此基礎上幫我弄一個簡單的 agent，就跟 proto2 那樣。」「此基礎」＝今天的 proto4 那套：`proto4-3/`（aos-exec／aos-run／daemon／kernel、inst.json）、`proto4-5/`（`aos-llm call` 一次呼叫、`aos-kernel llm K req --name X` 丟給 kernel 排隊、結果在 `K/llm/results/X.json`）、`proto4-6/`（逐步 JSON／Python／Lua，`wait_for` 等檔退 101）。先讀這三份 README 各一遍，知道新地基長什麼樣。

使用者另一條規矩：舊 proto 是遺產，**可以參考、謹慎採用**，逐條說採不採、為什麼，不照搬檔案。

## 去讀

- `proto2/README.md` 的 aos-agent／aos-user／信箱／工具（packs）那幾節；`proto2/aos-agent`、`proto2/aos_agent.py`、`proto2/aos-user`；`proto2/packs/` 隨便挑兩個看工具怎麼定義；`proto2/examples/agent/`；`proto2/docs/` 跟 agent 有關的；`proto2/notes/` 裡 lessons／play 類的（找「agent」、「retry」、「stuck」、「inbox」、「tool」相關的段，不用全讀）。
- `proto/`、`proto3/`、`proto4-2/` 若有 agent 相關的也掃一眼，有就列、沒有就說沒有。

## 交出來

寫一份 markdown 直接回我（不要寫進 repo），繁體中文、大白話、200 行以內：

1. **proto2 agent 的骨架**（一段話＋一張表）：七個 state 各做什麼、檔案佈局、信箱格式、工具怎麼宣告與怎麼跑、`aos-user` 有哪些子命令。
2. **逐條決定表**：每條一列——「proto2 怎麼做／為什麼那樣做（筆記裡找得到就引）／在 proto4 地基上建議：採、改、不採／一句理由」。至少涵蓋：資料夾佈局、messages 存法、state 機（七格會不會太多）、retry／stuck 規則、信箱一來源一資料夾、outbox 四位數編號、工具宣告格式（packs／tools.json）、工具回傳怎麼接回記憶、模型把 tool call 寫成文字的救回、`max_steps_per_question`、空白回覆處理、`--home`、kids／contacts／side packs／MCP／預算（這幾個使用者說先不做，只要說「不採，理由」即可）。
3. **proto2 玩出來的坑**（lessons／play 筆記裡的）哪些在新地基上會再撞、哪些自然消失（因為 LLM 排程、等檔退 101、kernel 都有了）。
4. **你建議的 v1 最小集**：十行以內。
