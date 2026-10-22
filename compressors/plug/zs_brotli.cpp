/* -ma:brotli: brotli's one-shot API (default window and mode), as zpaq-std
   called it. See zs_codec.h. data(ZS_DATA_PREFIX) is the fixed data prefix that
   every -ma:brotli block starts with and ZPAQBROTLI reads (the static
   dictionary, the context table, the transforms, the dictionary sizes and
   constants), built from libbrotli's own tables. */
#include "zs_plugin.h"
#include <string.h>
#include <string>
extern "C" {
#include "../brotli/include/brotli/encode.h"
#include "../brotli/include/brotli/decode.h"
#include "../brotli/common/dictionary.h"
#include "../brotli/common/transform.h"
extern const uint8_t _kBrotliContextLookupTable[2048];
}

static const int ZPAQBROTLI_PREFIJO=126608;
static std::string zs_build_prefix() {
  static const unsigned K[220]={
    0,1,2,3,4,5,6,8,10,14,18,26,34,50,66,98,130,194,322,578,1090,2114,6210,22594,
    0,0,0,0,0,0,1,1,2,2,3,3,4,4,5,5,6,7,8,9,10,12,14,24,
    2,3,4,5,6,7,8,9,10,12,14,18,22,30,38,54,70,102,134,198,326,582,1094,2118,
    0,0,0,0,0,0,0,0,1,1,2,2,3,3,4,4,5,5,6,7,8,9,10,24,
    0,0,0,0,8,8,0,16,8,16,16,  0,8,0,8,0,8,16,0,16,8,16,
    1,5,9,13,17,25,33,41,49,65,81,97,113,145,177,209,241,305,369,497,753,1265,2289,4337,8433,16625,
    2,2,2,2,3,3,3,3,4,4,4,4,5,5,5,5,6,6,7,8,9,10,11,12,13,24,
    1,2,3,4,0,5,17,6,16,7,8,9,10,11,12,13,14,15,
    2,2,2,3,2,2,2,4,2,2,2,3,2,2,2,4,  0,4,3,2,0,4,3,1,0,4,3,2,0,4,3,5};
  const BrotliDictionary* d=BrotliGetDictionary();
  const BrotliTransforms* t=BrotliGetTransforms();
  std::string q(ZPAQBROTLI_PREFIJO, '\0');
  size_t o=0;
  memcpy(&q[o], d->data, 122784); o+=122784;
  memcpy(&q[o], _kBrotliContextLookupTable, 2048); o+=2048;
  memcpy(&q[o], t->prefix_suffix, t->prefix_suffix_size); o+=224;
  for (int i=0; i<50; i++) { q[o+2*i]=(char)(t->prefix_suffix_map[i]&255); q[o+2*i+1]=(char)(t->prefix_suffix_map[i]>>8); }
  o+=128;
  memcpy(&q[o], t->transforms, t->num_transforms*3); o+=384;
  memcpy(&q[o], d->size_bits_by_length, 32); o+=32;
  for (int i=0; i<32; i++) for (int k=0; k<4; k++) q[o+4*i+k]=(char)((d->offsets_by_length[i]>>(8*k))&255);
  o+=128;
  for (int i=0; i<220; i++) for (int k=0; k<4; k++) q[o+4*i+k]=(char)((K[i]>>(8*k))&255);
  o+=880;
  return q;
}
static const void* zs_data(int what, size_t* size) {
	static const std::string p = zs_build_prefix();	/* once, thread-safe */
	if (what != ZS_DATA_PREFIX)
		return NULL;
	*size = p.size();
	return p.data();
}

static size_t zs_bound(size_t n, int) {
	return BrotliEncoderMaxCompressedSize(n);
}
static long long zs_compress(const void* src, size_t n, void* dst, size_t cap, int level) {
	size_t len = cap;
	if (BrotliEncoderCompress(level, BROTLI_DEFAULT_WINDOW, BROTLI_DEFAULT_MODE, n, (const uint8_t*)src, &len, (uint8_t*)dst) != BROTLI_TRUE)
		return -1;
	return (long long)len;
}
static long long zs_decompress(const void* src, size_t n, void* dst, size_t cap, int) {
	size_t len = cap;
	if (BrotliDecoderDecompress(n, (const uint8_t*)src, &len, (uint8_t*)dst) != BROTLI_DECODER_RESULT_SUCCESS)
		return -1;
	return (long long)len;
}

ZS_DEFINE_CODEC(brotli, "brotli 1.2.1", 0, 11, zs_bound, zs_compress, zs_decompress, nullptr, zs_data)
