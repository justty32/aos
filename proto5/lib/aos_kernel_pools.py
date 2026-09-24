"""kernel 這邊怎麼增減 cpu（kernel-pools.md）與家的建法（kernel-home.md）。

每格第 7 步：收 scale 回音 → info 變了沒 → 重算（dirty 才做）→ 送下一張 scale 單 → envs → 搬池／池消失。
只碰有變化的池；集合重算 O(池大小)，只在 dirty 時。
"""
import hashlib
import json
from pathlib import Path

import aos_daemon
import aos_home
from aos_kernel_info import (
    CPU_CLI, KERNEL_POOL, chain_epoch, encode, error_code, member_set, members, new_pool,
    pool_location, split_key,
)

RETRY_TICKS = 10


def envs_digest(envs):
    raw = json.dumps(envs, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def template():
    """池模板：每顆 cpu 的 inst.json 都一樣（kernel-home §2）。"""
    return {"argv": [str(CPU_CLI.resolve()), "."], "cwd": ".",
            "stderr": {"$opt": "append", "$val": "cpu.log"},
            "envs": {"$ref": "../../envs.json"}}


def pool_summary(daemon, dpool):
    """daemon 隊提供的 aos_daemon.pool_summary（不在或壞了回 None）；只給顯示用（ls、health）。"""
    return aos_daemon.pool_summary(daemon, dpool)


def pool_summary_state(daemon, dpool):
    """交接用（搬池 retire、boot、halt）：回 ("gone", None)／("ok", 摘要)／("unknown", None)。
    只有 gone（summary.json 確定不在）才算池已拿掉；unknown（在但讀不到、壞 JSON…）一律當還在（astra P6）。"""
    return aos_daemon.pool_summary_state(daemon, dpool)


def chain_request(chain, name):
    """這張 scale 單是不是這條鏈送的（k-<chain>-<seq>-scale-… 或 k-<chain>-boot-…）。"""
    return name.startswith("k-%s-" % chain)


def scale_request(name, home, pool, entry, count, skip, decl):
    cpus = str(Path(home) / "pools" / pool / "cpus")
    return {"jsonrpc": "2.0", "id": name[:-5], "method": "scale",
            "params": {"pool": entry["dpool"], "owner": str(home), "count": count, "skip": list(skip),
                       "target": cpus + "/{name}/inst.json", "home": cpus + "/{name}", "decl": list(decl)}}


class PoolsMixin:
    # ---- 家（kernel-home §3：缺的補齊、不覆蓋） ----
    def write_pool_files(self, pool, envs):
        """重寫 envs.json 與 inst.json 模板（boot 與 envs 變了時）；回新的摘要。"""
        d = self.pool_dir(pool)
        (d / "cpus").mkdir(parents=True, exist_ok=True)
        aos_home.write_json(d / "envs.json", envs)
        aos_home.write_json(d / "inst.json", template())
        return envs_digest(envs)

    def ensure_cpu_home(self, pool, i):
        home = self.pool_dir(pool) / "cpus" / str(i)
        home.mkdir(parents=True, exist_ok=True)
        aos_home.ensure_queue(home)
        if not (home / "info.json").exists():
            if pool == KERNEL_POOL:
                info = {"_metainfo": {"_type": "exec_cpu", "_version": 1}, "poll_ms": 20, "timeout_ms": 0}
            else:
                cpu = self.info["cpu"]
                info = {"_metainfo": {"_type": "exec_cpu", "_version": 1}, "poll_ms": cpu["poll_ms"],
                        "timeout_ms": cpu["timeout_ms"], "notify": str(self.home / "requests")}
            aos_home.write_json(home / "info.json", info)
        if not (home / "inst.json").exists():
            if not (self.pool_dir(pool) / "inst.json").exists():
                aos_home.write_json(self.pool_dir(pool) / "inst.json", template())
            aos_home.write_json(home / "inst.json", template())

    # ---- 第 7 步 ----
    def busy_numbers(self, pool):
        prefix = pool + "/"
        return {split_key(k)[1] for k in self.state["busy"] if k.startswith(prefix)}

    def pools_step(self):
        info_pools = [p for p in self.info["pools"] if p != KERNEL_POOL]
        names = list(dict.fromkeys([*info_pools, *(p for p in self.state["pools"] if p != KERNEL_POOL)]))
        for pool in names:
            self.pool_step(pool)

    def pool_step(self, pool):
        pools = self.state["pools"]
        loc = pool_location(self.info, pool)
        entry = pools.get(pool)
        if entry is None:
            if loc is None:
                return
            if loc[0] is None:
                # D-24：這池解不出 daemon；不建帳本格、不送單（boot 會擋 NoDaemon，這裡只記一行）。
                self.events.append({"event": "pool_no_daemon", "pool": pool})
                return
            entry = pools[pool] = new_pool(*loc)
            self.events.append({"event": "pool_new", "pool": pool, "daemon": loc[0], "dpool": loc[1]})
        retiring = loc is None or (entry["daemon"], entry["dpool"]) != tuple(loc)
        self.collect_scale(pool, entry)
        if retiring and self.abandon(pool, entry, loc):
            if loc is not None and loc[0] is not None:
                self.pool_step(pool)  # 新位置本格就宣告
            return
        if retiring or self.state.get("halting"):
            want = {"count": 0, "skip": []}
        else:
            config = self.info["pools"][pool]
            want = {"count": config["count"], "skip": list(config["skip"])}
        if entry["want"] != want:
            entry["want"] = want
            entry["dirty"] = True
            if entry["error"] is not None and entry["pending"] is None:
                entry["redeclare"] = True  # info 變了：出過錯的池再試一次（kernel-pools §2 第 1 步）
        if entry["retry_at"] is not None and self.seq >= entry["retry_at"]:
            entry["retry_at"] = None
            entry["redeclare"] = True
        target = None
        if entry["dirty"]:
            target = self.recompute(pool, entry)
        # 出過錯（redeclare 沒設）就不自動重送：等 info 再變、Stopping 到期或 boot（kernel-pools §2 第 1 步）。
        changed = target is not None and entry["error"] is None and target != member_set(entry["sent"])
        if entry["pending"] is None and (entry["redeclare"] or changed):
            if target is None:
                target = self.target_set(pool, entry)
            self.send_scale(pool, entry, target)
        if not retiring:
            envs = self.info["pools"][pool]["envs"]
            if entry["envs_digest"] != envs_digest(envs):
                entry["envs_digest"] = self.write_pool_files(pool, envs)
                self.events.append({"event": "pool_envs", "pool": pool})
        if retiring:
            self.retire(pool, entry, loc)

    def collect_scale(self, pool, entry):
        """kernel-pools §2 第 1 步：收 scale 回音。"""
        pending = entry["pending"]
        if pending is None:
            return
        name, daemon = pending["name"], Path(entry["daemon"])
        if (daemon / "requests" / name).exists():
            return
        if any(s["name"] == name and s["home"] == entry["daemon"] for s in self.state["sends"]):
            return
        response_path = daemon / "responses" / name
        if response_path.exists():
            response = aos_home.read_json(response_path)
            self.state["acks"].append({"home": entry["daemon"], "name": name})
            code = None if "error" not in response else error_code(response)
        else:
            response, code = None, "Interrupted"  # 兩個檔都不在、也不在 sends：當 Interrupted
        old_chain = entry.get("boot_redeclare") and not chain_request(self.state["chain"], name)
        if code is None:
            entry["acquired"] = True  # astra P4：daemon 確認過這個位置
        if old_chain:
            # astra P3：boot 要求的整份重送還沒做完，舊鏈的回音照收、ack，但不清重送、舊錯誤不記成 error。
            if code is None:
                entry["sent"] = {"count": pending["count"], "skip": list(pending["skip"])}
            entry["redeclare"] = True
        elif code is None:
            entry["sent"] = {"count": pending["count"], "skip": list(pending["skip"])}
            entry["redeclare"] = False
            entry["boot_redeclare"] = False
            entry["error"] = None
            entry["retry_at"] = None
        elif code in ("Interrupted", "Stale"):
            entry["redeclare"] = True
        else:
            message = (response or {}).get("error", {}).get("message", "")
            entry["error"] = {"code": code, "message": message}
            entry["retry_at"] = self.seq + RETRY_TICKS if code == "Stopping" else None
            entry["redeclare"] = False
        entry["pending"] = None
        entry["dirty"] = True
        self.events.append({"event": "scale_echo", "pool": pool, "request": name,
                            "result": "ok" if code is None else code})

    def target_set(self, pool, entry):
        """T＝W ∪ (S 裡還在 busy 的號)。"""
        want = entry["want"] or {"count": 0, "skip": []}
        sent = member_set(entry["sent"])
        return set(members(want["count"], want["skip"])) | (sent & self.busy_numbers(pool))

    def recompute(self, pool, entry):
        """kernel-pools §2 第 2 步：free＝S∩Q∩W−busy，draining＝busy 裡不在 W 的號數；回 T。"""
        want = entry["want"] or {"count": 0, "skip": []}
        w = set(members(want["count"], want["skip"]))
        s = member_set(entry["sent"])
        q = member_set(entry["pending"]) if entry["pending"] is not None else s
        busy = self.busy_numbers(pool)
        entry["free"] = sorted((s & q & w) - busy, reverse=True)  # 堆疊：尾巴是最小號
        entry["draining"] = len(busy - w)
        entry["dirty"] = False
        return w | (s & busy)

    def send_scale(self, pool, entry, target):
        """kernel-pools §2 第 3 步：新增的號先建家，再排一張 scale 單進 sends、記 pending。"""
        count, skip = encode(target)
        sent = member_set(entry["sent"])
        for i in sorted(target - sent):
            self.ensure_cpu_home(pool, i)
        name = "k-%s-%d-scale-%s.json" % (self.state["chain"], self.seq, pool)
        body = scale_request(name, self.home, pool, entry, count, skip, [chain_epoch(self.state["chain"]), self.seq])
        self.state["sends"].append({"home": entry["daemon"], "name": name, "body": body})
        entry["pending"] = {"name": name, "count": count, "skip": skip}
        entry["redeclare"] = False
        self.events.append({"event": "scale_send", "pool": pool, "request": name, "count": count, "skip": skip})

    def abandon(self, pool, entry, loc):
        """astra P4：舊位置 daemon 從沒確認過（沒成功過、sent 空）、沒 busy、沒 pending＝我們在那邊什麼都沒有；
        直接放棄、換新位置（或忘掉），不送縮 0、不等別人的 summary 消失。回 True＝放棄了。"""
        if entry.get("acquired", True) or entry["pending"] is not None or entry["sent"]["count"] != 0:
            return False
        prefix = pool + "/"
        if any(k.startswith(prefix) for k in self.state["busy"]):
            return False
        self.events.append({"event": "pool_abandon", "pool": pool, "daemon": entry["daemon"], "dpool": entry["dpool"]})
        self._replace(pool, loc)
        return True

    def _replace(self, pool, loc):
        if loc is None or loc[0] is None:
            del self.state["pools"][pool]
        else:
            self.state["pools"][pool] = new_pool(*loc)

    def retire(self, pool, entry, loc):
        """kernel-pools §2 第 5 步：舊位置縮到 0、收完、舊池的 summary.json 消失，才忘掉或換新位置。"""
        if entry["pending"] is not None or entry["sent"]["count"] != 0 or entry["redeclare"] or entry["dirty"]:
            return
        prefix = pool + "/"
        if any(k.startswith(prefix) for k in self.state["busy"]):
            return
        state, _ = pool_summary_state(entry["daemon"], entry["dpool"])
        if state != "gone":
            if state == "unknown":  # astra P6：讀不到不算消失
                self.events.append({"event": "pool_summary_unknown", "pool": pool, "daemon": entry["daemon"],
                                    "dpool": entry["dpool"]})
            return
        self.events.append({"event": "pool_gone", "pool": pool, "daemon": entry["daemon"], "dpool": entry["dpool"]})
        self._replace(pool, loc)

    def pools_quiet(self):
        """停機縮池（kernel-tick 第 9 步）：每個工作池都確認縮到 0、沒在途、不用再送。"""
        return all(e["pending"] is None and e["sent"]["count"] == 0 and not e["redeclare"] and not e["dirty"]
                   for p, e in self.state["pools"].items() if p != KERNEL_POOL)
