# aos-agent chat 打中文偶爾整句「not UTF-8」被丟：原因是 WSL 終端機沒開 iutf8，改成終端機上用 readline 讀一行（11-12，已施工）

← [2026-11-12](README.md)｜[thinking](../../README.md)｜程式：[aos-agent README「chat」](../../../cmd/aos-agent/README.md#agent-對話協議p-42併自-extrashuman)

## 使用者原話

「aos-chat有時候會這樣」，附上的畫面：

```
> 太扯了，你是怎麼給自己加 jsonx的？好強！對了，假如我要你在./下弄一個notes，把你的一些筆記紀錄進去，你...直接做吧，讓我看看你會怎麼做。
aos-agent: error: ArgumentsBad this line is not UTF-8, not sent (usage: aos-agent [--daemon D] chat [-t NAME])
```

## 原因（實測過）

- **主因：終端機沒開 `iutf8`，打字途中按 Backspace 刪中文只刪掉一個 byte。** 原本 chat 用 `sys.stdin.buffer.readline()` 讀，行編輯交給 tty 的 cooked 模式；cooked 模式要開 `iutf8` 才知道一個中文字是 3 個 byte。公司機從 Windows 終端機開 `wsl -d Ubuntu`，`stty -a` 是 `-iutf8`；`script` 開的 pty 也是 `-iutf8`。pty 重現：打「你好」→ Backspace →「嗎」，送出的是 `e4 bd a0 e5 a5 e5 97 8e`（「好」只刪掉最後一個 byte），解碼失敗、整句不寄；開 `iutf8` 同樣打法得到「你嗎」。畫面上看不出來，因為終端機把半個字畫掉了，使用者看到的那行是乾淨的。
- **一行太長：cooked 模式一行最多 4095 bytes＋換行，多的直接丟。** 剛好切在字中間就變成這個錯；沒切在字中間更糟——句子被悄悄截斷照寄（pty 打 5101 bytes，只收到 4096）。使用者那句約 200 bytes，不是這個原因。
- **方向鍵：** 沒有行編輯時，左鍵變成 `\x1b[D` 三個字元混進句子、照寄（是合法 UTF-8，不會報這個錯，但句子壞了）。
- **讀法本身沒問題：** 是按行讀，不是固定大小切塊，多 byte 字不會被讀法切開。
- 輸入法本身送進來的是完整的字，沒看到它帶控制字元；貼上多行在 cooked 模式下會變成好幾則訊息。

## 修法

- 讀一行抽成獨立的 `aos_agent/read_line.py`（`read_line()`），chat 迴圈只換掉原本「印提示符＋讀一行」那三行，錯誤訊息改成講清楚：`this line is not UTF-8, not sent; type it again (a half-erased character usually means the terminal lacks iutf8: stty iutf8)`，錯誤代號照舊 `ArgumentsBad`、不寄、回提示符。
- stdin 與 stdout 都是終端機＝Python `input()` 配 GNU readline：readline 自己做行編輯（不靠 tty 的 cooked 模式），中文按字刪、方向鍵移游標、上鍵叫回前幾句、一行沒有 4096 上限、bracketed paste 貼上多行＝一則。
- 其他情況照舊按行讀 bytes、提示符在 stderr；stdin 是終端機（stdout 被導走）時先替它開 `iutf8`、結束時還原。管線完全照舊。
- 測試 `cmd/aos-agent/tests/test_chat_read_line.py`：真 pty（先關 `iutf8` 照 WSL 預設）打中文＋Backspace、方向鍵、5101 bytes 長句、bracketed paste 兩行、兩句再 Ctrl-D；stdout 導走時開 iutf8 並還原；管線一行壞 bytes 不連累前後、stdout 沒東西。7 支全過；aos-agent 全套 72 支只紅既有的 `test_daemon_down` 2 支。

## 代定

- C1：readline 那條路的提示符 `> ` 由 readline 畫，Python 的 `input()` 只會畫到 stdout；stdin、stdout 都是終端機時兩邊是同一個畫面，看起來一樣（`2>/dev/null` 時提示符還在）。stdout 被導走時照舊印在 stderr，`chat > 答案.txt` 的檔裡不會有提示符。
- C2：貼上多行（終端機有 bracketed paste 時）＝一則訊息，內含換行；原本會拆成好幾則。
- C3：上鍵歷史只在這次 chat 內，不存檔。
- C4：stdin 是終端機但 stdout 被導走時沒有 readline，仍受 4096 bytes 一行上限；這條路少用，不另處理。
- C5：Python 沒編進 readline 就走老路（開 iutf8）。
