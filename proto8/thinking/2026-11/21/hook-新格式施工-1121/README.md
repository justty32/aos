aos 的 hook 整套換成新宣告格式＋檔名對調（hooks.json／hookeds.json）＋極簡引擎（第四層），連 kernel 的甲案一起施工的紀錄；入口。

← [2026-11-21](../README.md)｜定案：[審格式第 1～8 則](../hook-points-格式-使用者審-1121.md)、[簡化 07 使用者已答](../aos-hook-簡化-1121/07-使用者已答.md)、[kernel 09 使用者已答](../kernel-宣告進interfaces-1121/09-使用者已答.md)

線 top-1121-hooknew，11-21 家機，頂層派。沒 push；沒在 repo 跑 `install.py`；沒碰 `~/aos-home`；真模型沒叫（假腦與假 claude CLI）。

## 使用者原話（11-21，逐字，挑最直接的）

- 「hook point這塊，我決定就是新格式，block,if_block那些都不用，有需要的自己在input schema裏面添加，或是另外自己隨便加key。然後interfaces.json中，我要改成"hooks":...，值可以是string, array of string，ps.interfaces.json必須支援指示詞，pss.應該改成hooks.json, hookeds.json，hooks表示有哪些鉤子，hookeds表示有哪些被勾着。」
- 「1.不收。2.就是hookeds。……總之hook這邊就保持極簡。」
- 「發事件的程式自己決定 <- 沒錯，我們提供的hook fire本身會參與這個過程，所以也算在其中。如果有人不想用我們的aos-hook fire，那就弄他自己的。」
- 「簡化到第四層」；選項框：「庫也極簡」「留著」（逾時）「用旗標選」（退出碼）「編譯時決定」（before_run／after_run）；「1.對。2.對。」（agent 自己留「只攔某支工具」、工作夾改 `hookeds/`）
- kernel：「1.先做甲。2.hooks/hookeds放interfaces.json的頂層。"kernel":...也放頂層。3.把kernel自己提供的hook點位弄成kernel_hooks.json，然後hooks指過去，還有kernel_hookeds.json，同樣hookeds指過去。4.沒宣告的照樣跑，其他的也是，就是說，宣告這東西只是參考。……」

## 分檔

| 份 | 內容 |
|---|---|
| [01-現在怎麼寫](01-現在怎麼寫.md) | interfaces.json、宣告檔、被勾清單、aos-hook fire、aos-agent hook add、各家自己的規矩、kernel 甲案，各一個最短例子 |
| [02-替使用者做的選擇](02-替使用者做的選擇.md) | 定案沒講到、施工時挑的實作選擇，逐條 |
| [03-保不住的行為與活樹更新](03-保不住的行為與活樹更新.md) | 行為差別（拿掉的、保不住的）；家機活樹要做什麼才吃得到、stack 裡舊清單怎麼搬 |
| [04-驗證](04-驗證.md) | 乾淨複本全套、暫存樹實跑（假腦 ann／編譯的 bob／kernel hook／eca-claude／aos-hook 兩種退出碼）、行數 |
| [05-條文要補的字](05-條文要補的字.md) | `proto8/docs/` 沒改；C-90、N-45、附錄 4 等要補的字 |
| [06-建議刪除與沒做的](06-建議刪除與沒做的.md) | 沒人用了的兩支程式檔；這次沒做的 |

## 施工的切法

- 程式、範本、編譯、測試一筆（kernel 甲案也在這筆：kernel 原本靠舊引擎的 `hook_point.read`／`engine_table`，拆開做等於 kernel 那段寫兩次）；文件、知識庫、這份紀錄一筆。
- 隊員：文件與知識庫一隻（opus），測試三隻（opus：`py/tests`；`py/tests/apps` 與工具測試；範本與 cpp 測試），只改各自範圍的檔，程式由隊長改。
- 開工後 HEAD 前進兩筆（top-1121-smalls 的 `ecedfa41c`、`e781ef00e`），三方合併進複本後再交。
