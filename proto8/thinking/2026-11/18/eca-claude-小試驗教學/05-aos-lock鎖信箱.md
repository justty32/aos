這份教你用 `aos-lock` 鎖一個信箱、看鎖、解鎖，以及鎖著時 aos-post、aos-agent say 和 agent 收信各會怎樣（試驗 05，11-18 在公司 WSL 用 haiku 實跑過）。

← [目錄](README.md)

使用者原話：「5.使用aos-lock鎖住某信箱，嘗試aos-post，然後解鎖。」

## 結論

- **鎖就是一個資料夾**：`aos-lock acquire X` 會建 `X.lock/`，X 是現有資料夾或以 `/` 結尾時建 `X/.lock/`，裡面放一張名牌 `holder.json`。看鎖用 `aos-lock show X`，解鎖用 `aos-lock release X`。這是大家講好的約定，不是作業系統的門鎖。
- **鎖「信箱本身」（`queue/`）擋不住任何人**：aos-post 照寄、agent 照收照答。aos-post 只認一把鎖：信箱裡的 **`order.lock/`**，而且只有「有序號的寄法」（`--ordered`）才去拿它。要鎖到 aos-post，目標要寫成 `<信箱>/order`。
- 鎖住 `order` 之後：
  - `aos-post send --ordered` 和 `aos-agent say`／`ask` 會**一直等，不報錯、沒有逾時、什麼都不印**。
  - 不加 `--ordered` 的 `aos-post send` 照常寄進去。
  - agent 自己取信、回答不受影響。
- **解鎖後，卡著的那封會自己寄進去**：實測 `ask` 卡了 5 秒，解鎖後 3 秒拿到回答。
- **鎖的人死了，鎖會不會自己放**：用命令列 `aos-lock acquire` 拿的鎖**永遠不會自己放**，因為命令列拿完就退出了，名牌也不登記死活。要嘛自己 `release`，要嘛拿的時候給租約 `--lease-cycles N`，到期別人可以收。程式裡面拿的鎖（aos-post 自己拿的那種）登記了 flock，持有的行程一死，下一個人當場收掉。這兩種都實測了。

## 先準備

