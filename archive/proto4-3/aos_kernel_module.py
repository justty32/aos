"""從 kernel config 載入單檔 module，並隔離 module 的載入／tick 錯誤。"""
import hashlib
import importlib.util
import os
import sys


class LoadedModules(list):
    """仍是一份 list；`notes` 帶回不致命的載入錯誤。"""

    def __init__(self):
        super().__init__()
        self.notes = []


def load_modules(cfg):
    loaded = LoadedModules()
    for raw_path in cfg.get("modules", []):
        path = os.path.abspath(raw_path)
        label = os.path.basename(path) or path
        try:
            key = hashlib.sha256(path.encode()).hexdigest()[:16]
            spec = importlib.util.spec_from_file_location("aos_kernel_module_" + key, path)
            if spec is None or spec.loader is None:
                raise ImportError("無法建立 Python module spec")
            module = importlib.util.module_from_spec(spec)
            module_dir = os.path.dirname(path)
            sys.modules[spec.name] = module
            sys.path.insert(0, module_dir)
            try:
                spec.loader.exec_module(module)
            except BaseException:
                sys.modules.pop(spec.name, None)
                raise
            finally:
                sys.path.pop(0)
            if not isinstance(getattr(module, "NAME", None), str) or not module.NAME:
                raise ValueError("缺少非空字串 NAME")
            ops = getattr(module, "OPS", None)
            if (not isinstance(ops, tuple)
                    or any(not isinstance(op, str) or not op for op in ops)):
                raise ValueError("缺少字串 tuple OPS")
            for hook in ("handle", "tick", "status", "cli"):
                value = getattr(module, hook, None)
                if value is not None and not callable(value):
                    raise ValueError("%s 不是函式" % hook)
            loaded.append(module)
        except BaseException as exc:
            loaded.notes.append("module %s 載入失敗：%s" % (label, _one_line(exc)))
    return loaded


def run_modules(h, cfg, st, modules, notes):
    for module in modules:
        hook = getattr(module, "tick", None)
        if hook is None:
            continue
        try:
            got = hook(h, cfg, st)
            if isinstance(got, list):
                notes.extend(str(note).replace("\n", " ") for note in got)
        except BaseException as exc:
            notes.append("module %s 壞了：%s" % (module.NAME, _one_line(exc)))


def _one_line(exc):
    return str(exc).replace("\n", " ") or type(exc).__name__
