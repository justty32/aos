// lat: times stat, open+read+close and stat of a missing name on given paths (median, p90, p99 in microseconds); "lat list" opens each path read from stdin once and prints the mean.
// usage: lat MODE N PATH...   (MODE = stat | open | miss)      or: lat list < pathlist
// Built by perf/common.py into the run's temp folder; plain C99 + POSIX, no libraries.
#define _GNU_SOURCE
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

static double now(void) {
  struct timespec t;
  clock_gettime(CLOCK_MONOTONIC, &t);
  return t.tv_sec * 1e9 + t.tv_nsec;
}

static int cmp(const void *a, const void *b) {
  double x = *(const double *)a, y = *(const double *)b;
  return x < y ? -1 : x > y;
}

static int op(const char *mode, const char *p) {
  char buf[256];
  struct stat st;
  if (!strcmp(mode, "stat") || !strcmp(mode, "miss")) return stat(p, &st);
  int fd = open(p, O_RDONLY);
  if (fd < 0) return -1;
  ssize_t r = read(fd, buf, sizeof buf);
  close(fd);
  return r < 0 ? -1 : 0;
}

int main(int argc, char **argv) {
  if (argc < 2) {
    fprintf(stderr, "usage: lat stat|open|miss N PATH... | lat list < paths\n");
    return 2;
  }
  if (!strcmp(argv[1], "list")) {
    char line[4096];
    int n = 0, bad = 0;
    double t0 = now();
    while (fgets(line, sizeof line, stdin)) {
      line[strcspn(line, "\n")] = 0;
      if (!line[0]) continue;
      if (op("open", line)) bad++;
      n++;
    }
    double t = now() - t0;
    printf("list n=%d bad=%d mean_us=%.3f\n", n, bad, n ? t / n / 1000 : 0.0);
    return 0;
  }
  if (argc < 4) return 2;
  const char *mode = argv[1];
  int n = atoi(argv[2]);
  if (n < 1) return 2;
  double *v = malloc(sizeof(double) * n);
  for (int a = 3; a < argc; a++) {
    const char *p = argv[a];
    int bad = 0;
    for (int i = 0; i < 50; i++) op(mode, p);
    for (int i = 0; i < n; i++) {
      double t = now();
      if (op(mode, p)) bad++;
      v[i] = now() - t;
    }
    qsort(v, n, sizeof(double), cmp);
    printf("%s %s fail=%d median_us=%.3f p90_us=%.3f p99_us=%.3f\n", mode, p, bad, v[n / 2] / 1000,
           v[n * 9 / 10] / 1000, v[n * 99 / 100] / 1000);
  }
  free(v);
  return 0;
}
