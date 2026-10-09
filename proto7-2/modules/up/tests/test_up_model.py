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


# Only the model cases belong to this subclass.
    test_idempotent = None
    test_sigkill_reconnect = None
    test_foreground_interrupt = None
    test_status_and_stop = None
    test_invalid_and_missing = None
