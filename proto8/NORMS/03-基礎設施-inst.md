← [回入口 NORMS.md](../NORMS.md)｜主題：**基礎設施／inst**｜概念：[CONCEPTS 基礎設施 § inst](../CONCEPTS/03-基礎設施.md#inst)｜規範：本檔｜實作：[lib inst.md](../lib/inst.md)

同主題：inst｜[loop 與 daemon](04-基礎設施-loop與daemon.md)｜[窗](05-基礎設施-窗.md)｜[命令列與指示詞](06-基礎設施-命令列與指示詞.md)｜[組合子](07-基礎設施-組合子.md)

# 基礎設施／inst

- **N-04** inst.json 裡可以多放東西，inst 不認的別人可以讀。（3g.13b）
- **N-24**（D-2，草稿）`--`：`aos-inst [旗標] [TARGET] -- cmd args…`，`--` 後面整段蓋過設定的 `argv`；可與 JSON 併用。不收 `--` 的程式（loop、daemon）報錯。（10-14）
- **N-25**（D-4，草稿）程式內呼叫：aos-inst 的 `run(x)` 收路徑或一份設定 dict（dict＝命令列合成好的那份設定）；loop 起 aos-inst 改成直接起子程序、從 stdin 灌設定，`run()` 主要給 tasks 和人用。（10-14）
- **N-27**（D-6，草稿）子程式的參數：用現有的 inst key `stdin: "params.json"` 交給子程式，不加新 key；LLM 工具轉接時把 arguments 落成 call.json。（10-14）10-15 收工後（[意見 1～4](../thinking/2026-10-15-opinions-1-4.md) Q11）：agent 的工具每次在一個新資料夾裡跑（預設呼叫者 `work/<n>/`），arguments 落成那裡的 `args.json`，也照本條當 stdin；那個資料夾要不要當 frame 是那張工具 inst 自己的事，agent 不知道（C-52，10-15 深夜）。
- **N-30**（原 h4、h5，草稿）aos-inst 的結果（stdout 那一份）帶 `id`、`code`、`signal`：`code`＝子程式的碼（照實轉交的資料，不是 aos-inst 的退出碼；被訊號停掉時是某個非 0 的數，基礎實作用 128＋N；規範只認 0／非 0，N-43），訊號號碼另放 `signal`。aos-inst 自己出錯一律退 1、是哪種錯看 stderr 的 `code`（原本 127／126／125，10-15 晚收掉）。`id` 沒寫＝TARGET 的 `realpath#/位置`；設定從 stdin 來又沒寫才是 null。**沒有 exit 檔**（10-15 深夜 KISS 批次 1 拿掉，原「選填、與舊時代的橋樑」，見 [KISS 彙整批次 1](../thinking/2026-10-15-kiss/README.md#批次-1純刪彼此不相依不碰第四版的形狀) 1.1）：要子程式的碼，讀這份結果的 `code`。inst 自己不開窗（沒有 state／ctl）。（10-14 深夜）
