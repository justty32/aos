# 2026-10-10 第一次體驗新手試用（QS 隊，代 U2）

← [試玩紀錄](../README.md)｜藍圖 [blueprint-firstrun](../../blueprint-firstrun.md) §6 H1～H3｜受測文件 [QUICKSTART](../../../QUICKSTART.md)

## 先做的事：QUICKSTART 實跑校對

F1／F2 進 main 後照 QUICKSTART 實跑一次（假 AI），原始輸出在 [raw/real-up.txt](raw/real-up.txt)、[real-ask.txt](raw/real-ask.txt)、[real-status.txt](raw/real-status.txt)、[real-status-stopped.txt](raw/real-status-stopped.txt)。跟 F3 原文不一樣的地方：

| 段 | F3 原文 | 實跑 |
|---|---|---|
| 指令 1 | 一行「bob 起好了」 | 三行頭（起好了＋怎麼 ask＋怎麼 status／停），之後每秒 `心跳 N` |
| 寄信後 | 一行「收到信 → 問 AI → 已回信」 | 分兩行：`心跳 5 收到 1 封信`、`心跳 6 → 問 AI → 已回信` |
| Ctrl-C | 沒寫 | 多一行「心跳停了；檔案都留著，再跑 … 就接上」 |
| 指令 2 | 「回信全文」 | `bob 回信（DONE）：（假 AI）收到你的信：…`（帶英文 DONE） |
| 指令 3 | 五行 | 六行，多一行「檔案：… 全清：先停心跳，再刪這兩個資料夾」；AI 那行用英文 `token` |
| 收掉 | 沒寫 | 房子（`/tmp/aos`）底下還有藏起來的 `.aosd`，只刪 bob、you 會留下它 |

QUICKSTART 改成：三段都貼實跑輸出、補「收掉」一節（`rm -r /tmp/aos` 整個刪）、一句帶過 DONE／token／`--model`／`-d`／`stop`、加連 [up 包 README](../../../modules/up/README.md)；為守 ≤3 KiB，圖縮小、「想多做一件事」表改成一行。最後 3069 B、帳／回合／預留／ack／退出碼／daemon／tick 零出現，wf-lint 0 壞連結。README-head 範例第三行換成實跑第一行。

## 怎麼試

- 兩位新手：Claude **Haiku**（Agent 工具，每輪新開）、codex **gpt-6-luna**（`model_reasoning_effort=low`）。只准讀 QUICKSTART 與它連到的 up README、`--help`；在 `/tmp/u2-firstrun/<試用者>/<輪>/` 操作，`/tmp/aos` 換成該目錄下的 `aos/`。任務：起 node、ask 交代一件自己想的事、看到回信、status、收掉。題目原文 [raw/task-template.md](raw/task-template.md)（是第 2 輪版本）。
- AI 不能開兩個視窗，題目給了固定替代：指令 1 放背景存到 `win1.txt`、Ctrl-C＝`kill -INT`。這兩條不算卡點。
- 分鐘照 U 隊估法：QUICKSTART 1849 字 ÷ 400 ≈ 4.6 分＋指令行 5×0.25（alias、三指令、rm）≈ 1.3 分＋卡點分鐘（取多的一位）。AI 實測都在 1 分鐘內。
- 判準：兩位取差，五條平均 ≥7；另記指令 ≤3、概念 ≤5、ELI5 後不複雜。

## 總表

| 輪 | 試用者 | 跑通 | 分鐘（估） | 指令 | 概念 | 分數 | ELI5 後複雜？ | 報告 |
|---|---|---|---|---|---|---|---|---|
| 1 | Haiku | 成功 | 10 | 4（含 rm） | 7 | **6.6** | 是 | [raw/haiku-r1.md](raw/haiku-r1.md) |
| 1 | luna | 部分 | 6 | 4（含 stop） | 5 | 7.8 | 否 | [raw/luna-r1.md](raw/luna-r1.md) |
| 2 | Haiku | 成功 | 7 | 3 | 8 | **7.6** | 否 | [raw/haiku-r2.md](raw/haiku-r2.md) |
| 2 | luna | 成功 | 6 | 3 | 5 | 8.6 | 否 | [raw/luna-r2.md](raw/luna-r2.md) |
| 3（ER-up 改接口後） | Haiku | 成功 | 6 | 3 | 8（QUICKSTART 列的 5） | **7.0** | 是 | [raw/haiku-r3.md](raw/haiku-r3.md) |
| 3（ER-up 改接口後） | luna | 成功 | 5 | 3 | 5 | 8.8 | 否 | [raw/luna-r3.md](raw/luna-r3.md) |

