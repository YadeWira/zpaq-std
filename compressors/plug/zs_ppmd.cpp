/* -ma:ppmd: PPMd var.H through its wrapper (compressors/ppmd/ppmd_wrapper.c), as
   zpaq-std called it: the level is the model order (2..32), and from bit 8 on
   the model memory in MB (0 there: 64 MB; -ma:ppmd:<order>:<MB>, since 2.13.1).
   decompress()'s param is the order, and the memory in MB from bit 8 on, both
   read from the block header. See zs_codec.h. */
#include "zs_plugin.h"
#include "../ppmd/ppmd_wrapper.h"

static size_t zs_bound(size_t n, int) {
	return n + n / 2 + 4096;
}
static long long zs_compress(const void* src, size_t n, void* dst, size_t cap, int level) {
	unsigned order = (unsigned)level & 255, mem_mb = (unsigned)level >> 8;
	if (order < 2) order = 2;
	if (order > 32) order = 32;
	if (mem_mb == 0) mem_mb = 64;
	if (mem_mb > 1024) return -1;
	const size_t r = ppmd_compress((const unsigned char*)src, n, (unsigned char*)dst, cap, order, mem_mb);
	return r > 0 ? (long long)r : -1;
}
static long long zs_decompress(const void* src, size_t n, void* dst, size_t cap, int param) {
	const unsigned order = (unsigned)param & 255, mem_mb = (unsigned)param >> 8;
	if (!ppmd_decompress((const unsigned char*)src, n, (unsigned char*)dst, cap, order, mem_mb))
		return -1;
	return (long long)cap;
}

static long long zs_query(int what, const void*, size_t) {
	return what == ZS_QUERY_LEVEL_MEMORY ? 1 : -1;
}

ZS_DEFINE_CODEC(ppmd, "PPMd var.H (7-Zip)", 2, 32, zs_bound, zs_compress, zs_decompress, zs_query, nullptr)
