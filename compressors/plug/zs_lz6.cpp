/* -ma:lz6: lz6's one-shot API with a 4 MB window (2^22), as zpaq-std called it.
   Level 0 is the fast compressor, 1..15 the HC levels. See zs_codec.h. */
#include "zs_plugin.h"
extern "C" {
#include "../lz6/lz6.h"
#include "../lz6/lz6hc.h"
}

static size_t zs_bound(size_t n, int) {
	if (n > 0x7E000000)
		return 0;
	const int b = LZ6_compressBound((int)n);
	return b > 0 ? (size_t)b : 0;
}
static long long zs_compress(const void* src, size_t n, void* dst, size_t cap, int level) {
	if (n > 0x7E000000 || cap > 0x7FFFFFFF)
		return -1;
	const int r = level <= 0 ? LZ6_compress_fast_window((const char*)src, (char*)dst, (int)n, (int)cap, 1, 22)
	                         : LZ6_compress_HC_window((const char*)src, (char*)dst, (int)n, (int)cap, level, 22);
	return r > 0 ? (long long)r : -1;
}
static long long zs_decompress(const void* src, size_t n, void* dst, size_t cap, int) {
	if (n > 0x7FFFFFFF || cap > 0x7FFFFFFF)
		return -1;
	const int r = LZ6_decompress_safe((const char*)src, (char*)dst, (int)n, (int)cap);
	return r >= 0 ? (long long)r : -1;
}

ZS_DEFINE_CODEC(lz6, "lz6 v1.6.14-pre", 0, 15, zs_bound, zs_compress, zs_decompress, nullptr, nullptr)
