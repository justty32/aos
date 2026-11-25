← [回入口 附錄1-名詞.md](../附錄1-名詞.md)｜附錄 1 名詞｜上一份：[02-inst到table](02-inst到table.md)｜下一份：[附錄1-續-板子比喻](../附錄1-續-板子比喻.md)

## 1. 名詞（三）：aos-exec、stack、工作區、分層

| 詞 | 使用者的意思 | 出處 |
|---|---|---|
| `aos-exec [FLAGS...] XXX [args...]` | 「在工作區執行 XXX 這個程式」：XXX 前面是 aos-exec 自己的旗標（`--ws WS`＝工作區，沒給沿用 `$AOS_WS`；`--stack S`；`--stack-lazy`＝不先建 stack 資料夾；`--dotenv-override`），之後原樣傳給入口；XXX 可以是資料夾、檔、或 `檔#/指標`；找到入口、設好 `AOS_WS`、`AOS_STACK`、`AOS_CF`、`AOS_CD`，cd 到入口檔所在的資料夾，讀那裡的 `.env`（預設不蓋已有的：旗標 ＞ 環境變數 ＞ `.env`；加 `--dotenv-override` 才是旗標 ＞ `.env` ＞ 環境變數 ＞ 預設），開跑——可執行檔與 argv 陣列 exec、inst 單子行程內跑（C-68、N-58、N-59、N-61）。impls 的命令列從 aos-exec 起（[ideas § 20](../../../thinking/2026-10/19/ideas/README.md)），另有 aos-loop、aos-fsm（§ 23）、aos-daemon | 10-19、10-21 |
| stack（`AOS_STACK`） | **被叫的那個程式自己的執行中狀態放哪**（預設 `$AOS_WS/.stack/`）：狀態、草稿、叫別的程式時開的小格。像函數的呼叫堆疊（C-46、C-65）。放哪由呼叫方自由決定（C-67）。名字照使用者（「不過frame那塊能不能換成stack(或heap)?。」→ 頂層推薦 stack →「好！」） | 10-16 夜、10-19 |
| 小格 | 叫別的資料夾程式（工具、另一個 agent）時給它的 stack：`$AOS_STACK/tools/<名>/`，小格名＝工具資料夾名；叫的時候不先建，工具真的寫東西才建（[tool-cells-lazy](../../../thinking/2026-11/11/tool-cells-lazy.md)）；叫完不自動收（見 [P-17](../../CONVENTION/02-題目stack停錯腦.md)）。三種「格」分開講——「小格」只指這裡的 `tools/<名>/`（叫工具時給的 stack）；fsm 的「格」是狀態機的一個狀態（idle、think…）；daemon 的 `procs/<名>/`（或那個 proc 寫的 `stack`）叫「proc 的 stack」，不叫小格。 | 10-19、11-02 |
| heap | **保留**：以後指跨呼叫共用的記憶，目前沒有機制 | 10-16 夜 |
| 工作區（`ws`，workspace） | 使用者的檔、成品要留的地方；保持乾淨，只放交辦的東西與成果。位置由環境變數 `AOS_WS` 給（C-65、C-66、N-55） | 10-16 夜 |
| 指標 | 工具要影響外部（呼叫者的工作區）時拿到的那個東西；在 aos 就是環境變數 `AOS_WS`（C-66） | 10-16 夜 |
| 基礎層 | 分層的最下層：核心 aos-exec（含 inst 庫、指示詞、旗標）＋ loop、daemon（C-74） | 10-22 |
| 核心（分層） | 基礎層中的核心＝aos-exec（使用者「aos-exec是core，是基礎中的基礎」）；C-74 分層裡說的核心就是它，C-12、C-18 的「核心」是「核心（aos 作業系統核心）」那列；kernel 不叫核心（C-74） | 10-22 |
| 標準庫 | 基礎層之上：fsm、tasks、其他；再上去是 agent／kernel（C-74）。跟「純標準庫 Python」（只用 Python 自帶的庫）是兩回事 | 10-22 |
| std（庫） | `agent.py` 裡**隨 aos 發的那一份庫**（`std = defs.std`），根是 `$AOS_HOME`。<br>用法：`std.pack("look")` 一個工具包、`std.tool("base/read")` 一支工具、`std.fsm()` agent-fsm 的四格、`std.hooks()` 某個範本的 hook 組。<br>放哪：包在 `lib/packs`、工具在 `lib/tools`、fsm 格在 `lib/aos/apps/agent_fsm`，hook 組從 `templates/agents/<範本>/` 抄。<br>工具名：std 的工具腦看到短名（`read`）。別的庫用 `defs.lib("名", 根)` 宣告，根只收絕對路徑或指示詞，庫名不能叫 std；它的工具自動帶「名_」（`my_read`）。<br>編譯：`python3 agent.py --compile` 把包展開成一支支工具寫進 `tools.json`，預設 `--static`。`--dynamic`，或逐包 `link="dynamic"`，是讓 `tools.json` 指向包檔（`$override`）。<br>跟上一列「標準庫」（C-74 的一層）是兩回事。std 算 C-74 哪一層**先留著**：使用者 11-19「先留著。以後搞不好可以統合，因為這些東西搞不好也可以在aos.py.std中找到。或是aos.std。」，這是想法，不是裁定。<br>設計與裁定：[aos-ns-1119/07](../../../thinking/2026-11/19/aos-ns-1119/07-使用者裁定.md)、[第一刀](../../../thinking/2026-11/19/aos-ns-第一刀.md) | 11-19、11-25 |
| 基礎設施 | **主題**名（CONCEPTS 03、NORMS 03～07、10），不是層：橫跨基礎層與標準庫 | 10-22 |
| 最小實作／完整實作 | 實作兩級：最小實作只做最少步驟、確保合規（aos-exec＝cd → 設環境變數 → 跑檔）；完整實作顧邊緣狀況、精修過（`proto8/cpp` 的 C++ 那幾支）。名字免得跟基礎層撞（新詞頂層代定；N-18） | 10-14、10-21、10-22 |
