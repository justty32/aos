"""protocol §1～§3：daemon 收的單（scale、kill、ls）怎麼驗、怎麼判；stop／ack 走 aos_home.scan_controls。

一律同步：做完才回。scale 只改宣告、標這池「要對帳」，實際拉、收是之後迴圈的事。
"""
import os
import time

import aos_daemon_pools as pools
import aos_home
from aos_exec_run import DEFAULT_DIR_TARGET


class DaemonError(aos_home.HomeError):
    def __init__(self, code, msg, rpc_code=-32000, position=None):
        super().__init__(code, msg)
        self.rpc_code, self.position = rpc_code, position


def _bad(key, msg):
    raise DaemonError("FieldTypeMismatch", msg, -32602, ["params", key])


def _template(params, key):
    value = params[key]
    if (not isinstance(value, str) or "\0" in value or not os.path.isabs(value) or
            value.count("{name}") != 1):
        _bad(key, "%s 必須是絕對路徑樣板，恰好含一個 {name}" % key)
    return value


def is_int(value, minimum=0):
    return type(value) is int and value >= minimum


def check_scale(params):
    """protocol §1 第 1 步：形狀不合＝-32602。回整理過的 params（skip 排好序）。"""
    if not isinstance(params, dict):
        raise DaemonError("FieldTypeMismatch", "params 必須是物件", -32602, ["params"])
    if not pools.valid_pool_name(params.get("pool")):
        _bad("pool", "pool 必須是 1～64 bytes、只用 A-Z a-z 0-9 _ . - 的名字")
    owner = params.get("owner")
    if not isinstance(owner, str) or not owner or "\0" in owner:
        _bad("owner", "owner 必須是非空字串")
    count = params.get("count")
    if not is_int(count) or count > pools.MAX_COUNT:
        _bad("count", "count 必須是 0～%d 的整數" % pools.MAX_COUNT)
    skip = params.get("skip", [])
    if not isinstance(skip, list) or not all(is_int(x) for x in skip) or len(set(skip)) != len(skip):
        _bad("skip", "skip 必須是不重複的非負整數陣列")
    out = {"pool": params["pool"], "owner": owner, "count": count, "skip": sorted(skip)}
    for key in ("target", "home"):
        if key in params:
            out[key] = _template(params, key)
    if "dir_target" in params:
        if not isinstance(params["dir_target"], str) or "\0" in params["dir_target"]:
            _bad("dir_target", "dir_target 必須是字串")
        out["dir_target"] = params["dir_target"]
    if "decl" in params:
        decl = params["decl"]
        if not isinstance(decl, list) or len(decl) != 2 or not all(is_int(x) for x in decl):
            _bad("decl", "decl 必須是兩個非負整數的陣列")
        out["decl"] = list(decl)
    return out


def check_name(value):
    return isinstance(value, str) and bool(pools.NAME_RE.fullmatch(value))


def is_busy(home):
    """偷看那顆 cpu 家的 state.json 有沒有 current（daemon-cli ls 的 busy）。"""
    if home is None:
        return None
    try:
        state = aos_home.read_json(os.path.join(home, "state.json"))
    except aos_home.HomeError:
        return False
    return isinstance(state, dict) and state.get("current") is not None


