/* inst_proc.c：起子程式、等它、收它。
 *   inst_start           fork＋exec；exec 失敗的 errno 經一條 CLOEXEC pipe
 * 傳回來 inst_open_pidfd      拿代表子程式的 pidfd（拿不到回 -1）
 *   inst_wait_child      等到結束；時間到就 SIGTERM，過 grace_ms 再 SIGKILL
 *   inst_now_ms          單調時鐘的毫秒數
 *   inst_deadline_after  現在＋幾毫秒的期限
 *
 * 等子程式的寫法（不用碰訊號、多執行緒也安全）：
 *   主路：pidfd_open（Linux 5.3+）拿到一個代表子程式的 fd，
 *         poll 它；子程式一結束 poll 就醒，再 waitpid 收屍。
 *   退路：pidfd_open 失敗（核心太舊 ENOSYS、被 seccomp 擋 EPERM…）
 *         就每 1 毫秒 waitpid(WNOHANG) 看一次。
 *   編譯時加 -DAOS_INST_NO_PIDFD 會強制走退路（給測試用）。
 *
 * fork 之後，子程式那一側只呼叫 async-signal-safe 的函數
 * （setsid、dup2、chdir、sigaction、execvp、write、_exit…），
 * 不配記憶體：要用的字串都在 fork 前備好。
 * 這樣呼叫者是多執行緒程式也不會卡死。
 */
#define _GNU_SOURCE /* pipe2、close_range、syscall */

#include "inst_internal.h"

#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <poll.h>
#include <signal.h>
#include <string.h>
#include <sys/syscall.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

extern char **environ;

/* ---- 時間 ---- */

unsigned long long inst_now_ms(void) {
  struct timespec t;
  clock_gettime(CLOCK_MONOTONIC, &t);
  unsigned long long sec = (unsigned long long)t.tv_sec;
  unsigned long long nsec = (unsigned long long)t.tv_nsec;
  return sec * 1000ULL + nsec / 1000000ULL;
}

/* 睡 ms 毫秒。
 * 被訊號打斷就提早醒，沒關係，外面會再看一次。 */
static void nap_ms(unsigned long long ms) {
  struct timespec t;
  t.tv_sec = (time_t)(ms / 1000);
  t.tv_nsec = (long)(ms % 1000) * 1000000L;
  nanosleep(&t, NULL);
}

/* ---- 起子程式 ---- */

/* 把 3 以上的 fd 都標成 CLOEXEC，exec 時自動關。
 * 先試 close_range（Linux 5.11+）；不支援（回 -1）就退回 fcntl 一個一個標。
 * 退路的迴圈有上限 65536，所以不會無窮迴圈；
 * 代價是舊核心上 65536 以上的 fd 可能漏給子程式。 */
static void cloexec_from_3(void) {
#ifdef CLOSE_RANGE_CLOEXEC
  if (close_range(3, ~0U, CLOSE_RANGE_CLOEXEC) == 0) {
    return;
  }
#endif
  long max = sysconf(_SC_OPEN_MAX);
  if (max <= 0 || max > 65536) {
    max = 65536;
  }
  for (int fd = 3; fd < max; ++fd) {
    fcntl(fd, F_SETFD, FD_CLOEXEC);
  }
}

/* 子程式那一側：（new_session 就 setsid）、接好串流、恢復訊號、chdir、exec。
 * in／out／err＝-1 的那個 fd 不動（inherits：直接用呼叫者的 0／1／2）。
 * envp 不是 NULL 就先 environ = envp，再 execvp：
 *   execvp 用 getenv("PATH") 找程式，並把 environ 交給新程式，
 *   所以找程式用的 PATH 和子程式看到的環境是同一份 envp。
 *   改 environ 只發生在 fork 出來的子行程，不影響呼叫者。
 * envp 是 NULL＝不動 environ，沿用呼叫者的。
 * glibc 的 execvp 不 malloc（找的路徑放在堆疊上），fork 之後可以用。
 * 失敗就把 errno 寫進 report 然後結束。
 * 這裡只用 async-signal-safe 的呼叫。 */
