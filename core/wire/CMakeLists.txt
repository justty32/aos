# wire：唯一懂 inbox、outcome 與 state JSON 形狀的純函式庫。

aos_add_subproject(wire
    SOURCES
        src/inst.cpp
        src/outcome.cpp
        src/state.cpp
    HEADERS include/aos/wire.hpp
)
