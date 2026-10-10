"""CLI 的一行訊息與累積確認；保存函式的語意不變。"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "lib"))
from aos7_fs import say_line  # noqa: E402


def say(msg):
    say_line("aos7-events: ", msg)


class Parser(argparse.ArgumentParser):
    def error(self, message):
        examples = {
            "pub": "請給 events 路徑、kind 與 JSON payload。例：aos7-events pub --events DIR --kind hello --payload '{}'",
            "read": "請給 events 路徑與有效通道、正整數游標與 limit。例：aos7-events read --events DIR --channel must --text",
            "ack": "請給 events 路徑、must 通道與非負整數。例：aos7-events ack --events /tmp/demo/events 1",
        }
        hint = examples.get(self.prog.split()[-1],
                            "手動請給 pub／read／ack 子命令。例：aos7-events read --events DIR --text；取樣器見 --help-sampler")
        say("參數不對：%s。%s" % (message, hint))
        self.exit(2)


def missing(events):
    """只有「確定不存在」才算沒夾；權限等讀不到交給後面當不確定。"""
    try:
        os.stat(events)
    except FileNotFoundError:
        return True
    except OSError:
        pass
    return False


def ack_main(events, upto):
    import aos7_events_store as store
    from aos7_fs import Unknown
    path = os.path.join(events, "state.json")
    try:
        os.stat(events)
    except FileNotFoundError:
        print(json.dumps({"acked_upto": None, "why": "no_events"}))
        say("沒有這個 events 夾。檢查 --events 路徑")
        return 1
    except OSError as e:
        detail = str(e)
    else:
        try:
            os.stat(path)   # 跟著連結：壞連結也算沒 state
        except FileNotFoundError:
            print(json.dumps({"acked_upto": None, "why": "unknown", "detail": "no state.json"}))
            say("不確定：這個 events 夾沒有 state.json，不知道 must 存到哪，什麼都沒動。確認 --events 指對夾；pub 寫過後再 ack")
            return 3
        except OSError as e:
            detail = str(e)
        else:
            try:
                upto = store.ack(events, upto)
            except Unknown as e:
                detail = str(e)
            else:
                print(json.dumps({"acked_upto": upto}))
                return 0
    print(json.dumps({"acked_upto": None, "why": "unknown", "detail": detail}, ensure_ascii=False))
    say("不確定：確認進度未能確定（%s）；既有紀錄與進度證據留著。照原樣再跑一次會接續" % detail)
    return 3


def main(argv=None):
    ap = Parser(prog="aos7-events ack", description="確認 must 的 seq 到這裡都處理完了；只確認、不讀。",
                epilog="例：aos7-events ack --events /tmp/demo/events 1")
    ap.add_argument("--events", required=True, help="events 夾路徑")
    ap.add_argument("--channel", choices=("must",), default="must", help="確認 must 本子（預設 must）")
    ap.add_argument("upto", type=int, help="已處理完的 seq（非負整數）")
    a = ap.parse_args(argv)
    if a.upto < 0:
        ap.error("確認 seq 須為非負整數")
    return ack_main(a.events, a.upto)