static void child_side(int in, int out, int err, int report, const char *cwd,
                       char *const *argv, char *const *envp, bool new_session) {
  /* 自成一個 session／行程群組（群組號＝自己的 pid），收掉時才能整群送。
   * 剛 fork 出來的子行程不是群組組長，setsid 不會失敗，所以不檢查 */
  if (new_session) {
    setsid();
  }

  /* 訊號處置恢復預設、遮罩清空：
   * 呼叫者怎麼設是呼叫者的事，不傳給子程式 */
  struct sigaction dfl;
  memset(&dfl, 0, sizeof dfl);
  dfl.sa_handler = SIG_DFL;
  sigemptyset(&dfl.sa_mask);
  for (int sig = 1; sig < NSIG; ++sig) {
    sigaction(sig, &dfl, NULL); /* SIGKILL 這些改不了，失敗也無妨 */
  }
  sigset_t none;
  sigemptyset(&none);
  sigprocmask(SIG_SETMASK, &none, NULL);

  /* 開來的 fd 都已經保證 >= 3，dup2 不會互相蓋掉；
   * dup2 出來的 0／1／2 不帶 CLOEXEC。
   * -1＝不動（接呼叫者的）。err 可能是 1（merge 進呼叫者的 stdout），
   * 這時 1 已經是對的，照順序 dup2 就好 */
  if (in >= 0) {
    dup2(in, 0);
  }
  if (out >= 0) {
    dup2(out, 1);
  }
  if (err >= 0) {
    dup2(err, 2);
  }

  int error = 0;
  if (cwd != NULL) {
    if (chdir(cwd) != 0) {
      error = errno;
      ssize_t ignored = write(report, &error, sizeof error);
      (void)ignored;
      _exit(127);
    }
  }

  /* 3 以上的 fd 都不帶過去
   * （report 撐到 exec 成功那一刻才自動關） */
  cloexec_from_3();

  if (envp != NULL) {
    environ = (char **)envp; /* 只是指標賦值；exec 不會改內容 */
  }
  execvp(argv[0], argv);
  error = errno; /* 走到這裡＝exec 失敗 */
  ssize_t ignored = write(report, &error, sizeof error);
  (void)ignored;
  _exit(127);
}

/* exec 失敗的 errno → 錯誤代號。 */
static int launch_error(int error) {
  if (error == ENOENT || error == ENOTDIR) {
    return AOS_INST_ERR_COMMAND_NOT_FOUND;
  }
  if (error == EACCES || error == EPERM) {
    return AOS_INST_ERR_COMMAND_NOT_EXECUTABLE;
  }
  return AOS_INST_ERR_LAUNCH_FAILED;
}

/* fork＋exec。成功把 pid 放進 *pid、回 AOS_INST_OK。 */
int inst_start(int in, int out, int err, const char *cwd, char *const *argv,
               char *const *envp, bool new_session, pid_t *pid) {
  /* 子程式 exec 失敗就把 errno 寫進這條 pipe；
   * exec 成功它自動關掉（CLOEXEC），父程式讀到 0 bytes */
  int report[2];
  if (pipe2(report, O_CLOEXEC) != 0) {
    return AOS_INST_ERR_LAUNCH_FAILED;
  }
  int rd = inst_lift_fd(report[0]);
  int wr = inst_lift_fd(report[1]);
  if (rd < 0 || wr < 0) {
    if (rd >= 0) {
      close(rd);
    }
    if (wr >= 0) {
      close(wr);
    }
    return AOS_INST_ERR_LAUNCH_FAILED;
  }

  pid_t p = fork();
  if (p == 0) {
    child_side(in, out, err, wr, cwd, argv, envp, new_session); /* 不會回來 */
  }
  close(wr);
  if (p < 0) {
    close(rd);
    return AOS_INST_ERR_LAUNCH_FAILED;
  }

  /* 讀子程式回報的 errno；被訊號打斷就再讀 */
  int error = 0;
  ssize_t n = -1;
  while (n < 0) {
    n = read(rd, &error, sizeof error);
    if (n < 0 && errno != EINTR) {
      break;
    }
  }
  close(rd);
  if (n != (ssize_t)sizeof error) {
    *pid = p; /* 讀到 0 bytes＝exec 成功 */
    return AOS_INST_OK;
  }

  /* 起不來的子程式也要收掉 */
  while (waitpid(p, NULL, 0) < 0) {
    if (errno != EINTR) {
      break;
    }
  }
  return launch_error(error);
}

/* ---- 等與收 ---- */

/* 拿一個代表子程式的 pidfd；拿不到回 -1（呼叫端改走輪詢）。
 * 直接用 syscall，不靠 glibc 有沒有包 pidfd_open。
 * pidfd_open 給的 fd 本來就帶 CLOEXEC，不會漏給別的子程式。 */
int inst_open_pidfd(pid_t pid) {
#if defined(AOS_INST_NO_PIDFD)
  (void)pid;
  return -1;
#elif defined(SYS_pidfd_open)
  return (int)syscall(SYS_pidfd_open, pid, 0);
#else
  (void)pid;
  return -1;
#endif
}

/* 現在起再過 ms 毫秒的期限（inst_now_ms 的值）。
 * ms＝0，或加起來溢位（ms 太大，例如 FFI 傳 -1＝ULLONG_MAX），
 * 都當成沒有期限，回 0。 */
unsigned long long inst_deadline_after(unsigned long long ms) {
  if (ms == 0) {
    return 0;
  }
  unsigned long long now = inst_now_ms();
  unsigned long long deadline = now + ms;
  if (deadline < now) {
    return 0;
  }
  return deadline;
}