class Requests:
    """Daemon 的收單那一半（混進 aos_daemon_loop.Daemon）。"""

    def process_request(self, name):
        path = self.home / "requests" / name
        env = aos_home.read_request(path)
        self.state["current"] = {"name": name, "id": env.id, "notify": env.notify}
        self.save()
        response = env.error
        if response is None:
            try:
                handler = {"scale": self.scale, "kill": self.kill, "ls": self.ls}.get(env.method)
                if handler is None:
                    raise DaemonError("MethodNotFound", "不認得 method：%s" % env.method, -32601)
                response = aos_home.result_response(env.id, handler(env.params))
            except DaemonError as exc:
                data = None if exc.rpc_code == -32601 else {"code": exc.code}
                if exc.position is not None:
                    data["position"] = exc.position
                response = aos_home.error_response(env.id, exc.rpc_code, exc.msg, data)
        if not env.notify:
            aos_home.write_json(self.home / "responses" / name, response)
        path.unlink()
        self.state["current"] = None
        self.save()

    # ---- scale（protocol §1 的七步）----

    def scale(self, params):
        p = check_scale(params)                                        # 1
        if self.state["stopping"]:                                     # 2
            raise DaemonError("Stopping", "daemon 正在停機")
        name, pool = p["pool"], self.pools.get(p["pool"])
        old = pool.decl if pool is not None else None
        if old is not None and old["owner"] != p["owner"]:             # 3
            raise DaemonError("NameTaken", "池 %s 已是 %s 的" % (name, old["owner"]))
        if (old is not None and "decl" in p and old.get("decl") is not None and
                p["decl"] < old["decl"]):                              # 4
            raise DaemonError("Stale", "宣告序號 %s 比現有的 %s 舊，不改" % (p["decl"], old["decl"]))
        if old is None and p["count"] == 0:                            # 5
            return {"pool": name, "count": 0, "ver": 0}
        if old is None and "target" not in p:
            _bad("target", "池不在時 target 必填")
        total = self.declared() - (old["count"] if old else 0) + p["count"]
        if total > self.budget:                                        # 6
            raise DaemonError("TooMany", "全 daemon 宣告 %d 顆，超過上限 %d" % (total, self.budget))
        decl = dict(old) if old is not None else {
            "pool": name, "owner": p["owner"], "ver": 0, "dir_target": DEFAULT_DIR_TARGET}
        decl.update({k: v for k, v in p.items() if k != "owner"})
        changed = old is None or (
            pools.members(old["count"], old["skip"]) != pools.members(p["count"], p["skip"]))
        decl["ver"] = decl["ver"] + 1 if changed else decl["ver"]
        if decl != old:
            try:                                                       # 7
                pools.write_pool_json(self.home, decl)
            except aos_home.HomeError as exc:
                raise DaemonError(exc.code, exc.msg) from exc
        if pool is None:
            pool = self.pools[name] = self.new_pool(decl)
        retarget = old is not None and (old.get("target"), old.get("dir_target")) != \
            (decl.get("target"), decl.get("dir_target"))
        pool.decl, pool.changed = decl, True
        pool.dirty = pool.dirty or changed
        if retarget:                                                   # 換 target：failed 的馬上可以再試
            now = time.monotonic()
            for kid in pool.kids.values():
                if kid.state == "failed":
                    kid.due = now
                    self.enqueue(pool, kid)
        return {"pool": name, "count": decl["count"], "ver": decl["ver"]}

    # ---- kill（protocol §2）----

    def kill(self, params):
        if not isinstance(params, dict):
            raise DaemonError("FieldTypeMismatch", "params 必須是物件", -32602, ["params"])
        if not pools.valid_pool_name(params.get("pool")):
            _bad("pool", "pool 必須是合法的池名")
        names, every = params.get("names"), params.get("all", False)
        if type(every) is not bool:
            _bad("all", "all 必須是布林")
        if (names is None) == (not every):
            _bad("names", "names 與 all:true 恰好給一個")
        if names is not None and (not isinstance(names, list) or not all(map(check_name, names))):
            _bad("names", "names 必須是十進位號碼字串的陣列（不帶前導 0）")
        pool = self.pools.get(params["pool"])
        if pool is None:
            raise DaemonError("NotFound", "沒有這個池：%s" % params["pool"])
        order = sorted(pool.members) if every else [int(n) for n in dict.fromkeys(names)]
        killed, skipped = [], {}
        for i in order:
            kid = pool.kids.get(i)
            if kid is None or not kid.member:
                skipped[str(i)] = "not-member"
            elif kid.state in ("pending", "killing"):
                skipped[str(i)] = kid.state
            elif kid.state == "running":
                self.start_killing(pool, kid)
                killed.append(str(i))
            else:                                                      # dead／failed：清掉等待、儘快重拉
                kid.due = time.monotonic()
                pool.update(kid, next_at=time.time())
                pool.write_kid(kid)
                self.enqueue(pool, kid)
                killed.append(str(i))
        return {"killed": killed, "skipped": skipped}

    # ---- ls（protocol §3）----

    def ls(self, params):
        if params is None:
            params = {}
        if not isinstance(params, dict):
            raise DaemonError("FieldTypeMismatch", "params 必須是物件", -32602, ["params"])
        now = time.time()
        if "pool" not in params:
            return {"pools": {name: pool.summary(now) for name, pool in sorted(self.pools.items())}}
        pool = self.pools.get(params["pool"])
        if pool is None:
            raise DaemonError("NotFound", "沒有這個池：%s" % params["pool"])
        children = {}
        for i in sorted(pool.kids):
            kid = pool.kids[i]
            record = kid.record()
            record["busy"] = is_busy(pool.home_of(i)) if kid.state == "running" else None
            children[str(i)] = record
        return {"pool": pool.name, "summary": pool.summary(now), "children": children}
