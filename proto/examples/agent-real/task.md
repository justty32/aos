`work/` 是一個很小的 Python 專案：

- `work/shapes.py`：算面積的函式。
- `work/test_shapes.py`：它的測試。現在**有一個測試是紅的**，因為 `shapes.py` 少了一個函式。

你的工作：先看清楚少了什麼，把那個函式加進 `work/shapes.py`（其他函式不要動壞），
然後跑測試確認全綠。

跑測試的指令是：

    python3 -m unittest discover -s work -t work

看到 `OK` 就是全綠。全綠之後回一行 DONE:，不要再跑指令。
