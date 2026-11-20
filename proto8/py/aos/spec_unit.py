"""spec_unit - 能編譯的東西的底 Unit（.dry_run() 只算、.compile(夾) 寫進夾）與它的命令列殼 main（--compile [FOLDER]／--dry-run／--help）。

編譯程式庫第 2 刀（線 aos-pylib-k2-1120，設計稿 thinking/2026-11/20/aos-pylib-plan-1120/02「kernel 以後怎麼接上」、07b）：
新的一種東西（defs.Agent、defs.fsm 回的 Fsm；以後的 kernel）只寫 _files(folder, warn, **選項) → {夾裡的相對檔名: 內容}。
設計稿把這兩樣排進 spec_base；第 1 刀那條線同時在用 spec_base，任務書定「spec_base 兩邊只用不改」，所以另開這一支，用 spec_base 的例外、推名字、location、寫檔後端。
只給 aos 內部用（agent_spec、agent_spec_agent）；寫 agent.py 的人不直接 import 它。
"""
import json, os, sys

from aos import flags
from aos import spec_base
from aos.spec_base import SpecBad, DefBad


class Unit:
    """能編譯的一種東西。子類只寫 _files；要改寫檔政策的覆寫 _write。LINKS＝命令列收不收 --static／--dynamic（只有 Agent）；AFTER＝--compile 寫完多印的幾行。"""
    LINKS = False
    AFTER = ()

    def events(self):
        """這個東西收哪些 hook 事件（一張事件表）；None＝不收 hook。是方法不是固定的表：同是 Agent，身體不同收的可以不同。"""
        return None

    def _files(self, folder, warn, **opts):
        raise NotImplementedError

    def _write(self, folder, files):
        spec_base.write_files(folder, files)
        return ["wrote %s" % os.path.join(folder, name) for name in files]

    def dry_run(self, folder=None, **opts):
        """算出 {檔名: 內容}，全部驗完才回，不寫。要知道夾才算得出的（不給 fsm 的 agent）沒給夾＝SpecBad。"""
        return self._files(folder, lambda msg: flags.warn("defs", msg), **opts)

    def compile(self, folder, **opts):
        """算完寫進 folder（要已經在；直接蓋），回「寫了哪些」的字串串列。夾一定要明給。"""
        if not isinstance(folder, str) or not folder:
            raise SpecBad("compile(folder): give the folder to write into, got %r" % (folder,))
        return self._write(folder, self._files(folder, lambda msg: flags.warn("defs", msg), **opts))


def main(unit, script, main_file, help_text):
    """主檔（agent.py）最後一行的命令列殼：--compile [FOLDER]、--dry-run、--help（unit.LINKS 才多收 --static／--dynamic），
    都沒有＝ArgumentsBad 帶用法（P-44）。宣告錯印一行 SpecBad、退 1、什麼都不寫。不回（sys.exit）。"""
    base, prog = os.path.basename(script), spec_base.prog_name(script, main_file)
    link_flags = ("--static", "--dynamic") if unit.LINKS else ()
    shown = " [--static | --dynamic]" if unit.LINKS else ""
    usage = "usage: python3 %s --compile%s [FOLDER] | --dry-run%s | --help" % (base, shown, shown)
    die = lambda code, msg: flags.die(prog, code, msg)  # noqa: E731
    argv = sys.argv[1:]
    if argv[:1] in (["--help"], ["-h"]):
        sys.stdout.write(help_text.replace(main_file, base))
        sys.exit(0)
    if not argv:
        die("ArgumentsBad", "give --compile or --dry-run (%s)" % usage)
    if argv[0] not in ("--compile", "--dry-run"):
        die("FlagUnknown", "%s (%s)" % (argv[0], usage))
    links = [a for a in argv[1:] if a in link_flags]
    rest = [a for a in argv[1:] if a not in link_flags]
    if len(links) > 1:
        die("ArgumentsBad", "give one of --static and --dynamic, not %s (%s)" % (" ".join(links), usage))
    unknown = [a for a in rest if a.startswith("-")]
    if unknown:
        die("FlagUnknown", "%s (%s)" % (unknown[0], usage))
    folder = spec_base.location(argv[0], rest, argv, script, usage, die)
    opts = {"link": links[0][2:] if links else "static"} if unit.LINKS else {}   # 預設靜態（使用者 11-19 選項框「預設靜態 (Recommended)」）
    try:
        out = unit._files(folder, lambda msg: flags.warn(prog, msg), **opts)
    except SpecBad as e:
        die("SpecBad", "%s (fix the declaration in %s)" % (e, base))
    except DefBad as e:
        die("DefBad", str(e))
    if argv[0] == "--dry-run":                  # 連結（defs.extern，第 4 刀）印成 {"$symlink": 目標}，其他格是內容
        shown = {k: {"$symlink": str(v)} if isinstance(v, spec_base.Link) else v for k, v in out.items()}
        print(json.dumps(shown, ensure_ascii=False, indent=2))
        sys.exit(0)
    try:
        lines = unit._write(folder, out)
    except DefBad as e:
        die("DefBad", str(e))
    except OSError as e:
        die("WriteFailed", "cannot write the definition into %s: %s" % (folder, e))
    for line in list(lines) + list(unit.AFTER):
        print(line)
    sys.exit(0)
