/* -ma:zxc: one zxc frame per block (zxc_compress, one thread, no checksum, zxc's
   default 512 KB blocks). See zs_codec.h. The library string starts with the
   format ("zxc format 9 "): zpaq-std decodes zxc9-tagged blocks natively only
   with a plugin of that format. */
#include "zs_plugin.h"
extern "C" {
#include "../zxc/include/zxc.h"
}

static size_t zs_bound(size_t n, int) {
	return (size_t)zxc_compress_bound(n);
}
static long long zs_compress(const void* src, size_t n, void* dst, size_t cap, int level) {
	zxc_compress_opts_t o = {};
	o.n_threads = 1;
	o.level = level;
	const int64_t r = zxc_compress(src, n, dst, cap, &o);
	return r > 0 ? (long long)r : -1;
}
static long long zs_decompress(const void* src, size_t n, void* dst, size_t cap, int) {
	zxc_decompress_opts_t o = {};
	o.n_threads = 1;
	const int64_t r = zxc_decompress(src, n, dst, cap, &o);
	return r >= 0 ? (long long)r : -1;
}

ZS_DEFINE_CODEC(zxc, "zxc format 9 (zxc 0.15.0)", 1, 7, zs_bound, zs_compress, zs_decompress, nullptr, nullptr)
