# exec：唯一碰 fork/exec/waitpid 的層。一次 fork 一整批、統一等完。

aos_add_subproject(exec
    SOURCES
        src/clock.cpp
        src/tempfile.cpp
        src/spawn_prep.cpp
        src/interrupt.cpp
        src/wait.cpp
        src/start.cpp
        src/wait_all.cpp
    HEADERS include/aos/exec.hpp
)
