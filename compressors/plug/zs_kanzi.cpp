/* -ma:kanzi: kanzi through zpaq-std's wrapper (compressors/kanzi/kanzi_zpaqstd.cpp),
   as zpaq-std called it. decompress()'s param is the level, read from the block
   header; query(ZS_QUERY_FIRST_PRE) gives the length of the stream's first
   pre-transform, which sizes the ZPAQL decoder's memory. See zs_codec.h. */
#include "zs_plugin.h"
#include "../kanzi/kanzi_zpaqstd.h"

static size_t zs_bound(size_t n, int) {
	return n + n / 8 + 65536;
}
static long long zs_compress(const void* src, size_t n, void* dst, size_t cap, int level) {
	const size_t r = kanzi_zs_compress(src, n, dst, cap, level);
	return r > 0 ? (long long)r : -1;
}
static long long zs_decompress(const void* src, size_t n, void* dst, size_t cap, int param) {
	const int r = kanzi_zs_decompress(src, n, dst, cap, param);
	if (r == 2)
		return ZS_ERR_MEMORY;
	return r == 0 ? (long long)cap : -1;
}
static long long zs_query(int what, const void* src, size_t n) {
	if (what != ZS_QUERY_FIRST_PRE)
		return -1;
	return (long long)kanzi_zs_first_pre(src, n);
}

ZS_DEFINE_CODEC(kanzi, "kanzi 2.6.0", 1, 9, zs_bound, zs_compress, zs_decompress, zs_query, nullptr)
