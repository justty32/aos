"""模型與端點保存。"""
import test_up as cases


class UpModel(cases.UpTests):
    def test_model(self):
        url = 'http://localhost:4567/v1'
        self.invoke(self.node, '--model', 'chatgpt-gpt-6-luna', '-d', AOS7_LITELLM_URL=url)
        self.assertEqual(self.data('budget/llm/grant.json')['gateway'], 'llm.litellm')
        self.assertEqual(self.data('.aos/up.json')['litellm_url'], url)
        self.assertEqual(self.data('.aos/up.json')['model'], 'chatgpt-gpt-6-luna')
        self.invoke(self.node, '-d')
        self.assertEqual(self.data('.aos/up.json')['model'], 'chatgpt-gpt-6-luna')
        self.assertEqual(self.data('.aos/up.json')['litellm_url'], url)

    def test_reject_gateway_change_before_mutation(self):
        self.invoke(self.node, '-d')
        paths = ['budget/llm/grant.json', '.aos/up.json', '.aos/tasks.json', 'AGENTS.md']
        before = [(self.node / p).read_bytes() for p in paths]
        self.invoke(self.node, '--model', 'chatgpt-gpt-6-luna', '-d', rc=2)
        self.assertEqual(before, [(self.node / p).read_bytes() for p in paths])

    def test_ask_through_up(self):
        # 藍圖 S2：經 aos7-up 起的 node，ask 假 AI 一圈拿到回信；status 記到一次 AI
        self.invoke(self.node, '-d')
        out = self.invoke('ask', self.node, '用一句話介紹你自己', '--wait', '30')
        self.assertIn('回信', out)
        lines = self.invoke('status', self.node).splitlines()
        self.assertIn('問過 1 次', lines[4])
        self.assertIn('收到 1 封要辦的信，辦完 1 封', lines[1])


# Only the model cases belong to this subclass.
    test_idempotent = None
    test_sigkill_reconnect = None
    test_foreground_interrupt = None
    test_status_and_stop = None
    test_invalid_and_missing = None
