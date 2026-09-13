#!/usr/bin/env python3
"""aos-kernel add：檢查並正規化一份 inst.json，再原子排進 kernel 佇列。"""
import argparse
import json
import os
import sys

from aos_kernel import KHome


def _fail(msg):
    sys.stderr.write("aos-kernel add: %s\n" % msg)
    return 1


def _names_in(path):
    try:
        names = os.listdir(path)
    except OSError:
        return set()
    return {n[:-5] for n in names
            if n.endswith(".json") and os.path.isfile(os.path.join(path, n))}


def _used_names(h):
    names = _names_in(h.procs) | _names_in(h.bad) | _names_in(h.done)
    st = h.state()
    names.update(q for q in st["queue"] if isinstance(q, str))
    names.update(c.get("pid") for c in st["cpus"].values()
                 if isinstance(c, dict) and isinstance(c.get("pid"), str))
    return names


def cmd_add(argv):
    ap = argparse.ArgumentParser(prog="aos-kernel add", add_help=True)
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--name")
    try:
        a = ap.parse_args(argv)
    except SystemExit:
        return 2
    if len(a.paths) not in (1, 2):
        sys.stderr.write("用法：aos-kernel add [K] INST.json [--name NAME]\n")
        return 2

    called_from = os.getcwd()
    if len(a.paths) == 1:
        kernel_dir, inst_arg = called_from, a.paths[0]
    else:
        kernel_dir, inst_arg = a.paths
        kernel_dir = os.path.abspath(os.path.join(called_from, kernel_dir))
    inst_path = os.path.abspath(os.path.join(called_from, inst_arg))
    if len(a.paths) == 2:
        try:
            os.chdir(kernel_dir)
        except OSError as e:
            sys.stderr.write("aos-kernel: 進不去 kernel 的家：%s（%s）\n"
                             % (a.paths[0], e))
            return 1
    h = KHome(kernel_dir)
    if h.config() is None:
        sys.stderr.write("aos-kernel: 這裡不是 kernel 的家（沒有 config.json）：%s\n" % h.dir)
        return 1

    try:
        with open(inst_path, encoding="utf-8") as f:
            inst = json.load(f)
    except (OSError, ValueError) as e:
        return _fail("讀不到 inst.json：%s（%s）" % (inst_path, e))
    if not isinstance(inst, dict):
        return _fail("inst.json 不是 JSON 物件：%s" % inst_path)

    base = os.path.dirname(inst_path)
    cwd = inst.get("cwd", base)
    if not isinstance(cwd, str):
        return _fail("cwd 不是字串")
    if not os.path.isabs(cwd):
        cwd = os.path.abspath(os.path.join(base, cwd))
    inst["cwd"] = cwd
    if not os.path.isdir(cwd):
        return _fail("cwd 不是資料夾：%s" % cwd)

    argv_value = inst.get("argv")
    if not isinstance(argv_value, list) or not argv_value or not isinstance(argv_value[0], str):
        return _fail("argv 缺了、是空的，或 argv[0] 不是字串")
    argv0 = argv_value[0]
    if "/" in argv0 and not os.path.isabs(argv0):
        argv0 = os.path.abspath(os.path.join(cwd, argv0))
        argv_value[0] = argv0
    if "/" in argv0 and not os.path.exists(argv0):
        return _fail("argv[0] 指的檔不存在：%s" % argv0)

    used = _used_names(h)
    if a.name is not None:
        name = a.name
        if not name or "/" in name:
            return _fail("--name 不能是空字串，也不能含 /")
        if name in used:
            return _fail("名字已經存在或正在 cpu 上：%s" % name)
    else:
        nums = [int(name) for name in used if name.isdigit()]
        name = str((max(nums) if nums else 0) + 1)

    if "stderr" not in inst:
        sys.stderr.write('這份 inst.json 沒寫 stderr，出錯會看不到；建議加 "stderr":"err.txt"\n')
    dst = h.proc(name)
    tmp = os.path.join(h.procs, ".%s.json.tmp" % name)
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(inst, f, ensure_ascii=False, indent=1)
        os.replace(tmp, dst)
    except OSError as e:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        return _fail("排不進佇列：%s" % e)
    print("排進去了：%s  cwd=%s  argv=%s"
          % (dst, cwd, json.dumps(argv_value, ensure_ascii=False)))
    return 0
