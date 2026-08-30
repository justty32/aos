# wire：唯一懂 inbox、outcome 與 state JSON 形狀的純函式庫。

aos_add_subproject(wire
    SOURCES
        src/inst.cpp
        src/outcome.cpp
        src/state.cpp
    HEADERS include/aos/wire.hpp
)

aos_add_test(aos_wire_tests
    SOURCES
        tests/test_inst.cpp
        tests/test_outcome.cpp
        tests/test_state.cpp
        tests/test_errors.cpp
    LINK aos::wire
)
