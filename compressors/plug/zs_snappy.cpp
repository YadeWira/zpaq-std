/* -ma:snappy: snappy's C API. Levels 1 and 2 since snappy 1.3.0 (the C API had
   none before, so up to zpaq-std 1.5.0 every level wrote level 1). The format is
   the same at both levels: ZPAQSNAPPY decodes either. See zs_codec.h. */
#include "zs_plugin.h"
extern "C" {
#include "../snappy/snappy-c.h"
}

static size_t zs_bound(size_t n, int) {
	return snappy_max_compressed_length(n);
}
static long long zs_compress(const void* src, size_t n, void* dst, size_t cap, int level) {
	size_t len = cap;
	if (level < SNAPPY_MIN_COMPRESSION_LEVEL) level = SNAPPY_MIN_COMPRESSION_LEVEL;
	if (level > SNAPPY_MAX_COMPRESSION_LEVEL) level = SNAPPY_MAX_COMPRESSION_LEVEL;
	if (snappy_compress_with_level((const char*)src, n, level, (char*)dst, &len) != SNAPPY_OK)
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
