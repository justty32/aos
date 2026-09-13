完成，只改 `proto4-6/`，未 commit／push。
- `aos-step-py` 2 行；`aos_step_py.py` 203 行；`aos_py.py` 115 行；`step_common.py` 58 行。
- `aos_step_json.py` 抽共用後 172 行；README 148 行；Python 測試 178 行。
- 測試共 30 條：既有 JSON 15＋新增 Python 15；指定指令最後一行：`OK`。
- Repo 整體 build＋ctest：8/8，全綠。
- 自決：`--status` 的狀態留 stdout、traceback 放 stderr，方便程式解析。
- 踩坑：同秒等長改檔可能誤吃舊 `.pyc`；已改成編譯當次讀取的原始 bytes。
- 沒做到的：無；測試只連本機假 OpenAI server，沒有打真網路。