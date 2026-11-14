# 圖紙 B4：daemon 收緊與看得懂（線限 11-14，照 kernel-limits-plan 段 1；C++）

← [線限 11-14 紀錄](../kernel-limits-1114.md)｜設計出處：[04 段 1](../../13/kernel-limits-plan/04-施工與驗收.md)、[03 第一節第 1、7 條與第四節](../../13/kernel-limits-plan/03-opus細化.md)、[05 K2、K11](../../13/kernel-limits-plan/05-待裁與衝突.md)、[06 X7、X8、X11](../../13/kernel-limits-plan/06-試驗紀錄.md)｜事實出處：`~/code/limits-1114/notes/G1-facts.md`（sol 11-14 蒐集，行號以 base `90d9a46d0` 為準）

施工隊照這份寫碼，不做設計決定。圖紙沒寫到、或自相矛盾＝BLOCKED。

## 0. 範圍（只准動這些檔；全在 `proto8/` 底下）

- `impls/aos-daemon/src/child/limits.hpp`、`limits.cpp`
- `impls/aos-daemon/src/child/child.hpp`、`child.cpp`
- `impls/aos-daemon/src/daemon/daemon.hpp`、`daemon.cpp`、`reconcile.cpp`、`procs.cpp`、`adopt.cpp`
- `impls/aos-daemon/tests/test_limits.py`（新）
- `impls/aos-daemon/docs/09-份額.md`、`docs/06-結束碼等.md`、`docs/07-建置與測試.md`（測試清單加一行）
- `docs/NORMS/04-基礎設施-loop與daemon/02-N-28.md`（`limits` 那段）

知識庫 `cli/daemon.json` 在活樹，**不改**；要改的句子寫進回報，由 ok-limits 列給頂層。

程式輸出英文；註解繁體中文；照該檔既有風格（`code::LimitBad` 等常數、`Error{code, msg}`、`warn(...)`）。

## 1. 背景（施工隊需要知道的事實）

- 現在 `apply_limits` 對每個鍵 soft＝hard（`limits.cpp:148`）。cpu 到頂時，soft＝hard 會被核心直接 SIGKILL（退 137），看不出是 cpu 用完；hard＝soft＋1 才會先收到 SIGXCPU（signal 24，退 152）。這是 11-13 實測 X7、X8 的結果。
- 現在列上寫 `limits: {}`＝不限，蓋過 daemon 預設（`reconcile.cpp:19` `limits_of`）。使用者裁 K2：改成「用預設」，要不限只能寫在 daemon.json 頂層（不寫 `limits`）。
- 列上寫了非空的 `limits`＝**整份取代**預設（不逐鍵合併）。**這條不改。**
- 單支起不來的既有收斂位置：`reconcile.cpp` 兩個 `catch (const Error& e)`（約 :88 與 :202），會留一列 `stopped`、`reason "failed to start: CODE msg"`、`warn(...)` 一行到 daemon stderr，daemon 自己不退。新的天花板檢查要丟 `Error` 進這兩條路，**不可**放進 `read_procs`／`check_limits`（那邊丟錯會拒整封信或讓整台 daemon 退）。
- kernel 站（B1，已交）在轉信前就把 `limits` 夾進它自己的 `max`，並寫上 `limits_clamped`。daemon 這邊是保底：**超過天花板就拒，不夾**（03 第 7 條、C-56）。

## 2. 改什麼

### 2.1 cpu_s 的 hard＝soft＋1（limits.hpp／limits.cpp）

- `Limits::Rl` 多一欄 `unsigned long long hard`；其他鍵 `hard = value`；`cpu_s` 的 `hard = value + 1`。
- `apply_limits`：`rlim_cur = value`、`rlim_max = hard`。
- daemon 自己的 cpu hard 是有限值，而且 `value + 1` 超過它、但 `value` 沒超過：hard 退回成 `value`（照舊能跑，只是看不到 SIGXCPU），不報錯。判斷用 `getrlimit(RLIMIT_CPU)`，在 `prep_limits`（父行程）裡算好。
- `limits.hpp` 檔頭註解 `soft＝hard＝寫的值` 改成 `soft＝寫的值；hard 同值，cpu_s 多 1 秒（先收到 SIGXCPU）`。

