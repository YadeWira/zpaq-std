/* libzpaqstd called many times in one process: the same bytes each time, no memory or descriptor left behind.
   lib_loop <lib.so> <file> <rounds> [args of c...]   (build with -fsanitize=address to have LeakSanitizer) */
#define _GNU_SOURCE
#include <dirent.h>
#include <dlfcn.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
typedef int (*run_t)(int, char **, intptr_t, intptr_t, intptr_t);
static int quanti_fd(void)
{
	int n= 0;
	DIR *d= opendir("/proc/self/fd");
	struct dirent *e;
	while ((e= readdir(d)) != NULL)
		n++;
	closedir(d);
	return n;
}
static long rss_kb(void)
{
	long a= 0, b= 0;
	FILE *f= fopen("/proc/self/statm", "r");
	if (fscanf(f, "%ld %ld", &a, &b) != 2)
		b= 0;
	fclose(f);
	return b * (sysconf(_SC_PAGESIZE) / 1024);
}
static unsigned long long somma(const char *nome, long long *o_len)
{
	unsigned long long h= 1469598103934665603ULL;
	unsigned char buf[65536];
	FILE *f= fopen(nome, "rb");
	size_t r;
	*o_len= 0;
	if (!f)
		return 0;
	while ((r= fread(buf, 1, sizeof(buf), f)) > 0)
	{
		for (size_t i= 0; i < r; i++)
			h= (h ^ buf[i]) * 1099511628211ULL;
		*o_len+= (long long)r;
	}
	fclose(f);
	return h;
}
int main(int argc, char **argv)
{
	if (argc < 4)
		return 2;
	void *lib= dlopen(argv[1], RTLD_NOW);
	if (!lib)
	{
		fprintf(stderr, "%s\n", dlerror());
		return 2;
	}
	run_t run= (run_t)dlsym(lib, "zpaqstd_run");
	const char *(*ver)(void)= (const char *(*)(void))dlsym(lib, "zpaqstd_version");
	printf("%s\n", ver());
	const int giri= atoi(argv[3]);
	char z[256], o[256];
	snprintf(z, sizeof(z), "%s.zpaq.tmp", argv[2]);
	snprintf(o, sizeof(o), "%s.out.tmp", argv[2]);
	long long l0, lz0= -1, l1, lz;
	const unsigned long long h0= somma(argv[2], &l0);
	unsigned long long hz0= 0;
	char *cargs[16]= {"c"};
	int nc= 1;
	for (int i= 4; (i < argc) && (nc < 16); i++)
		cargs[nc++]= argv[i];
	char *dargs[2]= {"d", getenv("LIBD")};
	const int nd= dargs[1] ? 2 : 1;
	int male= 0;
	const int fd0= quanti_fd();
	long rss1= 0;
	for (int g= 0; g < giri; g++)
	{
		int rc= run(nc, cargs, open(argv[2], O_RDONLY), open(z, O_WRONLY | O_CREAT | O_TRUNC, 0644), dup(2));
		const unsigned long long hz= somma(z, &lz);
		if (g == 0)
			hz0= hz, lz0= lz;
		int rd= run(nd, dargs, open(z, O_RDONLY), open(o, O_WRONLY | O_CREAT | O_TRUNC, 0644), dup(2));
		const unsigned long long h1= somma(o, &l1);
		if (rc || rd || (h1 != h0) || (l1 != l0) || (hz != hz0) || (lz != lz0))
		{
			male++;
			printf("round %d: c rc=%d d rc=%d same back=%d same archive=%d\n", g, rc, rd, (h1 == h0) && (l1 == l0), hz == hz0);
		}
		if (g == 1)
			rss1= rss_kb();
	}
	printf("rounds %d bad %d | %lld -> %lld bytes | archive %016llx | descriptors %d -> %d | RSS after round 2: %ld KiB, at the end: %ld KiB\n", giri, male, l0, lz0, hz0, fd0, quanti_fd(), rss1, rss_kb());
	unlink(z);
	unlink(o);
	return male != 0;
}
