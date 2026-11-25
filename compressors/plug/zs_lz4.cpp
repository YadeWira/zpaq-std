/* -ma:lz4, -ma:lz4hc, -ma:lz4f (and what -m6 wrote): LZ4's block API. See zs_codec.h.
   The level carries the mode, as zpaq-std's lz4_encode() packs it:
     level = mode * 0x1000000 + (value + 0x100000)
     mode 0: LZ4_compress_default; 1: LZ4_compress_fast, value = acceleration;
     mode 2: LZ4_compress_HC, value = level. */
#include "zs_plugin.h"
#include "../lz4/lz4.h"
#include "../lz4/lz4hc.h"

static size_t zs_bound(size_t n, int) {
	if (n > (size_t)LZ4_MAX_INPUT_SIZE)
		return 0;
	return (size_t)LZ4_compressBound((int)n);
}
static long long zs_compress(const void* src, size_t n, void* dst, size_t cap, int level) {
	if (n > (size_t)LZ4_MAX_INPUT_SIZE || cap > 0x7FFFFFFF)
		return -1;
	const int mode = level / 0x1000000, value = level % 0x1000000 - 0x100000;
	int r;
	if (mode == 2)
		r = LZ4_compress_HC((const char*)src, (char*)dst, (int)n, (int)cap, value);
	else if (mode == 1)
		r = LZ4_compress_fast((const char*)src, (char*)dst, (int)n, (int)cap, value);
	else
		r = LZ4_compress_default((const char*)src, (char*)dst, (int)n, (int)cap);
	return r > 0 ? (long long)r : -1;
}
static long long zs_decompress(const void* src, size_t n, void* dst, size_t cap, int) {
	if (n > 0x7FFFFFFF || cap > 0x7FFFFFFF)
		return -1;
	const int r = LZ4_decompress_safe((const char*)src, (char*)dst, (int)n, (int)cap);
	return r < 0 ? -1 : (long long)r;
}

ZS_DEFINE_CODEC(lz4, "LZ4 " LZ4_VERSION_STRING, 1, 12, zs_bound, zs_compress, zs_decompress, nullptr, nullptr)