### 2.2 `limits: {}`＝用預設（reconcile.cpp `limits_of`）

- 新邏輯：
  - 先照舊選出 `l`；
  - `l` 是空物件、而且來源是列上自己寫的 `spec["limits"]` → 改用 `limits_`（daemon 預設）；
  - 最後照舊：`l` 是非空物件就回 `l`，否則回 `Json()`（不限）。
- 接回只留名的列（`spec` 是 null、用 `kept`）照舊。
- 註解 `{}＝不限（蓋過預設）` 改成 `{}＝用預設（K2；要不限只能 daemon.json 不寫 limits）`。

### 2.3 daemon.json 新鍵 `limits_max`（daemon.hpp／daemon.cpp／limits.cpp／reconcile.cpp）

- **讀**：`daemon.cpp:79` 那串要解指示詞的鍵加上 `"limits_max"`。`daemon.hpp` 加成員 `Json limits_max_;`。在 `:133-134` 讀 `limits_` 的地方之後：`limits_max_ = cfg_.value("limits_max", Json());`。
- **驗**（daemon 起動時，錯＝`CfgBad`、daemon 退 1，跟現有 `limits` 一樣）：
  1. `check_limits(limits_max_, "limits_max")`，沿用同一套形狀檢查。
  2. 另外 `limits_max` 不准有 `user` 鍵：`limits_max.user is not allowed (limits_max only caps numbers)`。
  3. `limits_max` 是非空物件時，`limits_` 必須也是非空物件、而且每個 `limits_max` 的鍵都在 `limits_` 裡、值 ≤ max。不符＝`CfgBad`，訊息照下表逐字（`<k>`、`<v>`、`<m>` 換成實際值）：

| 情況 | CfgBad 訊息 |
|---|---|
| `limits_` 沒寫或空 | `limits_max needs limits to name a default for every capped key` |
| 缺鍵 | `limits.<k> is missing but limits_max.<k> is <m>` |
| 超過 | `limits.<k> <v> exceeds limits_max.<k> <m>` |

- **新函式**（limits.hpp 宣告、limits.cpp 實作）：`void check_limits_max(const Json& lim, const Json& max);`
  - `max` 是 null 或空：直接 return。
  - 否則對 `max` 的每個鍵 `k`（照 KEYS 順序）：
    - `lim` 是 null（不限）或沒有 `k`：丟 `Error{code::LimitBad, "<k> unlimited exceeds limits_max <m>"}`；
    - `lim[k] > max[k]`：丟 `Error{code::LimitBad, "<k> <v> exceeds limits_max <m>"}`。
  - 只比數字鍵；`user` 不比。
- **呼叫點**：`reconcile.cpp` 兩條起動路徑（:88 與 :202 那兩個 try）裡，`lim` 算出來之後、真的 launch 之前，各呼叫一次 `check_limits_max(lim, limits_max_)`。
  - 丟出的 Error 由既有 catch 收：那一列 `stopped`、`reason "failed to start: LimitBad cpu_s 100 exceeds limits_max 10"`；daemon stderr 一行 warn（既有的 `cannot start …`）。
  - 不另外印，不另外加碼。

### 2.4 收屍翻譯 `limit_hit`／`limit_suspect`（child.hpp／child.cpp／adopt.cpp）

- `Child` 加兩欄 `Json limit_hit;`、`Json limit_suspect;`（預設 null）。每次起動（launch 成功、或走 catch 留 stopped）都先清成 null。
- `alive()`：自己 fork 的、`got == c.pid` 時，照下列順序設：
  - `WIFSIGNALED` 且 signal 是 `SIGXCPU`（24），而且 `c.limits` 有 `cpu_s`：`c.limit_hit = "cpu_s"`。
  - `WIFSIGNALED` 且 signal 是 `SIGXFSZ`（25），而且 `c.limits` 有 `file_mb`：`c.limit_hit = "file_mb"`。
  - 正常結束、碼是 1，而且 `c.limits` 有 `mem_mb`：`c.limit_suspect = "mem_mb"`。只是猜：rlimit 記憶體到頂，程式多半自己退 1。
  - 其他情況都不設。接回的（`own == false`）拿不到 wait status，一律不設。
