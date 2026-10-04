"""aos7-run：任務的包裝程式——讀 birth.json，把任務起在自己的程序群組，寫 pid.json，等它，寫 exit.json（spec.md 5.3）。

起點複製自 proto7-1 lib/aos7_run.py；pid.json、exit.json 多帶 `run`（＝birth.json 的 run），pid.json 多帶 starttime。

    aos7-run <taskdir> [<taskdir 的 fd>]

由 tick 啟動，作為 Linux 子程序與檔案協定間的交接者（S-10；spec §5.3 不變條件二）。
經任務 fd 讀 birth.json 及 ../../round.json；寫 out.log、pid.json、exit.json。
任務自己寫的 state／usage 等檔不由 runner 清理，跨 run 的狀態由同槽接續（spec §5.1、§8）。

tick 用新 session 起它，並把任務資料夾的 fd 傳進來、cwd 設成它抓著的 node（astra-6 G-02）、不等；它自己活到任務結束。環境變數（AOS7_*）由 tick 給好，這裡原樣傳下去。

**第二個參數是內部交接用的能力，不是身分約束**（astra-7 H-09）：它必須是呼叫者開好、繼承下來的任務資料夾 fd，cwd 也由呼叫者保證
是那個 node。給了第二參數，fd 就是權威：讀 birth、寫 pid／out／exit 都經它，`<taskdir>` 字串只給錯誤訊息用；fd 無效（不是數字、
沒開、不是資料夾）時 stderr 說清楚、退出碼 2，**不回退**去寫 `<taskdir>` 字串指的地方（可能已被換掉）。這不是驗證或隔離任務身分的邊界。
"""
import json
import os
import re
import stat
import subprocess
import sys

from aos7_fs import BIN, OK, fact, now, proc_starttime, test_point


RUN = [None]   # 這次的 run（讀到 birth.json 後填上；寫 pid.json／exit.json 用）
def build_argv(birth, node):
    """由 birth 任務定義與 node 路徑回傳實際 argv 清單（spec §4.1、§5.3）。
    inst 相對 node 定位並交搬來的 aos-exec（S-12）；否則展開 argv，未給 argv 回空清單由呼叫者報錯。"""
    if birth.get("inst"):
        inst = os.path.normpath(os.path.join(node, birth["inst"]))
        return [sys.executable, os.path.join(BIN, "aos-exec"), inst]
    return [expand(a) for a in birth.get("argv") or []]


def expand(arg):
    """展開 arg 字串中的 $AOS7_TASK、${AOS7_NODE} 等 AOS7_* 環境值，回展開結果。
    未設變數保留原文，其他 $ 不展開，非字串原樣回傳；讓 argv 指到槽與掛載點（spec §4.1、§5.5）。"""
    return re.sub(r"\$\{?(AOS7_[A-Z_]+)\}?", lambda m: os.environ.get(m.group(1), m.group(0)), arg) \
        if isinstance(arg, str) else arg


def read_birth(dfd):
    """從任務目錄 fd（dfd）讀 birth.json（經 fact：非阻塞、只讀一般檔），回 JSON 值；讀不到或壞掉回 None。"""
    st, b = fact("birth.json", dir_fd=dfd)
    return b if st == OK else None


def fail(dfd, msg):
    """將起程序前的失敗 msg 寫 stderr，經目錄 fd（dfd）寫 exit 127，回 runner 退出碼 1。
    連 exit.json 都寫不進去時再告警；tick 記的 runner 讓 tock 後續判 lost（spec §5.3；astra-7 H-06）。
    這裡的 127 是任務結果，不是本函式回傳值，避免起失敗的任務永遠停在 born。"""
    print("aos7-run: %s" % msg, file=sys.stderr, flush=True)
    if not write_at(dfd, "exit.json", {"run": RUN[0], "code": 127, "at": now(), "round": round_at(dfd), "error": msg}):
        print("aos7-run: exit.json 也寫不進去；tock 會照 birth.json 的 runner 判 lost", file=sys.stderr, flush=True)
    return 1


