/* 評估用下限：極小 C 版 tick／tock。只做空任務 node 必要的檔案動作：
   查 timeline.json、flock action.lock、讀 round.json、讀 tasks.json、列 .aos/tasks、原子寫 round.json；tock 另 append rounds.jsonl。
   不解析任務、不起任務、不比世代。用途只是量「換成 C 的程序成本下限」。 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/file.h>
#include <dirent.h>
static char buf[1<<16];
static int readf(const char*p){int fd=open(p,O_RDONLY);if(fd<0)return -1;int n=read(fd,buf,sizeof buf-1);close(fd);if(n<0)n=0;buf[n]=0;return n;}
int main(int c,char**v){
  if(c!=4)return 1; int tick=strcmp(v[1],"aos7-tick")==0; char p[4096],q[4096];
  const char*node=strcmp(v[3],".")?v[3]:"";
  char base[4096]; snprintf(base,sizeof base,"%s/%s/.aos",v[2],node);
  snprintf(p,sizeof p,"%s/timeline.json",base); if(access(p,F_OK)){puts("{\"round\":null,\"started\":[],\"gone\":true}");return 0;}
  snprintf(p,sizeof p,"%s/action.lock",base); int lk=open(p,O_CREAT|O_WRONLY|O_APPEND,0644); flock(lk,LOCK_EX);
  snprintf(p,sizeof p,"%s/round.json",base); long r=0; if(readf(p)>0){char*s=strstr(buf,"\"round\":");if(s)r=strtol(s+8,0,10);}
  snprintf(q,sizeof q,"%s/tasks.json",base); readf(q);
  snprintf(q,sizeof q,"%s/tasks",base); DIR*d=opendir(q); if(d){while(readdir(d));closedir(d);}
  if(tick) r++;
  snprintf(q,sizeof q,"%s/.round.json.tmp.%d",base,getpid()); FILE*f=fopen(q,"w");
  fprintf(f,"{\"round\": %ld, \"open\": %s, \"started\": []}\n",r,tick?"true":"false"); fclose(f); rename(q,p);
  if(!tick){snprintf(q,sizeof q,"%s/rounds.jsonl",base); f=fopen(q,"a"); fprintf(f,"{\"round\": %ld, \"ended\": []}\n",r); fclose(f);}
  printf(tick?"{\"round\": %ld, \"started\": []}\n":"{\"round\": %ld, \"ended\": []}\n",r); return 0;}
