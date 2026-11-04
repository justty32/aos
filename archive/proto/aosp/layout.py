"""一塊地的版面。路徑名字全部照 WRITER-BRIEF 4.1，一字不改。"""
import os

from . import fsutil

AOS_DIR = ".aos"


def home():
    """家：$AOS_HOME，預設 ~。"""
    return os.path.abspath(os.environ.get("AOS_HOME") or os.path.expanduser("~"))


class Land:
    """一塊地。path 就是身分（裁決 2026-09-04）。"""

    def __init__(self, root):
        self.root = os.path.abspath(root)

    # --- 基本 ---
    @property
    def aos(self):
        return os.path.join(self.root, AOS_DIR)

    def rel(self, *parts):
        return os.path.join(self.aos, *parts)

    def resolve(self, path):
        """路徑欄：相對路徑以這塊地的根為基準；也可以是絕對路徑（WRITER-BRIEF 3）。"""
        if os.path.isabs(path):
            return path
        return os.path.join(self.root, path)

    def is_land(self):
        return os.path.isfile(self.layout)

    # --- 靜態設定（進 git）---
    @property
    def layout(self):
        return self.rel("layout.json")

    @property
    def config(self):
        return self.rel("config.json")

    @property
    def contacts(self):
        return self.rel("contacts.json")

    def tool(self, name):
        return self.rel("tools", "%s.json" % name)

    @property
    def tools_dir(self):
        return self.rel("tools")

    # --- 原稿與模板 ---
    def source(self, name="main"):
        return os.path.join(self.root, "%s.aos.json" % name)

    def program(self, name):
        return self.rel("program", "%s.json" % name)

    @property
    def program_dir(self):
        return self.rel("program")

    # --- 執行期 ---
    @property
    def series(self):
        return self.rel("series.json")

    @property
    def lock(self):
        return self.rel("lock")

    @property
    def stopped(self):
        return self.rel("stopped.json")

    @property
    def inbox(self):
        return self.rel("inbox")

    @property
    def inbox_rejected(self):
        return self.rel("inbox", "rejected")

    @property
    def control(self):
        return self.rel("control")

    @property
    def mail(self):
        return self.rel("mail")

    @property
    def calls_dir(self):
        return self.rel("calls")

    def call(self, call_id):
        return self.rel("calls", "%s.json" % call_id)

    def tick_dir(self, n):
        return self.rel("ticks", str(n))

    def inst_file(self, n, inst_id):
        return self.rel("ticks", str(n), "insts", "%s.json" % inst_id)

    def result_file(self, n, inst_id):
        return self.rel("ticks", str(n), "results", "%s.json" % inst_id)

    def result_stdout(self, n, inst_id):
        return self.rel("ticks", str(n), "results", "%s.stdout" % inst_id)

    def result_stderr(self, n, inst_id):
        return self.rel("ticks", str(n), "results", "%s.stderr" % inst_id)

    def tick_tmp(self, n, inst_id):
        return self.rel("ticks", str(n), "tmp", inst_id)

    def frame(self, series_id):
        return self.rel("frames", series_id)

    # --- 設定讀取 ---
    def load_config(self):
        return fsutil.read_json(self.config, {}) or {}

    def inbox_max(self):
        return int(self.load_config().get("inbox_max", 1000))


class Home(Land):
    """家的 .aos/：登記表、使用者層設定、帳簿、daemon.pid、llm/。"""

    def __init__(self, root=None):
        Land.__init__(self, root or home())

    @property
    def registry(self):
        return self.rel("registry.json")

    @property
    def registry_lock(self):
        return self.rel("registry.lock")

    @property
    def ledger(self):
        return self.rel("ledger.jsonl")

    @property
    def daemon_pid(self):
        return self.rel("daemon.pid")

    @property
    def llm_world(self):
        cfg = self.load_config()
        p = cfg.get("llm_world")
        if p:
            return os.path.abspath(p)
        return self.rel("llm")


def init(root, force=False):
    """aos init <地>：建 .aos/layout.json 與 config.json。"""
    land = Land(root)
    fsutil.ensure_dir(land.root)
    fsutil.ensure_dir(land.aos)
    if land.is_land() and not force:
        return land, False
    fsutil.write_json(land.layout, {"format_version": 1, "layout_version": 1})
    if not os.path.exists(land.config):
        fsutil.write_json(land.config, {
            "format_version": 1,
            "path": [],
            "max_parallel": 4,
            "inst_timeout_ms": 60000,
            "inbox_max": 1000,
        })
    for d in (land.inbox, land.inbox_rejected, land.control, land.mail,
              land.program_dir, land.calls_dir, land.tools_dir):
        fsutil.ensure_dir(d)
    return land, True