- `row()`：緊接在 `limits` 那段（`child.cpp:297`）之後：`limit_hit` 不是 null 就輸出 `r["limit_hit"]`；`limit_suspect` 同理。是 null 就不輸出這個鍵。
- `adopt.cpp`：接回 stopped／sleeping 列、帶回 `code`、`signal` 的地方（約 :257-258），照樣從舊列帶回 `limit_hit`、`limit_suspect`（舊列有才帶）。
- `table.cpp` 的 log 不動。

### 2.5 沒換 uid 時寫 `procs`＝警告一行照套（K11；limits.cpp）

- `prep_limits`（父行程、fork 之前）：備好的份額有 `procs`、而且沒有 `user`（不換 uid）時，往 daemon stderr 印一行：
  `aos-daemon: warning: procs <n> counts every process of uid <getuid()>, not only this proc (no user switch)`
- 照常套用，不擋。
- 印法照 limits.cpp 既有的 `std::fprintf(stderr, ...)`；這裡在父行程，不 `_exit`。

### 2.6 `limits_clamped` 不讓列變成 loop 型（procs.cpp／child.cpp）

- `procs.cpp:205` `is_once` 白名單加 `k != "limits_clamped"`。
- `child.cpp:154-163` loop 型起動前擦掉 daemon 專用鍵的那串，也加 `limits_clamped`。
- daemon 不讀它、不輸出它（列的 `as_written` 照舊原樣留著）。

## 3. 建置（照 G1 第 7 節；不在 repo、不在活樹編）

```sh
L=/home/lorkhan/code/limits-1114
$L/clean.sh bash -eu -c '
B=/home/lorkhan/code/limits-1114/build; W=/home/lorkhan/code/limits-1114/work
rsync -a --delete --exclude=bin --exclude=lib "$W/proto8/impls/" "$B/source/impls/"
export VCPKG_ROOT="$B/tools/vcpkg" XDG_CACHE_HOME="$B/cache" VCPKG_BINARY_SOURCES="clear;files,/home/lorkhan/.cache/vcpkg/archives,read" VCPKG_DISABLE_METRICS=1
cmake --build "$B/cmake" --target aos-daemon_main --parallel 2
cp "$B/source/impls/aos-daemon/bin/aos-daemon" "$W/proto8/impls/aos-daemon/bin/aos-daemon"
'
```

`rsync --delete` 只作用在 `build/source/impls/` 裡，而且排除 `bin`、`lib`。這是暫存樹的建置複本，不是 repo，也不是活樹。最後一行把新的 binary 放進 `work/` 的 bin，因為測試的 `support.py` 會把 work 的 `impls/*/bin` 放在 PATH 最前面。

## 4. 測試 `tests/test_limits.py`（新）

- 用 `support.py` 的 Fixture（照 `test_lifecycle.py:227`、`:235` 的寫法）。
- proc 的 exec 照現行語法：在暫存夾寫一支可執行的 shell 檔，exec 指向它。**不要**照 04 的 `"exec": "sh -c '…'"` 字面。
- 每支 proc 都要有上限，不准真的無限迴圈：cpu 例子靠 `cpu_s: 1` 收，再加一層 `timeout_ms` 或測試自己的等待上限。
- 至少要有這幾例：
  1. `limits: {"cpu_s": 1}`，跑 `while :; do :; done` → 表上 `signal 24`、`code 152`、`limit_hit "cpu_s"`。
  2. `limits: {"file_mb": 1}`，寫 2MB（`head -c 2097152 /dev/zero > f`）→ `limit_hit "file_mb"`。
  3. `limits: {"mem_mb": 64}`，`python3 -c "x = bytearray(200 * 1024 * 1024)"` → `code 1`、`limit_suspect "mem_mb"`、沒有 `limit_hit`。
  4. daemon.json `limits: {"files": 256}`，列寫 `limits: {}` → 表上 `limits` 是 `{"files": 256}`；proc 裡 `ulimit -n` 印 256。
  5. daemon.json `limits: {"cpu_s": 5}`、`limits_max: {"cpu_s": 10}`：
     - 列寫 `cpu_s: 100` → 那列 `stopped`、reason 含 `LimitBad cpu_s 100 exceeds limits_max 10`，daemon 自己還活著，別的列照跑；
     - 列寫 `{"files": 64}`（缺 cpu_s）→ reason 含 `cpu_s unlimited exceeds limits_max 10`。
  6. `limits_max: {"cpu_s": 10}`，`limits` 沒寫 → daemon 起不來（CfgBad，退 1）；`limits: {"cpu_s": 20}` 也退 1，訊息逐字照 2.3 的表。
  7. `limits: {"procs": 50}`、不換 uid → daemon stderr 有 `procs 50 counts every process of uid`。
  8. proc 規格帶 `limits_clamped: ["cpu_s"]`，其餘是 once 型 → 列照 once 型起；loop 型列帶它也不會傳給 proc。
  9. 寫了 `cpu_s` 的 proc，在 `/proc/<pid>/limits` 讀到的 Max cpu time 是 soft N、hard N+1。
