/* -ma:lz5, lz5hc and lz5f: lz5-ex's one-shot API, as zpaq-std called it. See
   zs_codec.h. One plugin serves the three names; the level carries the mode:
     1..15     -ma:lz5   (fast below 5, HC from 5 on)
     101..115  -ma:lz5hc (always HC)
     201..215  -ma:lz5f  (always fast)
   zpaq-std passes the original size minus 17 as cap: a larger output is no use. */
#include "zs_plugin.h"
extern "C" {
#include "../lz5/lz5.h"
#include "../lz5/lz5hc.h"
}

static size_t zs_bound(size_t n, int) {
	if (n > 0x7E000000)
		return 0;
	const int b = LZ5_compressBound((int)n);
	return b > 0 ? (size_t)b : 0;
}
static long long zs_compress(const void* src, size_t n, void* dst, size_t cap, int level) {
	if (n > 0x7E000000 || cap > 0x7FFFFFFF)
		return -1;
	const int mode = level / 100, lvl = level % 100;
	const bool hc = (mode == 1) || (mode == 0 && lvl >= 5);
	const int r = hc ? LZ5_compress_HC((const char*)src, (char*)dst, (int)n, (int)cap, lvl)
	                 : LZ5_compress_fast((const char*)src, (char*)dst, (int)n, (int)cap, lvl);
	return r > 0 ? (long long)r : -1;
}
static long long zs_decompress(const void* src, size_t n, void* dst, size_t cap, int) {
	if (n > 0x7FFFFFFF || cap > 0x7FFFFFFF)
		return -1;
	const int r = LZ5_decompress_safe((const char*)src, (char*)dst, (int)n, (int)cap);
	return r >= 0 ? (long long)r : -1;
}

ZS_DEFINE_CODEC(lz5, "lz5-ex 1.5.2", 1, 15, zs_bound, zs_compress, zs_decompress, nullptr, nullptr)
