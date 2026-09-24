← [kernel](README.md)｜[spec 總導航](../README.md)

# 6. 命令列（續）：boot

**boot** 只做「交接、拉起來、放第 1 格」，K 的帳本從此只在 kernel cpu 上被改。**兩個 boot 不能同時跑**——
這是給人的規矩，不在保證內（沒有 boot 鎖）。步驟：
1. K 轉絕對路徑；`cli/aos-kernel` 取自己的 realpath、驗有執行位；驗 D 是 daemon 家、daemon 活著（§5 的 flock 探測）；
   info 整份驗過（頂層字面物件、恰好一顆 kernel 池）。這一步不改任何東西。
2. **交接**：kernel 池那顆叫 c。（09-24 補：boot 對帳本裡舊的 `kcpu` 與新 info 選出的 c 去重後**兩顆都交接**——先全部驗 target，
   再依序 kill 並等各自從孩子表消失；只殺新 c 的話，換池時舊鏈還可能在改帳本。新 c 若原本是工作 cpu，它手上的工作 slot
   暫留到 collect 結清，第 4 步清舊 tick 回音時跳過那則。）偷看 `D/state.json`：表裡有 c 且 `target` 不是我們的 → `NameTaken`、退 1。
   表裡有 c（不管 alive／dead）→ 向 daemon `kill c`（`NotFound` 也算成功），然後**等到 c 從孩子表消失**
   （最多 `--wait-ms`，預設 30 秒）。逾時＝退 1、`AlreadyRunning`——**kill 已送出、不會撤回**，舊的那格做完
   還是會被收掉，只是 chain 沒換；等一下再 boot 一次就好。c 消失＝沒有任何一格在跑、也不會再有——這才是「舊鏈停了」的證據。
   （09-24 補）例外：cpu 若是被 KILL 硬砍，另一個 process group 的 tick 子程式可能還活著（範式 §5.3 的保證外），
   這種情況「c 消失」不保證 tick 已死；本版不做 kill-tree。
3. 寫 info.daemon；帳本：`chain`＝新 id、`kcpu`＝c、`cli`、`last_seq`＝0、`phase`＝running、**`stops` 清空**
   （上一條鏈欠的 stop 是給上一代 cpu 的，不重放。09-24 補：只丟**帳本裡還沒出貨**的；已經放進 cpu `requests/` 的 stop 仍有效，
   新主人可能一開機就讀到而退出——boot 成功不保證排除這種跨代通知，要另確認鏈真的在跑）；`cpus`／`queue`／`procs`／`acks`／`replies`／`deletes` **照舊**
   （在途 `req`、`pending` 都留著，新鏈接手收；名字帶舊 chain 沒關係，收的是舊名、ack 用新名）。
   **第一次 boot 沒有帳本**＝這些全部從空的開始（`cpus` 照 info 列工作 cpu、`req` 都 null）。
4. 每顆 cpu：家缺什麼補什麼（info、inst，`envs` 照 info；已在的不覆蓋，§1.1 末）；`spawn` 全部、等回音（c 剛被收掉，這裡拉回來；
   其他活著的同名同 target 就回 pid、不動）。
5. `link` 第 1 格 `k-<chain>-1.json` 到 `cpus/<c>/requests/`。退 0。

再 boot 一次＝重做第 2 步的交接再開新鏈；舊鏈殘格帶著舊 chain 自滅。
**daemon 重啟過**（孩子表被清空）也要 boot——kernel cpu 死了沒人會放第 1 格，「每格補拉」補的是工作 cpu。
