/* test_lib.c：libaos 的 C 測試（aos_inst_exec，以及兩步的
 * aos_inst_start／aos_inst_wait）。
 * 不靠測試框架：每個 CHECK 失敗就印出來，最後有失敗就回 1。
 *
 * 每個測試在一個暫存資料夾裡跑（tmp），
 * 多半用 sh -c 當子程式，看結果和寫出來的檔。
 * lib 只收絕對路徑，所以檔名都用 at("名字") 接成 tmp/名字。
 * 單子用 C99 的指定初始化寫：沒寫到的欄位都是零＝預設值。
 * 寫法跟 src/ 一樣：一行一件事，每個 CHECK 只看一件事。
 *
 * CMakeLists.txt 會把它編兩份：一份連一般的 lib（走 pidfd＋poll），
 * 一份連 -DAOS_INST_NO_PIDFD 編的 lib（走 1 毫秒輪詢），兩條路都測。
 */
#define _GNU_SOURCE /* setenv、mkdtemp、realpath */

#include "aos.h"

#include <fcntl.h>
#include <limits.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

static int failures = 0;
static char tmp[256]; /* 這次測試的暫存資料夾（絕對路徑） */

#define CHECK(cond)                                                            \
  do {                                                                         \
    if (!(cond)) {                                                             \
      fprintf(stderr, "失敗 %s:%d：%s\n", __FILE__, __LINE__, #cond);          \
      ++failures;                                                              \
    }                                                                          \
  } while (0)

/* argv 簡寫：ARGV("a", "b") → {"a", "b", NULL}；
 * SH("腳本") → sh -c 腳本（照 PATH 找 sh） */
#define ARGV(...) ((const char *const[]){__VA_ARGS__, NULL})
#define SH(script) ARGV("sh", "-c", script)

/* tmp/name。輪流用 8 塊緩衝，同一個單子裡可以同時用好幾個。 */
static const char *at(const char *name) {
  static char bufs[8][512];
  static int next = 0;
  char *buf = bufs[next];
  next = (next + 1) % 8;
  snprintf(buf, 512, "%s/%s", tmp, name);
  return buf;
}

/* tmp 底下某個檔的完整內容（最多 1023 字）；讀不到回空字串。 */
static const char *slurp(const char *name) {
  static char buf[1024];
  buf[0] = '\0';
  FILE *f = fopen(at(name), "r");
  if (f == NULL) {
    return buf;
  }
  size_t n = fread(buf, 1, sizeof buf - 1, f);
  buf[n] = '\0';
  fclose(f);
  return buf;
}

/* tmp 的真實路徑＋換行（pwd -P 印出來的樣子）。 */
static const char *real_tmp_line(const char *sub) {
  static char want[600];
  char *real = realpath(at(sub), NULL);
  snprintf(want, sizeof want, "%s\n", real);
  free(real);
  return want;
}

static void test_ok(void) {
  aos_inst_result_t r;
  aos_inst_input_t in = {.argv = SH("exit 0"), .cwd = tmp};
  CHECK(aos_inst_exec(&in, &r) == AOS_INST_OK);
  CHECK(r.code == 0);
  CHECK(r.signal == 0);
  CHECK(!r.timed_out);
  CHECK(r.pid > 0);
}

static void test_nonzero(void) {
  aos_inst_result_t r;
  aos_inst_input_t in = {.argv = SH("exit 7"), .cwd = tmp};
  /* 子程式回幾號都算 lib 成功 */
  CHECK(aos_inst_exec(&in, &r) == AOS_INST_OK);
  CHECK(r.code == 7);
  CHECK(r.signal == 0);
}

static void test_timeout_grace(void) {
  aos_inst_result_t r;
  /* 不理 SIGTERM 的子程式：過 grace 被 SIGKILL */
  aos_inst_input_t in = {
      .argv = SH("trap '' TERM; sleep 5"), .timeout_ms = 100, .grace_ms = 200};
  CHECK(aos_inst_exec(&in, &r) == AOS_INST_OK);
  CHECK(r.timed_out);
  CHECK(r.signal == SIGKILL);
  CHECK(r.code == 128 + SIGKILL);
  CHECK(r.ms >= 300);
  CHECK(r.ms < 2000);
  /* 理 SIGTERM 的：被 SIGTERM 收掉 */
  aos_inst_input_t in2 = {
      .argv = ARGV("sleep", "5"), .timeout_ms = 100, .grace_ms = 2000};
  CHECK(aos_inst_exec(&in2, &r) == AOS_INST_OK);
  CHECK(r.timed_out);
  CHECK(r.signal == SIGTERM);
  CHECK(r.ms < 1000);
  /* grace 0：直接 SIGKILL */
  in2.grace_ms = 0;
  CHECK(aos_inst_exec(&in2, &r) == AOS_INST_OK);
  CHECK(r.timed_out);
  CHECK(r.signal == SIGKILL);
}

static void test_wait_speed(void) {
  aos_inst_result_t r;
  /* 立即結束的子程式：要馬上發現，不能等滿一個輪詢間隔太多 */
  aos_inst_input_t in = {.argv = ARGV("true")};
  CHECK(aos_inst_exec(&in, &r) == AOS_INST_OK);
  CHECK(r.ms < 50);
  /* 長一點的子程式：跑 300 毫秒，量到的要接近 */
  aos_inst_input_t slow = {.argv = ARGV("sleep", "0.3"), .timeout_ms = 5000};
  CHECK(aos_inst_exec(&slow, &r) == AOS_INST_OK);
  CHECK(!r.timed_out);
  CHECK(r.code == 0);
  CHECK(r.ms >= 250);
  CHECK(r.ms < 1000);
}

static void test_overflow(void) {
  aos_inst_result_t r;
  /* timeout＝-1（ULLONG_MAX）：加起來溢位，當成不限時，不會被立刻殺 */
  aos_inst_input_t in = {.argv = ARGV("sleep", "0.2"),
                         .timeout_ms = ULLONG_MAX};
  CHECK(aos_inst_exec(&in, &r) == AOS_INST_OK);
  CHECK(!r.timed_out);
  CHECK(r.code == 0);
  CHECK(r.ms >= 150);
  /* grace＝-1：一直等 SIGTERM 生效。sh 不理 TERM，sleep 跑完 sh 自己結束：
   * timed_out＝true，但 signal＝0（以 timed_out 為準） */
  aos_inst_input_t g = {.argv = SH("trap '' TERM; sleep 0.3"),
                        .timeout_ms = 50,
                        .grace_ms = ULLONG_MAX};
  CHECK(aos_inst_exec(&g, &r) == AOS_INST_OK);
  CHECK(r.timed_out);
  CHECK(r.signal == 0);
  CHECK(r.code == 0);
  CHECK(r.ms >= 250);
  CHECK(r.ms < 2000);
}

static void test_grandchild(void) {
  aos_inst_result_t r;
  /* 收掉只管直接子程式：sh 被收掉，函數照樣回來；
   * 背景的 sleep（孫程式）會留著，這裡自己清掉 */
  aos_inst_input_t in = {.argv = SH("sleep 5 & echo $! > grand.pid; wait"),
                         .cwd = tmp,
                         .timeout_ms = 100,
                         .grace_ms = 100};
  CHECK(aos_inst_exec(&in, &r) == AOS_INST_OK);
  CHECK(r.timed_out);
  CHECK(r.ms < 1000);
  int grand = atoi(slurp("grand.pid"));
  CHECK(grand > 0);
  if (grand > 0) {
    CHECK(kill(grand, 0) == 0); /* 孫程式還活著 */
    kill(grand, SIGKILL);
  }
}

static void test_pid_on_error(void) {
  aos_inst_result_t r;
  /* SIGCHLD 設成 SIG_IGN：子程式會被系統自動收掉，lib 收不到結果。
   * 這時 pid 已經填好、code＝-1 */
  signal(SIGCHLD, SIG_IGN);
  aos_inst_input_t in = {.argv = ARGV("true")};
  CHECK(aos_inst_exec(&in, &r) == AOS_INST_ERR_WAIT_FAILED);
  CHECK(r.pid > 0);
  CHECK(r.code == -1);
  CHECK(r.signal == 0);
  signal(SIGCHLD, SIG_DFL);
}

static void test_signaled(void) {
  aos_inst_result_t r;
  aos_inst_input_t in = {.argv = SH("kill -USR1 $$")};
  CHECK(aos_inst_exec(&in, &r) == AOS_INST_OK);
  CHECK(!r.timed_out);
  CHECK(r.signal == SIGUSR1);
  CHECK(r.code == 128 + SIGUSR1);
}

static void test_stdout_file(void) {
  aos_inst_result_t r;
  aos_inst_input_t in = {.argv = SH("echo one"),
                         .paths = {NULL, at("out.txt"), NULL}};
  CHECK(aos_inst_exec(&in, &r) == AOS_INST_OK);
  CHECK(strcmp(slurp("out.txt"), "one\n") == 0);
  in.argv = SH("echo two"); /* 預設覆寫 */
  CHECK(aos_inst_exec(&in, &r) == AOS_INST_OK);
  CHECK(strcmp(slurp("out.txt"), "two\n") == 0);
  in.argv = SH("echo three");
  in.appends[1] = true; /* append */
  CHECK(aos_inst_exec(&in, &r) == AOS_INST_OK);
  CHECK(strcmp(slurp("out.txt"), "two\nthree\n") == 0);
}

static void test_stdin_file(void) {
  aos_inst_result_t r;
  aos_inst_input_t in = {.argv = SH("echo hello"),
                         .paths = {NULL, at("in.txt"), NULL}};
  CHECK(aos_inst_exec(&in, &r) == AOS_INST_OK);
  aos_inst_input_t cat = {.argv = ARGV("cat"),
                          .paths = {at("in.txt"), at("copy.txt"), NULL}};
  CHECK(aos_inst_exec(&cat, &r) == AOS_INST_OK);
  CHECK(strcmp(slurp("copy.txt"), "hello\n") == 0);
}

static void test_no_parent_dir(void) {
  aos_inst_result_t r;
  /* 上層資料夾不存在：lib 不幫忙建，開不了 */
  aos_inst_input_t in = {.argv = SH("echo hi"),
                         .paths = {NULL, at("no/such/dir/out.txt"), NULL}};
  CHECK(aos_inst_exec(&in, &r) == AOS_INST_ERR_OPEN_FAILED);
}

static void test_merge(void) {
  aos_inst_result_t r;
  aos_inst_input_t in = {.argv = SH("echo out; echo err >&2"),
                         .paths = {NULL, at("merged.txt"), NULL},
                         .merge = true};
  CHECK(aos_inst_exec(&in, &r) == AOS_INST_OK);
  CHECK(strcmp(slurp("merged.txt"), "out\nerr\n") == 0);
  in.paths[2] = at("err.txt");
  CHECK(aos_inst_exec(&in, &r) == AOS_INST_ERR_PATH_CONFLICT);
}

static void test_not_found(void) {
  aos_inst_result_t r;
  aos_inst_input_t in = {.argv = ARGV("no-such-program-aos-xyz"), .cwd = tmp};
  CHECK(aos_inst_exec(&in, &r) == AOS_INST_ERR_COMMAND_MISSING);
  in.argv = ARGV("/no/such/program");
  CHECK(aos_inst_exec(&in, &r) == AOS_INST_ERR_COMMAND_MISSING);
  const char *name = aos_inst_strerror(AOS_INST_ERR_COMMAND_MISSING);
  CHECK(strcmp(name, "CommandMissing") == 0);
}

static void test_not_executable(void) {
  aos_inst_result_t r;
  FILE *f = fopen(at("noexec.sh"), "w");
  fputs("#!/bin/sh\nexit 0\n", f);
  fclose(f);
  chmod(at("noexec.sh"), 0644);
  /* 相對的 argv[0] 從 cwd 算 */
  aos_inst_input_t in = {.argv = ARGV("./noexec.sh"), .cwd = tmp};
  CHECK(aos_inst_exec(&in, &r) == AOS_INST_ERR_COMMAND_BAD);
  CHECK(strcmp(aos_inst_strerror(AOS_INST_ERR_COMMAND_BAD), "CommandBad") == 0);
  chmod(at("noexec.sh"), 0755);
  CHECK(aos_inst_exec(&in, &r) == AOS_INST_OK);
  CHECK(r.code == 0);
}

static void test_path_search(void) {
  aos_inst_result_t r;
  /* 找程式用 envs 裡的 PATH：bin/ 底下放一支小腳本，
   * argv[0] 只寫名字；呼叫者的 PATH 裡沒有它 */
  mkdir(at("bin"), 0777);
  FILE *f = fopen(at("bin/aos-hello"), "w");
  fputs("#!/bin/sh\nexit 9\n", f);
  fclose(f);
  chmod(at("bin/aos-hello"), 0755);
  aos_inst_input_t in = {.argv = ARGV("aos-hello")};
  CHECK(aos_inst_exec(&in, &r) == AOS_INST_ERR_COMMAND_MISSING);
  char path_env[600];
  snprintf(path_env, sizeof path_env, "PATH=%s", at("bin"));
  in.envs = ARGV(path_env);
  CHECK(aos_inst_exec(&in, &r) == AOS_INST_OK);
  CHECK(r.code == 9);
  /* 能執行但沒有 #! 的腳本：glibc 改用 /bin/sh 跑 */
  f = fopen(at("noshebang"), "w");
  fputs("exit 5\n", f);
  fclose(f);
  chmod(at("noshebang"), 0755);
  aos_inst_input_t ns = {.argv = ARGV("./noshebang"), .cwd = tmp};
  CHECK(aos_inst_exec(&ns, &r) == AOS_INST_OK);
  CHECK(r.code == 5);
}

static void test_cwd(void) {
  aos_inst_result_t r;
  aos_inst_input_t in = {.argv = ARGV("true"), .cwd = "/no/such/dir"};
  CHECK(aos_inst_exec(&in, &r) == AOS_INST_ERR_CWD_MISSING);
  in.cwd = "/bin/sh"; /* 不是資料夾 */
  CHECK(aos_inst_exec(&in, &r) == AOS_INST_ERR_CWD_MISSING);
  in.cwd = NULL; /* NULL＝呼叫者的 cwd */
  CHECK(aos_inst_exec(&in, &r) == AOS_INST_OK);
  /* 子程式真的在 cwd 跑 */
  aos_inst_input_t pwd = {
      .argv = SH("pwd -P"), .cwd = tmp, .paths = {NULL, at("pwd.txt"), NULL}};
  CHECK(aos_inst_exec(&pwd, &r) == AOS_INST_OK);
  CHECK(strcmp(slurp("pwd.txt"), real_tmp_line(".")) == 0);
}

static void test_cwd_no_exec(void) {
  aos_inst_result_t r;
  /* 資料夾在，但沒有 x 權限：進不去，也算 CwdMissing。
   * root 不受權限限制（access 會成功），就略過 */
  if (geteuid() == 0) {
    return;
  }
  mkdir(at("nox"), 0700);
  chmod(at("nox"), 0600);
  aos_inst_input_t in = {.argv = ARGV("true"), .cwd = at("nox")};
  CHECK(aos_inst_exec(&in, &r) == AOS_INST_ERR_CWD_MISSING);
  chmod(at("nox"), 0700); /* 讓最後的 rm -rf 刪得掉 */
}

static void test_not_absolute(void) {
  aos_inst_result_t r;
  aos_inst_input_t in = {.argv = ARGV("true"), .cwd = "relative"};
  CHECK(aos_inst_exec(&in, &r) == AOS_INST_ERR_PATH_NOT_ABSOLUTE);
  in.cwd = ""; /* 空字串也不是絕對路徑 */
  CHECK(aos_inst_exec(&in, &r) == AOS_INST_ERR_PATH_NOT_ABSOLUTE);
  in.cwd = NULL;
  for (int i = 0; i < 3; ++i) {
    aos_inst_input_t p = {.argv = ARGV("true")};
    p.paths[i] = "out.txt";
    CHECK(aos_inst_exec(&p, &r) == AOS_INST_ERR_PATH_NOT_ABSOLUTE);
  }
  const char *name = aos_inst_strerror(AOS_INST_ERR_PATH_NOT_ABSOLUTE);
  CHECK(strcmp(name, "PathNotAbsolute") == 0);
}

static void test_envs(void) {
  aos_inst_result_t r;
  setenv("AOS_TEST_KEEP", "keep", 1);
  aos_inst_input_t in = {.argv = SH("echo \"$FOO|$AOS_TEST_KEEP\""),
                         .paths = {NULL, at("env.txt"), NULL}};
  /* envs NULL＝沿用呼叫者的環境 */
  CHECK(aos_inst_exec(&in, &r) == AOS_INST_OK);
  CHECK(strcmp(slurp("env.txt"), "|keep\n") == 0);
  /* envs 非 NULL＝就是完整環境：呼叫者的變數不會出現 */
  in.envs = ARGV("FOO=bar", "PATH=/usr/bin:/bin");
  CHECK(aos_inst_exec(&in, &r) == AOS_INST_OK);
  CHECK(strcmp(slurp("env.txt"), "bar|\n") == 0);
  /* 空的 envs＝空環境；用 env 印出來應該什麼都沒有 */
  aos_inst_input_t empty = {.argv = ARGV("/usr/bin/env"),
                            .envs = (const char *const[]){NULL},
                            .paths = {NULL, at("env.txt"), NULL}};
  CHECK(aos_inst_exec(&empty, &r) == AOS_INST_OK);
  CHECK(strcmp(slurp("env.txt"), "") == 0);
}

static void test_bad_args(void) {
  aos_inst_result_t r;
  aos_inst_input_t in = {0}; /* argv 沒填 */
  CHECK(aos_inst_exec(&in, &r) == AOS_INST_ERR_INPUT_BAD);
  in.argv = (const char *const[]){NULL}; /* argv 是空的 */
  CHECK(aos_inst_exec(&in, &r) == AOS_INST_ERR_INPUT_BAD);
  in.argv = ARGV("true");
  CHECK(aos_inst_exec(&in, NULL) == AOS_INST_ERR_INPUT_BAD);
  CHECK(aos_inst_exec(NULL, &r) == AOS_INST_ERR_INPUT_BAD);
  CHECK(strcmp(aos_inst_strerror(AOS_INST_ERR_INPUT_BAD), "InputBad") == 0);
  /* 只填 argv，其他全零＝全預設 */
  CHECK(aos_inst_exec(&in, &r) == AOS_INST_OK);
  in.paths[0] = "/"; /* stdin 是資料夾 */
  CHECK(aos_inst_exec(&in, &r) == AOS_INST_ERR_OPEN_FAILED);
}

static void test_start_wait(void) {
  aos_inst_result_t r;
  aos_inst_proc_t p;
  /* 起好就回、拿得到 pid；呼叫者自己送訊號，wait 看得到 */
  aos_inst_input_t in = {.argv = ARGV("sleep", "5")};
  CHECK(aos_inst_start(&in, &p) == AOS_INST_OK);
  CHECK(p.pid > 0);
  CHECK(kill((pid_t)p.pid, SIGTERM) == 0);
  CHECK(aos_inst_wait(&p, &r) == AOS_INST_OK);
  CHECK(r.pid == p.pid);
  CHECK(r.signal == SIGTERM);
  CHECK(r.code == 128 + SIGTERM);
  CHECK(!r.timed_out);
  CHECK(p.pidfd == -1); /* wait 關掉了 */

  /* timeout 從 start 算：start 後睡 300 毫秒才 wait，
   * 100 毫秒的期限早就過了，一進 wait 就收掉 */
  aos_inst_input_t slow = {
      .argv = ARGV("sleep", "5"), .timeout_ms = 100, .grace_ms = 0};
  CHECK(aos_inst_start(&slow, &p) == AOS_INST_OK);
  struct timespec t = {.tv_sec = 0, .tv_nsec = 300000000L};
  nanosleep(&t, NULL);
  CHECK(aos_inst_wait(&p, &r) == AOS_INST_OK);
  CHECK(r.timed_out);
  CHECK(r.signal == SIGKILL);
  CHECK(r.ms >= 300);
  CHECK(r.ms < 1000);

  /* 起不來：回代號，proc 不動 */
  aos_inst_proc_t untouched = {.pid = 12345};
  aos_inst_input_t bad = {.argv = ARGV("no-such-program-aos-xyz")};
  CHECK(aos_inst_start(&bad, &untouched) == AOS_INST_ERR_COMMAND_MISSING);
  CHECK(untouched.pid == 12345);

  /* NULL */
  CHECK(aos_inst_start(NULL, &p) == AOS_INST_ERR_INPUT_BAD);
  CHECK(aos_inst_start(&in, NULL) == AOS_INST_ERR_INPUT_BAD);
  CHECK(aos_inst_wait(NULL, &r) == AOS_INST_ERR_INPUT_BAD);
}

static void test_empty_path_searches_cwd(void) {
  aos_inst_result_t r;
  /* PATH 是空字串：glibc 把空的一段當成目前資料夾，在 cwd 找 */
  mkdir(at("emptypath"), 0777);
  FILE *f = fopen(at("emptypath/aos-here"), "w");
  fputs("#!/bin/sh\nexit 4\n", f);
  fclose(f);
  chmod(at("emptypath/aos-here"), 0755);
  aos_inst_input_t in = {
      .argv = ARGV("aos-here"), .cwd = at("emptypath"), .envs = ARGV("PATH=")};
  CHECK(aos_inst_exec(&in, &r) == AOS_INST_OK);
  CHECK(r.code == 4);
  in.cwd = tmp; /* 換個資料夾就找不到 */
  CHECK(aos_inst_exec(&in, &r) == AOS_INST_ERR_COMMAND_MISSING);
}

/* 把自己的 fd（0／1／2）暫時換成 path 那個檔，跑 in，再換回來。
 * 給 inherits 測試用：子程式「接呼叫者的」，就會讀寫到這個檔。 */
static int exec_with_fd(int fd, const char *path, int flags,
                        aos_inst_input_t *in, aos_inst_result_t *r) {
  fflush(NULL);
  int saved = dup(fd);
  int f = open(path, flags, 0666);
  dup2(f, fd);
  close(f);
  int rc = aos_inst_exec(in, r);
  fflush(NULL);
  dup2(saved, fd);
  close(saved);
  return rc;
}

static void test_inherits(void) {
  aos_inst_result_t r;
  int w = O_WRONLY | O_CREAT | O_TRUNC;
  /* stdout 接呼叫者的：子程式寫到呼叫者 fd 1 指的檔 */
  aos_inst_input_t out = {.argv = SH("echo hi"), .inherits = {false, true}};
  CHECK(exec_with_fd(1, at("inh_out.txt"), w, &out, &r) == AOS_INST_OK);
  CHECK(r.code == 0);
  CHECK(strcmp(slurp("inh_out.txt"), "hi\n") == 0);
  /* 對照：沒設 inherits＝/dev/null，檔是空的（零值行為不變） */
  out.inherits[1] = false;
  CHECK(exec_with_fd(1, at("inh_out.txt"), w, &out, &r) == AOS_INST_OK);
  CHECK(strcmp(slurp("inh_out.txt"), "") == 0);
  /* stderr 接呼叫者的 */
  aos_inst_input_t err = {.argv = SH("echo oops >&2"),
                          .inherits = {false, false, true}};
  CHECK(exec_with_fd(2, at("inh_err.txt"), w, &err, &r) == AOS_INST_OK);
  CHECK(strcmp(slurp("inh_err.txt"), "oops\n") == 0);
  /* stdin 接呼叫者的：cat 讀呼叫者 fd 0 的檔 */
  FILE *f = fopen(at("inh_in.txt"), "w");
  fputs("from caller\n", f);
  fclose(f);
  aos_inst_input_t in = {.argv = ARGV("cat"),
                         .paths = {NULL, at("inh_copy.txt"), NULL},
                         .inherits = {true}};
  CHECK(exec_with_fd(0, at("inh_in.txt"), O_RDONLY, &in, &r) == AOS_INST_OK);
  CHECK(strcmp(slurp("inh_copy.txt"), "from caller\n") == 0);
  /* merge＋inherits[1]：stderr 併進呼叫者的 fd 1 */
  aos_inst_input_t merged = {.argv = SH("echo out; echo err >&2"),
                             .inherits = {false, true},
                             .merge = true};
  CHECK(exec_with_fd(1, at("inh_merge.txt"), w, &merged, &r) == AOS_INST_OK);
  CHECK(strcmp(slurp("inh_merge.txt"), "out\nerr\n") == 0);
  /* 衝突：inherits[i] 又給 paths[i]；merge 又 inherits[2] */
  for (int i = 0; i < 3; ++i) {
    aos_inst_input_t c = {.argv = ARGV("true")};
    c.inherits[i] = true;
    c.paths[i] = at("x.txt");
    CHECK(aos_inst_exec(&c, &r) == AOS_INST_ERR_PATH_CONFLICT);
  }
  aos_inst_input_t c = {
      .argv = ARGV("true"), .inherits = {false, false, true}, .merge = true};
  CHECK(aos_inst_exec(&c, &r) == AOS_INST_ERR_PATH_CONFLICT);
}

/* pid 那個程式沒了（或只剩殭屍、等別人收屍）就回 true；最多等 1 秒。 */
static bool gone(int pid) {
  for (int i = 0; i < 100; ++i) {
    if (kill(pid, 0) != 0) {
      return true;
    }
    char path[64];
    snprintf(path, sizeof path, "/proc/%d/stat", pid);
    char buf[512] = "";
    FILE *f = fopen(path, "r");
    if (f != NULL) {
      size_t n = fread(buf, 1, sizeof buf - 1, f);
      buf[n] = '\0';
      fclose(f);
    }
    char *close_paren = strrchr(buf, ')');
    bool zombie =
        close_paren != NULL && close_paren[1] == ' ' && close_paren[2] == 'Z';
    if (zombie) {
      return true;
    }
    struct timespec t = {.tv_sec = 0, .tv_nsec = 10000000L};
    nanosleep(&t, NULL);
  }
  return false;
}

static void test_new_session(void) {
  aos_inst_result_t r;
  aos_inst_proc_t p;
  /* new_session：子程式自成一個行程群組（群組號＝它的 pid） */
  aos_inst_input_t in = {.argv = ARGV("sleep", "5"), .new_session = true};
  CHECK(aos_inst_start(&in, &p) == AOS_INST_OK);
  CHECK(getpgid((pid_t)p.pid) == (pid_t)p.pid);
  CHECK(kill(-(pid_t)p.pid, SIGTERM) == 0); /* 呼叫者對 -pid 送＝整群 */
  CHECK(aos_inst_wait(&p, &r) == AOS_INST_OK);
  CHECK(r.signal == SIGTERM);
  /* 對照：零值＝跟呼叫者同一個群組 */
  in.new_session = false;
  CHECK(aos_inst_start(&in, &p) == AOS_INST_OK);
  CHECK(getpgid((pid_t)p.pid) == getpgrp());
  kill((pid_t)p.pid, SIGKILL);
  CHECK(aos_inst_wait(&p, &r) == AOS_INST_OK);

  /* 逾時整群收：背景的 sleep（孫程式）跟 sh 一起死（對照 test_grandchild） */
  aos_inst_input_t g = {.argv = SH("sleep 30 & echo $! > sess.pid; wait"),
                        .cwd = tmp,
                        .timeout_ms = 200,
                        .new_session = true};
  CHECK(aos_inst_exec(&g, &r) == AOS_INST_OK);
  CHECK(r.timed_out);
  CHECK(r.signal == SIGKILL);
  int grand = atoi(slurp("sess.pid"));
  CHECK(grand > 0);
  if (grand > 0) {
    CHECK(gone(grand));
    kill(grand, SIGKILL); /* 萬一失敗也別留著 */
  }
  /* grace 路：SIGTERM 也整群送 */
  g.grace_ms = 2000;
  CHECK(aos_inst_exec(&g, &r) == AOS_INST_OK);
  CHECK(r.timed_out);
  CHECK(r.signal == SIGTERM);
  grand = atoi(slurp("sess.pid"));
  CHECK(grand > 0);
  if (grand > 0) {
    CHECK(gone(grand));
    kill(grand, SIGKILL);
  }
}

int main(void) {
  const char *base = getenv("TMPDIR");
  if (base == NULL) {
    base = "/tmp";
  }
  snprintf(tmp, sizeof tmp, "%s/aos_c_test_XXXXXX", base);
  if (mkdtemp(tmp) == NULL) {
    perror("mkdtemp");
    return 1;
  }
  test_ok();
  test_nonzero();
  test_timeout_grace();
  test_wait_speed();
  test_overflow();
  test_grandchild();
  test_pid_on_error();
  test_signaled();
  test_stdout_file();
  test_stdin_file();
  test_no_parent_dir();
  test_merge();
  test_not_found();
  test_not_executable();
  test_path_search();
  test_cwd();
  test_cwd_no_exec();
  test_not_absolute();
  test_envs();
  test_bad_args();
  test_start_wait();
  test_empty_path_searches_cwd();
  test_inherits();
  test_new_session();

  char cmd[512];
  snprintf(cmd, sizeof cmd, "rm -rf '%s'", tmp);
  if (system(cmd) != 0) {
    fprintf(stderr, "清不掉 %s\n", tmp);
  }
  if (failures > 0) {
    fprintf(stderr, "test_lib：%d 個失敗\n", failures);
    return 1;
  }
  printf("test_lib：全部通過\n");
  return 0;
}
