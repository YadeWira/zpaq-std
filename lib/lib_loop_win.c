/* zpaqstd.dll called many times in one process (Windows): lib_loop_win <dll> <file> <rounds> [args of c...] */
#include <windows.h>
#include <psapi.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef int(__cdecl *run_t)(int, char **, intptr_t, intptr_t, intptr_t);
typedef const char *(__cdecl *ver_t)(void);
static HANDLE apri(const char *n, int scrivi)
{
	return CreateFileA(n, scrivi ? GENERIC_WRITE : GENERIC_READ, FILE_SHARE_READ, NULL, scrivi ? CREATE_ALWAYS : OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
}
static HANDLE errori(void)
{
	HANDLE h= INVALID_HANDLE_VALUE;
	DuplicateHandle(GetCurrentProcess(), GetStdHandle(STD_ERROR_HANDLE), GetCurrentProcess(), &h, 0, FALSE, DUPLICATE_SAME_ACCESS);
	return h;
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
#include <malloc.h>
static int heapbad(const char *dove, int g)
{
	HANDLE hh[64];
	DWORD n= GetProcessHeaps(64, hh);
	int bad= 0;
	for (DWORD i= 0; i < n && i < 64; i++)
		if (!HeapValidate(hh[i], 0, NULL))
			bad++;
	if (bad && getenv("LIBHEAP"))
		printf("HEAP BAD %s round %d (%d of %lu heaps)\n", dove, g, bad, (unsigned long)n);
	return bad;
}
static HMODULE g_lib= NULL;
static LONG CALLBACK veh(EXCEPTION_POINTERS *e)
{
	const DWORD c= e->ExceptionRecord->ExceptionCode;
	if ((c != 0xC0000374) && (c != 0xC0000005) && (c != 0xC0000409))
		return EXCEPTION_CONTINUE_SEARCH;
	void *st[48];
	USHORT n= RtlCaptureStackBackTrace(0, 48, st, NULL);
	printf("EXCEPTION %08lx at %p, dll base %p, exe base %p\n", (unsigned long)c, e->ExceptionRecord->ExceptionAddress, (void *)g_lib, (void *)GetModuleHandle(NULL));
	for (USHORT i= 0; i < n; i++)
	{
		HMODULE m= NULL;
		char nome[260]= "?";
		if (GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT, (LPCSTR)st[i], &m) && m)
			GetModuleFileNameA(m, nome, sizeof(nome));
		const char *b= strrchr(nome, '\\');
		printf("  #%d %s+0x%llx\n", i, b ? b + 1 : nome, (unsigned long long)((char *)st[i] - (char *)m));
	}
	return EXCEPTION_CONTINUE_SEARCH;
}
static void stato(DWORD *o_handles, size_t *o_kb)
{
	PROCESS_MEMORY_COUNTERS pmc;
	*o_handles= 0;
	GetProcessHandleCount(GetCurrentProcess(), o_handles);
	GetProcessMemoryInfo(GetCurrentProcess(), &pmc, sizeof(pmc));
	*o_kb= pmc.WorkingSetSize / 1024;
}
int main(int argc, char **argv)
{
	if (argc < 4)
		return 2;
	setvbuf(stdout, NULL, _IONBF, 0);
	printf("loading\n");
	if (getenv("LIBVEH"))
		AddVectoredExceptionHandler(1, veh);
	HMODULE lib= LoadLibraryA(argv[1]);
	g_lib= lib;
	printf("loaded\n");
	if (!lib)
	{
		printf("LoadLibrary failed: %lu\n", GetLastError());
		return 2;
	}
	run_t run= (run_t)GetProcAddress(lib, "zpaqstd_run");
	ver_t ver= (ver_t)GetProcAddress(lib, "zpaqstd_version");
	if (!run || !ver)
	{
		printf("exports missing\n");
		return 2;
	}
	printf("%s\n", ver());
	const int giri= atoi(argv[3]);
	char z[512], o[512];
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
	DWORD hh0= 0, hh1= 0, hh2= 0;
	size_t kb0= 0, kb1= 0, kb2= 0;
	stato(&hh0, &kb0);
	for (int g= 0; g < giri; g++)
	{
		if (getenv("LIBV")) printf("c...\n");
		int rc= run(nc, cargs, (intptr_t)apri(argv[2], 0), (intptr_t)apri(z, 1), (intptr_t)errori());
		if (getenv("LIBV")) printf("c done %d\n", rc);
		const unsigned long long hz= somma(z, &lz);
		if (g == 0)
			hz0= hz, lz0= lz;
		if (getenv("LIBHEAP")) heapbad("after c", g);
		int rd= 0;
		unsigned long long h1= h0;
		l1= l0;
		if (!getenv("LIBNOD"))
		{
			rd= run(nd, dargs, (intptr_t)apri(z, 0), (intptr_t)apri(o, 1), (intptr_t)errori());
			h1= somma(o, &l1);
		}
		if (getenv("LIBHEAP")) heapbad("after d", g);
		if (rc || rd || (h1 != h0) || (l1 != l0) || (hz != hz0) || (lz != lz0))
		{
			male++;
			printf("round %d: c rc=%d d rc=%d same back=%d same archive=%d\n", g, rc, rd, (h1 == h0) && (l1 == l0), hz == hz0);
		}
		if (g == 1)
			stato(&hh1, &kb1);
	}
	stato(&hh2, &kb2);
	printf("rounds %d bad %d | %lld -> %lld bytes | archive %016llx | handles %lu, %lu after round 2, %lu at the end | working set %lu KiB after round 2, %lu KiB at the end\n", giri, male, l0, lz0, hz0, (unsigned long)hh0, (unsigned long)hh1, (unsigned long)hh2, (unsigned long)kb1, (unsigned long)kb2);
	DeleteFileA(z);
	DeleteFileA(o);
	if (getenv("LIBSLEEP"))
		Sleep(atoi(getenv("LIBSLEEP")));
	if (getenv("LIBFREE"))
		FreeLibrary(lib);
	return male != 0;
}
