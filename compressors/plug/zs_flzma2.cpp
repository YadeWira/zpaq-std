/* -ma:flzma2: fast-lzma2's one-shot API, as zpaq-std called it. See zs_codec.h. */
#include "zs_plugin.h"
#include "../fl2/fast-lzma2.h"

static size_t zs_bound(size_t n, int) {
	return FL2_compressBound(n);
}
static long long zs_compress(const void* src, size_t n, void* dst, size_t cap, int level) {
	const size_t r = FL2_compress(dst, cap, src, n, level);
	return FL2_isError(r) ? -1 : (long long)r;
}
static long long zs_decompress(const void* src, size_t n, void* dst, size_t cap, int) {
	const size_t r = FL2_decompress(dst, cap, src, n);
	return FL2_isError(r) ? -1 : (long long)r;
}

ZS_DEFINE_CODEC(flzma2, "fast-lzma2 " FL2_VERSION_STRING, 1, FL2_maxCLevel(), zs_bound, zs_compress, zs_decompress, nullptr, nullptr)

#if defined(ZS_PLUGIN) && defined(_WIN32)
/* On Windows fast-lzma2's util.c is left out (it is POSIX), and fl2_threading.c
   still references UTIL_countPhysicalCores; the program provides it, and so does
   the plugin. One thread, as zpaq-std compresses each block with one. */
extern "C" int UTIL_countPhysicalCores(void) { return 1; }
#endif
