# 接上現有 parent：生一個 child，再合作

這是教學用工具橋接範例。沿用已建立的 `/tmp/haha/parent`、`D`、`K`、`project`、`reference`，不建立新團隊，也不重設 parent 的人格、記憶或既有工具。

## 安裝

從 repo 根目錄：

```sh
. /tmp/haha/env.sh
python3 proto5/examples/parent-child-demo/install.py --root "$W"
aos-agent tools ls --target "$W/parent"
aos-agent check --target "$W/parent"
```

增加 `spawn_child(task)` 與 `send_peer(message)`。第一次呼叫 spawn 才會建立 `$W/child`；之後重用同一個 child，沿用其記憶。child 只有 `send_peer`，不能再生孩子。已存在但不屬於本範例的 child 會被拒絕，不接管、不覆寫。

**這兩支管理工具以 `_jail: false` 在主機執行**，因此 check 的不關牢警告是預期的。使用者安裝此橋接就是授予固定的建立與互傳權限：CLI、daemon、kernel、parent、child、掛載全部寫在主機配置，模型只可提供文字 task/message，不能選路徑或命令。程式與配置放在 `$W/parent-child-demo`，不掛進 agent 可寫工作目錄。這是受信任的教學管理工具，不是適合任意不可信同 UID 程式的安全邊界。

child 的基本檔案工具仍走沙盒：`/work/ws` → `$W/project` **可讀寫且與 parent 共用**；`/work/ref` → `$W/reference` 唯讀；工具網路關閉。雙方應分開產物檔名，避免同時覆寫。模型請求仍由 llm 池處理。

## 第一次合作

```sh
aos-agent say '請用 spawn_child 指派一個任務給 child：實際用 bash 執行 Python 計算 1 到 10 的平方和，將純數字結果寫入 /work/ws/child-result.txt，讀回確認，再用 send_peer 回報 parent。spawn 回覆 queued 後先結束本輪。之後收到 child 的回報時，你用 read 讀該檔，再用 bash 獨立計算核對，將含 385 與 PASS 的驗收結論寫入 /work/ws/parent-review.txt，最後回覆我。不要對 child 發客套確認信。' \
  --target "$W/parent" --wait 180
```

`queued` 是收單，不是 child 完成。`say --wait` 可能先等到 parent 的「已指派」就返回；child 完成後用 `send_peer` 投訊，parent 會被喚醒接著驗收。不用輪詢工具，也不占住 llm cpu 等另一個 agent。

```sh
aos-agent listen --target "$W/parent" --follow --show-calls-full
```

看到 parent 驗收完成，Ctrl-C 離開 listen（不會停止 agent），查看兩方紀錄與產物：

```sh
aos-agent listen --target "$W/parent" --last 5 --show-calls-full
aos-agent listen --target "$W/child" --last 5 --show-calls-full
cat "$W/project/child-result.txt" "$W/project/parent-review.txt"
aos-agent access ls --target "$W/child"
aos-agent tools ls --target "$W/child"
```

## 再傳一個任務

child 已在時可使用 parent 的 `send_peer`；也可以再次 `spawn_child`，它會確認同一個 child、確保 start、再投新任務。child 每份任務只回報一次，parent 收件後驗收，不互傳客套話。

```sh
aos-agent say '請用 send_peer 交給 child：計算 1 到 5 的立方和，寫入 /work/ws/child-cubes.txt 並回報。收到結果後你自行驗算，回覆我即可，不再向 child 回信。' \
  --target "$W/parent" --wait 180
```

單獨停止 child：`aos-agent stop --target "$W/child"`。收工：

```sh
aos-agent stop --target "$W/child"
aos-agent stop --target "$W/parent"
aos down
```

此範例沒有自動取消、任務 ID、超時追蹤、恰好一次投遞或父程序結束時連帶停止的功能。父子是角色關係，兩者各自向同一 kernel 登記。安裝中斷或 child 生到一半會明確拒絕自動重試，需在主機檢查；不要反覆送同一任務來猜有沒有成功。

## 檔案與驗證

- `install.py`：向既有 parent 增加工具引用；重跑已完成安裝不寫檔。
- `bridge.py`：固定 child 建立、啟動、非同步投訊；驗參數與配置路徑。
- `test_boundaries.py`：非法參數、symlink、非本工具 child、保留 parent 檔案、半套安裝與 child 禁止生孫子的離線測試。

```sh
python3 proto5/examples/parent-child-demo/test_boundaries.py
```

2026-09-27 實跑驗證：獨立 `/tmp/aos-parent-child-check-wd7_l0br`，`http://localhost:4000/v1` 的 `deepseek-chat`，2 個 default cpu + 1 個 llm cpu。第一輪 parent 真呼叫 `spawn_child`，child 產出 `385`、傳回訊息，parent 自動醒來獨立驗算並寫 `385 PASS`。第二輪 parent 真呼叫 `send_peer` 派給同一個 child，雙向傳回 `225`，parent 寫 `225 PASS`。兩方歷史留在該測試目錄；測後 stop 兩個 agent、`aos down`，確認無殘留該目錄的程序。未操作使用者的 `/tmp/haha`。離線邊界測試 6/6；repo 根目錄 build 成功、ctest 8/8 全綠。
