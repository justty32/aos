# daemon 帳號模組：主程式降權、root 端開別的帳號的程序

← [daemon 目錄](README.md)｜[核心 B-640](core.md)｜[控制 B-641](control.md)｜[重讀設定 B-642](reload.md)｜[記住狀態 B-643](state.md)｜[收屍／cgroup B-644](cgroup.md)｜[訊息 B-645](mq.md)｜格式：[P-126](../protocol/daemon/account.md)｜舊設計：[暫緩區 B-303](../deferred/helper.md)、[B-609](../deferred/daemon/helper-actions.md)

本篇只有 B-646，寫帳號模組**做什麼**。設定怎麼寫、root 端的封包、stderr 的行，寫在格式篇 [P-126](../protocol/daemon/account.md)。

依據：[verdicts 11 篇末「2026-10-01 第十三批：帳號模組」](../../../notes/verdicts/11-tick-as-unit.md#2026-10-01-第十三批帳號模組)、[第十二批](../../../notes/verdicts/11-tick-as-unit.md#2026-10-01-第十二批cgroup-與帳號)、[plan m3m 模組五](../../../plan/m3m-daemon-modules.md#模組五帳號modulesaccount)；現行程式 [帳號](../../../src/py/README.md#帳號m3m-模組五)（`lib/aos_daemon_account.py`、`lib/aos_daemon_root.py`，有出入以程式為準）。

## B-646：帳號模組〔使用者 2026-10-01 第十二、十三批〕

**某一項指定用哪個帳號跑，daemon 就用那個帳號開那一項的 `aos-exec`。** 它是 daemon 的一個模組（[B-640](core.md)「模組」），設定檔寫了 `modules.account` 才有，而且要用 root 開（`sudo aos-daemon --config F`）；沒用 root 開回 1。

**切帳號只在 daemon 設定檔做**〔使用者 2026-10-01 第十三批〕：單位是 daemon 的一項，不在一格裡面中途換。tick 不切帳號；任務在 argv 包 `aos-as` 的做法在[暫緩區](../deferred/protocol/tick.md#p-212aos-as切換帳號建議預設未拍板)。inst 自己包 `sudo -u` 不在規劃中，aos 不管、不保證。

### 兩支程序

```text
sudo aos-daemon --config F
 ├─ root 端（aos-daemon-root）：一直是 root；只做「用某帳號開一個程序」
 └─ 主程式（aos-daemon）：開起來就永久降成預設帳號；其他所有事都是它做
```

1. **開起來**（root）：讀設定、核帳號（下面）；掛了收屍模組就照 [B-644](cgroup.md) 建好子樹，再把整棵子樹交給預設帳號；開出 root 端（另一支小程式，不讀設定檔、不載入 aos 其他模組），把名單交給它。
2. **主程式永久降成預設帳號**（UID、主群組、補充群組；`HOME`、`USER`、`LOGNAME` 也換成它的），回不去。之後才開控制、訊息 socket（**權限 666**，別的帳號的任務也連得上〔第十二批：先 666；之後會有多個 socket、權限另外設計〕）、起各項。所以 socket、狀態檔、輸出檔都歸預設帳號。
3. **跑一項**：帳號是預設帳號的，主程式自己開，跟沒掛模組時一樣。別的帳號的，主程式請 root 端開：root 端開新 session、有框就先把它放進那一項的框（還是 root，別的帳號的程序才搬得進去）、切成那個帳號（UID、主群組、補充群組；`HOME`、`USER`、`LOGNAME` 換成它的）、開 `aos-exec`，等它結束把碼回給主程式。主程式收到碼才算 `aos-exec` 結束（`ms=` 算到這裡），接著照舊清框、收齊輸出、印 `exit=`。
4. **root 端開之前再核一次**：帳號照名單是准的、查得到、不是 root。開起來之後帳號才被刪掉（查不到）：那一次當成 `exit=1`，stderr 一行，daemon 照跑、下一次照排（A6）。
5. **停**：主程式照核心 Ctrl-C／SIGTERM 直接退出、不殺子程序；root 端發現主程式那頭關了就自己退出，也不殺子程序。root 端被殺掉：主程式 stderr 一行、**整個 daemon 回 1**（A5）。

### 預設帳號與名單

- **預設帳號**＝`modules.account.user`；沒寫用 `SUDO_USER`（從某人的 shell 打 `sudo aos-daemon …`、或 `sudo -i` 之後再開，就是那個人；`su -`、root 直接登入、root 的 systemd unit 或 cron 開的沒有，要自己寫）。兩個都沒有、查不到、或是 root：設定錯。
- **名單**〔使用者 2026-10-01 第十三批：「daemon設定檔中要有白名單和黑名單，然後名單支援prefix，比如agent-*。」〕：`allow`（白名單）、`deny`（黑名單）。一個字串是完整帳號名，或結尾一個 `*` 當前綴（`agent-*`；單獨 `*` 比所有帳號）；`*` 寫在結尾以外＝設定錯。
- **判斷**：黑名單比到就不准 → 白名單比到才准 → 都沒比到不准。root（UID 0）不管名單一律不准。`allow` 省略＝空（只有預設帳號能用）。
- 預設帳號不受名單管（它就是主程式自己）；但 **`deny` 比得到預設帳號（含前綴、單獨 `*`）＝設定錯**，不論 `allow` 有沒有寫〔使用者 2026-10-01 第十三批追加與 A7〕。
- **每一項的帳號**（那一項的 `account.user`，沒寫＝預設帳號）**開起來時就核**：要照名單是准的、在 Linux 上查得到（A6）；不合就是設定錯、回 1。daemon 不建帳號。
- 名單在開起來時交給 root 端，之後不變。主程式被攻破時，最多拿到「用名單准的帳號開程序」，拿不到 root。

### 跟其他模組

- **控制、訊息**（[B-641](control.md)、[B-645](mq.md)）：socket 由降權後的主程式開、權限 666。別的帳號的項一樣拿得到 `AOS_DAEMON_*`。
- **重讀設定**（[B-642](reload.md)）：重讀是主程式（預設帳號）做的，設定檔要讀得到。每一項的帳號照**開起來時**的名單核：名單不准或查不到＝重讀出錯（整份不套用、stderr 一行、舊的照跑）；還在的項帳號改了，下一次起用新帳號。改 `modules.account`（含名單）算 `modules` 改了：只警告、不套用。
- **記住狀態**（[B-643](state.md)）：狀態檔由主程式寫，歸預設帳號。
- **收屍／cgroup**（[B-644](cgroup.md)）：子樹開起來時整棵交給預設帳號，主程式自己建框、寫上限、清框、刪框；別的帳號的子程序由 root 端放進框。留下的背景程序照樣被清掉。

### 先不做

一格裡某個任務換帳號（`aos-as`，暫緩）、佈建（建帳號、群組、chown、quota）、多帳號交接檔案的群組規劃、多個 socket 各自的權限、root 端死掉後重開。舊設計的身分額度、登記綁 UID、通道憑證、runner、`provision` 動作都在暫緩區（[B-303](../deferred/helper.md)、[B-609](../deferred/daemon/helper-actions.md)）。

依據：使用者 2026-10-01 第十二批（模組鍵 `account`、H1 拆 root 端與主程式降權、socket 先 666）；第十三批（A1～A5 照建議、白名單與黑名單支援前綴、`allow` 不寫而 `deny` 有預設帳號就報錯、`aos-as` 暫緩、`sudo -u` 不在規劃中；A6、A7 照建議）。

**驗收：**`sudo` 開，`a` 不寫帳號、`b` 寫名單准的別的帳號：`a` 的任務 `id -un` 是預設帳號、`b` 是那個帳號，`id -G` 有那個帳號的補充群組，`HOME`／`USER`／`LOGNAME` 是它的；主程式的 Uid 四欄都是預設帳號、root 端是 root；控制 socket 是 666、歸預設帳號，`b` 的任務 `aos-ctl status` 連得上；輸出檔歸預設帳號；結束碼與被訊號殺（128+N）照實；用 `SUDO_USER` 當預設帳號；用名單不准的帳號、root、查不到的帳號、預設帳號是 root 或沒有、`deny` 比到預設帳號（`allow` 寫不寫都算）、`*` 在中間：回 1；沒用 root 開：回 1；重讀加名單不准的帳號：stderr 一行、舊的照跑；加准的帳號：用它跑；改名單：`reload: need restart: modules`；root 端開跑時帳號查不到：回錯、那一次 `exit=1`；殺掉 root 端：daemon 回 1；SIGTERM：daemon 回 0、root 端跟著退；跟收屍模組一起：別的帳號留下的背景程序被清掉、框歸預設帳號。測試見 `proto6/src/py/tests/test_account.py`（假 root 用 `unshare --user --map-root-user --map-auto`，拿不到就跳過；真 root 下的整套要手動驗，見 [plan m3m 模組五](../../../plan/m3m-daemon-modules.md#模組五帳號modulesaccount)）。
