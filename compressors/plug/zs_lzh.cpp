/* -ma:lzh: LZHAM's memory API, as zpaq-std called it: a 1 MB dictionary and no
   helper threads (the output must not depend on them); level 1..4 is
   LZHAM_COMP_LEVEL_FASTEST..UBER. See zs_codec.h. */
#include "zs_plugin.h"
#include <string.h>
extern "C" {
#include "../lzham/lzham.h"
}

static size_t zs_bound(size_t n, int) {
	return n + n / 8 + 1024;
}
static long long zs_compress(const void* src, size_t n, void* dst, size_t cap, int level) {
	lzham_compress_params p;
	memset(&p, 0, sizeof(p));
	p.m_struct_size = sizeof(p);
	p.m_level = (lzham_compress_level)(LZHAM_COMP_LEVEL_FASTEST + level - 1);
	p.m_dict_size_log2 = 20;
	p.m_max_helper_threads = 0;
	size_t len = cap;
	if (lzham_compress_memory(&p, (lzham_uint8*)dst, &len, (const lzham_uint8*)src, n, NULL) != LZHAM_COMP_STATUS_SUCCESS)
		return -1;
	return (long long)len;
}
static long long zs_decompress(const void* src, size_t n, void* dst, size_t cap, int) {
	lzham_decompress_params p;
	memset(&p, 0, sizeof(p));
	p.m_struct_size = sizeof(p);
	p.m_dict_size_log2 = 20;
	size_t len = cap;
	if (lzham_decompress_memory(&p, (lzham_uint8*)dst, &len, (const lzham_uint8*)src, n, NULL) != LZHAM_DECOMP_STATUS_SUCCESS)
		return -1;
	return (long long)len;
}

ZS_DEFINE_CODEC(lzh, "LZHAM 1.0", 1, 4, zs_bound, zs_compress, zs_decompress, nullptr, nullptr)
