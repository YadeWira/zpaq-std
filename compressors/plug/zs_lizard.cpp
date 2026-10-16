/* -ma:lizard: Lizard's one-shot API, as zpaq-std called it. See zs_codec.h. */
#include "zs_plugin.h"
extern "C" {
#include "../lizard/lizard_compress.h"
#include "../lizard/lizard_decompress.h"
}

static size_t zs_bound(size_t n, int) {
	if (n > 0x7E000000)
		return 0;
	const int b = Lizard_compressBound((int)n);
	return b > 0 ? (size_t)b : 0;
}
static long long zs_compress(const void* src, size_t n, void* dst, size_t cap, int level) {
	if (n > 0x7E000000 || cap > 0x7FFFFFFF)
		return -1;
	const int r = Lizard_compress((const char*)src, (char*)dst, (int)n, (int)cap, level);
	return r > 0 ? (long long)r : -1;
}
static long long zs_decompress(const void* src, size_t n, void* dst, size_t cap, int) {
	if (n > 0x7FFFFFFF || cap > 0x7FFFFFFF)
		return -1;
	const int r = Lizard_decompress_safe((const char*)src, (char*)dst, (int)n, (int)cap);
	return r >= 0 ? (long long)r : -1;
}

ZS_DEFINE_CODEC(lizard, "Lizard " LIZARD_VERSION_STRING, 10, 49, zs_bound, zs_compress, zs_decompress, nullptr, nullptr)
