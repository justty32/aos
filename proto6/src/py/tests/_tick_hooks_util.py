"""aos-tick hooks 系列測試共用：HooksCase 基底（寫 tasks.json 的 put()／hooks()）。"""
import json

from _tick_util import TickCase, sh


class HooksCase(TickCase):

    def put(self, doc):
        self.write(".aos/tasks.json", json.dumps(doc, ensure_ascii=False))

    def hooks(self, after_all, tasks=None, **top):
        doc = dict(top, tasks=tasks if tasks is not None else [sh("a", "echo task >> h.log")],
                   hooks={"after_all": after_all})
        self.put(doc)