照 [README 的「共同準備」](README.md#共同準備)起好樹，`ann` 是 running。在 `~/aos-home` 打，先設一個短名字：

```sh
Q=.stack/procs/ann/queue
```

## 試法一：鎖信箱資料夾本身（擋不住）

```sh
aos-lock acquire --note test-folder $Q/
```

什麼都不印、退出碼 0。`ls -a $Q` 會多一個 `.lock`。

```sh
aos-lock show $Q/
```

```
{"holder": "/home/你/aos-home", "acquired_at": "2026-11-18T08:07:44.028+00:00", "note": "test-folder"}
```

`holder` 是誰拿的，依序取 `$AOS_WS`、`$AOS_STACK`、`$AOS_CF`，都沒有就用目前的資料夾。這時再丟一封：

```sh
echo '{"role":"user","content":"Reply with exactly: through-folder-lock"}' | aos-post send --ordered $Q
```

馬上印出信件名稱，agent 也照答 `through-folder-lock`。**這把鎖沒人理。**

再拿一次同一把鎖，`aos-lock acquire $Q/` 退出碼 10，表示拿不到。加 `--wait-ms 1500` 會等 1.5 秒，還是 10。

```sh
aos-lock release $Q/
```

退出碼 0。之後 `show` 退 10，表示沒有鎖。再 release 一次會看到：

```
aos-lock: error: LockMissing lock not held: /home/你/aos-home/.stack/procs/ann/queue/.lock
```

## 試法二：鎖 aos-post 認的那把（`order`）

```sh
aos-lock acquire --note test-order $Q/order
```

`ls $Q` 會多一個 `order.lock`。

**不加序號的寄法照過**：

```sh
echo '{"role":"user","content":"Reply with exactly: unordered-through"}' | aos-post send $Q
```

馬上印出名字，agent 照答 `unordered-through`。

**加序號的寄法會卡住**。我用 `timeout 6` 包著，6 秒後砍掉：

```sh
echo '{}' | timeout 6 aos-post send --ordered $Q; echo rc=$?
```

6 秒內什麼都不印，最後印 `rc=124`（被 timeout 砍掉）。`aos-agent -t ann say hi` 一樣卡住，因為 `say` 一律用 `--ordered`。

**卡著的時候解鎖**：在視窗 C 打：

```sh
aos-agent -t ann ask --timeout-s 120 "Reply with exactly: after-unlock"
```

它卡住。5 秒後到另一個視窗打：

```sh
cd ~/aos-home && source env.sh && aos-lock release .stack/procs/ann/queue/order
```

視窗 C 約 3 秒後印出 `after-unlock`。**卡著的那封自己進去了**，不用重打。

## 鎖的人不見了，鎖會不會放

**命令列拿、不給租約**：拿完 `aos-lock` 就退出，鎖一直留著。上面試法二要不是我自己 release，`--ordered` 會一直等下去。

**命令列拿、給租約**：

```sh
aos-lock acquire --lease-cycles 3 --note lease3 $Q/order
```

```sh
echo '{"role":"user","content":"Reply with exactly: lease-ok"}' | aos-post send --ordered $Q
```

這封等了約 3 秒寄出，agent 答 `lease-ok`，鎖也被收掉了（`show` 退 10）。一格多長：人的殼裡沒有 `AOS_CLOCK`，就照牆上的時鐘算，一格 1 秒。有 `AOS_CLOCK` 就照那個鐘的格數算，鐘停著時租約不會到期。

**程式拿的鎖、持有者死了**：我手做了一把「持有者已經死掉」的鎖：名牌寫 `"flock": true`，旁邊放一個沒人鎖著的 `holder.flock`。aos-post 自己拿鎖時就是這個樣子。這時 `--ordered` 寄信，**當場**（十幾毫秒）就收掉那把鎖、寄進去。

**名牌壞掉的鎖**：`holder.json` 讀不懂時，`aos-lock show` 會看到下面這行：

```
aos-lock: error: HolderBad holder file missing or unreadable: …/queue/order.lock/holder.json
```

`--ordered` 會等到那個鎖夾 10 秒沒動，才收掉它寄進去。實測等了 10 秒。

**別人的鎖不能隨便放**：換個資料夾（`cd /tmp`）再 release 會看到：

```
aos-lock: warning: not releasing …/queue/order.lock: it is held by /home/你/aos-home, not by /tmp (its lease may have expired and someone else took it); use --force to release it anyway
```

退出碼 10。加 `--force` 就放了。

## 常見卡點

- `aos-lock acquire` 拿到時什麼都不印，要看退出碼：0 是拿到，10 是拿不到。
- 鎖住 `order` 時，`say` 或 `ask` 看起來像當機，其實是在等鎖。先 `aos-lock show <信箱>/order` 看是不是有鎖。
- 卡住的 `--ordered` 被你 Ctrl+C 或 timeout 砍掉，信箱的 `tmp/` 會留下半成品小夾。我留了兩個，agent 不理它們，不會被當成信。

## 發現的問題

1. `aos-post send --ordered` 拿不到鎖時**沒有逾時、不印任何東西**（程式寫的是 `acquire(…, -1)`，一直等），`say`／`ask` 也跟著無聲卡住。人從畫面上分不出是當機還是在等鎖。
2. 被砍掉的 `--ordered` 會在 `tmp/` 留半成品。我沒等到看誰會清它們。
3. `aos-lock --help` 寫的是一般規則（「資料夾＝`TARGET/.lock/`」），沒提到 aos-post 只認 `order.lock/`。照字面「鎖住信箱」會以為已經鎖住了，其實沒有。
