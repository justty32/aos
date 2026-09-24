← [kernel](README.md)｜[spec 總導航](../README.md)

# 6. 命令列（續）：cpu add／rm／ls

（2026-09-24 proto5-2 池式納入，新節。）`cpu add／rm` 只是改 `K/info.json` 的池表（[§1.1](info.md)）——**不放任何單、不用 boot**，
kernel 在跑的話下一格就照新數字做（[§3.1](pools.md)）。

## `cpu add`

- 池不在：新增 `{"count": N}`（`--count` 省略＝1，可以是 0＝先宣告 0 顆），`--env KEY=VALUE` 可重複（字面字串；KEY 空、以 `$` 開頭、同 KEY 兩次＝用法錯 2），
  `--daemon`（轉絕對路徑）／`--dpool` 有給就寫。
- 池在：`count` 加 N。這時給 `--env`／`--daemon`／`--dpool`＝用法錯 2，代號 `PoolExists`（改既有池的環境或位置請直接編 info，影響見 §1.1；09-24 Q5 照草稿）。
- `P` 是 `kernel`＝用法錯（kernel 池永遠 1 顆）。池名、`--dpool` 不合 §1.1 規則＝用法錯 2。負數＝用法錯 2。
- 印 `pool P count A -> B`；kernel 沒在跑（帳本 `phase` 是 running、有 kernel 池、那個 daemon 活著、kernel 池摘要 `running` > 0，四個缺一）再多印一行
  `kernel 沒在跑：下次 boot 生效（aos-kernel boot --target K）`。

**加完到真的能派有一段延遲，是接受的**：cpu add 寫完 info，kernel 要下一格才送 scale 單、再下一格才收回音（kernel 一格才收一次回音）。
所以 `cpu add` 後一兩秒 `aos-kernel ls`／`cpu ls` 的池行尾印 `宣告已送出，下一格確認`、`sent` 還是舊數字，是正常的，不是卡住；
daemon 那邊照節流慢慢拉，`running` 也要一段時間才補滿（09-24 裁定）。

## `cpu rm`

- `--count` 必須是正整數（0、負數＝用法錯 2）。`P` 是 `kernel`＝用法錯。
- `cpu rm P/<i>`：那號必須是現在的成員（不是＝`NotFound`、退 1）。把 i 加進 `skip`、`count` 減 1——**永久退休**，之後長大也不會用回（§1.1；09-24 Q4 照草稿）。
- `cpu rm --pool P --count N`：`count` 減 N；N 大於現在的 `count`＝用法錯。收的是最大的那幾號。
- 被收的號手上有工作的，會做完才真的收（§3.1）。印 `pool P count A -> B`，kernel 沒在跑同樣多印一行。

**怎麼寫 info**：先拿 `K/.info.lock` 的獨占 flock（等最多 10 秒，拿不到＝`Busy`、退 1），
鎖著做完「讀 → 改 → 驗 → 寫唯一的 `.tmp` → rename」，再放鎖。兩個 CLI 一定排隊，不會互蓋。
tick 只讀 info、不拿這把鎖（rename 是原子的）。人手改 info 不會拿鎖，跟 CLI 同時改是保證外。
- 改完的 info 一樣要能過讀驗；過不了（例如 `count` 超過上限）就不寫、退 1。
- info 裡的指示詞（`$env`…）保留原樣，CLI 只改 `pools.P.count`／`skip`／新池那一格；那格本身是指示詞（`pools` 整個 `$ref`、`count` 是 `$ref`…）＝`NotLiteral` 退 1、不寫。
- `skip` 寫入時只排序、去重，**不丟任何一號**（§1.1「退休號只增不減」）。原本沒有 `skip` 鍵又沒東西要寫就不加。

## `cpu ls`

一池一行，讀 info、帳本、daemon 的 `summary.json`（O(池數)）：

```text
kernel   want 1  sent 1   daemon k1-kernel: running 1 restarting 0 pending 0 dead 0 failed 0
default  want 8  sent 8  busy 3  idle 5  draining 0   daemon k1-default: running 8 restarting 0 pending 0 dead 0 failed 0
llm      want 3  sent 2  busy 1  idle 1  draining 0   daemon k1-llm: running 2 restarting 0 pending 0 dead 0 failed 0   宣告已送出，下一格確認
gpu      want 3  sent 0  busy 0  idle 0  draining 0   daemon /abs/D2 gpu: 錯誤 NameTaken（owner /abs/K9）
```

- 欄位：`want`＝info 現在的 `count`（剛 `cpu add` 完就看得到）；`sent`／`busy`／`idle`（`free` 長度）取帳本；
  `draining`＝已經不是成員、還在做事的號數（顯示時即時算，不等帳本下一格重算）。kernel 池只印 want／sent，排第一。
- daemon 標籤：用的是頂層 `daemon` 就只印 dpool，否則印 `D dpool`。摘要有 `killing`／`draining` 才多印。
- 尾註：info 有、帳本沒有＝`還沒宣告`；帳本有、info 沒有＝`移除中`；搬池中印新位置；有 draining 印 `收掉中 N 顆，等 <行程名>`；
  池 `error`＝`錯誤 <代號>（<message>）`；摘要不在但 `sent` 不空＝`池不見了（跑 aos-kernel boot --target K）`。
  scale 單在路上時分三種：kernel 已 `stopped`＝`停機中，下次 boot 收回音`；daemon 沒在跑＝`宣告已送出，daemon 沒在跑（daemon 一上線就會收到）`；其餘＝`宣告已送出，下一格確認`。
- `--pool P` 再一顆一行（O(池大小)）：`P/<i>  idle｜busy <行程名>｜draining <行程名>｜等 daemon 確認｜收掉中  daemon <state> gen <n>`
  （daemon 那欄讀 `kids/<i>.json`；沒有 kids 檔：在 S＝`daemon pending`、收掉中＝`daemon 在收`、否則 `daemon -`）。
  `等 daemon 確認`＝在 W、還不在 S；`--json` 的 `status` 這格寫 `待宣告`（實作 D-121，只換印出來的字）。
- `--json` 同樣內容（每池一格，欄位同 [ls `--json` 的 `pools`](cli-ls.md)）。
