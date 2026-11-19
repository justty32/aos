線 subuid-1119（11-19）紀錄：aos-daemon 開始認 `limits.user: "sub:N"`，免 root 把一支 proc 換成使用者名下的 subuid（linux-as-hw 05 的乙案、kernel-limits-plan 段 3 的最小一刀）；公司 WSL 缺 newuidmap，真換身分等使用者裝好後補驗。

← [11-19 日索引](README.md)｜分檔夾 [subuid-1119/](subuid-1119/01-現況核對與施工計劃.md)

使用者 11-19 早：「子帳號：linux-as-hw 剩的那一段 <- 派線去繼續吧」。目的照 [linux-as-hw 06](../18/linux-as-hw-1118/06-使用者裁定.md)：先做防呆，單人使用、模型可信。

## 先講結論

1. **daemon 那一哩接上了（程式）**：proc 的 `limits` 寫 `"user": "sub:5"`，daemon 起它時讓它自己開一個 user namespace、由 daemon 跑 `newuidmap`／`newgidmap` 對號碼，再換成真的 100004（群組＝這台 daemon 的 `group`，預設 60001＝真 160000）；起之前把它的 stack 改成 700＋ACL（它和使用者都進得去、同台別隻進不去），換身分前清環境、關多餘的 fd，換完檢查路走不走得到。kernel 站本來就會照 `users` 表填 `sub:N`，不用改。
2. **驗到哪**：設定驗證、`group`、helper 找不到、helper 失敗、小格 ACL、父子握手與 helper 收到的號碼都在這台實測過；aos-daemon 全部 13 支測試照過。**真的換成 100004 沒驗到**——這台沒有 newuidmap（要 `sudo apt install uidmap`）。真機那兩條測試已寫好，裝了就會自己跑（[02](subuid-1119/02-測試結果與補驗步驟.md)）。
3. **裝好之後還會卡一個地方**：這台家目錄是 750，換了身分的 proc 走不進 `/home/guanyu`，daemon 會報 `cannot reach /home/guanyu` 讓那支起不來。怎麼開這扇門會動到使用者的家目錄設定，**要使用者拍板（Q1）**。
4. **這一刀能跑的是「不用寄信」的 proc**：換了身分的 agent 寫不進 daemon、kernel 的信箱（照 K16 要用 `aos-share` 開），也還沒有「用信夾擁有者認寄件人」（丙）。

## 要你拍板

**Q1：換了身分的 agent 怎麼走進你的家目錄？**（`/home/guanyu` 是 750：別人連「穿過去」都不行。aos、暫存樹、工作區都在家目錄底下。）

| 選項 | 做法（你親手跑） | 後果 |
|---|---|---|
| **b（推薦）** 只給 aos 的群組「穿過去」 | `sudo apt install acl` 後 `setfacl -m g:160000:x ~` | 只有 aos 換了身分的 proc（主群組 160000＝預設 `group` 60001）能穿過家目錄、列不出裡面有什麼；其他帳號照舊進不來。daemon 換了 `group` 就要多加一行 |
| a 給所有人「穿過去」 | `chmod o+x ~` | 最簡單、不用裝 acl；這台其他帳號也能穿過去，讀得到家目錄裡本來就開放讀的東西（例 `~/repo` 是 755）。單人 WSL 其實只有 aos 的 subuid 是「其他人」 |
| c 把 aos 搬出家目錄 | 例 `sudo mkdir /srv/aos && sudo chown guanyu: /srv/aos`，樹與 repo 放那裡 | 家目錄不動；但重建步驟單、兩台機器的路徑都要改，代價最大 |
| d daemon 起 proc 前自動替每層祖先加 ACL | （程式改） | 不用你動手；但 daemon 會默默改你家目錄的權限，跟「權限是使用者的事」（C-64）相反，不推薦 |

推薦 b：防呆夠用、只開最小的門；a 也可以，差別只在這台有沒有別的帳號。

沒有其他要拍板的；規劃沒講到的細節我自己定了，列在 [01 第三節](subuid-1119/01-現況核對與施工計劃.md)（D1～D9）。

## 做了什麼

| 檔 | 改了什麼 |
|---|---|
| `cpp/aos-daemon/src/child/subuid.{hpp,cpp}`（新） | 認 `sub:N`、查 `/etc/subuid`／`subgid` 與 PATH 上的 helper、環境白名單、小格 ACL（直接寫 xattr）、socketpair 握手、子行程 `unshare`→`setgroups({})`→`setresgid`→`setresuid`→換環境→`close_range`→走得到檢查 |
| `child/limits.{hpp,cpp}` | `sub:N` 寫法驗證、改走 `prep_sub`；`/etc` 讀檔共用 `etc_rows` |
| `child/child.cpp` | `launch` 在 fork 前備好、fork 後替子行程對號碼；`run_child` 在 setrlimit 之後換身分 |
| `daemon/daemon.cpp`、`daemon/table.cpp` | daemon.json `group`（60001～65536）；`state.json` 多 `group` |
| `tests/test_subuid.py`（新） | 7 條，2 條要真 newuidmap |
| daemon `docs/09`、`docs/01`、`docs/06`、`docs/07`、N-28（NORMS 09）、知識庫 `aos/cli/daemon.json` 的 `subuid`、kernel 站 README | 新節「換成 subuid」、`group` 鍵、錯誤表兩列、測試清單、條文一條、給 agent 看的英文說明、拿掉「daemon 認之前不要填 sub:N」 |

程式、測試與文件在 commit `368719e7a`。持久格式：daemon 的 `state.json` 多一欄 `group`，不用重建任何東西。

## 沒做與為什麼

- **真機換身分的實測**：缺 newuidmap，agent 不能 sudo。
- **K18 後半**（子 daemon 沒寫 `group` 沿用父的）：要讀父 daemon 的表，跟最小一刀無關；今天子 daemon 沒寫就是 60001。
- **信上的 `groups`**（K15 進階附屬群組）：仍不認；普通用途用不到。
- **信箱與共用夾的權限**：K16 定成用 `aos-share`，不歸 daemon 自動做；所以換了身分的 agent 還寄不出信。
- **K9 用信夾擁有者認寄件人**、**K10 收緊活樹權限**、**清道夫讀不到 environ**（04 第 24 條）、**`rm` 時用同一個 subuid 清垃圾**：都在乙之後，下一刀。
- **eca 本體換身分**：K7 已裁先留 1000。

## 留下的東西

- 暫存：`~/.aos/scratch/subuid-1119/`（`src/` 乾淨複本＋已建好的執行檔、`tools/` 測試腳本、`run-*` 測試現場、`regress.log`）。另有兩個我手誤留下的空檔／暫存：`~/.aos/scratch/subuid-1119-setup.sh`（0 位元組）、`/tmp/kd-before.json`；照規矩不刪，留給使用者。
- 沒起常駐行程；測試起的 daemon 都由測試自己 SIGTERM 收掉。
