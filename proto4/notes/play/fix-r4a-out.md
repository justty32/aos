完成，只修改 `proto4-5/`，沒有 commit、push 或開 agent。

改動：

- [README.md](/home/lorkhan/repo/simple_tools/aos/proto4-5/README.md)：補兩份可直接抄的 local endpoint 設定、結果欄位分組、模型預檢、`--json`、逾時後果、同名冪等規則，以及移出的遠端／process 範例。
- [aos_llm.py](/home/lorkhan/repo/simple_tools/aos/proto4-5/aos_llm.py)：`strict_model:true` 先查 `/models`；找不到回 `model_not_found` 且不送 chat。`/models` 失敗則照送並記入 `notes`。沒有有效回應時 `model:null`。
- [llm_cpu_home.py](/home/lorkhan/repo/simple_tools/aos/proto4-5/llm_cpu_home.py)：預設 endpoints 只留 local；首次建立會提示更換 model；加入正規化請求 SHA-256。
- [llm_cpu_module.py](/home/lorkhan/repo/simple_tools/aos/proto4-5/llm_cpu_module.py)：成功 `--wait` 只印 text＋結果路徑；`--json` 才印完整 JSON；逾時區分撤單與已送出；同名同內容安全重用，不同內容指出衝突位置。
- [llm_cpu_tick.py](/home/lorkhan/repo/simple_tools/aos/proto4-5/llm_cpu_tick.py)、[llm_cpu_worker.py](/home/lorkhan/repo/simple_tools/aos/proto4-5/llm_cpu_worker.py)：保存請求指紋至 request/result。
- 假 server 與測試：[_fake_openai.py](/home/lorkhan/repo/simple_tools/aos/proto4-5/test/_fake_openai.py)、[test_aos_llm.py](/home/lorkhan/repo/simple_tools/aos/proto4-5/test/test_aos_llm.py)、[test_home.py](/home/lorkhan/repo/simple_tools/aos/proto4-5/test/test_home.py)、[test_module.py](/home/lorkhan/repo/simple_tools/aos/proto4-5/test/test_module.py)。

驗證結果：

- `proto4-3`：baseline 實際 235，最後 236，全綠；任務書的 226 已被並行工作增加。
- `proto4-4`：42／45／12 → 42／46／12，全綠。
- `proto4-6`：71 → 77，全綠。
- `proto4-5`：45 → 56，全綠。
- repo 根目錄 build 成功，ctest 8/8 全綠。
- 所有修改後的單檔均未超過 300 行。
- LM Studio 真打成功：`/models` 找到 `google/gemma-4-e4b`，chat 回 `OK`，預檢沒有擋住正確模型。

沒有呼叫 DeepSeek，也沒有讀取任何 API key。其他 proto 的工作樹變更屬於同期作業，我未修改。