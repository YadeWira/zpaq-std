/* -ma:hs: heatshrink through its wrapper (compressors/hs/hs_wrapper.c), as
   zpaq-std called it. The window travels in the low 4 bits of the first byte.
   See zs_codec.h. */
#include "zs_plugin.h"
#include "../hs/hs_wrapper.h"

static size_t zs_bound(size_t n, int) {
	return n + 64;
}
static long long zs_compress(const void* src, size_t n, void* dst, size_t cap, int level) {
	size_t len = 0;
	if (hs_compress_wrapper((const uint8_t*)src, n, (uint8_t*)dst, cap, &len, level) != 0)
		return -1;
	return (long long)len;
}
static long long zs_decompress(const void* src, size_t n, void* dst, size_t cap, int) {
	size_t len = 0;
	if (hs_decompress_wrapper((const uint8_t*)src, n, (uint8_t*)dst, cap, &len) != 0)
		return -1;
	return (long long)len;
}

ZS_DEFINE_CODEC(hs, "heatshrink 0.4.1", 0, 2, zs_bound, zs_compress, zs_decompress, nullptr, nullptr)
