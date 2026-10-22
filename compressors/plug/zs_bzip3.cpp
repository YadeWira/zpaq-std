/* -ma:bzip3: libbz3's one-shot API, as zpaq-std called it: the level is the
   block size in units of 100 KB. See zs_codec.h. */
#include "zs_plugin.h"
#include <stdint.h>
extern "C" {
#include "../bzip3/libbz3.h"
}

/* bz3_bound() is n + n/50 + 32, but bz3_compress can write up to 4 bytes more
   than that for incompressible inputs of 64 to about 1,500 bytes (13 bytes of
   frame header, 8 per block, and the block's own), past the caller's buffer.
   Seen with codec_check under AddressSanitizer (bzip3 1.5.4 and 1.5.5). zpaq-std's
   blocks end with the list of fragments, whose zeros kept them under the bound in
   every test, but the margin makes it certain. */
static size_t zs_bound(size_t n, int) {
	return bz3_bound(n) + 64;
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

ZS_DEFINE_CODEC(bzip3, "bzip3 1.5.5", 1, 9, zs_bound, zs_compress, zs_decompress, nullptr, nullptr)
