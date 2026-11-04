"""〔core〕防再胖：核心程式（lib/aos7_*.py）的行數預算（精簡方案第 9 節）。

量法：總行＝檔案行數；實際程式＝去掉空行、註解、docstring 之後還有 token 的行（ast 找 docstring、tokenize 找其他 token）。
不算：lib/aos_*.py（從 proto6／proto7-1 原樣搬來的 inst 執行器，方案說不算預算）、modules/（模組包）、tests/。
**2026-10-09 起只印不擋**（loop7 D7：開發階段不設行數上限，等成果整理階段再重構拆檔濃縮）：超過預算時把逐檔表印到
stderr，測試照樣過。整理階段要恢復擋線時，把 ENFORCE 改回 True。
"""
import os, sys  # noqa: E401
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # tests/：base
import ast  # noqa: E402
import glob  # noqa: E402
import io  # noqa: E402
import tokenize  # noqa: E402
import unittest  # noqa: E402

from base import LIB  # noqa: E402

TOTAL_MAX = 2800   # 總行
CODE_MAX = 2200    # 實際程式（之後收到 2000）
ENFORCE = False    # D7：開發階段只印不擋


def count(path):
    """回 (總行, 實際程式行)。"""
    src = open(path, encoding="utf-8").read()
    doc = set()
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.body:
            b = n.body[0]
            if isinstance(b, ast.Expr) and isinstance(b.value, ast.Constant) and isinstance(b.value.value, str):
                doc.update(range(b.lineno, b.end_lineno + 1))
    code = set()
    skip = (tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT, tokenize.ENDMARKER)
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type not in skip:
            code.update(l for l in range(tok.start[0], tok.end[0] + 1) if l not in doc)
    return len(src.splitlines()), len(code)


class TestBudget(unittest.TestCase):
    """〔core〕核心行數預算：總行 2800、實際程式 2200；目前只印不擋（D7）。"""
    def test_core_line_budget(self):
        rows = {os.path.basename(p): count(p) for p in sorted(glob.glob(os.path.join(LIB, "aos7_*.py")))}
        total, code = sum(t for t, _ in rows.values()), sum(c for _, c in rows.values())
        table = "\n".join("  %-26s 總行 %4d  實際程式 %4d" % (n, t, c) for n, (t, c) in rows.items())
        msg = ("核心超過行數預算（總行 %d／%d、實際程式 %d／%d）：\n%s\n新功能預設進模組（proto7-2/README.md「進核心的三問」）；"
               "真要加預算，先在 notes/problems.md 寫理由、經使用者同意再改 tests/core/test_budget.py。"
               % (total, TOTAL_MAX, code, CODE_MAX, table))
        self.assertTrue(rows, "找不到 lib/aos7_*.py")
        if not ENFORCE:
            if total > TOTAL_MAX or code > CODE_MAX:
                sys.stderr.write("\n［只印不擋，D7］" + msg + "\n")
            return
        self.assertLessEqual(total, TOTAL_MAX, msg)
        self.assertLessEqual(code, CODE_MAX, msg)


if __name__ == "__main__":
    unittest.main()