- 跑法（兩條都要全綠；第二條是既有的全套回歸）：

```sh
L=/home/lorkhan/code/limits-1114
$L/clean.sh bash -c "cd $L/work && export TMPDIR=$L PYTHONDONTWRITEBYTECODE=1 && python3 -m unittest proto8/impls/aos-daemon/tests/test_limits.py -v"
$L/clean.sh bash -c "cd $L/work && export TMPDIR=$L PYTHONDONTWRITEBYTECODE=1 && python3 -m unittest discover -s proto8/impls/aos-daemon/tests -p 'test_*.py'"
```

- 測試 fixture 會殺它自己起的 daemon 和 proc，那些是你這次測試起的程序，可以。不准殺別的。

## 5. 說明文件

- `docs/09-份額.md`：
  - cpu hard＝soft＋1；
  - `{}`＝用預設；
  - `limits_max`（天花板、超過＝那支 `LimitBad` 起不來、不夾；`limits` 要涵蓋每個被封頂的鍵）；
  - `limit_hit`／`limit_suspect` 的意思（suspect 只是猜）；
  - procs 不換 uid 的警告；
  - `limits_clamped` 是 kernel 寫的記號，daemon 不讀。
- `docs/06-結束碼等.md`：錯誤表加 `LimitBad … exceeds limits_max`、`CfgBad limits_max …` 三條；結束碼加「152＝SIGXCPU（cpu_s 到頂）、153＝SIGXFSZ（file_mb 到頂）」。
- `docs/07-建置與測試.md`：測試清單加 `test_limits.py`。
- N-28 的 `limits` 段：加 `limits_max` 一句，並把 `{}` 的語意改掉。
- 回報裡另列「知識庫 `cli/daemon.json` 要改的句子」（不改檔）。

## 6. 完成條件

- 第 0 節以外沒動。
- 照第 3 節建置成功。
- 第 4 節兩條測試全綠，並在回報裡貼原文。
- `git diff --stat` 附在回報裡。

## 7. Argon 審後的修正（11-14 ok-limits；跟上面衝突時以這節為準）

原文在 `/tmp/ok-limits-argon2/argon.out`（暫存）。採納表在紀錄檔。

### 7.1 範圍加檔

- `impls/aos-daemon/docs/01-用法.md`（daemon.json 頂層鍵表加 `limits_max`）
- `impls/aos-daemon/docs/02-看寫法決定怎麼起.md`（is_once 白名單加 `limits_clamped`）
- `knowledge/aos/cli/daemon.json`（repo 裡的知識庫源頭，不是活樹；在 `#/add` 那句 `--limits` 旁補 `{}`＝用預設、`limits_max`、`limit_hit`。照檔裡既有的寫法，一句一鍵，不另開大節）
- 第 0 節「知識庫不改」那句作廢，改成上面這條。

### 7.2 程式

