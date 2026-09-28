# proto5：Linux 外牆的實作可行性與複雜度

> 2026-09-28 交接快照；[原始來源](../../../wf/workflows/investigations/proto5-linux-wall-feasibility.md)保留於原位置。本文的現行行為與實測均指當時 proto5／環境，非 proto6 已實作；僅調整導航與探針重跑路徑。

## 問題

延續[宿主機 root daemon 第二道牆](proto5-host-root-second-wall.md)：正式員工有專屬 Linux 身分和 tick worker，怎樣落地才不會把權限系統重新做一遍？比較三個 Linux 候選，區分已測機制、尚未整合的設計與長期成本。三條路線不是同等保證，也都不等於 VM。

## 方法

2026-09-28 讀官方文件，執行唯讀能力查詢與無特權、短生命週期隔離實驗；未 sudo、未改服務或帳號、未安裝套件。一次性 Python ctypes 僅在 fork 子程序安裝 Landlock，user namespace 實驗用現有 unshare 與既有 subordinate ID 授權；臨時檔案與 sleep 子程序測完即清理。沒有測試宿主 UID 0，也沒有跑完整 proto5。

環境實測：kernel `6.18.49-1-MANJARO`；LSM `capability,landlock,lockdown,yama,bpf`；Landlock syscall 查詢 ABI **7**。`systemd-run --version` 回報 **261.2-1-manjaro**，bwrap **0.12.0**，setpriv **2.42.3**。先前找不到 `systemd` 執行檔不能推論沒有 systemd；本次也沒有驗證系統 manager 連線或 service 啟動能力。systemd binary 編入 AppArmor 支援不代表目前 kernel 啟用 AppArmor。

## 發現

### 共同需要的執行入口

三條路線都要有確定的員工身分映射，以及工具執行前的不可逆降權。候選流程是可信、單執行緒啟動入口先建立外牆，清除不需要的 FD、環境與控制連線，再啟動 daemon。daemon fork 員工子程序後設定核准的補充群組／GID，處理 capability bounding 與 ambient，設定 real/effective/saved UID，確認其餘能力全無、NNP 已開，再 exec 員工程序。需要能力的操作要在喪失該能力前完成；不能把次序當成任意交換的設定表。

