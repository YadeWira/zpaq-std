/* zs_example: a codec plugin for zpaq-std's -mae/-mat and -sae/-sat, as small as it gets.
   Four codecs in one file (zpaqstd_codecs_v1): "rle", a byte run-length coder that
   gives its ZPAQL decoder; "rlenz", the same coder without one (for -mat); "rlea",
   whose decoder takes $3 from query(); and "rles", which tells zpaq-std that its
   decoder handles several segments in one block (-sae/-sat put consecutive files
   it takes together).
   Build:  cc -O2 -shared -fPIC -I../../compressors/plug zs_example.c -o example.so
           x86_64-w64-mingw32-gcc -O2 -shared -I../../compressors/plug zs_example.c -o example.dll
   Use:    put it in codecs/ next to zpaq-std, then
           zpaq-std a test.zpaq files -mat:example:rle:1
           zpaq-std a test.zpaq files -sat:example:rle+1     (only the files it takes)
   Stream: a control byte c; c < 128: c+1 literal bytes follow; c >= 128: the next
   byte repeats c-125 times (3..130). zpaq-std puts the original size (u32) first.
   zpaq-std, 2026. MIT licence. */
#include <string.h>
#include "zs_codec.h"

static size_t ex_bound(size_t n, int level) { (void)level; return n + n / 128 + 16; }

static long long ex_compress(const void* src, size_t n, void* dst, size_t cap, int level)
{
	const unsigned char* s = (const unsigned char*)src;
	unsigned char* d = (unsigned char*)dst;
	size_t i = 0, o = 0;
	(void)level;
	while (i < n) {
		size_t run = 1;
		while (i + run < n && run < 130 && s[i + run] == s[i]) run++;
		if (run >= 3) {
			if (o + 2 > cap) return ZS_ERR_DATA;
			d[o++] = (unsigned char)(run + 125); d[o++] = s[i]; i += run;
		} else {
			size_t lit = 0;    /* literals up to the next run of 3 */
			while (i + lit < n && lit < 128 && !(i + lit + 2 < n && s[i + lit] == s[i + lit + 1] && s[i + lit] == s[i + lit + 2])) lit++;
			if (o + 1 + lit > cap) return ZS_ERR_DATA;
			d[o++] = (unsigned char)(lit - 1); memcpy(d + o, s + i, lit); o += lit; i += lit;
		}
	}
	return (long long)o;
}

static long long ex_decompress(const void* src, size_t n, void* dst, size_t cap, int param)
{
	const unsigned char* s = (const unsigned char*)src;
	unsigned char* d = (unsigned char*)dst;
	size_t i = 0, o = 0;
	(void)param;
	while (i < n) {
		const unsigned c = s[i++];
		if (c < 128) {
			if (i + c + 1 > n || o + c + 1 > cap) return ZS_ERR_DATA;
			memcpy(d + o, s + i, c + 1); i += c + 1; o += c + 1;
		} else {
			if (i >= n || o + c - 125 > cap) return ZS_ERR_DATA;
			memset(d + o, s[i++], c - 125); o += c - 125;
		}
	}
	return o == cap ? (long long)o : ZS_ERR_DATA;
}

/* The decoder in ZPAQL: skips the 4-byte size, then decodes byte by byte.
   r1: 0 = a control byte, 2 = literals, 3 = the byte of a run; r2 counts the
   size bytes, r3 what is left. */
#define EX_ZPAQL_BODY \
	"hcomp\n" \
	"  halt\n" \
	"pcomp zs_example_rle ;\n" \
	"  a> 255 if a=0 r=a 1 r=a 2 halt endif\n" \
	"  c=a\n" \
	"  a=r 2 a< 4 if a++ r=a 2 halt endif\n" \
	"  a=r 1\n" \
	"  a== 0 if\n" \
	"    a=c a< 128 if a++ r=a 3 a= 2 r=a 1 else a-= 125 r=a 3 a= 3 r=a 1 endif\n" \
	"  else a== 2 if\n" \
	"    a=c out a=r 3 a-- r=a 3 a== 0 if a=0 r=a 1 endif\n" \
	"  else\n" \
	"    do a=c out a=r 3 a-- r=a 3 a> 0 while\n" \
	"    a=0 r=a 1\n" \
	"  endif endif\n" \
	"  halt\n" \
	"end\n"
