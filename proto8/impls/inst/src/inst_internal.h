/* inst_internal.h：src/ 各檔之間共用的內部函數宣告。
 * 不對外安裝；這些函數在 .so 裡是 hidden（CMakeLists.txt 的 C_VISIBILITY_PRESET
 * hidden）， 只有 aos.h 標了 AOS_API 的四個函數會匯出。 名字都加 inst_
 * 前綴，免得連靜態庫 lib/libinst.a 時跟呼叫者的函數撞名。
 *
 * 誰定義在哪：
 *   inst_stream.c  inst_lift_fd、inst_open_stream
 *   inst_proc.c    inst_now_ms、inst_deadline_after、inst_start、
 *                  inst_open_pidfd、inst_wait_child
 */
#ifndef AOS_INST_INTERNAL_H
#define AOS_INST_INTERNAL_H

#include "./aos.h"

#include <stdbool.h>
#include <sys/types.h>

/* ---- inst_stream.c ---- */

/* 確保 fd 不是 0／1／2。回新的 fd（CLOEXEC），失敗回 -1。 */
int inst_lift_fd(int fd);

/* 開一個串流的檔（NULL＝/dev/null）。成功把 fd 放進 *fd、回 AOS_INST_OK。 */
int inst_open_stream(const char *path, int flags, int *fd);

/* ---- inst_proc.c ---- */

/* 單調時鐘的毫秒數（只拿來算經過多久）。 */
unsigned long long inst_now_ms(void);

/* fork＋exec。envp＝NULL 沿用呼叫者的環境。
 * in／out／err＝-1：子程式那個 fd（0／1／2）不動，直接用呼叫者的。
 * new_session＝true：子程式 exec 前 setsid()。
 * 成功把 pid 放進 *pid、回 AOS_INST_OK。 */
int inst_start(int in, int out, int err, const char *cwd, char *const *argv,
               char *const *envp, bool new_session, pid_t *pid);

/* 現在起再過 ms 毫秒的期限（inst_now_ms 的值）；
 * ms＝0 或加起來溢位＝沒有期限，回 0。 */
unsigned long long inst_deadline_after(unsigned long long ms);

/* 拿一個代表子程式的 pidfd（CLOEXEC）；拿不到回 -1（等的時候改走輪詢）。 */
int inst_open_pidfd(pid_t pid);

/* 等子程式結束；deadline＝0 不限時，到了就 SIGTERM／SIGKILL
 * （group＝true 對整個行程群組 -pid 送）。
 * pidfd＝-1 走輪詢；pidfd 由呼叫者關。
 * 回 AOS_INST_OK（狀態放 *status）、AOS_INST_ERR_WAIT_FAILED
 * 或 AOS_INST_ERR_KILL_FAILED。 */
int inst_wait_child(pid_t pid, int pidfd, unsigned long long deadline,
                    unsigned long long grace_ms, bool group, int *status,
                    bool *timed_out);

#endif
