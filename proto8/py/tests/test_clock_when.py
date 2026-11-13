"""Test aos_clock_when: at parsing (HH:MM, ISO, +N), 5-field cron parsing and next time, the late text (no files, no clock)."""
import datetime
import os
import sys
import unittest

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), ".."))
import aos_clock_when as w  # noqa: E402


def local(*a):
    return datetime.datetime(*a).astimezone()


class At(unittest.TestCase):
    base = local(2026, 11, 13, 21, 0, 0)

    def test_relative(self):
        self.assertEqual(w.parse_at("+10m", self.base), local(2026, 11, 13, 21, 10))
        self.assertEqual(w.parse_at("+2h", self.base), local(2026, 11, 13, 23, 0))
        self.assertEqual(w.parse_at("+1d", self.base), local(2026, 11, 14, 21, 0))
        self.assertEqual(w.parse_at("+30s", self.base), local(2026, 11, 13, 21, 0, 30))

    def test_hhmm_today_or_tomorrow(self):
        self.assertEqual(w.parse_at("21:30", self.base), local(2026, 11, 13, 21, 30))
        self.assertEqual(w.parse_at("09:00", self.base), local(2026, 11, 14, 9, 0))
        self.assertEqual(w.parse_at("21:00", self.base), local(2026, 11, 14, 21, 0))   # 正好現在＝明天

    def test_iso(self):
        self.assertEqual(w.parse_at("2026-11-14 09:00", self.base), local(2026, 11, 14, 9, 0))
        self.assertEqual(w.parse_at("2026-11-14T09:00:05", self.base), local(2026, 11, 14, 9, 0, 5))
        t = w.parse_at("2026-11-14T01:00:00+00:00", self.base)
        self.assertEqual(t, datetime.datetime(2026, 11, 14, 1, 0, tzinfo=datetime.timezone.utc))

    def test_bad(self):
        for bad in ("", "soon", "25:00", "12:60", "+0m", "+5w", "2026-11-12 09:00", 5):
            with self.assertRaises(ValueError, msg=repr(bad)):
                w.parse_at(bad, self.base)
        with self.assertRaisesRegex(ValueError, "in the past"):
            w.parse_at("2026-11-12 09:00", self.base)


class Cron(unittest.TestCase):
    def test_next(self):
        fri = local(2026, 11, 13, 21, 7)                       # 2026-11-13 is a Friday
        self.assertEqual(w.cron_next("*/15 * * * *", fri), local(2026, 11, 13, 21, 15))
        self.assertEqual(w.cron_next("0 9 * * 1", fri), local(2026, 11, 16, 9, 0))
        self.assertEqual(w.cron_next("0 9 * * 7", fri), local(2026, 11, 15, 9, 0))      # 7 = Sunday
        self.assertEqual(w.cron_next("30 21 * * *", fri), local(2026, 11, 13, 21, 30))
        self.assertEqual(w.cron_next("0 21 * * *", fri), local(2026, 11, 14, 21, 0))     # 21:00 today already past
        self.assertEqual(w.cron_next("0 0 1 1 *", fri), local(2027, 1, 1, 0, 0))
        self.assertEqual(w.cron_next("0 12 1 * 1", fri), local(2026, 11, 16, 12, 0))    # day and weekday both set = either
        self.assertEqual(w.cron_next("5-10/5 8 * * 1-5", fri), local(2026, 11, 16, 8, 5))
        self.assertEqual(w.cron_next("0 0 29 2 *", fri), local(2028, 2, 29, 0, 0))

    def test_strictly_after(self):
        t = local(2026, 11, 13, 21, 15)
        self.assertEqual(w.cron_next("*/15 * * * *", t), local(2026, 11, 13, 21, 30))

    def test_bad(self):
        for bad in ("* * * *", "60 * * * *", "* 24 * * *", "* * 0 * *", "* * * 13 *", "* * * * 8", "a * * * *",
                    "*/0 * * * *", "5-1 * * * *", None):
            with self.assertRaises(ValueError, msg=repr(bad)):
                w.parse_cron(bad)
        with self.assertRaisesRegex(ValueError, "never fires"):
            w.cron_next("0 0 30 2 *", local(2026, 11, 13))


class Late(unittest.TestCase):
    def test_late(self):
        due = local(2026, 11, 13, 9, 0)
        self.assertEqual(w.late(due, due + datetime.timedelta(seconds=59)), "")
        self.assertEqual(w.late(due, due + datetime.timedelta(minutes=5)), "late by 5m")
        self.assertEqual(w.late(due, due + datetime.timedelta(hours=2, minutes=5)), "late by 2h 5m")
        self.assertEqual(w.late(due, due + datetime.timedelta(days=1, hours=1)), "late by 1d 1h")
        self.assertEqual(w.show(local(2026, 11, 13, 9, 0)), "2026-11-13 09:00")


if __name__ == "__main__":
    unittest.main()
