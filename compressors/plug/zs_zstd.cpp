/* -ma:zstd: zstd's one-shot API, as zpaq-std called it. See zs_codec.h. */
#include "zs_plugin.h"
#include "../zstd/zstd.h"

static size_t zs_bound(size_t n, int) {
	return ZSTD_compressBound(n);
}
static long long zs_compress(const void* src, size_t n, void* dst, size_t cap, int level) {
	const size_t r = ZSTD_compress(dst, cap, src, n, level);
	return ZSTD_isError(r) ? -1 : (long long)r;
}
static long long zs_decompress(const void* src, size_t n, void* dst, size_t cap) {
	const size_t r = ZSTD_decompress(dst, cap, src, n);
	return ZSTD_isError(r) ? -1 : (long long)r;
}

ZS_DEFINE_CODEC(zstd, "zstd " ZSTD_VERSION_STRING, 1, 22, zs_bound, zs_compress, zs_decompress, nullptr)
