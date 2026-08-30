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

aos_add_test(aos_exec_tests
    SOURCES
        tests/test_run_one.cpp
        tests/test_parallel.cpp
        tests/test_timeout.cpp
        tests/test_env_cwd.cpp
        tests/test_interrupt.cpp
        tests/test_ended_at.cpp
    LINK aos::exec
)
