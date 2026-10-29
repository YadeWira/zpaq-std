/* -ma:bz2: bz2-ng, libbz2's buffer-to-buffer API, as zpaq-std called it. The
   Makefile bundles bz2-ng with its BZ2_* functions renamed bz2ng_BZ2_*, so that
   it links next to libbzip2. See zs_codec.h. */
#include "zs_plugin.h"
#include <stdio.h>
#include <stdlib.h>
extern "C" {
#include "../bzip2/bzlib.h"
BZ_EXTERN int BZ_API(bz2ng_BZ2_bzBuffToBuffCompress)(char* dest, unsigned int* destLen,
                                                     char* source, unsigned int sourceLen,
                                                     int blockSize100k, int verbosity, int workFactor);
BZ_EXTERN int BZ_API(bz2ng_BZ2_bzBuffToBuffDecompress)(char* dest, unsigned int* destLen,
                                                       char* source, unsigned int sourceLen,
                                                       int small, int verbosity);
}

static size_t zs_bound(size_t n, int) {
	return n + n / 100 + 1024;
}
static long long zs_compress(const void* src, size_t n, void* dst, size_t cap, int level) {
	if (n > 0x7FFFFFFF || cap > 0xFFFFFFFFu)
		return -1;
	unsigned int len = (unsigned int)cap;
	const int r = bz2ng_BZ2_bzBuffToBuffCompress((char*)dst, &len, (char*)src, (unsigned int)n, level, 0, 0);
	return r == BZ_OK ? (long long)len : -1;
}
static long long zs_decompress(const void* src, size_t n, void* dst, size_t cap, int) {
	if (n > 0xFFFFFFFFu || cap > 0x7FFFFFFF)
		return -1;
	unsigned int len = (unsigned int)cap;
	const int r = bz2ng_BZ2_bzBuffToBuffDecompress((char*)dst, &len, (char*)src, (unsigned int)n, 0, 0);
	return r == BZ_OK ? (long long)len : -1;
}

#ifdef ZS_PLUGIN
/* bz2-ng is built with BZ_NO_STDIO and reports an internal error through
   bz_internal_error(), which the program provides; a plugin provides its own. */
extern "C" void bz_internal_error(int errcode) {
	fprintf(stderr, "bz2-ng internal error %d\n", errcode);
	abort();
}
#endif

ZS_DEFINE_CODEC(bz2, "bz2-ng 517948e", 1, 9, zs_bound, zs_compress, zs_decompress, nullptr, nullptr)
