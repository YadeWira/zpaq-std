/* -ma:lzfse: LZFSE's buffer API, as zpaq-std called it (it has no levels).
   See zs_codec.h. */
#include "zs_plugin.h"
#include <new>
#include "../lzfse/lzfse.h"

static size_t zs_bound(size_t n, int) {
	return n + n / 8 + 1024;
}
static long long zs_compress(const void* src, size_t n, void* dst, size_t cap, int) {
	unsigned char* scratch = new (std::nothrow) unsigned char[lzfse_encode_scratch_size()];
	if (!scratch)
		return -1;
	const size_t r = lzfse_encode_buffer((uint8_t*)dst, cap, (const uint8_t*)src, n, scratch);
	delete[] scratch;
	return r > 0 ? (long long)r : -1;
}
static long long zs_decompress(const void* src, size_t n, void* dst, size_t cap, int) {
	return (long long)lzfse_decode_buffer((uint8_t*)dst, cap, (const uint8_t*)src, n, NULL);
}

ZS_DEFINE_CODEC(lzfse, "lzfse-ex 1.0.3", 0, 1, zs_bound, zs_compress, zs_decompress, nullptr, nullptr)