/* 離 deadline 還剩幾毫秒，給 poll 用。
 * deadline＝0 是「沒有期限」，回 -1（poll 的無限等）。
 * 已經過了回 0。太大的話壓在 INT_MAX。 */
static int ms_left(unsigned long long deadline) {
  if (deadline == 0) {
    return -1;
  }
  unsigned long long now = inst_now_ms();
  if (now >= deadline) {
    return 0;
  }
  unsigned long long left = deadline - now;
  if (left > INT_MAX) {
    left = INT_MAX;
  }
  return (int)left;
}

/* 睡一下等子程式：有 pidfd 就 poll 它（子程式結束就醒），
 * 沒有就睡 1 毫秒。left＝-1 是無限等。
 * 被訊號打斷（EINTR）就直接回去，外面會重算剩餘時間；
 * poll 出了別的錯就睡 1 毫秒，免得空轉。 */
static void nap(int pidfd, int left) {
  if (pidfd >= 0) {
    struct pollfd p;
    p.fd = pidfd;
    p.events = POLLIN;
    p.revents = 0;
    int r = poll(&p, 1, left);
    if (r < 0 && errno != EINTR) {
      nap_ms(1);
    }
    return;
  }
  if (left != 0) {
    nap_ms(1);
  }
}

/* wait_until 的結果 */
enum { WAIT_ERROR = -1, WAIT_TIMEOUT = 0, WAIT_DONE = 1 };

/* 等子程式結束，最多等到 deadline（inst_now_ms 的值；0＝沒有期限）。
 * 結束了回 WAIT_DONE（狀態放 *status）、時間到回 WAIT_TIMEOUT、
 * waitpid 出錯回 WAIT_ERROR。 */
static int wait_until(pid_t pid, int pidfd, unsigned long long deadline,
                      int *status) {
  for (;;) {
    pid_t r = waitpid(pid, status, WNOHANG);
    if (r == pid) {
      return WAIT_DONE;
    }
    if (r < 0 && errno != EINTR) {
      return WAIT_ERROR;
    }
    int left = ms_left(deadline);
    if (left == 0) {
      return WAIT_TIMEOUT;
    }
    nap(pidfd, left);
  }
}

/* 送訊號給子程式；group＝true 送給整個行程群組（-pid）。成功回 true。
 * ESRCH（已經結束、只是還沒收屍；群組已經沒人）不算失敗。
 * 其他失敗（例如 EPERM：子程式 exec 了 setuid 程式）回 false。
 * 整群送不會打錯人：子程式還沒收屍，它的 pid（＝群組號）不會被別人拿去用。 */
static bool send_signal(pid_t pid, bool group, int sig) {
  pid_t target = pid;
  if (group) {
    target = -pid;
  }
  if (kill(target, sig) == 0) {
    return true;
  }
  return errno == ESRCH;
}

/* SIGTERM，等 grace_ms，還沒結束就 SIGKILL。
 * grace_ms＝0 直接 SIGKILL；grace_ms 大到溢位＝一直等 SIGTERM 生效。
 * 回 AOS_INST_OK、AOS_INST_ERR_WAIT_FAILED 或 AOS_INST_ERR_KILL_FAILED。 */
static int stop(pid_t pid, int pidfd, unsigned long long grace_ms, bool group,
                int *status) {
  if (grace_ms > 0) {
    if (!send_signal(pid, group, SIGTERM)) {
      return AOS_INST_ERR_KILL_FAILED;
    }
    int r = wait_until(pid, pidfd, inst_deadline_after(grace_ms), status);
    if (r == WAIT_DONE) {
      return AOS_INST_OK;
    }
    if (r == WAIT_ERROR) {
      return AOS_INST_ERR_WAIT_FAILED;
    }
  }
  if (!send_signal(pid, group, SIGKILL)) {
    return AOS_INST_ERR_KILL_FAILED;
  }
  int r = wait_until(pid, pidfd, 0, status);
  if (r == WAIT_ERROR) {
    return AOS_INST_ERR_WAIT_FAILED;
  }
  return AOS_INST_OK;
}

/* 起好的子程式等到結束；deadline＝0（沒有期限）就不限時。
 * 回 AOS_INST_OK（狀態放 *status）、AOS_INST_ERR_WAIT_FAILED
 * 或 AOS_INST_ERR_KILL_FAILED；時間到要收掉的話 *timed_out＝true。 */
int inst_wait_child(pid_t pid, int pidfd, unsigned long long deadline,
                    unsigned long long grace_ms, bool group, int *status,
                    bool *timed_out) {
  *timed_out = false;
  int r = wait_until(pid, pidfd, deadline, status);
  if (r == WAIT_ERROR) {
    return AOS_INST_ERR_WAIT_FAILED;
  }
  if (r == WAIT_TIMEOUT) {
    *timed_out = true;
    return stop(pid, pidfd, grace_ms, group, status);
  }
  return AOS_INST_OK;
}
