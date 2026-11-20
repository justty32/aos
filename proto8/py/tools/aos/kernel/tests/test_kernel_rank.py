# 驗證骨架的「誰先」一步（round.ordered）：包的 order 整個接手、row／rank 兩個口、驗不過的排最前、都沒有時照信名。
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest


KERNEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KERNEL.parents[2]))
sys.path.insert(0, str(KERNEL))
import round  # noqa: E402


INCOMING = {"b": {"body": {"n": 2}}, "a": {"body": {"n": 3}}, "c": {"body": "bad"}, "d": {"body": {"n": 1}}}


class OrderedTest(unittest.TestCase):
    def test_pack_order_takes_over(self):
        pack = SimpleNamespace(order=lambda ctx, incoming: ["d", "c"],
                               rank=lambda ctx, rows: self.fail("rank must not run when order exists"))
        self.assertEqual(round.ordered(pack, SimpleNamespace(), INCOMING), ["d", "c"])

    def test_no_ports_sorts_by_letter_name(self):
        self.assertEqual(round.ordered(SimpleNamespace(), SimpleNamespace(), INCOMING), ["a", "b", "c", "d"])

    def test_bad_rows_first_then_rank(self):
        seen = {}

        def row(ctx, name, letter):
            body = letter["body"]
            return {"id": name, "n": body["n"]} if isinstance(body, dict) else None

        def rank(ctx, rows):
            seen["ids"] = [r["id"] for r in rows]       # rank 拿到的列照信名先後、不含驗不過的
            seen["ctx"] = ctx
            return sorted(rows, key=lambda r: r["n"])

        ctx = SimpleNamespace(tag="kernel state")
        self.assertEqual(round.ordered(SimpleNamespace(row=row, rank=rank), ctx, INCOMING), ["c", "d", "b", "a"])
        self.assertEqual(seen["ids"], ["a", "b", "d"])
        self.assertIs(seen["ctx"], ctx)                  # 規則讀得到 kernel 自己的狀態

    def test_rank_without_row_gets_letters(self):
        def rank(ctx, rows):
            return sorted(rows, key=lambda r: str(r["letter"]["body"]))
        self.assertEqual(round.ordered(SimpleNamespace(rank=rank), SimpleNamespace(), INCOMING),
                         ["c", "d", "b", "a"])


if __name__ == "__main__":
    unittest.main()
