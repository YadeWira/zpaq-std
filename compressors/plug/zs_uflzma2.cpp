/* -ma:uflzma2: ultra-fast-lzma2.s one-shot API, as zpaq-std called it. See zs_codec.h. */
#include "zs_plugin.h"
#include "../uflzma2/uf-lzma2.h"

static size_t zs_bound(size_t n, int) {
	return UF2_compressBound(n);
}
static long long zs_compress(const void* src, size_t n, void* dst, size_t cap, int level) {
	const size_t r = UF2_compress(dst, cap, src, n, level);
	return UF2_isError(r) ? -1 : (long long)r;
}
static long long zs_decompress(const void* src, size_t n, void* dst, size_t cap, int) {
	const size_t r = UF2_decompress(dst, cap, src, n);
	return UF2_isError(r) ? -1 : (long long)r;
}

ZS_DEFINE_CODEC(uflzma2, "ultra-fast-lzma2 " UF2_VERSION_STRING, 1, UF2_maxCLevel(), zs_bound, zs_compress, zs_decompress, nullptr, nullptr)
