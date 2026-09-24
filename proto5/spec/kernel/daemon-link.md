← [kernel](README.md)｜[spec 總導航](../README.md)

# 5. 跟 daemon 講話

（2026-09-24 proto5-2 池式納入：`spawn`／`kill` 拿掉，只剩 `scale`；不再偷看孩子表。）

kernel 對 daemon 只放一種單：**`scale`**——「池 P 要這幾號」（形狀、daemon 怎麼處理見 [daemon §3](../daemon/methods.md)）。
每格第 7 步、一池最多一張（[§3.1](pools.md)），boot 與停機另外送（[§6 boot](boot.md)）。回音照範式在 `D/responses/` 同名，kernel 讀完放 ack。

| 要知道什麼 | 怎麼看 |
|---|---|
| daemon 本身活不活 | 對 `D/.daemon.lock` 試拿**非阻塞的共享 flock**——拿不到＝daemon 持著獨占鎖＝活著；拿到了馬上放掉＝沒有 daemon（[daemon §1](../daemon/home.md)）。不看 pid |
| 池裡活了幾顆 | 偷看 `D/pools/<dpool>/summary.json`（[daemon §1.2](../daemon/pools.md)）。只有 `ls`、`cpu ls`、`halt`、boot、搬池時看，**tick 平常不看** |
| 某一顆的狀態 | 只有 `cpu ls --pool`／`ls --pool` 逐顆偷看 `kids/<i>.json` |
| 池是不是已經整個拿掉 | `summary.json` **確定不在**（檔或池資料夾不存在）才算；讀不到、壞 JSON 一律當「還在」（實作 D-49a／D-66） |

cpu 死了是 daemon 自己照宣告補（[daemon §4](../daemon/loop.md)），kernel 不管；第 1 版的「兩個 kernel 共用 daemon、cpu 同名＝`NameTaken`」
改成池的 owner：別的 kernel 已經用了同一個 `dpool`，scale 回 `NameTaken`，記進 `pools.P.error`、`ls` 大聲印。

## 崩潰窗口

| 誰崩、崩在哪 | 會看到什麼 | 怎麼收 |
|---|---|---|
| kernel：記了 `pending`、還沒放單 | 單在 `sends` | 下一格出貨補放 |
| daemon：收了單、寫 `pool.json` 之前 | 新 daemon 開機對帳回 `Interrupted` | kernel 清 `pending`、重算重送 |
| daemon：寫了 `pool.json`、回音之前 | 同上（`Interrupted`），但宣告已生效 | 重送同一份，`ver` 不加 |
| daemon 沒在跑 | 單留在 `D/requests/` | 等；daemon 開起來就處理。`cpu ls` 印「宣告已送出，daemon 沒在跑」 |
| kernel：讀了回音、還沒寫帳本 | 回音還在 | 下一格重讀重判（冪等） |
| 兩個 kernel 用同一個 `dpool` | 後來的收到 `NameTaken` | kernel 記進 `pools.P.error`、`ls` 大聲印；人改 `dpool` |
| 人刪了 `D/pools/<pool>/` 或換了 daemon 家 | kernel 的 `sent` 還在、daemon 沒這池 | kernel 平常不知道（不送單就不會發現）；`ls` 看摘要不在就報 `池 P：池不見了（跑 aos-kernel boot）`，boot 會重送全部宣告 |
| 人用 `aos-daemon scale --force` 改了 kernel 的池 | daemon 宣告跟 kernel 的 `sent` 不同 | kernel 下次送單就蓋回去；中間派到被收掉的號會卡住，所以 `--force` 只給救急（[daemon §6.3](../daemon/cli.md)） |

## 保證外

- **池刪掉之後，舊鏈晚到的 scale 單把池建回來**：池縮到 0 收完就從 daemon 消失，連它記的 `decl` 一起忘掉；
  之後才被處理的舊單（比刪掉前的 `decl` 舊）會被當成新池照建——`Stale` 只擋得住「池還在」的情況。
  實務上 daemon 照檔名順序處理（舊 chain 的檔名排前）、boot 先把 kernel 池縮到 0，擋掉大半；剩下的窗口
  （舊鏈殘格的 tick 在 boot 之後才放單）列為**保證外**（09-24 裁定，實作 D-69）。要補得讓 daemon 另存每池最後的宣告序號與 owner（tombstone）。
- 兩個 boot 同時跑、人手直接跑 `aos-cpu`（同 §7）。
