> 封存 2026-11-03：沒有取代者。使用者 11-03 晚「瘦身...這些你提到的，其實都是我有一個模糊的概念，然後就交給AI生成了，整個都需要重新手修一遍，所以說瘦身嗎...也不盡然，或者說可以先封存，等之後我們進展到那塊的時候可以拉出來看看。」

# self-improve（原 proto8/demo/self-improve 與它專用的零件）

底下照原本相對 proto8/ 的路徑擺：`demo/self-improve/`（自我改進流程 run → judge → improve）、`lib/aos/try_run/`（改進者的工具，只有它在用）、`extras/sandbox/examples/self-improve.json`（交辦工作區的沙箱設定例）、`tests/test_self_improve.py`（整檔）、`tests/test_sandbox_self_improve.py`（從 proto8/tests/test_sandbox.py 切出來的 SelfImproveSandboxTest）。環境變數 `AOS_IMPROVE_RUN`、`AOS_IMPROVE_SANDBOX` 只在這裡用，隨之退場。improver/tools 底下 read／write／edit 的相對捷徑指 lib/base，搬來後是斷的。只作歷史，不測試、內部路徑與連結不維護；要拉回去就照路徑搬回原處、切出來的案例併回原檔。設計：proto8/thinking/2026-10/24/self-improve/README.md。
