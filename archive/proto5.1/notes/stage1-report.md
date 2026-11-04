# 第 1 段回報（2026-09-22）

- 完成 llm cpu 資料夾／請求／結果協議與 CLI、agent 非同步 think、工具預設 60 秒／覆寫與真逾時旗標、引擎連敗 3 次暫停與 touch 恢復。
- 只改 proto5.1；分支仍是 main。未執行 git commit／push／stash／checkout。母本 proto5 的 64 個檔案 SHA-256 前後完全相同。
- [findings.md](findings.md) 共 17 條，包含具體檔名、故障流程、選擇與限制。優先看 #1（rename／短鎖）、#8～#9（mtime／遲到 HTTP）、#11～#13（跨檔中斷與結果歸屬）、#3（再次暫停）、#4（逾時旗標）。

## 檔案清單

| 群組 | 檔案（相對 proto5.1） |
|---|---|
| 新增程式 | `lib/aos_llm_cpu.py`、`cli/aos-llm-cpu` |
| 修改程式 | `lib/aos_agent.py`、`lib/aos_agent_info.py`、`lib/aos_exec.py`、`lib/aos_llm_ask.py` |
| 新增測試 | `lib/test/test_llm_cpu.py` |
| 補充測試 | `lib/test/test_agent.py`、`lib/test/test_agent_info.py`、`lib/test/test_exec.py`、`lib/test/test_llm_ask.py` |
| 新增規範 | `spec/llm-cpu.md`、`spec/aos-llm-cpu.md` |
| 更新規範與導航 | `spec/agent.md`、`spec/aos-agent.md`、`spec/aos-llm-ask.md`、`README.md`、`lib/README.md` |
| 驗證與筆記 | `.gitignore`（只忽略獨立 build）、`notes/findings.md`、`notes/stage1-demo.py`、本回報 |

## 測試

從 repo 根執行：

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=proto5.1/lib python3 -m unittest discover -s proto5.1/lib/test
```

- 改前：571 tests，36.457 秒，OK。
- 改後：**635 tests，43.467 秒，OK**。新增 64，沒有刪或 skip 原測試；少數明確與新契約衝突的斷言已更新（findings #2）。
- 分項：directives 101、inst 139、exec 94、agent_info 93、llm_ask 54、agent 125、llm_cpu 29。
- 含 FakeLLM HTTP 成敗、真兩進程搶同單（0／101、只送一次 HTTP）、Barrier 驗兩 CPU 真正同時進 HTTP、收屍及遲到回覆、壞 JSON／UTF-8、故障注入、工具真進程超時／普通 exit 143 區別。
- 根 default build 命令先因舊 cache 路徑與 Catch2 查找失敗。保留根設定，改用以下相同 default 配置、隔離產物位置；build 成功，**ctest 8/8 全過，5.21 秒**：

```sh
cmake --preset default -B proto5.1/.build
nice -n 19 cmake --build proto5.1/.build -j 4
ctest --test-dir proto5.1/.build --output-on-failure
```

`ctest --preset default --test-dir …` 在此環境仍會回根 build，實際驗證使用上面不帶 preset 的 test-dir 命令（findings #7）。

## LM Studio 真跑

`http://127.0.0.1:1234/v1`，`qwen/qwen3-1.7b`，兩次真模型請求、一個 now 工具，沒有強制 tool_choice。
腳本：[stage1-demo.py](stage1-demo.py)（建全新 demo，不覆蓋既有資料）。

實機產物：`/tmp/claude-1000/-home-guanyu-projs-aos/c15290bb-f956-4ef2-8f96-46acea00faa2/scratchpad/p51-demo/`。
A 是 agent、C 是 CPU；A/engine.cpu 為 `../C`、input 為「現在幾點？用工具查」。`trace.json` 是每次呼叫的完整紀錄，A 的 history 與 C/done 請求均保留。

| 次序 | 呼叫 | 退出碼 | agent state | agent waits |
|---|---|---|---|---|
| 1 | `aos-agent A` | 0 | idle → think | [] → [] |
| 2 | `aos-llm-cpu C` | 101 | think → think | [] → [] |
| 3 | `aos-agent A` | 0 | think → think | [] → ask-result.json |
| 4 | `aos-llm-cpu C` | 0 | think → think | ask-result.json → ask-result.json |
| 5 | `aos-agent A` | 0 | think → act | ask-result.json → [] |
| 6 | `aos-llm-cpu C` | 101 | act → act | [] → [] |
| 7 | `aos-agent A` | 0 | act → think | [] → [] |
| 8 | `aos-llm-cpu C` | 101 | think → think | [] → [] |
| 9 | `aos-agent A` | 0 | think → think | [] → ask-result.json |
| 10 | `aos-llm-cpu C` | 0 | think → think | ask-result.json → ask-result.json |
| 11 | `aos-agent A` | 0 | think → idle | ask-result.json → [] |
| 12 | `aos-llm-cpu C` | 101 | idle → idle | [] → [] |
| 13 | `aos-agent A` | 101 | idle → idle | [] → [] |

每次 errors 都是 0、stdout／stderr 都空。now 工具實際輸出 `2026-09-22 10:10:50 CST`；最終 assistant 回覆：

> 今天是2026年9月22日，現在時間是上午10點10分50秒。

第 13 次 agent 退 101，state=idle、waits=[]，完整往返完成。

## 還沒做的

- 第 1 段任務已完成。第 2 段 tool cpu／_run:cpu、第 3 段 run／daemon／kernel 按分段未做。
- 未擴增 request id／pending／跨檔交易；請求送出與 waits、結果與記憶／state、CPU 結果與 done 之間仍有已具體記錄的崩潰窗口。沒有宣稱 exactly-once。
- 未加入排隊期限、waits 期限、HTTP／整格 hard deadline、agent 並行鎖、usage、優先序或自動重試。
- 根 build 舊 cache 未修；已在 proto5.1 內用獨立 build 跑完相同 C++ 測試。