1. **預設 `user` 不會被列洗掉**（`limits_of`，2.2）：列寫了非空 `limits`、裡面沒有 `user`，而且 `limits_` 有 `user` → 結果補上 `limits_["user"]`。列自己寫了 `user`，照寫的（身分政策歸 kernel 站管）。這是數字鍵「整份取代」之外唯一的例外。
2. **`limits_max` 的驗證順序**（2.3）：
   - 先檢查 `limits_max_` 是物件而且有 `user` → `CfgBad limits_max.user is not allowed (limits_max only caps numbers)`，再呼叫 `check_limits`；
   - `limits_max_` 不是物件或有未知鍵時，`check_limits` 原本的訊息照用（裡面提到 user 不另改）；
   - 第 3 步巡鍵照 **KEYS 順序**，每個鍵先查缺、再查超過。
3. **父行程預檢 daemon 自己的 hard**（`prep_limits`）：
   - 對每個要套的數字鍵 `getrlimit`；`rlim_max != RLIM_INFINITY` 而且 `value > rlim_max` → 丟 `Error{code::LimitBad, "<k> <v> exceeds the daemon's own hard limit <h>"}`（數字跟寫的單位一樣：mem_mb／file_mb 寫 MB）。
   - 這樣它也走 reconcile 的 catch，留單列 stopped，不會進子行程 `_exit(1)`、也不會被誤標 `limit_suspect`。
   - 子行程 `apply_limits` 原本的 EPERM 那條留著當保險。
   - cpu 的 hard：寫成 `hard = val + 1`；如果 daemon 自己的 cpu hard 有限、`val <= h` 但 `val + 1 > h`，就 `hard = val`（Argon 第 5 條的程式段照用）。
   - `mem_mb` 有兩筆 `push_back`（RLIMIT_AS、RLIMIT_DATA），兩筆都要填 `hard`。
4. **`limit_suspect` 的條件**：一定要是 `WIFEXITED(status) && WEXITSTATUS(status) == 1`，不能只看 `c.code == 1`。
5. **K11 警告每列只印一次**：`Child` 加 `bool procs_warned`。同一列（同一個 Child）第一次 launch 帶 procs、又不換 uid 時印；之後重起不再印；該列的 `limits` 變了就重設。
6. **reconcile :202 那條重起路徑**：
   - 用 `c.limits` 呼叫 `check_limits_max`；
   - 進 catch 時一併 `c.signal = Json()`、`c.limit_hit = Json()`、`c.limit_suspect = Json()`。
7. **註解**：`daemon.hpp:190`、`child.hpp:84` 的「`{}`＝null（不限）」改成「用預設」。
8. **接回（adopt）的 running 列**：**不**重新檢查 `limits_max`。只有之後重起、走 launch 時才檢查。照現狀，不加主動停的邏輯；寫進 docs/09。

### 7.3 測試（改第 4 節）

- `test_limits.py` 檔頭加 `sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))`。第一條跑法改成 `python3 proto8/impls/aos-daemon/tests/test_limits.py -v`（照既有測試的跑法）。
- 拿掉「`timeout_ms` 或」；cpu 例子只靠測試端輪詢等待的上限（最多 15 秒）。
- 例 1、2、9 的 shell 檔一律用 `exec` 跑最後那支程式（`exec head -c 2097152 /dev/zero > f`），讓它就是 daemon 的直接子行程；沒用 exec 的話，訊號會被 shell 轉成一般結束碼 152／153。
- 例 3 改成 `mem_mb: 256`，跑 `LC_ALL=C exec python3 -c "x = bytearray(1024 * 1024 * 1024)"`。
  - 驗 `code 1`、`limit_suspect "mem_mb"`。
  - 如果家機上 python 在 256MB 底下連起都起不來（退的不是 1），改成 512／2048，回報裡寫實際用的數字。
- 例 6 補兩種：
  - `limits: {"files": 64}` 加 `limits_max: {"cpu_s": 10}` → 缺鍵那條訊息；
  - `limits_max: {"user": "root"}` → `limits_max.user is not allowed`。
