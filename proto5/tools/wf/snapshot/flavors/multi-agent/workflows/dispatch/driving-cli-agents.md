# 驅動一條外部 CLI agent 線

[dispatch](README.md)｜[WORKFLOWS](../../WORKFLOWS.md)

把整條工作線外包給同機的另一個 CLI agent，自己當調度者。派線規則見 [dispatch](README.md)，這裡只講**怎麼把它啟動、盯住、收乾淨**。

下面的終端多工器、`<agent> exec` 都只是**例**；換成你手上工具的等價機制即可，規則不變。

## 啟動與驅動（互動式）

用終端多工器的 send-keys 之類機制送提示，**內容與送出鍵分開送**：

```sh
<多工器> new-session -d -s <線名> -c <工作目錄>
<多工器> send-keys -t <線名> '<啟動 agent 的指令>' Enter
<多工器> send-keys -t <線名> '<提示詞>'
<多工器> send-keys -t <線名> Enter
sleep 5
<多工器> capture-pane -t <線名> -p | tail -5
```

提示還停在輸入框就是**沒送出**，再按一次送出鍵；看到它開始輸出才算啟動。
**固定等待秒數不可靠，判準永遠是畫面。** 觀察一律用 capture-pane 這種唯讀方式，**不要 attach 進去**。

要它壓縮 context 時，compact 指令一樣**從輸入端送**（內容與送出鍵分開送）；細節見 [team-model/context](../team-model/context.md)。

## 非互動變體

沒有終端多工器、或要背景跑時，一條線一個背景 process：

```sh
<agent> exec <沙箱／權限旗標> -C "<唯一可寫工作目錄>" \
  --add-dir "<額外可寫目錄；至少含回報用的 inbox>" \
  '讀 <交接書絕對路徑> 並完整執行；驗收條數已寫死，不要自行加碼。' \
  > "<log 路徑>" 2>&1 < /dev/null
```

- **`< /dev/null` 必須保留**，否則它會停在等 stdin。
- **可寫目錄的聯集不得超出領地表**（`-C` 與追加可寫目錄的參數加起來）。
- **模型／推理強度用單次參數覆蓋，不要改全域設定檔。**
- **子代理上限寫進交接書**（例：每條主線最多 1 個），不然它會自己開一堆。

## 監看三訊號（缺一不可）

| 訊號 | 代表 |
|------|------|
| inbox 收到終局狀態 | 正常結束 |
| 線的 session 消失 | 崩潰或被殺 |
| 畫面停滯、或停在批准提示 | 活著但卡住 |

批准提示是固定字樣，例：`Would you like to run`、`Press enter to confirm`、`Yes, proceed`——命中就立刻通知。

**監看跟著「有沒有現役線」開關；timeout 到期不可以靜默假裝還在看。**
長編譯或背景 `sleep` 會讓「閒置＝孤兒」的偵測誤報，派長任務時要看畫面內容，不要只看 hash。

便宜模型的癖好**交接書擋不住**，過程中要**動態提醒**（例：一直驗證無關緊要的小事，就提醒它專注在真正重要的事情上）；見 [team-model/speed](../team-model/speed.md)。

## 通訊

- 終局回報永遠走 `new/`；`orders`／`mail`／`topics` **沒有推播**，**每完成一個工作步驟跑一次輪詢**（見 [inbox/PROTOCOL](../inbox/PROTOCOL.md)）。
- 要線檢查環境變數時，**只准回報「有／無」，禁止印值**：

  ```sh
  [ -n "$VAR" ] && echo 有 || echo 無
  ```

- 查敏感內容有沒有外洩時**不要用會略過二進位檔的 `grep -I`**——大型記錄檔會因此被漏查。

## 清理

**不要讓線直接 `rm -rf`**（會卡在批准提示，或誤刪）。

| 產物 | 暫放位置 |
|------|---------|
| 大於 10 MB | `/tmp/<線名>-trash/` |
| KB 級文字產物 | `<交接書目錄>/<線名>/trash/` |

兩類都用 `mv`。gitignore 只是安全網，不是授權。

## 線不能 commit 的環境

沙箱拿不到憑證、或機器政策不允許時：線**只改工作樹**，回報改了哪些檔與位置，**不回報分支／commit hash／push**。commit 由調度者核完再做，push 一律等使用者。

也不准繞路：**不得 clone 到暫存目錄、不得另設 git-dir、不得用 `git apply` 把 diff 搬進副本。**

## 收線七步

1. 依交接書寫死的驗收**逐條核**，不只看自我宣告。
2. 核 commit 與未推狀態（`git log --oneline --all --not --remotes`）；線不能 commit 的環境改核工作樹 diff。
3. 確認鎖已釋放、該線起的行程清乾淨（見 [resources](../resources.md)）。
4. 交接書移到 `done/` 並附完成證據。
5. 把該線從領地表「現役」移到「歷史」。
6. 報告進版控；大型中間產物不留在 repo 或家目錄，要刪除先問使用者。
7. **現役線歸零**才回報「全部收完」。

## 交接

- 派線流程與領地表 → [dispatch](README.md)；踩過的坑 → [lessons](lessons.md)。
- 鎖與限流 → [resources](../resources.md)；通訊契約 → [inbox/PROTOCOL](../inbox/PROTOCOL.md)。
