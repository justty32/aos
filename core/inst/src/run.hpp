#pragma once

namespace aos {

int run_exec(int argc, char *argv[]);
int run_init(int argc, char *argv[]);
/* deliver 的 argv 解析與 C 進入點都自帶於 run_deliver.cpp，不經過 run.cpp。 */
int run_deliver(int argc, char *argv[]);

}  // namespace aos
