/* -ma:deflate: libdeflate's raw deflate, as zpaq-std called it. See zs_codec.h. */
#include "zs_plugin.h"
#include "../libdeflate/libdeflate.h"

static size_t zs_bound(size_t n, int level) {
	struct libdeflate_compressor* c = libdeflate_alloc_compressor(level);
	if (!c)
		return 0;
	const size_t b = libdeflate_deflate_compress_bound(c, n);
	libdeflate_free_compressor(c);
	return b;
}
static long long zs_compress(const void* src, size_t n, void* dst, size_t cap, int level) {
	struct libdeflate_compressor* c = libdeflate_alloc_compressor(level);
	if (!c)
		return -1;
	const size_t r = libdeflate_deflate_compress(c, src, n, dst, cap);
	libdeflate_free_compressor(c);
	return r > 0 ? (long long)r : -1;
}
static long long zs_decompress(const void* src, size_t n, void* dst, size_t cap, int) {
	struct libdeflate_decompressor* d = libdeflate_alloc_decompressor();
	if (!d)
		return -1;
	size_t len = 0;
	const libdeflate_result r = libdeflate_deflate_decompress(d, src, n, dst, cap, &len);
	libdeflate_free_decompressor(d);
	return r == LIBDEFLATE_SUCCESS ? (long long)len : -1;
}

ZS_DEFINE_CODEC(deflate, "libdeflate " LIBDEFLATE_VERSION_STRING, 0, 12, zs_bound, zs_compress, zs_decompress, nullptr, nullptr)
