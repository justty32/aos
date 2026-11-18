# 問腦的格數：總格、high 保留格、包格、後端格與同時幾種包，在飛與這輪新掛的一起算。
import budget


class Slots:
    def __init__(self, cfg, stack):
        self.cfg, self.stack = cfg, stack
        self.busy = 0            # 上一輪留下、還在飛的
        self.started = 0         # 這一輪新掛的
        self.packs = {}          # 代號 → 在飛＋新掛
        self.senders = {}        # 寄件人（相對 stack 的 key）→ 在飛＋新掛
        self.backends = {}       # 後端 → 在飛＋新掛
        self.backend_packs = {}  # 後端 → 正在用的代號
        self.stopped = False     # 總格滿了或總額到頂要等：這輪後面的信都不再看

    def _count(self, endpoint, backend, sender):
        self.packs[endpoint] = self.packs.get(endpoint, 0) + 1
        if backend is not None:
            self.backends[backend] = self.backends.get(backend, 0) + 1
            self.backend_packs.setdefault(backend, set()).add(endpoint)
        if sender:
            key = budget.sender_key(sender, self.stack)
            self.senders[key] = self.senders.get(key, 0) + 1

    def flying(self, proc):
        """收成品時還在飛的一封，照 proc.json 記的代號、後端、寄件人算進去。"""
        self.busy += 1
        endpoint = proc.get("endpoint")
        sender = proc.get("sender") if isinstance(proc.get("sender"), str) else ""
        if isinstance(endpoint, str):
            backend = proc.get("backend")
            if not isinstance(backend, str):
                pack = self.cfg["packs"].get(endpoint, {})
                backend = pack.get("backend")
            self._count(endpoint, backend, sender)
        elif sender:
            key = budget.sender_key(sender, self.stack)
            self.senders[key] = self.senders.get(key, 0) + 1

    def mounted(self, waiting):
        """這一輪新掛上一封。"""
        self.started += 1
        self._count(waiting["endpoint"], waiting["pack"]["backend"], waiting["sender"])

    def total(self):
        return self.busy + self.started

    def room(self, waiting):
        """這封現在有沒有格（總格與總額另外看）：包格、後端格、後端同時幾種包。"""
        pack, endpoint = waiting["pack"], waiting["endpoint"]
        if pack["slots"] is not None and self.packs.get(endpoint, 0) >= pack["slots"]:
            return False
        if pack["backend"] is not None:
            limits = self.cfg["backends"][pack["backend"]]
            using = self.backend_packs.get(pack["backend"], set())
            if self.backends.get(pack["backend"], 0) >= limits["slots"]:
                return False
            if limits["max_packs"] is not None and endpoint not in using and len(using) >= limits["max_packs"]:
                return False
        return True
