# hello：驗 build 鏈用的樣板小專案（函式庫＋執行檔 aos-hello＋一支測試）；新零件照抄這份改名字。

aos_add_subproject(hello
    SOURCES
        src/hello.cpp
    HEADERS include/aos/hello.hpp
    PROGRAM src/main.cpp
    TESTS
        tests/hello_test.cpp
)

# 也直接跑執行檔，看輸出對不對（ctest 的 PASS_REGULAR_EXPRESSION）。
add_test(NAME hello.runs COMMAND aos_hello_main)
set_tests_properties(hello.runs PROPERTIES PASS_REGULAR_EXPRESSION "\"hello\":\"impl_cpp\"")
