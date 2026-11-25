/* -ma:lzav (and what -m7 wrote): LZAV. See zs_codec.h.
   Compressing: level 0 lzav_compress_default, 1 lzav_compress_hi.
   Decompressing, the level is the format of the stream: 3 or 4, the decoder of that
   format (the room given is the block's: a stream that ends "shorter than the room",
   LZAV_E_DSTLEN, is a good one, and the bytes written are returned); 0, lzav_decompress
   with the exact size (the blocks tagged lzav, up to 1.x). */
#include "zs_plugin.h"
#define LZAV_NS_CUSTOM zs_lzav_ns
#include "../lzav/lzav.h"

static size_t zs_bound(size_t n, int level) {
	if (n > 0x7FFFFFFF)
		return 0;
	const int b = level == 1 ? zs_lzav_ns::lzav_compress_bound_hi((int)n) : zs_lzav_ns::lzav_compress_bound((int)n);
	return b > 0 ? (size_t)b : 0;
}
static long long zs_compress(const void* src, size_t n, void* dst, size_t cap, int level) {
	if (n > 0x7FFFFFFF || cap > 0x7FFFFFFF)
		return -1;
	const int r = level == 1 ? zs_lzav_ns::lzav_compress_hi(src, dst, (int)n, (int)cap)
	                         : zs_lzav_ns::lzav_compress_default(src, dst, (int)n, (int)cap);
	return r > 0 ? (long long)r : -1;
}
static long long zs_decompress(const void* src, size_t n, void* dst, size_t cap, int format) {
	if (n > 0x7FFFFFFF || cap > 0x7FFFFFFF)
		return -1;
	if (format == 0) {
		const int r = zs_lzav_ns::lzav_decompress(src, dst, (int)n, (int)cap);
		return r < 0 ? -1 : (long long)r;
	}
	if (format != 3 && format != 4)
		return -1;
	int written = 0;
	const int r = format == 4 ? zs_lzav_ns::lzav_decompress_4(src, dst, (int)n, (int)cap, &written)
	                          : zs_lzav_ns::lzav_decompress_3(src, dst, (int)n, (int)cap, &written);
	if (r >= 0)
		return (long long)r;
	if (r == zs_lzav_ns::LZAV_E_DSTLEN)
		return (long long)written;
	return -1;
}

ZS_DEFINE_CODEC(lzav, "LZAV " LZAV_VER_STR, 0, 1, zs_bound, zs_compress, zs_decompress, nullptr, nullptr)
