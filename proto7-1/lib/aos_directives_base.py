"""aos 指示詞的底層型別（從 aos_directives.py 拆出）：錯誤、文件、Context、回傳用的 namedtuple、判斷指示詞物件。

純函式庫、只用標準庫。對外照舊從 aos_directives import（那裡 re-export）；解析在 aos_directives，
選項物件在 aos_directives_options。
"""
import collections
import json
import os


class DirectiveError(Exception):
    """指示詞被拒。不是程式炸了，是這份 JSON 有問題。

    `code` 是規範裡的錯誤代號（例如 `"ReferenceCycle"`），`msg` 是白話；
    `str(e)` 是「代號: 白話」。
    """

    def __init__(self, code, msg):
        super().__init__("%s: %s" % (code, msg))
        self.code = code
        self.msg = msg


class Document:
    """一份 JSON 文件：`path`（realpath；純記憶體的文件是 None）＋ `root`（解析好的 JSON，未解指示詞）。"""

    def __init__(self, path, root):
        self.path = None if path is None else os.path.realpath(path)
        self.root = root

    @property
    def ident(self):
        """循環偵測用的身分：有檔案就是 realpath，純記憶體的就用物件本身的 id。"""
        return self.path if self.path is not None else "<memory#%x>" % id(self)

    def __repr__(self):
        return "Document(%r)" % (self.ident,)


def load_document(path):
    """讀一個 JSON 檔成 `Document`。讀不到＝`ReferenceReadFailed`，不是合法 JSON＝`ReferenceJsonInvalid`。"""
    real = os.path.realpath(path)
    try:
        with open(real, encoding="utf-8") as f:
            raw = f.read()
    except OSError as e:
        raise DirectiveError("ReferenceReadFailed", "讀不到 %s：%s" % (real, e))
    try:
        root = json.loads(raw)
    except ValueError as e:
        raise DirectiveError("ReferenceJsonInvalid", "%s 不是合法 JSON：%s" % (real, e))
    return Document(real, root)


class Context:
    """解析時一路帶著的東西：

    - `doc`：目前文件（`$ref:""` 指的就是它）。
    - `base_dir`：中心路徑——`$ref` 的相對檔名從這裡起算。宿主決定（inst 是解出來的 cwd）；
      沒給就用文件所在的資料夾，純記憶體的文件則用現在的工作目錄。
    - `env`：`$env` 查的表，預設 `os.environ`。
    - 循環鏈（內部）：走過的 (文件身分, 絕對位置)。

    `Context` 本身不可變；要換文件／中心路徑用 `child()` 派生一個新的（鏈照帶）。
    """

    __slots__ = ("doc", "base_dir", "env", "_chain")

    def __init__(self, doc, base_dir=None, env=None, _chain=()):
        if base_dir is None:
            base_dir = os.path.dirname(doc.path) if doc.path is not None else os.getcwd()
        self.doc = doc
        self.base_dir = base_dir
        self.env = os.environ if env is None else env
        self._chain = tuple(_chain)

    def child(self, doc=None, base_dir=None, env=None):
        """派生一個新的 Context：沒指定的欄位照舊，循環鏈照帶。"""
        return Context(self.doc if doc is None else doc,
                       self.base_dir if base_dir is None else base_dir,
                       self.env if env is None else env,
                       self._chain)

    def _visited(self, ident):
        """鏈上再加一個身分。"""
        return Context(self.doc, self.base_dir, self.env, self._chain + (ident,))

    def __repr__(self):
        return "Context(doc=%r, base_dir=%r)" % (self.doc, self.base_dir)


# `resolve_located()` 的回傳：解出來的值、它現在所在的 Context（文件可能已經換了）、它的位置
Located = collections.namedtuple("Located", "value ctx position")

# `split_option()` 的回傳：是不是選項物件、`$opt` 的原始值、`$val`、有沒有 `$val`
Option = collections.namedtuple("Option", "is_option opt val has_val")


def is_directive(value):
    """一個 dict 只要有 `$` 開頭的 key 就是指示詞物件（含選項物件）。"""
    return isinstance(value, dict) and any(isinstance(k, str) and k.startswith("$") for k in value)


def is_option_object(value):
    """有 `$opt` key 的 dict 就是選項物件（優先順序最高，其他 `$` key 都不看）。"""
    return isinstance(value, dict) and "$opt" in value


def _show(position):
    """位置顯示成 JSON pointer 的樣子：根＝`/`，token 裡的 `~`、`/` 照 `~0`、`~1` 跳脫。"""
    return "/" + "/".join(t.replace("~", "~0").replace("/", "~1") for t in position)
