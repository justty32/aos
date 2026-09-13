已補 Python state 的 `bytes`／`bytearray` `$b64` 自動編解碼。
已新增 `aos.b64()`／`aos.unb64()` 與 3 條回歸測試。
`python3 -m unittest discover -s test`：55/55 通過。
CMake build 與 ctest：8/8 通過；未 commit／push。