- 例 7 的 shell 檔只用內建指令（`:`；`exit 0`），不 fork 外部指令，只驗 daemon stderr 的警告字串，而且同一列重起後不再出現第二行。
- 例 8：照 `docs/02-看寫法決定怎麼起.md` 與 `test_lifecycle.py` 現成的 loop 型寫法造一列，帶 `limits_clamped`。
  - 驗 once 型那列仍是 once（表上沒有 loop 欄）；
  - 驗 loop 型那列交給 proc 的設定裡沒有 `limits_clamped`。怎麼看設定，照現成 loop 測試的做法；沒有現成做法就 BLOCKED。
- 例 9：腳本 `touch ready && exec sleep 30`；測試等到 `ready` 出現才讀 `/proc/<pid>/limits`。
- 新增例 10：daemon 用 `prlimit --cpu=5:5` 包著起，列寫 `cpu_s: 10` → 那列 stopped，reason 含 `exceeds the daemon's own hard limit 5`。
  - 再一列寫 `cpu_s: 5` → 照起，`/proc/<pid>/limits` 的 cpu 是 soft 5、hard 5（退回的那條）。

### 7.4 說明文件（加進第 5 節）

docs/09 加這幾點：

- `limit_hit` 看的是 daemon 的直接子行程；沒用 exec 包一層 shell，或程式自己攔／忽略 SIGXCPU、SIGXFSZ，就看不到訊號：
  - 攔 SIGXCPU 拖到 hard＝被 SIGKILL，退 137；
  - 忽略 SIGXFSZ＝write 回 EFBIG，程式自己退。
- `limit_suspect` 只是猜：任何以 1 結束、又帶 `mem_mb` 的列都會被標。
- **數字鍵整份取代**：列寫了非空 `limits`，就會蓋掉預設裡沒寫的鍵。所以不想讓信件取消的預設鍵，一定要列進 `limits_max`。預設 `user` 例外，會補上。
- 一期 rlimit 的邊界，附一張短表跟二期 cgroup 對照：
  - `cpu_s` 是單一行程，fork 出去的子行程重新起算；
  - `file_mb` 是單檔大小；
  - `mem_mb` 是虛擬位址空間；
  - `procs` 是整個 uid 的總數。
- 接回的 running 列不會重新檢查 `limits_max`，要等它重起。

## 8. 施工前更正（11-14 ok-limits，sol-3 回報 BLOCKED 後；跟 2.3、7.2.6 衝突時以這節為準）

sol-3 對過現在的程式碼：`reconcile.cpp:202` 是 `refresh()` 的 catch，不是第二條起動路徑。實際起動只有 `Daemon::start()`（:32）一條：

- `:285`：held 列重起（start／wake／自動重起）呼叫 `start()`；
- `:327`：新列呼叫 `start()`；
- 沒有其他呼叫點。

改法：

1. **天花板檢查只放一處**：`start()` 的 try（約 :73）裡，`bad_rows_`／`launch_spec.is_null()` 那兩個檢查之後、`spawn_exec`／`spawn` 之前，呼叫 `check_limits_max(lim, limits_max_)`。`lim` 是函式開頭 `limits_of(spec, kept_limits)` 算出來的，held 列重起時用的就是列上的 `c.limits`。丟出的 `Error` 由 :88 那個 catch 接住（留成 stopped、寫 reason、warn），不用另外處理。
2. **`refresh()`（:139～:202）完全不動**：它只重解路徑，不起行程。沒有 `as_written` 時提前 return 也沒問題，因為檢查已經在後面的 `start()` 裡。
3. 7.2.6 改成：**:88 那個 catch** 裡多清 `c.signal = Json()`、`c.limit_hit = Json()`、`c.limit_suspect = Json()`。新建的 `Child c` 本來就是空的，這只是寫明。:202 不改。
4. 第 2 節開頭的「兩個 catch」、2.3「呼叫點」那一段，一律以本節為準。
5. **使用者 11-14 的裁定（選 a）**：整份取代不改。docs/09 與 knowledge `aos/cli/daemon.json` 要寫明兩件事：
   - 不想被列取消的預設鍵，放進 `limits_max`；
   - 在列上寫 `limits` 時，要的鍵都要寫全（`user` 例外，會從預設補上）。
