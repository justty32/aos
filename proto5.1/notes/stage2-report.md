# 第 2 段回報（2026-09-22）

A／B／C／E 已完成：共用 CPU 佇列、tool CPU、act 整批送收與有限自癒、測試與真跑；D 依任務書現行要求只評估、保持 KISS。沒有新增結果 name 或 state ask／calls。

只修改 `proto5.1/`，分支仍為 main；未執行 git commit／push／stash／checkout。`proto5/` 無 diff，最後 git status 的所有變更均在 proto5.1。

## 檔案清單

下列路徑相對 `proto5.1/`；使用者提供的 `notes/stage2-task.md` 保持原檔，不列為本次產出。

| 類別 | 檔案 |
|---|---|
| 新增程式／入口 | `lib/aos_cpu.py`、`lib/aos_tool_cpu.py`、`cli/aos-tool-cpu` |
| 修改程式 | `lib/aos_llm_cpu.py`、`lib/aos_agent.py`、`lib/aos_agent_info.py` |
| 新增測試 | `lib/test/test_cpu.py`、`lib/test/test_tool_cpu.py` |
| 擴充測試 | `lib/test/test_agent.py`、`lib/test/test_agent_info.py` |
| 新增規範 | `spec/cpu-queue.md`、`spec/tool-cpu.md`、`spec/aos-tool-cpu.md` |
| 修改規範 | `spec/llm-cpu.md`、`spec/aos-llm-cpu.md`、`spec/aos-agent.md`、`spec/agent.md`、`spec/aos-llm-ask.md` |
| 導航與逐檔 API | `README.md`、`lib/README.md` |
| findings／驗證 | `notes/findings.md`、`notes/stage2-demo.py`、`notes/stage2-trace.json`、`notes/stage2-report.md`（本檔） |

共 24 個產出檔案；另有被既有 `.gitignore` 忽略的 `.build/` 建置、測試紀錄與真跑資料。

## 測試

