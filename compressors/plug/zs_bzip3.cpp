/* -ma:bzip3: libbz3's one-shot API, as zpaq-std called it: the level is the
   block size in units of 100 KB. See zs_codec.h. */
#include "zs_plugin.h"
#include <stdint.h>
extern "C" {
#include "../bzip3/libbz3.h"
}

static size_t zs_bound(size_t n, int) {
	return bz3_bound(n);
}
static long long zs_compress(const void* src, size_t n, void* dst, size_t cap, int level) {
	size_t len = cap;	/* in: the buffer's capacity, as libbz3.h asks */
	if (bz3_compress((uint32_t)(level * 100000), (const uint8_t*)src, (uint8_t*)dst, n, &len) != 0)
		return -1;
	return (long long)len;
}
static long long zs_decompress(const void* src, size_t n, void* dst, size_t cap, int) {
	size_t len = cap;
	if (bz3_decompress((const uint8_t*)src, (uint8_t*)dst, n, &len) != 0)
		return -1;
	return (long long)len;
}

ZS_DEFINE_CODEC(bzip3, "bzip3 1.5.4", 1, 9, zs_bound, zs_compress, zs_decompress, nullptr, nullptr)