def main(argv=None):
    """執行 argv（None 用命令列）的 taskdir／可選繼承 fd，等任務結束並記錄 pid／exit。
    回 0 表示已走完啟動嘗試或等待流程；1 表示用法／前置失敗，2 表示交接 fd 無效。
    任務的成功、失敗與訊號碼寫 exit.json，不直接當 runner 回傳值（spec §5.3）。"""
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) not in (1, 2):
        print("用法: aos7-run <taskdir> [<taskdir 的 fd>]", file=sys.stderr)
        return 1
    tdir = os.path.abspath(argv[0])
    held = len(argv) == 2   # tick 起的：第二個參數是任務資料夾的 fd，cwd 是 tick 抓著的 node（astra-6 G-02）
    if held:
        try:
            dfd = int(argv[1])
            os.set_inheritable(dfd, False)   # 不傳給任務
            if not stat.S_ISDIR(os.fstat(dfd).st_mode):
                raise OSError("不是資料夾")
        except (OSError, ValueError) as e:
            # 第二參數是繼承來的目錄 fd（內部交接，H-09）：無效就說清楚、不回退去寫字串路徑（可能已被換掉）
            print("aos7-run: 第二個參數 %r 不是繼承來的任務資料夾 fd（%s）；不照 %s 字串路徑寫任何東西。"
                  "這個參數只給 aos7-tick 用，人手跑請只給 <taskdir>" % (argv[1], e, tdir), file=sys.stderr)
            return 2
    else:
        try:
            dfd = os.open(tdir, os.O_RDONLY | os.O_DIRECTORY)   # 先抓住任務資料夾本身：node 搬家後照樣寫到它現在的位置
        except OSError:
            return 1   # 任務資料夾已經不在（剛被刪）：不建回來
    birth = read_birth(dfd)
    if isinstance(birth, dict):
        RUN[0] = birth.get("run")
    if not birth:
        # 經 fd 寫 exit.json：任務不會永遠算剛起（astra-6 G-02）；資料夾已刪就等於丟掉，不建回來
        return fail(dfd, "讀不到 birth.json")
    node = os.environ.get("AOS7_NODE") or os.getcwd()
    # 測試鉤子的環境（AOS7_TEST_*，P2-15）只給 aos7-run 自己，不傳給任務
    env = {k: v for k, v in os.environ.items() if not k.startswith("AOS7_TEST_")}
    try:
        out = os.fdopen(os.open("out.log", os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644, dir_fd=dfd), "ab")
    except OSError as e:
        return fail(dfd, "開不了 out.log：%s" % e)   # 例如 out.log 被建成資料夾（astra-7 H-06）
    try:
        cmd = build_argv(birth, node) if isinstance(birth, dict) else []
        if not cmd:
            raise FileNotFoundError("argv 是空的")
        # spec §5.3、§6：任務另立程序群組，收任務群組時 runner 才能留下來 wait 並記退出結果。
        proc = subprocess.Popen(cmd, cwd=None if held else node, env=env, stdin=subprocess.DEVNULL, stdout=out,
                                stderr=subprocess.STDOUT, process_group=0)
    except (OSError, TypeError, ValueError) as e:   # argv 有非字串、NUL：照樣寫 exit.json，不留「永遠剛起」的任務（probes/chaos B4）
        try:
            out.write(("aos7-run: 起不來: %s\n" % e).encode())
            out.close()
        except OSError:
            pass
        write_at(dfd, "exit.json", {"run": RUN[0], "code": 127, "at": now(), "round": round_at(dfd), "error": str(e)})
        return 0
    # pid.json 也經過 fd 寫：任務資料夾剛被刪（測試收尾、node 被 rm -rf）時不會用 makedirs 把它建回來
    # spec §5.4、P2-08：pid 可能重用，連同 starttime 才能辨認同一程序；讀不到由判定層保守處理。
    test_point("runner-before-pid")
    write_at(dfd, "pid.json", {"run": RUN[0], "pid": proc.pid, "pgid": proc.pid, "starttime": proc_starttime(proc.pid),
                               "runner_pid": os.getpid(), "at": now()})
    code = proc.wait()
    out.close()
    test_point("runner-before-exit")
    write_at(dfd, "exit.json", {"run": RUN[0], "code": code, "at": now(), "round": round_at(dfd)})
    return 0


def round_at(dfd):
    """由任務目錄 fd（dfd）讀 ../../round.json 的 round（exit.json 的欄位）；讀不到、壞掉或沒有 round 回 None，不猜回合。"""
    st, r = fact("../../round.json", dir_fd=dfd)
    return r.get("round") if st == OK and isinstance(r, dict) else None


def write_at(dfd, name, obj):
    """把 JSON 值 obj 原子寫入目錄 fd（dfd）下的 name；成功 True、I/O 失敗 False（spec §0、§5.3）。
    供 pid.json／exit.json 使用：先寫點開頭暫存檔再 rename，讀者不會讀到半份 JSON。
    node 搬走就寫到新位置；目錄已刪則寫入失敗，不沿舊路徑重建鬼目錄（probes/rename N8、N9，subtimeline 1）。"""
    tmp = ".%s.tmp.%d" % (name, os.getpid())
    try:
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644, dir_fd=dfd)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=1)
            f.write("\n")
        os.replace(tmp, name, src_dir_fd=dfd, dst_dir_fd=dfd)
    except OSError:
        return False
    return True
