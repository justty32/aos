/* inst_stream.c：子程式的三個串流。
 *   inst_open_stream  開一個串流的檔（NULL＝/dev/null）
 *   inst_lift_fd      把 fd 搬到 3 以上，免得 dup2 時互相蓋掉
 */
#define _GNU_SOURCE /* O_CLOEXEC、F_DUPFD_CLOEXEC */

#include "inst_internal.h"

#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>

/* 確保 fd 不是 0／1／2。
 * 呼叫者自己關掉了標準串流時，open 會拿到這些號碼，
 * 到子程式那側 dup2 時就會互相蓋掉。
 * 回新的 fd（一樣是 CLOEXEC），失敗回 -1。 */
int inst_lift_fd(int fd) {
  if (fd < 0) {
    return fd;
  }
  if (fd > 2) {
    return fd;
  }
  int high = fcntl(fd, F_DUPFD_CLOEXEC, 3);
  close(fd);
  return high;
}

/* 開一個串流的檔。path＝NULL 就開 /dev/null。
 * 上層資料夾不存在就是開不了（不幫忙建）。
 * 成功把 fd 放進 *fd、回 AOS_INST_OK。 */
int inst_open_stream(const char *path, int flags, int *fd) {
  if (path == NULL) {
    path = "/dev/null";
  }
  int f = inst_lift_fd(open(path, flags | O_CLOEXEC, 0666));
  if (f < 0) {
    return AOS_INST_ERR_OPEN_FAILED;
  }
  /* 唯讀開資料夾會成功，要自己擋 */
  struct stat st;
  bool ok = fstat(f, &st) == 0;
  bool is_dir = ok && S_ISDIR(st.st_mode);
  if (!ok || is_dir) {
    close(f);
    return AOS_INST_ERR_OPEN_FAILED;
  }
  *fd = f;
  return AOS_INST_OK;
}
