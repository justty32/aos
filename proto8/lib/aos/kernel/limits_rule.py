# 驗證 kernel 站的份額與身分設定，並在轉寄前套用到新 proc。
import copy
import fnmatch

from round import CfgBad


KEYS = ("mem_mb", "cpu_s", "procs", "file_mb", "files")


def _limit_table(value, path):
    if not isinstance(value, dict):
        raise CfgBad("%s must be an object of limit keys" % path)
    for key, number in value.items():
        if key not in KEYS:
            raise CfgBad("%s.%s is not a limit key (mem_mb, cpu_s, procs, file_mb, files)" % (path, key))
        if not isinstance(number, int) or isinstance(number, bool) or number <= 0:
            raise CfgBad("%s.%s must be a positive integer" % (path, key))


def load(cfg):
    limits = cfg.get("limits")
    if limits is not None:
        if not isinstance(limits, dict):
            raise CfgBad("limits must be an object {default, max, by_sender} or null")
        for key in limits:
            if key not in ("default", "max", "by_sender"):
                raise CfgBad("limits.%s is not a known key (default, max, by_sender)" % key)
        for key in ("default", "max"):
            if limits.get(key) is not None:
                _limit_table(limits[key], "limits.%s" % key)
        senders = limits.get("by_sender")
        if senders is not None:
            if not isinstance(senders, dict):
                raise CfgBad("limits.by_sender must be an object {sender: limits}")
            for sender, value in senders.items():
                _limit_table(value, "limits.by_sender[%s]" % sender)

    groups = cfg.get("groups")
    if groups is not None:
        if not isinstance(groups, dict):
            raise CfgBad("groups must be an object {name: number} or null")
        for name, number in groups.items():
            if not isinstance(number, int) or isinstance(number, bool) or not 60001 <= number <= 65536:
                raise CfgBad("groups.%s must be an integer from 60001 to 65536" % name)

    users = cfg.get("users")
    if users is None:
        return
    if not isinstance(users, dict):
        raise CfgBad("users must be an object {name pattern: user} or null")
    for pattern, value in users.items():
        message = 'users[%s] must be a user string or {"user": string, "groups": [names]}' % pattern
        user = value
        names = []
        if isinstance(value, dict):
            user = value.get("user")
            names = value.get("groups", [])
            if (any(key not in ("user", "groups") for key in value)
                    or not isinstance(names, list) or not all(isinstance(name, str) for name in names)):
                raise CfgBad(message)
        if not isinstance(user, str) or not user:
            raise CfgBad(message)
        if user.startswith("sub:"):
            number = user[4:]
            if (not number or len(number) > 5 or number[0] == "0"
                    or any(char not in "0123456789" for char in number)
                    or not 1 <= int(number) <= 60000):
                raise CfgBad("users[%s]: sub:N needs N from 1 to 60000" % pattern)
        for name in names:
            if name not in (cfg.get("groups") or {}):
                raise CfgBad("users[%s].groups names %s, which is not in groups" % (pattern, name))


def active(cfg):
    return cfg.get("limits") is not None or cfg.get("users") is not None


def apply(cfg, body, sender):
    if not active(cfg) or not isinstance(body, dict) or "procs_added" not in body:
        return body, None
    if not isinstance(body["procs_added"], dict):
        return None, ("BodyBad", "procs_added must be an object")

    body = copy.deepcopy(body)
    limits = cfg.get("limits") or {}
    default = dict(limits.get("default") or {})
    if isinstance(sender, str):
        default.update((limits.get("by_sender") or {}).get(sender, {}))
    maximum = limits.get("max") or {}
    for name, original in body["procs_added"].items():
        wrapped = isinstance(original, (str, list))
        if wrapped:
            spec = {"exec": original}
        elif isinstance(original, dict):
            spec = original
            if any(key.startswith("$") for key in spec):
                return None, ("BodyBad", "procs_added[%s] is written as a directive; a station with limits "
                              "or users cannot check it, write the proc out in full" % name)
        else:
            return None, ("BodyBad", "procs_added[%s] must be a string, an array or an object" % name)
        spec.pop("limits_clamped", None)
        own = spec.get("limits")
        if own is not None and not isinstance(own, dict):
            return None, ("BodyBad", "procs_added[%s].limits must be an object or null" % name)
        if own is not None:
            own.pop("user", None)
            own.pop("groups", None)
        lim = copy.deepcopy(own if own else default)
        clamped = []
        for key in KEYS:
            if key in maximum and (key not in lim or (
                    isinstance(lim[key], int) and not isinstance(lim[key], bool) and lim[key] > maximum[key])):
                lim[key] = maximum[key]
                clamped.append(key)
        for pattern, user in (cfg.get("users") or {}).items():
            if fnmatch.fnmatchcase(name, pattern):
                if isinstance(user, str):
                    lim["user"] = user
                else:
                    lim["user"] = user["user"]
                    if user.get("groups"):
                        lim["groups"] = [cfg["groups"][group] for group in user["groups"]]
                break
        if lim:
            spec["limits"] = lim
        else:
            spec.pop("limits", None)
        if clamped:
            spec["limits_clamped"] = clamped
        body["procs_added"][name] = original if wrapped and not lim and not clamped else spec
    return body, None
