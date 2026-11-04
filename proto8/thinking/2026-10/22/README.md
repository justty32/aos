# proto8 討論紀錄：2026-10-22

← [2026-10](../README.md)｜[thinking](../../README.md)

規矩見 [thinking/README](../../README.md)。這天的每份一列，一句：定了什麼、還有什麼未決。

| 日期 | 一句話 |
|---|---|
| [2026-10-22 Python 版向 C++ 看齊](ideas/README.md) | bin 版刪 `aos-inst` 命令列、inst 只剩庫；Python 照 C++ 的寬鬆與「程式名: 代號 原因」；C++ 的 loop／fsm／daemon 在子行程直接呼叫 `run_cli`；aos-exec 只用標準庫；`.env` 是 dotenv 基礎子集、預設不蓋原有環境、`--dotenv-override` 只管這一跳；分層：基礎層（核心 aos-exec＋loop、daemon）→ 標準庫（fsm、tasks…）→ agent／kernel，kernel 不譯「核心」；loop、fsm 的實際問題多數使用者自行承擔、條文照程式定稿；daemon 重開＝照名單重新起、子項名字擋撞名、N-28 沒做的從規範拿掉；fsm 開跑時查整張表 |
