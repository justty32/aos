# 「用 Python 寫、編譯成 aos 資料夾＋JSON」調查（11-18）：一個文字檔能不能描述整個 aos 程式，以及停在某條指令看資源

← [2026-11-18](../README.md)

使用者 11-18 晚：「我們現在的寫aos程式的方式，仍是mkdir這樣，那，是否可以做一套python lib，讓他最終編譯成aos資料夾+json呢？」同晚追加：「……然後step in去debug，然後我停在某個指令，我可以看到在這個狀態下，我們的一些資源的狀況？」（全文 [00](00-使用者原話.md)）。線 `aos-compile-1118` 做，只調查與發想，沒改程式、沒排實作；讀 repo HEAD `ce2e875eb`，沒碰活的 daemon 與 `~/aos-home`；在暫存樹寫了一支 37 行的玩具並實跑。

## 先講結論

1. **這題 aos 早就定過方向，叫 C-43**：「一套 library，用 lua／lisp 一類語言把整套資料夾布局生成出來——那個生成就是『編譯』」（10-19）。這次是把語言換成 Python；11-14 你說 lisp／lua「至少等 kernel 穩定」，所以時程本來就在後面，方向不用重想。
2. **做得到，而且很小**：玩具 `aosc.py` 37 行，16 行的 `prog.py` 生出 3 個工具夾＋1 張 fsm 表，直接用 aos-exec 跑得動（[01](01-現況.md) 第四節）。**在工具這一格其實已經有了**：`tool_spec` 就是「一支 Python 宣告 → `_tooldef.json`／`_metainfo.json`」。
3. **你的比喻最貼的一條是「fsm＋loop＝會自己取下一條指令的 CPU」**：`stage.txt`＝程式計數器、`next` 表＝跳轉、loop＝時脈；實測手打五次 `aos-exec counter.json`，就是推 CPU 走五步。**最不貼的是「kernel＝syscall」**：kernel 只收信（起停 proc、問腦），讀寫檔、跑工具都不經過它——像一張只有兩三格的 syscall 表（[02](02-比喻對照.md)）。
4. **lisp 真正搬得過來的是「程式即資料」**：aos 的程式就是夾，agent 用同一組工具就能讀、改、生程式；`$ref`／`$override`、kit、`agent_def new`、`tool_spec` 都是「巨集」；這次要的 lib 就是一個大巨集。
5. **別人的作法**（[03](03-別人怎麼做.md)）：Nix、CDK、Helm、Jsonnet、CUE、Bazel、kustomize、make、lisp 巨集……共同結論是**生成物別手改、反推回原始碼沒人做到全自動、錯誤最好在生成前就驗**；kustomize 那種「人寫底稿、上面疊補丁」跟手改共存最好（aos 的 kit、`self_*` 就是這種）。CDK for Terraform 已被官方棄用，是個提醒。
6. **最大的坑是「生成物 vs 手改」**（[04](04-邊緣狀況.md)，26 條）：aos 的精神是「夾就是程式、誰都能改」，編譯器要求「生成物別改」。再來是執行期才長的 stack（`self_*` 差異、kit）編譯器管不到；錯誤訊息指的是生成物（實測 traceback 指 `_entry` 第 5 行）——每份 JSON 加一個 `_from` 出處 key 就能指回去，而且 C-48「不認得的 key 忽略」讓它免費。
7. **九個樣子**（[05](05-發想.md)）：甲 維持 mkdir、乙 一份 JSON 展開成夾、丙 Python lib＋build、丁 描述即入口跑時才生、戊 雙向、己 只做展開預覽（一個文字檔「看」整個架構）、庚 把 tool_spec 往 agent 長一格、辛 lisp／lua 原案、壬 帶除錯資訊。
8. **停下來看資源**（[06](06-除錯與停下來看資源.md)）：aos 今天就有四層停住點——**一拍**（`ctl pause`）、**一格**（手打 aos-exec）、**一次工具呼叫**（`before_tool` hook 可擋可改、逾時給 0 就能一直等＝現成斷點）、**一封給 kernel 的信**（kernel hook 的 hold＝syscall 攔截）；停住時 `ctl state` 已能印十一類含資源。缺的是「這步對到原始碼哪行」、一頁把資源攤開的面板（像 Erlang Observer）、和倒帶（腦答不重現，要像 Temporal 那樣錄下來重播）。
9. **推薦（由你拍板）**：現在不開 lib 大工程；想往前一小步，就在**己**（最便宜、零衝突）和**庚**（照現有先例、最可能自然長）之間挑。不管哪條都守兩條底線：生成物是普通、能手改的 aos 夾；`$env` 之類的指示詞原樣吐出、不在編譯時展開。
10. **要你先答的兩題**：(1) 你要的「一個文字檔」主要是拿來**寫**（夾是生成物）還是拿來**看**（夾照舊是原始碼）？(2) 「停在某個指令」最想停在哪一層：一拍、一格、一次工具呼叫、還是一封給 kernel 的信？

## 分檔

| 份 | 內容 |
|---|---|
| [00-使用者原話](00-使用者原話.md) | 11-18 晚原話與追加逐字；C-43、C-35、C-51、C-71、11-06／11-13 長文、11-14 D15 的出處 |
| [01-現況](01-現況.md) | 寫一個 aos 程式的步驟；math、reviewer、gather、agent-fsm 的檔數與手寫量；現有生成器表（tool_spec、tools_def、agent_def、kit、install.py、ctl add、index_gen）；玩具實測 |
| [02-比喻對照](02-比喻對照.md) | 逐條對照表（貼／半貼／不貼、天然差異還是值得想）；lisp 的程式即資料、巨集、quote、macroexpand 在 aos 對應什麼；「一條指令」的四層 |
| [03-別人怎麼做](03-別人怎麼做.md) | Nix、Guix、Pulumi、CDK、cdktf、Dhall、Jsonnet、CUE、Bazel、Helm、kustomize、make、lisp 巨集，附來源；一張比較表 |
| [04-邊緣狀況](04-邊緣狀況.md) | 26 條：手改、執行期的 stack 與 `self_*`、git 與重生、錯誤訊息、跨機器、只想 mkdir 的人、編譯器本身是不是 aos 程式、跟另兩份調查的接點 |
| [05-發想](05-發想.md) | 甲～壬九案的好處、代價、合不合、會不會自然長；一覽表、推薦、要你先答的題 |
| [06-除錯與停下來看資源](06-除錯與停下來看資源.md) | 追加題：四層停住點與看得到的資源；gdb、strace、rr、Redux、Temporal、Airflow、Erlang、lisp condition system 附來源；D1～D7 點子；10 條邊緣 |

## 這條線的邊界與留下的東西

- 沒改 repo 程式；只新增本夾 7 份，另在 [linux-as-hw-1118](../linux-as-hw-1118/README.md) 補 `06-使用者裁定.md`（11-18 晚「先做防呆就好」逐字）與 README 兩處。日索引那一列沒加（日索引檔交給頂層）。
- 06 的第 3、4 層停住點（before_tool hook、kernel hold）只讀了文件與程式說明，**沒實測**；eca 身體的工具攔不攔得到未查。
- 暫存在 `~/.aos/scratch/aos-compile-1118/`：`src/` 是 HEAD 的 `git archive`＋`install.py` 建置；`toy/` 有 `aosc.py`、`prog.py`、生成物 `out1/`（多兩份手寫的 `loop.json`、`body.json`）、`out2/` 與工作區 `ws/`、`ws2/`。沒起 daemon、沒開 tmux、沒留背景行程；夾留著沒刪。