NNP 可以先開，仍持有 SETUID/SETGID 的程序可以切換身分；NNP 只阻止 exec 額外提權。若 namespace 初始化依賴 setuid newuidmap/newgidmap，NNP 應在那些 helper 完成後施加，否則可能阻止建立映射。root 已開的檔案與 socket 不會因降權自動失效，FD 清理要在可信邊界完成。[kernel NNP](https://docs.kernel.org/userspace-api/no_new_privs.html)、[capabilities](https://man7.org/linux/man-pages/man7/capabilities.7.html)、[newuidmap](https://man7.org/linux/man-pages/man1/newuidmap.1.html)

員工身分清單由可信設定決定，不接受工具傳入任意 UID。這限制正常 API；宿主 root daemon 一旦被接管，SETUID 本身仍可選其他宿主 UID，必須靠外部政策擋存取。帳號 provisioning 和日常工作分開：常態 daemon 不為建立員工而獲得修改宿主 `/etc` 的通行證。

### 候選 A：宿主 root，加 systemd 與 AppArmor／SELinux

這條最接近原本的宿主 root 構想：由 system manager 先建檔案／裝置／資源邊界並限制能力，再以 MAC 政策約束 daemon 與子程序，讓它即使 UID 0 也不能超出公司資料範圍。正式員工使用宿主 UID；預先建帳號、群組、目錄所有權，或由另行授權的管理步驟佈建。

新增 aos 程式碼相對較少：身分映射、降權入口、權限檢查與錯誤回報仍要寫；程序存活與資源上限可借現成服務管理。部署／運維成本主要落在 policy：AppArmor profile 或 SELinux domain、檔案標籤、exec 轉換、訊號與 socket 權限，以及升級工具或換目錄後的拒絕紀錄排查。兩種 MAC 並非交換名稱就能通用；目前可見 kernel 沒有啟用任何一種，不能當場視為已可部署。[AppArmor](https://apparmor.net/)、[Red Hat SELinux 說明](https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/8/html-single/using_selinux/index)

systemd 的 readonly、home、devices、NNP 與 bounding set 是可組合材料，非完整答案。須阻斷管理 socket 和政策修改；避免 daemon 自己重新要求一個無限制 service。`ProtectProc` 不保護 root；`ReadWritePaths` 不授 DAC、也不擋讀。完整 bwrap 所需 namespace 和 mount 不能被全面 seccomp 封掉後還期待正常。[systemd 官方文件](https://github.com/systemd/systemd/blob/main/man/systemd.exec.xml)

### 候選 B：可信 launcher，加 Landlock／能力上限／seccomp／cgroup

這條可避免依賴 AppArmor／SELinux，但會增加我們要維護的安全啟動程式。可信 launcher 在解析不可信工作前施加 Landlock，daemon 和其後代繼承；政策放在它們不能修改的地方。capability 控制特權、seccomp 縮小可用 syscall、cgroup 限 CPU／記憶體／程序數，各有職責；cgroup 配置本身仍需宿主授權或 delegation，不因 user namespace 而自動取得。

Landlock 的檔案規則、TCP port 規則、signal 與 abstract Unix socket scope 不同；它不替你解析「只允許這個 LLM 網址」，也不等於一般網路防火牆。scope 只允許向同 domain／子 domain 傳訊號，**不授予跨 UID signal 權限**；daemon 若原本無權，仍需能力或其他機制。員工各自再施加子 domain 可縮小範圍；重新啟動的 daemon 若落入 sibling domain，可能無法清理上一代孩子，因此重啟／停止需外層 supervisor 或穩定共同 domain 的明確設計。[Linux 6.18 Landlock 文件](https://www.kernel.org/doc/html/v6.18/userspace-api/landlock.html)

本機 ABI 7 可用檔案基本操作、跨目錄 refer、truncate、device ioctl 控制、TCP bind/connect，以及 ABI 6 的 signal／abstract socket scope。新文件中的 pathname Unix socket `RESOLVE_UNIX` 是 ABI 9、UDP 是 ABI 10；本機不能用。檔案規則亦非所有 metadata 操作的萬用權限模型。因此目前至少要另以掛載可見性或 MAC 等機制處理 pathname 管理 socket，並限制可達的網路端點；不要只給 Landlock 一份目錄表就宣稱完成外牆。[新版 ABI 差異](https://docs.kernel.org/userspace-api/landlock.html)

開發成本最高的部分是處理能力探測、FD、單執行緒安裝、policy 生成、namespace 相容、錯誤診斷和回歸測試。seccomp 能按 syscall 及純值參數篩選，不能安全地把任意路徑指標當路徑政策；應交給檔案機制。cgroup 用於資源及生命週期管理，不取代機密資料存取規則。[seccomp](https://docs.kernel.org/userspace-api/seccomp_filter.html)、[cgroup v2](https://docs.kernel.org/admin-guide/cgroup-v2.html)

### 候選 C：成熟容器 runtime，daemon 是 namespace root

這條保留「裡面 root 管員工、員工有不同 Linux UID」的語意，但 daemon **不是宿主 root**。user namespace 將內部 UID 映射到已授權的 subordinate UID 範圍；kernel 真的看見不同宿主數字 UID，DAC 仍有效，並非我們模擬使用者。名字可以放容器內 `/etc/passwd`，不必為每名員工改宿主帳號資料。若使用者要求每名員工可直接以宿主帳號登入，則這條不等價。[user namespaces](https://man7.org/linux/man-pages/man7/user_namespaces.7.html)、[subuid](https://man7.org/linux/man-pages/man5/subuid.5.html)

僅將自己映射為 root 只有一個 ID，不能建立多個有效員工；必須有多 UID/GID 映射與 helper 授權。本次不只查到 subids，已成功建立多 ID 映射，見下方。user namespace 自身不隔離檔案可見性；如果 namespace root 映射宿主登入 UID 且仍看見 home，它仍可能改宿主使用者資料。仍需受限 rootfs／掛載、PID／網路／IPC 邊界及資源上限；不能掛宿主 `/` 或管理 socket 進去後期待隔離。

若使用成熟 runtime，可少自製 namespace 啟動、PID 1、清理等程式，代價是新增 runtime 依賴、映像與更新、subuid/subgid 配置、檔案數字所有權、共享目錄／備份還原、rootless 網路及 cgroup delegation 的運維。ID 映射必須穩定；換範圍或搬資料可能改變檔案歸屬。既有工具內 bwrap 的巢狀 userns 還需整合測試。這是降低宿主特權的一個候選，不取代已選方向；共享 kernel，不具 VM 的獨立 kernel 邊界。

### 小實驗結果與可推論範圍

**NNP 與 bwrap：** `setpriv --no-new-privs bwrap --unshare-user --ro-bind / / --proc /proc --dev /dev /usr/bin/true` 回傳 0。這個實驗只測 NNP 相容，不是安全沙盒配置；其 readonly `/` 仍看得到宿主資料，沒有套上完整外牆。

**Landlock 的 FD 邊界：** x86_64 Python ctypes 使用 syscall 444 建 ruleset，handled_fs 只含 READ_FILE、無 allow；prctl NNP 後 syscall 446 套用。新 open `/etc/hostname` 得 EACCES(13)，安裝前已開的自建 TemporaryFile 仍讀得到 `probe-data`。實驗證明預開 FD 必須納入邊界；未測所有 FD 類型。

**Landlock signal scope：** 先在域外啟動本次自己的 sleep，再於 fork 子程序安裝 scope SIGNAL。向域外 sleep 發 SIGCONT 得 EPERM(1)，在域內再 fork 的子程序可被 SIGKILL。只有同 UID 測試，不能據此說跨 UID signal 已獲授權；所有測試子程序已收尾。

**多 UID namespace：** `unshare --user --map-auto --map-root-user` 成功，uid_map 為內部 `0 → 宿主 1000` 一個 ID、內部 `1 → 宿主 100000` 起 65536 個 ID；gid_map 為 `0 → 宿主 1001` 及相同 subordinate 區間，setgroups 為 allow。沒有修改 `/etc/subuid`／`subgid`。這證明現有映射流程可用，不證明容器檔案、網路、資源限制已設好。

**降權組合：** 在上述 namespace 內以 root 開 NNP、清補充群組、逐一 drop capability bounding、清 ambient，再 setresgid/setresuid 到 1。結果 UID/GID 四欄均 1、Groups 空、Inh/Prm/Eff/Bnd/Amb 全 0、NNP 為 1；嘗試 setuid(0) 得 EPERM。這證明次序可組合，但不是宿主 root／完整 launcher 的驗證。這些 exploratory probes 以一次性 Python 執行，沒有留作產品測試。

同輪另有可重跑的[Landlock canary 原始碼](../probes/landlock-canary.c)與[runner](../probes/run.py)，由另一條調查保留；本報告不修改那些檔案。

以下保留本次兩段實驗的 Python 核心，方便核對方法；不是 daemon 啟動器，也不是生產 sandbox。Landlock syscall 編號限本次 x86_64，scope 測試只對自己產生的程序發訊號。

```python
import ctypes, os, platform, signal, subprocess, tempfile
assert platform.machine() == 'x86_64'
libc = ctypes.CDLL(None, use_errno=True)
class Attr(ctypes.Structure):
    _fields_ = [('fs', ctypes.c_uint64), ('net', ctypes.c_uint64),
                ('scope', ctypes.c_uint64)]
def restrict(fs=0, scope=0):
    attr = Attr(fs, 0, scope)
    fd = libc.syscall(444, ctypes.byref(attr), ctypes.sizeof(attr), 0)
    assert fd >= 0, ctypes.get_errno()
    assert libc.prctl(38, 1, 0, 0, 0) == 0, ctypes.get_errno()
    assert libc.syscall(446, fd, 0) == 0, ctypes.get_errno()
    os.close(fd)
print('ABI', libc.syscall(444, 0, 0, 1), flush=True)
with tempfile.TemporaryFile() as f:
    f.write(b'probe-data'); f.flush(); f.seek(0)
    pid = os.fork()
    if pid == 0:
        restrict(fs=4)
        try:
            os.open('/etc/hostname', os.O_RDONLY)
            print('UNEXPECTED: open allowed', flush=True)
        except OSError as e:
            print('new read errno', e.errno, flush=True)
        print('preopened read', os.read(f.fileno(), 20), flush=True)
        os._exit(0)
    os.waitpid(pid, 0)
outside = subprocess.Popen(['sleep', '20'])
try:
    pid = os.fork()
    if pid == 0:
        restrict(scope=2)
        try:
            os.kill(outside.pid, signal.SIGCONT)
            print('UNEXPECTED: outside signal allowed', flush=True)
        except OSError as e:
            print('outside signal errno', e.errno, flush=True)
        inner = os.fork()
        if inner == 0:
            signal.pause(); os._exit(0)
        os.kill(inner, signal.SIGKILL); os.waitpid(inner, 0)
        print('inside signal allowed', flush=True)
        os._exit(0)
    os.waitpid(pid, 0)
finally:
    outside.terminate(); outside.wait()
```

降權實驗的子程序程式如下；由 Python `subprocess.run(['unshare', '--user', '--map-auto', '--map-root-user', 'python', '-c', script], capture_output=True, text=True, timeout=8)` 執行，當時回傳 0：

```python
import os, ctypes, json
c = ctypes.CDLL(None, use_errno=True)
def check(result):
    if result != 0:
        raise OSError(ctypes.get_errno(), 'prctl failed')
check(c.prctl(38, 1, 0, 0, 0))
os.setgroups([])
last = int(open('/proc/sys/kernel/cap_last_cap').read())
for cap in range(last + 1):
    check(c.prctl(24, cap, 0, 0, 0))
check(c.prctl(47, 4, 0, 0, 0))
os.setresgid(1, 1, 1)
os.setresuid(1, 1, 1)
keys = ('Uid', 'Gid', 'Groups', 'CapInh', 'CapPrm', 'CapEff',
        'CapBnd', 'CapAmb', 'NoNewPrivs')
state = {k: v.strip() for k, v in
         (line.split(':', 1) for line in open('/proc/self/status')
          if ':' in line) if k in keys}
try:
    os.setuid(0)
    state['regain_root'] = 'UNEXPECTED'
except OSError as e:
    state['regain_root_errno'] = e.errno
print(json.dumps(state))
```

當次完整降權輸出：

```json
{"Uid":"1\t1\t1\t1","Gid":"1\t1\t1\t1","Groups":"","CapInh":"0000000000000000","CapPrm":"0000000000000000","CapEff":"0000000000000000","CapBnd":"0000000000000000","CapAmb":"0000000000000000","NoNewPrivs":"1","regain_root_errno":1}
```

## 結論

實作可行，新增複雜度主要是**安全啟動邊界與部署政策**，不是 tick worker 的迴圈。候選 A 把成本放在宿主 MAC／服務部署與排障；B 把成本放在我們的 launcher 與長期安全測試；C 把成本放在容器 runtime、UID 映射、儲存和網路運維。沒有一條是加 `sudo` 或加一個設定就完成，也不應同時把三套全部塞進第一版。

若後續做原型，先固定一種 Linux 部署組合和必要防線，再以兩名員工驗證 tick、工具及停止恢復；同時測越界讀寫、管理 socket、訊號、重啟後舊程序和資源上限。必要 ABI／MAC／namespace／cgroup 條件不滿足，應明確拒絕啟動或拒絕建立該員工，不能默默退成裸跑。這是本專案對必要安全條件的候選要求；與官方範例為相容性而採 best effort 的目標不同。本文不交付未測 unit 或替使用者裁定三條路線。

## 來源

官方連結附於各段；systemd 讀官方 GitHub 文件。kernel 新版文件包含本機未支援的 ABI，已用本機 syscall 與 Linux 6.18 文件區分。上述指令及 ctypes 小實驗只在工具所見 Linux 環境完成，不能推論別台宿主或宿主 root 下也已驗證。
