# routines／schedule 事務包

一張「到時候跑這個」的清單：`add` 登記、`ls` 看、`rm` 移除，到期就跑你給的程式。

← [modules](../README.md)｜進階（讓它自己定時跑、表格式、維護細節）→ [ADVANCED.md](ADVANCED.md)

## 先懂這幾個詞

- **node**：放清單與程式的資料夾，任何空資料夾都行。
- **清單**：node 的 `wf/` 底下兩張表，登記時自動建立。
- **routine**：每隔一段時間做一次的事。
- **schedule**：指定時刻做一次的事，做完就從清單劃掉。

## 第一次跑

整段貼上就能跑，不用開背景程式；路徑自動帶好。

```sh
cd "$(git rev-parse --show-toplevel)"
P=$PWD/proto7-2
N=$(mktemp -d)/n1; R="$P/modules/routines/aos7-routines"
mkdir -p "$N"; printf '#!/bin/sh\necho hello\n' > "$N/hello.sh"; chmod +x "$N/hello.sh"
"$R" add "$N" hello --every 1m hello.sh   # 每 1 分鐘一次；程式路徑相對 node
"$R" add "$N" once --at +1s hello.sh      # 1 秒後做一次
sleep 2
"$R" ls "$N" --run                        # 做現在到期的事，再列清單
"$R" ls "$N" --run                        # 再一次：hello 還沒滿 1 分鐘，once 已劃掉
```

2026-10-09 實跑輸出（時間會不同）：

```text
added routine hello every 1m
要讓心跳自動跑：aos7-up 起的 node 已裝好；自己裝用 aos7-ctl add，見 routines 的 ADVANCED.md
added schedule once at 2026-10-09 16:13:44
要讓心跳自動跑：aos7-up 起的 node 已裝好；自己裝用 aos7-ctl add，見 routines 的 ADVANCED.md
hello
routine hello code 0
hello
schedule once code 0
routine hello  every 1m  last 2026-10-09 16:13:45  code 0  next 2026-10-09 16:14:45
（現在沒有到期的事）
routine hello  every 1m  last 2026-10-09 16:13:45  code 0  next 2026-10-09 16:14:45
```

`--every` 用正整數加 `s/m/h/d`（秒／分／時／天）；`--at` 用 `+5s` 這類相對時間，或 `2026-10-10T09:00` 這類完整時刻。剛登記、從沒做過的 routine，第一次 `--run` 就會做。`hello` 是你的程式印的；`code 0` 表示程式成功結束；`last` 是上次做的時間、`next` 是下次到期時間。不要了就 `"$R" rm "$N" hello`。

第一次用，到這裡就完成了。要讓它自己定時跑，看 [ADVANCED.md](ADVANCED.md)。
