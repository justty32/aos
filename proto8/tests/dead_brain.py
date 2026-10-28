"""測試裡當「腦壞了」的網址：保證連上去馬上被拒（10-28）。

原本寫死 http://127.0.0.1:9/v1（沒人聽的埠）。10-28 Windows 機的 WSL（networkingMode=mirrored）連低號的空埠會
等到逾時、不是馬上被拒，腦的請求 timeout 是 120 秒，測試就卡到逾時。
改成：本行程先 bind 一個 127.0.0.1 的埠、不 listen、一直拿著——連上去一定馬上被拒，也不會被別人搶走。
socket 留在本行程（子行程不繼承），測試跑完行程結束就放掉。"""
import atexit, socket

_HOLD = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
_HOLD.bind(("127.0.0.1", 0))
atexit.register(_HOLD.close)
DEAD = "http://127.0.0.1:%d/v1" % _HOLD.getsockname()[1]
