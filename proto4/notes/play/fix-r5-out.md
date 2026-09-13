fix-r5 #1–#8 已完成，沒有未做項目。未呼叫真 LLM、未讀 API key，也沒有 commit、push 或開 agent；既有 `playground/` 完全未碰。

### 各條處理

1. proto4-5 quickstart 補齊 daemon → init module → boot → 等一回合 → 改 endpoint → 投單，並統一 PATH 指令慣例。
2. proto4-6 Python 節補完整三格範例、`K = "/abs/K"`、函式簽名、兩種 LLM 家的差異，並明定 state JSON 是公開介面。
3. 自動生成的 `endpoints.json` 改為 `indent=2`；init 直接提醒換 model；kernel status 遇到 placeholder 顯示警告。
4. 撞名訊息補解法；新增 `aos-kernel llm ls K`、`rm K NAME`。running 會先終止 worker，失敗則保留檔案並退 1；`ls.json` 請求檔不會誤判。
5. README 明講 kernel 不活時，不論有無 `--wait` 都撤單、不排隊。
6. 四支執行器原本已具備 reset 刪 error 的行為；補上實際先製造錯誤、再驗 error 消失及 status 乾淨的測試與文件。
7. README 明講 `aos-kernel ls` 最多落後一回合。
8. `LAST_EXIT` 改為新行程實際跑過後才顯示；RUNS=0 固定顯示 `-`。

### 修改檔案

- proto4-3：[aos_kernel.py](/home/lorkhan/repo/simple_tools/aos/proto4-3/aos_kernel.py)、[aos_kernel_init.py](/home/lorkhan/repo/simple_tools/aos/proto4-3/aos_kernel_init.py)、[aos_kernel_status.py](/home/lorkhan/repo/simple_tools/aos/proto4-3/aos_kernel_status.py)、[test_kernel.py](/home/lorkhan/repo/simple_tools/aos/proto4-3/test/test_kernel.py)
- proto4-4：[README.md](/home/lorkhan/repo/simple_tools/aos/proto4-4/README.md)、[step.janet](/home/lorkhan/repo/simple_tools/aos/proto4-4/test/step.janet)
- proto4-5：[README.md](/home/lorkhan/repo/simple_tools/aos/proto4-5/README.md)、[llm_cpu_home.py](/home/lorkhan/repo/simple_tools/aos/proto4-5/llm_cpu_home.py)、[llm_cpu_module.py](/home/lorkhan/repo/simple_tools/aos/proto4-5/llm_cpu_module.py)、[llm_cpu_manage.py](/home/lorkhan/repo/simple_tools/aos/proto4-5/llm_cpu_manage.py)、[test_module.py](/home/lorkhan/repo/simple_tools/aos/proto4-5/test/test_module.py)、[test_module_manage.py](/home/lorkhan/repo/simple_tools/aos/proto4-5/test/test_module_manage.py)
- proto4-6：[README.md](/home/lorkhan/repo/simple_tools/aos/proto4-6/README.md)、[test_step_json.py](/home/lorkhan/repo/simple_tools/aos/proto4-6/test/test_step_json.py)、[test_step_py.py](/home/lorkhan/repo/simple_tools/aos/proto4-6/test/test_step_py.py)、[test_step_lua.py](/home/lorkhan/repo/simple_tools/aos/proto4-6/test/test_step_lua.py)
- 導航：[code-map.md](/home/lorkhan/repo/simple_tools/aos/wf/workflows/common/code-map.md)

### 測試數字

| 邊 | Baseline | 最終 |
|---|---:|---:|
| proto4-3 | 236 | 237 |
| proto4-5 | 56 | 63 |
| proto4-6 | 77 | 77 |
| proto4-4 | 42／46／12 | 42／48／12 |

任務書寫 proto4-4 step baseline 為 45，但實際開工時已是 46。

另已通過：

- 根目錄 `cmake --build --preset default`
- `ctest --preset default`：8/8
- `git diff --check`
- 所有本次涉及且原先未超限的程式碼／README 仍不超過 300 行。