static const char ex_zpaql[] = "comp 0 0 0 0 0\n" EX_ZPAQL_BODY;
/* rlea: the same decoder, given through ZS_DATA_ZPAQL_ARGS: its H size is $3, which
   query(ZS_QUERY_ZPAQL_ARGS) gives for each block (here always 7: 128 words, unused).
   It shows how a codec whose decoder needs memory by block asks for just enough. */
static const char ex_zpaql_args[] = "comp 0 0 $3 0 0\n" EX_ZPAQL_BODY;

/* The codec's card, shown by codecinfoex: "key=value" lines. */
static const char ex_info[] =
	"author=zpaq-std\n"
	"repo=https://github.com/YadeWira/zpaq-std (tools/plugin_example)\n"
	"license=MIT\n"
	"version=1.0\n"
	"format=byte run-length: control byte c < 128: c+1 literals; c >= 128: next byte c-125 times\n"
	"notes=an example plugin, as small as it gets\n";

static const void* ex_data(int what, size_t* size)
{
	if (what == ZS_DATA_INFO) { *size = sizeof(ex_info); return ex_info; }
	if (what != ZS_DATA_ZPAQL) return NULL;
	*size = sizeof(ex_zpaql);
	return ex_zpaql;
}
static const void* ex_data_args(int what, size_t* size)	/* rlea: the card, ZPAQL with $3 */
{
	if (what == ZS_DATA_INFO) { *size = sizeof(ex_info); return ex_info; }
	if (what != ZS_DATA_ZPAQL_ARGS) return NULL;	/* NULL for ZS_DATA_ZPAQL: older zpaq-std cannot fill $3 */
	*size = sizeof(ex_zpaql_args);
	return ex_zpaql_args;
}
static long long ex_query(int what, const void* src, size_t n)
{
	(void)src; (void)n;
	return what == ZS_QUERY_ZPAQL_ARGS ? 7 : -1;
}
/* rles: the decoder starts afresh at the end of each segment (a > 255: r1 = r2 = 0,
   so it skips the next 4-byte size), so it handles several segments in one block */
static long long ex_query_seg(int what, const void* src, size_t n)
{
	(void)src; (void)n;
	return what == ZS_QUERY_SEGMENTS ? 1 : -1;
}
static const void* ex_data_nz(int what, size_t* size)	/* rlenz: the card, no ZPAQL */
{
	if (what != ZS_DATA_INFO) return NULL;
	*size = sizeof(ex_info);
	return ex_info;
}

static const zs_codec ex_rle   = { ZS_CODEC_ABI, "rle",   "zs_example rle 1.0",   1, 1, ex_bound, ex_compress, ex_decompress, NULL, ex_data };
static const zs_codec ex_rlenz = { ZS_CODEC_ABI, "rlenz", "zs_example rlenz 1.0", 1, 1, ex_bound, ex_compress, ex_decompress, NULL, ex_data_nz };
static const zs_codec ex_rlea  = { ZS_CODEC_ABI, "rlea",  "zs_example rlea 1.0",  1, 1, ex_bound, ex_compress, ex_decompress, ex_query, ex_data_args };
static const zs_codec ex_rles  = { ZS_CODEC_ABI, "rles",  "zs_example rles 1.0",  1, 1, ex_bound, ex_compress, ex_decompress, ex_query_seg, ex_data };

ZS_CODEC_EXPORT const zs_codec* zpaqstd_codecs_v1(int i)
{
	return i == 0 ? &ex_rle : i == 1 ? &ex_rlenz : i == 2 ? &ex_rlea : i == 3 ? &ex_rles : NULL;
}

/* -sae/-sat: a "format" for the example: a file where at least half of the bytes
   are in runs of 3 or more, so that RLE pays. It looks only at the bytes. */
ZS_CODEC_EXPORT int zpaqstd_detect_v1(const char* codec, const void* src, size_t n)
{
	const unsigned char* s = (const unsigned char*)src;
	size_t i = 0, inrun = 0;
	if (strcmp(codec, "rle") != 0 && strcmp(codec, "rlenz") != 0 && strcmp(codec, "rlea") != 0 && strcmp(codec, "rles") != 0) return 0;
	while (i < n) {
		size_t run = 1;
		while (i + run < n && s[i + run] == s[i]) run++;
		if (run >= 3) inrun += run;
		i += run;
	}
	return n > 0 && inrun * 2 >= n;
}
