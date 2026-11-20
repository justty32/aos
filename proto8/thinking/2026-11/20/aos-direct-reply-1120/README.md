# 「問特定的東西、直接回特定的東西」通用模式的調查（線 aos-direct-reply-1120）：今天已有九處左右；吃 body 的時間空的時候量不出、每答一封 8～22 毫秒、100 封拖 1～2 秒；不吃 body 的做法四種；八題等你

← [2026-11-20](../README.md)｜前情：[aos-kask-1120](../aos-kask-1120/README.md)、[aos-kask-proto-1120](../aos-kask-proto-1120/README.md)

只調查、只擺事實，不替你選。repo 的程式、文件、教學、條文一行都沒動；要量的東西都在 `git archive HEAD`（`f522b5570`）的乾淨複本＋暫存夾 `~/.aos/scratch/aos-direct-reply-1120/` 裡做。只用假的東西，沒叫模型。頂層派、線隊長交。

## 你的原話（11-20 下午，逐字）

「然後啊，我發現，像這種"問某種特定的東西，然後不需要思考或做其他處理(當然，硬要的話也可以，就是用hook)，就是直接回覆特定的東西"的模式很好用。感覺之後可以特別專門去規劃，我最擔心的就是他每次的回覆都要吃到loop的body的運作時間，會讓整個變慢。」

頂層問下一步時：「這塊就派線去調查一下先前說的那個通用的。」

## 三句話

1. **今天已經有九處左右長成這樣**，分三類：寄信由對方的 body 答（daemon 的 `ping`、`procs_state_path`、今天的 kask 原型、agent-fsm 的 `/compact` 太短、eca 的 slash 信）；問的人直接讀對方寫好的檔（`procs_state.json`、`endpoints.json`、各 loop 的 `state.json`、agent 小格裡的檔）；指令或工具自己讀檔算。過不過 hook、進不進帳各處不一。
2. **吃 body 的時間**：信箱空的時候每輪多 0.024 毫秒，實跑量不出差別；每答一封 8～22 毫秒（幾乎全是起 `aos-post` 子行程）；同一輪 10／30／100 封約多 0.1／0.3／0.8～2 秒。agent 比 kernel 多一個問題：idle 格只在 agent 閒著時跑，放在 idle 的「直接回」要等它答完手上的事。
3. **不吃 body 的做法四種**：預先寫成檔讓問的人自己讀（寫的人每輪幾乎不花錢、讀一次 0.02 毫秒，但對方停了檔還在、只有同機讀得到）、另起一個專門答的 proc、daemon 代答、aos-loop 兩輪之間代答；後兩種沒實作。

## 分檔

| 檔 | 講什麼 |
|---|---|
| [01-盤點](01-盤點.md) | 今天已有的九處：誰問、怎麼問、誰答、佔誰的時間、過不過 hook、進不進帳、問錯了會怎樣 |
| [02-數字](02-數字.md) | 一輪多久、多一個信箱多少、每封多少、灌 10／30／100 封、現成檔 vs 現算 vs 1 MB、agent-fsm、預先寫檔 vs body 答同一張表、daemon ping |
| [03-可能的形狀](03-可能的形狀.md) | 七種（body 答、限 N 封、hook、預先寫檔、另起 proc、daemon 代答、aos-loop 代答）各要動什麼、怎麼找、會不會過期、不想給、鏈上 |
| [04-邊緣狀況](04-邊緣狀況.md) | 逾時、停了、卡住、同一封、寄錯、灌爆、答案大、多種問句、算不出來 |
| [05-要他定的題](05-要他定的題.md) | 八題 |

## 自己試

暫存夾的腳本都可以重跑（先讀 `env.sh`：它清掉所有 `AOS_*`、指向乾淨複本）：

```
wsl -e bash /home/guanyu/.aos/scratch/aos-direct-reply-1120/meter.sh    # agent-fsm idle、每封開銷、讀檔
wsl -e bash /home/guanyu/.aos/scratch/aos-direct-reply-1120/kmeter.sh   # kernel 一輪：不多做／寫檔／答 0～100 封
wsl -e bash /home/guanyu/.aos/scratch/aos-direct-reply-1120/dping.sh    # daemon ping（會起、會收一個根 daemon）
```

`kmeter.sh` 用的是 `patch.sh` 改過的複本 `lib/`（原型的 `kask.py`＋寫檔小函式），只在暫存夾。
