kernel 的宣告怎麼照 hooks 那套整合進 interfaces.json 的發想稿（11-21，線 top-1121-kiface，只出稿）：三種粗細的候選與完整樣本、各自後果、邊緣狀況、想問使用者的六題、十二處衝突，以及他補的「對外另外一份 json」怎麼不被現在的寫法堵住。

← [2026-11-21](../README.md)｜前情：[kernel 的宣告在哪](../kernel-宣告在哪-1121.md)（現況事實都在那份）、[hook 點格式・使用者審](../hook-points-格式-使用者審-1121.md)（第 1～7 則）、[編譯的 kernel 入口](../aos-pylib-kernel入口-1121.md)

只調查與發想：沒改程式、範本、條文；樣本沒有程式讀。這不是施工計劃。

## 原話（使用者 11-21，逐字）

- 「對了，kernel的宣告也是在interfaces.json嗎？也整理一份html放到桌面吧」
- 看完之後：「kernel你說的這塊我再想想」
- 接著：「然後派個調查線，讓fable去想想，關於kernel的宣告如何整合進interfaces.json，用類似我們剛剛說的hooks的方式。」
- 調查中途補的一句（頂層轉）：「kernel那塊，界面有分對外與對內，interfaces.json中當然兩者都可以有，只是說未來，對外的界面宣告的json，需要另外準備一份，用於讓他人存取」（展開在 [07](07-對外與對內.md)）

「hooks 的方式」指他同一天定的那套（[審稿紀錄第 6、7 則](../hook-points-格式-使用者審-1121.md)）：`interfaces.json` 裡 `"hooks"` 的值是字串或字串陣列，字串就是檔名，可以用指示詞；被指到的檔是一個物件，鍵是 id，值裡硬性只要 input schema，其餘鍵想放什麼放什麼；不收直接把內容寫在 `interfaces.json`；`hooks.json`＝有哪些鉤子、`hookeds.json`＝有哪些被勾著，對應的鍵 `"hooks"`、`"hookeds"`。

## 結論（先講）

1. **hook 那兩鍵可以原封不動搬到 kernel**，而且幾乎不用發明東西：三個點的宣告已經是一份檔（在程式夾），用指示詞指到 `$AOS_HOME` 就看得出哪來；loop 身體多放一份 loop 的四個點。卡住的只有一件：kernel 的被勾清單現在是 `kernel.json` 裡的一個鍵，不是獨立的檔（[05 第 3 題](05-想問的題.md)）。
2. **hook 以外的東西，照「id＋input schema 的物件檔」類推得最順的是「收什麼請求」**（id＝請求種類，input＝信的 body，output＝回信）；**endpoint 代號清單形狀也合**（id＝代號、其餘鍵自由，現在的窗 `endpoints.json` 就長這樣），但它同時是設定、又是執行時算出來的窗，要先決定它算哪一種（[01](01-什麼算介面.md)、[05 第 5 題](05-想問的題.md)）。錯誤代號、窗、`decisions/` 套這個樣子就開始勉強（它們沒有「input」）。
3. **三種粗細**（[02](02-候選寫法.md)，樣本在 [樣本/](樣本/)）：甲＝只搬 hook 兩鍵，其餘照舊在文件；乙＝再加「收什麼請求」「可挑的 endpoint」兩個鍵；丙＝每樣對外的東西一個鍵、包成 `aos-kernel` 一格。差別主要在「多寫的宣告有沒有人讀」：現在除了 hook，沒有任何程式會讀 kernel 的宣告。
4. **最該先讓他知道的三件事**（都不是我能替他定的）：
   - 他說的 `"hooks": …` 在 agent 那邊現況是包在 `"aos-agent"` 那格裡面，不是最外層；kernel 沒有自己的格。放哪一層，agent 跟 kernel 要一起定（[05 第 2 題](05-想問的題.md)）。
   - 寄信給 kernel 的人手上只有 kernel 的 stack（`AOS_LLM_KERNEL`）或信箱（`AOS_KERNEL`），**沒有定義夾的路徑**；宣告放在定義夾，寄信的人找不到（[04 第 1 條](04-邊緣狀況.md)）。他補的那句正好回答這條：給別人的是另外一份，不是叫別人來讀 `interfaces.json`。
   - 「有宣告就能用」反過來套到 kernel，會卡到三種沒有定義夾的 kernel：daemon 本身、agent 身上的 `kernel_gate`、自己從頭寫的程式（[04 第 3 條](04-邊緣狀況.md)）。

5. **對外與對內**（[07](07-對外與對內.md)）：請求、回信、代號、endpoint 清單是對外；hook 點、被勾清單、設定、帳本是對內；`hold.json`＋`decisions/` 與幾個窗難分。stack 的窗 `endpoints.json` 現在就是一份「另外準備的對外 json」（從設定算出來、拿掉內部鍵、`aos-llm ls` 讀）。他說的未來那份，跟 11-20 的「另外一個json」（寄信問 kernel）與 stack 的 public 資料夾幾乎是同一件事，是不是同一份要問他（[05 第 6 題](05-想問的題.md)）。
6. **現在別堵路**：甲完全不碰對外，不會堵；會堵的是四種做法——讓別人的程式去讀 kernel 的 `interfaces.json`、「沒在 interfaces.json 宣告就不收信」、把 stack 裡的位置寫死在 `interfaces.json`（丙的 `files`、endpoint 指 stack 的窗）、把帶指示詞與內部鍵的檔當成對外那份。被指到的檔一律用「物件、id 當鍵、schema」這個樣子，未來對外那份可以直接由它們攤平合併。

## 分檔

| 檔 | 內容 |
|---|---|
| [01-什麼算介面](01-什麼算介面.md) | kernel 對外的東西一覽；介面、設定、執行時狀態三種怎麼分，哪幾樣三邊都沾 |
| [02-候選寫法](02-候選寫法.md) | 甲乙丙三種粗細，各附 llm kernel 與一般 kernel 的例子，被指到的檔長什麼樣 |
| [03-後果對照](03-後果對照.md) | 每種候選在九個面向上的後果（看不看得出、搬不搬得走、誰讀、沒宣告能不能用…） |
| [04-邊緣狀況](04-邊緣狀況.md) | 十六條具體的邊緣狀況 |
| [05-想問的題](05-想問的題.md) | 六題，每題選項與後果；我的看法另外標明 |
| [06-衝突](06-衝突.md) | 跟他說過的話、跟現有條文、跟現有程式對不上的地方，分三組 |
| [07-對外與對內](07-對外與對內.md) | 他補的那句：每樣歸對外還是對內、對外那份 json 的幾種形狀、跟 11-20 兩條調查的重疊、哪些寫法會堵路 |
| [樣本/](樣本/) | 十三份 json：三種候選各兩份 `interfaces.json`、被指到的宣告檔七份 |

## 查證到哪

讀了 `templates/kernel/` 各夾、`templates/start-api/{llm,perm}`、`py/tools/aos/kernel*`（README、`hook_points.json`、`_tooldef.json`、llm kernel 的 `docs/01`）、`py/aos/kernel_spec.py`、`py/aos/hook_point.py`、`py/aos/declared_files.py`、`knowledge/aos/kernel.json`、NORMS「宣告介面」「N-45」「N-42-1」「N-68」、附錄 4，以及 11-20 的 `aos-kres-1120/08`、`aos-kask-proto-1120`、`aos-direct-reply-1120` 三份使用者已答。**沒跑任何程式**；樣本的 schema 是照 README 寫的，型別沒有逐行對程式。文中標「沒實測」的就是沒實測。
