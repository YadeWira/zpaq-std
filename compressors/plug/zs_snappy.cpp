/* -ma:snappy: snappy's C API, as zpaq-std called it (it has no levels). See
   zs_codec.h. */
#include "zs_plugin.h"
extern "C" {
#include "../snappy/snappy-c.h"
}

static size_t zs_bound(size_t n, int) {
	return snappy_max_compressed_length(n);
}
static long long zs_compress(const void* src, size_t n, void* dst, size_t cap, int) {
	size_t len = cap;
	if (snappy_compress((const char*)src, n, (char*)dst, &len) != SNAPPY_OK)
		return -1;
	return (long long)len;
}
static long long zs_decompress(const void* src, size_t n, void* dst, size_t cap, int) {
	size_t len = cap;
	if (snappy_uncompress((const char*)src, n, (char*)dst, &len) != SNAPPY_OK)
		return -1;
	return (long long)len;
}

ZS_DEFINE_CODEC(snappy, "Snappy 1.3.1", 1, 2, zs_bound, zs_compress, zs_decompress, nullptr, nullptr)