從 repo 根執行：

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=proto5.1/lib python3 -m unittest discover -s proto5.1/lib/test
nice -n 19 cmake --build proto5.1/.build -j 4
ctest --test-dir proto5.1/.build --output-on-failure
```

- **Python 686/686，44.064 秒，OK，無 skip**。保留既有 635 條，新增 51 條；LLM CPU 原有 29 條未改。
- 分項：directives 101、inst 139、exec 94、agent_info 98、llm_ask 54、agent 141、llm_cpu 29、cpu 14、tool_cpu 16。
- **C++ build 成功、ctest 8/8，5.41 秒**。沿用第 1 段同 default 配置的 `proto5.1/.build`；根 default cache 路徑問題見 findings #7，本次未改根 build／preset。
- `git diff --check` 通過。Python 完整輸出在 `.build/stage2-tests.log`。
- 新增覆蓋：三處撞名、並行認領與鎖外執行、收屍和遲到回覆、工具真逾時與普通 exit 143、壞 payload／共同欄位、混合 call 順序、全部結果預驗、半批結果補等待、兩處收尾故障注入，以及部分交件中斷的已知等待限制。

## LM Studio 真跑

端點 `http://127.0.0.1:1234/v1`，模型 `qwen/qwen3-1.7b`；沒有強制 tool_choice。腳本：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 proto5.1/notes/stage2-demo.py
```

腳本每次建立全新 `.build/stage2-demo-<ns>`，避免蓋舊資料。本次資料在
`proto5.1/.build/stage2-demo-1790043916127146209/`，A＝agent、C＝llm CPU、T＝tool CPU。
A 的 now 工具為 `_run:cpu`、`_timeout_ms:10000`，內容 `sleep 2; date`，TZ=Asia/Taipei。
完整原始逐次紀錄見 [stage2-trace.json](stage2-trace.json)，含耗時、stdout、stderr、before／after。

下表 L 表示 `["ask-result.json"]`；T 表示 `[{"$opt":"all","$val":["<A 的絕對路徑>/tool-results/0.json"]}]`；— 表示空 waits。

| 次序 | CLI | 退出碼 | state 前→後 | waits 前→後 |
|---|---|---|---|---|
| 1 | `aos-agent A` | 0 | idle → think | — → — |
| 2 | `aos-llm-cpu C` | 101 | think → think | — → — |
| 3 | `aos-tool-cpu T` | 101 | think → think | — → — |
| 4 | `aos-agent A` | 0 | think → think | — → L |
| 5 | `aos-agent A` | 101 | think → think | L → L |
| 6 | `aos-llm-cpu C` | 0 | think → think | L → L |
| 7 | `aos-tool-cpu T` | 101 | think → think | L → L |
| 8 | `aos-agent A` | 0 | think → act | L → — |
| 9 | `aos-llm-cpu C` | 101 | act → act | — → — |
| 10 | `aos-tool-cpu T` | 101 | act → act | — → — |
| 11 | `aos-agent A` | 0 | act → act | — → T |
| 12 | `aos-agent A` | 101 | act → act | T → T |
| 13 | `aos-llm-cpu C` | 101 | act → act | T → T |
| 14 | `aos-tool-cpu T` | 0 | act → act | T → T |
| 15 | `aos-agent A` | 0 | act → think | T → — |
| 16 | `aos-llm-cpu C` | 101 | think → think | — → — |
| 17 | `aos-tool-cpu T` | 101 | think → think | — → — |
| 18 | `aos-agent A` | 0 | think → think | — → L |
| 19 | `aos-agent A` | 101 | think → think | L → L |
| 20 | `aos-llm-cpu C` | 0 | think → think | L → L |
| 21 | `aos-tool-cpu T` | 101 | think → think | L → L |
| 22 | `aos-agent A` | 0 | think → idle | L → — |
| 23 | `aos-llm-cpu C` | 101 | idle → idle | — → — |
| 24 | `aos-tool-cpu T` | 101 | idle → idle | — → — |
| 25 | `aos-agent A` | 101 | idle → idle | — → — |

所有 CLI 的 stdout／stderr 都空、errors 都是 0。第 5／12／19 次主動在 CPU 尚未執行時叫 agent，確認門未開退 101、state／waits 不變。
兩次 LLM CPU 呼叫分別 2.033／1.640 秒；工具 CPU 執行 2.032 秒，agent 送工具一格只有 0.050 秒。
結果成功收回後 `tool-results/0.json.done` 在、原 `.json` 不在；T/done 一份、C/done 兩份。

工具原始輸出：`2026-09-22 10:25:20 CST`。模型最終回覆原文：

> 現在時間是2026年9月22日中午10:25。

第 25 次 agent 退 101，state=idle、waits=[]。本次驗證流程完成；上面的「中午」是模型原文措辭，工具實際時間如前。

## Findings：新增 9 條，#18～#26

最重要五條：

1. **#19 共用層邊界**：只有一個佇列模組與函式；LLM／tool payload 驗法仍各自負責，既有鎖與收屍保證保留。
2. **#21 全批預驗**：任何工具結果壞掉，不能先清 waits 或跑 sync 的副作用；inst 解不開則形成可收回的失敗結果。
3. **#22 有限自癒**：完整工具批次已接進記憶，封存到一半或 state 未寫都可收尾，不再跑 sync。
4. **#23 殘留中斷窗口**：半批提交可能重送或永久等待；sync 副作用與記憶之間也不是交易。故障測試明確重現等待限制。
5. **#26 B 方案評估**：請求身分有用，但三個欄位不等於只執行／只收回一次。

其他：#18 任務 D／E 衝突的採用界線、#20 壞 payload 的回報分界、#24 CPU 環境真跑、#25 結果文字與執行狀態。

## D 的拍板結論

目前這個可重建、人工觀察的原型可維持 KISS，接受 #11～#13／#23 的中斷限制；若下一步要崩潰後自動續跑、又不能接受工具重做或結果串單，就值得採 B，但應把「請求身分＋送件恢復」一起納入。代價至少是結果 name、state ask／calls 三個欄位，加上字面讀驗、先記名／重用、缺單恢復、錯配封存／補等待、清除身分及其故障測試。它可辨認 #11 舊收屍結果、改善 #13 結果歸屬；#12 重送只有在先記名並恢復送件後才改善。單靠這三格仍不能證明文字回覆已接過記憶、避免 errors 重計／漏計或工具副作用重做，這些需要消費紀錄或交易。本段只評估、未實作對帳。

## 尚未處理的範圍

第 2 段已完成；沒有新增一般請求對帳、跨檔交易、agent 並行鎖、排隊／waits 期限或第 3 段 daemon／kernel。
