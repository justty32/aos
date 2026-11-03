> 封存 2026-11-03：沒有取代者。使用者 11-03 晚「瘦身...這些你提到的，其實都是我有一個模糊的概念，然後就交給AI生成了，整個都需要重新手修一遍，所以說瘦身嗎...也不盡然，或者說可以先封存，等之後我們進展到那塊的時候可以拉出來看看。」

# llm-kernel 示範（原 proto8/demo/llm-kernel）

底下照原本相對 proto8/ 的路徑擺：`demo/llm-kernel/`（一個 daemon 管 LLM kernel 與三隻走 kernel 的 agent-ivy）；`tests/test_llm_kernel_demo.py` 是從 proto8/tests/test_llm_kernel.py 切出來的那一案。aos-llm-kernel、aos-llm-send 兩支程式本身沒封存（proto8/impls/）。環境變數 `AOS_IVY_BRAIN` 只在這裡用，隨之退場。只作歷史，不測試、內部路徑與連結不維護；要拉回去就把 demo/ 搬回原處、那一案併回原測試檔、run.sh 補回那段。設計：proto8/thinking/2026-10-24-llm-kernel.md。