**第 2 輪過**：取差 7.6 ≥ 7，兩位都答「ELI5 後不複雜」，指令 3、分鐘 ≤10。**概念數 Haiku 數到 8**（五詞＋假 AI、DONE、token），超過藍圖 H2 的 5；這三個詞是程式輸出帶出來的，文件已一句帶過，再壓要改輸出（見下「交頂層」）。

## 每輪卡點與改了什麼

**第 1 輪**（不過，Haiku 6.6）
- Haiku：① `--help` 列了 `stop`，QUICKSTART 只講 Ctrl-C，不知道用哪個（2 分）；② 輸出寫「要真的加 --model」，不知道填什麼（1 分）；③ 照 QUICKSTART 刪 bob、you 後 `aos/` 還有 `.aosd`，不知道該不該刪（1 分）。
- luna：題目給的背景寫法在 codex 裡被跟著 shell 一起收掉（環境問題，不是文件），它自己從 `--help` 找到 `-d`＋`stop` 跑通，因此把 `stop` 算成第 4 個指令。
- 改：QUICKSTART 加「收掉」一節 `rm -r /tmp/aos`（整個刪，含 `.aosd`）；一句說 `--model`、`-d`、`stop` 第一次用不到。題目背景寫法改 `setsid -f`。

**第 2 輪**（過）
- Haiku：只有題目給的 `pgrep` 樣式對不上（程序列的是相對路徑），1 分鐘，自己判定不是 QUICKSTART 的問題。評語：假 AI／DONE／token 沒放在同一處講；「想多做一件事」一行塞八個連結不好挑。
- luna：只有環境擋 `rm -rf`（codex 安全規則），改用 Python 刪，0.1 分。
- 試完兩位都停了心跳、刪了目錄，沒有殘留 aos7-up 程序；repo 沒被改。

## 交頂層（接口，不是文件能修的）

1. **status 的「全清」提示少一個資料夾**：印「再刪這兩個資料夾」（bob、you），房子底下的 `.aosd` 會留著。建議提示改成刪整個房子，或列出三樣。
2. **輸出帶英文詞**：ask 印 `（DONE）`、status 印 `token`，新手把它們算成新概念（Haiku 概念 7～8 的來源）。建議 ask 拿掉 `（DONE）` 或改「辦完了」，status 改「用了約 N 字」。
3. **`aos7-up --help` 露出進階與禁用詞**：最後一行「退出：0 做到了、1 做不到、2 參數不對、3 不確定」（退出碼在 QUICKSTART 規定零出現），另列 `-d`、`stop`；兩位都去讀了 `--help`，第 1 輪 Haiku 因此卡 2 分、luna 因此多記一個指令。建議 `--help` 只留三指令，退出碼與 `-d`／`stop` 放 ADVANCED。
4. **`--model` 要填什麼沒處講**：up README 也沒寫，第一次用不到，但起好那行就提示它。可把提示改成「要真的 AI 見 up 的 ADVANCED」或乾脆不在第一行提。
5. 藍圖 U2 列寫要在 [play 索引](../README.md) 加一列；本隊領地只到本資料夾，留給頂層加。

## 第 3 輪（ER-up 改完上面 1～4 後重試）

ER-up（分支 `loop10/up`）把交頂層 1～4 改進 up 包：`--help` 只列三指令（`-d`、`stop`、`--model`、退出碼搬 [ADVANCED](../../../modules/up/ADVANCED.md)）；ask 回信不印 DONE；status 用量改「讀寫約 N 字」；全清提示改成 `檔案：都在 /tmp/aos（bob、you、.aosd）；全清：先停心跳，再 rm -r /tmp/aos`（房子有雜物或別的 node 時只列安全可刪的）；起好那行只寫「假 AI」，ADVANCED 寫模型名從 LiteLLM 來。QUICKSTART 三段換新實跑（[raw/r3-real-*.txt](raw/r3-real-status.txt)），拿掉「DONE＝／token＝」那句，3040 B。題目同第 2 輪，只把概念數限定為「QUICKSTART、工具輸出、--help 裡出現的」。

- 兩位都成功、0～1 分鐘卡點，取差 **7.0 ≥ 7 過**；指令 3。
- 概念：luna 5；Haiku 自列 8＝五詞＋假 AI、aos 資料夾、.aosd。照「只算 QUICKSTART 列的」是 5；DONE／token 已從它的清單消失。
- Haiku 仍答「ELI5 後複雜」，理由是要記心跳／工作簿／信箱各是什麼、要先知道在哪個資料夾跑。唯一卡點是「cd 進 aos 資料夾（有 AGENTS.md 那層）」不知道實際在哪——新手若是 clone 下來的人應該知道；留給頂層判斷要不要在 QUICKSTART 寫「git clone 下來的那個資料夾」。
- Haiku 子代理寫報告檔被工具擋下，報告照它的最終回覆抄進 raw。試完兩個工作目錄已刪、無殘留程序。
