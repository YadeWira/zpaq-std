/* -ma:bzip2: libbzip2 1.0.8's buffer-to-buffer API, as zpaq-std called it.
   See zs_codec.h. */
#include "zs_plugin.h"
#include <stdio.h>
#include <stdlib.h>
extern "C" {
#include "../bzip2/bzlib.h"
}

static size_t zs_bound(size_t n, int) {
	return n + n / 100 + 1024;
}
static long long zs_compress(const void* src, size_t n, void* dst, size_t cap, int level) {
	if (n > 0x7FFFFFFF || cap > 0xFFFFFFFFu)
		return -1;
	unsigned int len = (unsigned int)cap;
	const int r = BZ2_bzBuffToBuffCompress((char*)dst, &len, (char*)src, (unsigned int)n, level, 0, 0);
	return r == BZ_OK ? (long long)len : -1;
}
static long long zs_decompress(const void* src, size_t n, void* dst, size_t cap) {
	if (n > 0xFFFFFFFFu || cap > 0x7FFFFFFF)
		return -1;
	unsigned int len = (unsigned int)cap;
	const int r = BZ2_bzBuffToBuffDecompress((char*)dst, &len, (char*)src, (unsigned int)n, 0, 0);
	return r == BZ_OK ? (long long)len : -1;
}

#ifdef ZS_PLUGIN
/* Built with BZ_NO_STDIO on Windows, libbzip2 reports an internal error through
   bz_internal_error(), which the program provides; a plugin provides its own. */
extern "C" void bz_internal_error(int errcode) {
	fprintf(stderr, "bzip2 internal error %d\n", errcode);
	abort();
}
#endif

ZS_DEFINE_CODEC(bzip2, "bzip2 1.0.8", 1, 9, zs_bound, zs_compress, zs_decompress, nullptr)
