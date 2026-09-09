"""envs：疊加、$opt clear（有／沒 $envs）、清空之後 PATH 怎麼找 argv[0]、$env 指示詞。"""
import os
import unittest

from _util import ExecCase

OUTER = dict(os.environ, AOSTEST_OUTER="外面來的")


class TestEnv(ExecCase):

    def test_envs_is_overlaid_on_aos_exec_env(self):
        """預設是疊加：aos-exec 自己的環境全留著，inst 裡的只加不減。"""
        self.inst({"argv": ["sh", "-c", "echo \"[$AOSTEST_OUTER][$ADDED]\""],
                   "envs": {"ADDED": "加上去的"}, "stdout": "out.txt"})
        self.assertEqual(self.aos(self.d, env=OUTER).returncode, 0)
        self.assertEqual(self.read("out.txt"), "[外面來的][加上去的]\n")

    def test_envs_overwrites_inherited(self):
        self.inst({"argv": ["sh", "-c", "echo $AOSTEST_OUTER"],
                   "envs": {"AOSTEST_OUTER": "蓋掉"}, "stdout": "out.txt"})
        self.assertEqual(self.aos(self.d, env=OUTER).returncode, 0)
        self.assertEqual(self.read("out.txt"), "蓋掉\n")

    def test_clear_with_envs(self):
        """{"$opt":"clear","$envs":{…}}＝從空環境開始，只放 $envs 裡的。"""
        self.inst({"argv": ["sh", "-c", "echo \"[$AOSTEST_OUTER][$ONLY]\""],
                   "envs": {"$opt": "clear", "$envs": {"ONLY": "只有我"}},
                   "stdout": "out.txt"})
        self.assertEqual(self.aos(self.d, env=OUTER).returncode, 0)
        self.assertEqual(self.read("out.txt"), "[][只有我]\n")

    def test_clear_without_envs(self):
        """$envs 可省＝完全空的環境。"""
        self.inst({"argv": ["sh", "-c", "echo \"[$AOSTEST_OUTER]\""],
                   "envs": {"$opt": "clear"}, "stdout": "out.txt"})
        self.assertEqual(self.aos(self.d, env=OUTER).returncode, 0)
        self.assertEqual(self.read("out.txt"), "[]\n")

    def test_clear_still_finds_sh_via_defpath(self):
        """清空之後沒有 PATH 了，argv[0] 退回 os.defpath 還是找得到 sh。"""
        self.assertIn("/bin", os.defpath)
        self.inst({"argv": ["sh", "-c", "echo 找得到"], "envs": {"$opt": "clear"},
                   "stdout": "out.txt"})
        self.assertEqual(self.aos(self.d, env=OUTER).returncode, 0)
        self.assertEqual(self.read("out.txt"), "找得到\n")

    def test_argv0_uses_the_overlaid_path(self):
        """argv[0] 走的是**疊加後**的 PATH：故意指到空的地方就 127。"""
        self.inst({"argv": ["sh", "-c", "true"],
                   "envs": {"$opt": "clear", "$envs": {"PATH": os.path.join(self.d, "空")}}})
        self.assertEqual(self.aos(self.d, env=OUTER).returncode, 127)

    def test_envs_value_can_be_dollar_env_directive(self):
        self.inst({"argv": ["sh", "-c", "echo $COPIED"],
                   "envs": {"COPIED": {"$env": "AOSTEST_OUTER"}}, "stdout": "out.txt"})
        self.assertEqual(self.aos(self.d, env=OUTER).returncode, 0)
        self.assertEqual(self.read("out.txt"), "外面來的\n")

    def test_envs_value_can_be_dollar_env(self):
        self.inst({"argv": ["sh", "-c", "echo $COPIED"], "stdout": "out.txt",
                   "envs": {"$opt": "clear",
                           "$envs": {"COPIED": {"$env": "AOSTEST_OUTER"}}}})
        self.assertEqual(self.aos(self.d, env=OUTER).returncode, 0)
        self.assertEqual(self.read("out.txt"), "外面來的\n")

    def test_dollar_env_missing_variable_is_125(self):
        self.inst({"argv": ["sh", "-c", "true"], "envs": {"X": {"$env": "AOSTEST_NOPE"}}})
        r = self.aos(self.d, env=OUTER)
        self.assertEqual(r.returncode, 125)
        self.assertIn("EnvironmentVariableMissing", r.stderr)

    def test_dollar_env_empty_string_is_ok(self):
        """存在但空＝空字串，跟不存在是兩件事。"""
        env = dict(OUTER, AOSTEST_EMPTY="")
        self.inst({"argv": ["sh", "-c", "echo \"[$X]\""],
                   "envs": {"X": {"$env": "AOSTEST_EMPTY"}}, "stdout": "out.txt"})
        self.assertEqual(self.aos(self.d, env=env).returncode, 0)
        self.assertEqual(self.read("out.txt"), "[]\n")

    def test_no_aos_star_variables_are_injected(self):
        """aos-exec 不塞 AOS_DIR／AOS_TICK 之類的東西。"""
        self.inst({"argv": ["sh", "-c", "env | grep '^AOS_' | wc -l"], "stdout": "out.txt"})
        self.assertEqual(self.aos(self.d, env=OUTER).returncode, 0)
        self.assertEqual(self.read("out.txt").strip(), "0")


if __name__ == "__main__":
    unittest.main()
