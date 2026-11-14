# ZPAQSYLZ4 and ZPAQSYLZ5: design notes

Two ZPAQL post-processors (PCOMP) for zpaq-std, generated from one source:

| | reads | for the plugin codec | config | code |
|---|---|---|---|---|
| ZPAQSYLZ4 | sylz v2 and v4 blocks | `sylz4` | `comp 0 0 8 PM 0` | 2361 bytes |
| ZPAQSYLZ5 | sylz v2, v3, v4 and v5 blocks | `sylz5` | `comp 0 0 12 PM 0` | 3234 bytes |

(ZPAQSYLZ3 is 4488 bytes.) ZPAQSYLZ4 has no Huffman code at all: a v3 or v5 block (bit 31 of its header) is
rejected. ZPAQSYLZ5 reads the literal chunk modes 0 and 2 in a v3 block and 0 and 3 in a v5 block; mode 1
(v3, never written since syc 0.2.14) is rejected, as in ZPAQSYLZ3.

The segment is `[original size: u32 LE][one sylz block]`, as for ZPAQSYLZ3.

## Files

| file | what |
|---|---|
| `sylz_src.py` | the decoder, in a subset of Python: the source of the ZPAQL **and** the model |
| `gen.py` | compiles it: `gen.py 4|5 [PH PM]` (config), `gen.py 4|5 body`, `gen.py 4|5 header`, `-d` first = DEBUG variant |
| `zref.py` | the Python model: runs `sylz_src.py` with ZPAQL's semantics (`-k` checks 32-bit overflow and indexes) |
| `tables.py` | SYLZ_TOKENS and SYLZ_TOKENS4 of syc v0.8.0 and the word the decoder keeps for each entry |
| `zpaqsylz4_body.h`, `zpaqsylz5_body.h` | `ZPAQSYLZ4_CUERPO`, `ZPAQSYLZ5_CUERPO` (made by `gen.py N header`) |
| `mkcont.c` | writes a segment with the plugin's real encoder (`../sylz.so`) |
| `zpaqsylz4`, `zpaqsylz5` | the preprocessor commands `zpaqd c` runs (they call mkcont) |
| `mkconts.sh`, `tests.py`, `run_tests.sh` | the validation; `myrun.log` is its last complete run |

`gen.py` is the compiler written for lz6seq's decoder (a Python subset to ZPAQL, with a tracker of what
A-D hold and jump relaxation), plus: a condition that is a constant keeps only the branch taken (how
`V5` and `DEBUG` select code), `copyout`, `ld16`, `loadtable`, and a hand-written entry. Model and ZPAQL
are the same source, so they cannot drift apart; what could differ is the compiler, and that is what
`zpaqd r` = model on about 12,700 damaged segments (and the 118 case runs, the DEBUG dumps, the runs
with an M that is too small) checks, besides `zpaqd r` = original on every real segment.

## The pm and ph formulas

```
int zpaqsylz4_pm(int64_t seg, int64_t orig) {      // orig is not used
  const int64_t need = seg + 65536;
  int pm = 17;
  while (pm < 31 && ((int64_t)1 << pm) < need) pm++;
  return pm;
}
int zpaqsylz5_pm(int64_t seg, int64_t orig) {      // orig is not used
  const int64_t need = seg + 131072;
  int pm = 17;                                      // (the loop makes it 18 at least)
  while (pm < 31 && ((int64_t)1 << pm) < need) pm++;
  return pm;
}
```

`seg` is the whole segment (4 + the block). M holds exactly:

- ZPAQSYLZ4: the segment, at 0, and a window of the last 65536 output bytes: `2^pm >= seg + 65536`.
- ZPAQSYLZ5: the same and a buffer of 65536 literals (one Huffman chunk): `2^pm >= seg + 131072`.

**The output is not kept in M** (ZPAQSYLZ3 needs `seg + 32 + 2 * orig`): a 64 MiB block that compresses to
21 MiB takes pm 25 (32 MiB) where ZPAQSYLZ3's layout takes pm 28 (256 MiB). Exact fit works (tested:
segment + 65536 = 2^17 and segment + 131072 = 2^18 to the byte). With pm 31 the segment can be
2^31 - 65536 (- 131072) bytes.

ph: 8 for ZPAQSYLZ4 (H = the 256 words of the token table, nothing else), 12 for ZPAQSYLZ5 (the table, 16
counters at 256, and the 2048-entry Huffman decoding table at 2048..4095). A larger ph works too; gen.py
refuses a smaller one.

If M is smaller than the formula says the program still ends and never leaves M (every index of M is
taken modulo its size by zpaq), but the output is garbage: tested, `zpaqd r` = model there too.

## Memory layout

M, 2^pm bytes:

```
0 .. n-1                         the segment: size (4), block header (4), tokens, [offset count], offsets,
                                 literals (v2, v4) or literal chunks (v3, v5)
2^pm - 131072 .. 2^pm - 65537    LBUF, ZPAQSYLZ5 only: the literals of the Huffman chunk in use
2^pm - 65536 .. 2^pm - 1         WIN: the last 65536 bytes of the output, a ring
```

The program does not know pm (the body is the same for every block). It addresses the top of M as
`0x7FFF0000 + i` (WIN) and `0x7FFE0000 + i` (LBUF): zpaq takes an index of M modulo its size, and
2^31 - 65536 is the last 64 KiB of M for every pm up to 31. No arithmetic on these addresses reaches
2^32 (the largest value computed is WEND = 0x80000000).

- Tokens, offsets and raw literals (v2, v4, and mode-0 chunks of v3, v5) are read where they are in the
  segment; nothing is copied before it is used.
- A Huffman chunk is decoded into LBUF when the sequences reach its first literal (not all chunks first, as
  the reference does), so the buffer is 65536 bytes whatever `litCount` is.
- A literal run or a match is copied in pieces that do not cross the end of the ring (nor, for literals, the
  end of the chunk): at most 3 pieces unless the run is longer than 64 KiB.

H: `0..255` the running token table. One word per token: bits 0-5 match length (63 = extended), bits 6-10
literal length (31 = extended), bits 11-12 where the distance comes from: 0 the offset stream, 1 the previous
distance, 2 the two bytes after the token (v2 and v3). A v2/v3 block loads SYLZ_TOKENS in that form, a v4/v5
block SYLZ_TOKENS4, so one loop decodes the sequences of all four formats; an update entry is converted when
it is read. The table is loaded for every block (code: 397 bytes for v2's, 547 for v4's: each entry from
the one before it, `a++` / `a+= N`, and runs of +1 as a loop). ZPAQSYLZ5 also: `256..271` codes per length,
then the next code of each length; `2048..4095` the decoding table (`length << 8 | symbol` for the next 11
bits).

## Registers

Every name of `sylz_src.py` is one R register; gen.py prints the map on stderr (36 registers in ZPAQSYLZ4,
63 in ZPAQSYLZ5). The ones that matter:

| name | |
|---|---|
| `n` | bytes of the segment (C when the segment ends) |
| `orig`, `hdr` | the original size, the block's first u32 |
| `c`, `cend`, `tend` | next token byte, end of the chunk, end of the token stream |
| `one`, `uflag` | a block of one chunk (v2, v3, or bit 29), its update flag (bit 28) |
| `op`, `oend` | the offset stream (v4, v5) |
| `lp`, `lend` | the literals at hand (in the segment, or in LBUF) |
| `lleft`, `p`, `hmode` | v3, v5: literals still in chunks, the next chunk, the Huffman mode allowed (2 or 3) |
| `o`, `wq` | bytes decoded, where the next one goes in the ring |
| `dist` | the distance (1 at the start of the block) |
| `ll`, `ml`, `e`, `x` | the sequence: lengths, table word, its offset kind |
| `last` | the output's last byte, held back |
| `fin` | 1 while the tail is copied |

**Nothing is assumed about the registers, M or H when a segment starts** (a zpaq block can hold several
segments and zpaq keeps everything between them): every register is set before it is read, the table is
loaded for each block, and C is set to 0 at the end. Tested in the model with random values in every
register, M and H before a segment, and with real archives of 13 and 152 segments in one block.

## How it runs

Each byte of the segment: `*c=a c++` (4 instructions with the test). At the end of the segment
(`a > 255`): `n = C`, then

1. `n < 8` or `orig >= 2^31`: reject. Read the header; load the table.
2. Find the three streams. v2/v3: tokens `8 .. 8 + ctrlLen`, then the literals. v4/v5: tokens, the offset
   count (in the header for a block of one chunk, else 1-5 bytes), offsets, literals. With bit 31 the
   literals are `litCount` and chunks; ZPAQSYLZ4 rejects there.
3. One loop, `while True`:
   - at the end of a chunk and not of the tokens: the next chunk's header (2 or 4 bytes; none in a block of
     one chunk), its update, its end;
   - at the end of the tokens: check the offsets are used up and that the literals left (at hand + in
     chunks) are exactly the bytes missing; they become a last literal run (`fin`);
   - else a token: table word, distance (new: 2 offset bytes; v2: the 2 bytes after the token; previous:
     nothing), the two extensions;
   - copy the literals (refilling from the next chunk when the ones at hand run out);
   - copy the match (`dist <= o`, `o + ml <= orig`).
4. Write the held-back last byte.

**The last byte of the output is only written when everything has been checked.** Without that, a block
whose damage shows after the last byte is decoded (offsets left over, a cut chunk header after the last
token, an update with a bad entry in a last empty chunk...) would give the complete output although the
block is bad. So: a rejected block always gives fewer bytes than its size (nothing if its size is 0), and
zpaq's SHA-1 reports it. This costs one compare per copied piece.

## Bounds: why it always ends, and never wraps

| loop | bounded by |
|---|---|
| the main loop | each turn takes a token byte, or a chunk header (2 bytes at least, or all the tokens left in a block of one chunk), or is the last |
| an extension (255-run) | the chunk's bytes; and its sum is checked against what is left of the output after every 255, so `sum <= orig - o + 255 < 2^31 + 255` |
| the offset count | 5 bytes: at shift 28 a byte over 15 is rejected and one under 128 ends it |
| an update | its count (1..256), checked against the token bytes left before the loop |
| a literal run, a match | pieces of at least 1 byte, `o + length <= orig` checked before |
| literal chunks | `lleft` (`<= orig`), each takes at least 1 |
| Huffman: counting, first codes, table | 16, 256, 11, 256 x (length <= 11 turns + 2048 >> length entries) |
| Huffman: symbols of a stream | its count, from the chunk's count (256..65536) |

Time is proportional to segment + orig for any input. Every value is below 2^32 without relying on a wrap:
`orig < 2^31`, positions are below `n`, `offCount <= 2^30` (checked against the bytes left before it is
doubled), a chunk's `n` is compared with `tend - c` before it is added, `count * 3 <= 768`. The model's
CHECK mode (`zref.py -k`) raises on any `+ - * <<` that leaves 32 bits, on a shift of 32 or more, on an
index outside H and on a copy that would wrap in M; all the good and bad cases and about 1500 real segments
run under it. Comparisons are unsigned in ZPAQL and every value compared is a non-negative number below
2^32 in the model, so they agree (pm 30 and 31 are run: the window is then above 2^30 in M).

A Huffman stream is read without checking its end byte by byte: past it the decoder reads what follows in
M (the next stream, or whatever is after the block: an index of M is always inside M), and after the
stream's last symbol `bits used > 8 * size` rejects the chunk. The symbols decoded that way went to LBUF and
are never used.

## What is rejected (the number is `fail(n)`, kept in `ferr` and written by the DEBUG variant)

| n | |
|---|---|
| 1 | a segment under 8 bytes |
| 2 | an original size of 2^31 or more |
| 3 | `ctrlLen` / `tokLen` past the block |
| 4 | a block of one chunk with the update flag and no token bytes |
| 5 | the offset count cut by the end of the block |
| 6 | an offset count over 32 bits (also: of more than 5 bytes) |
| 7 | more offsets than the bytes after the count |
| 8, 9 | v3, v5: no room for `litCount`; `litCount` 0 or over the original size |
| 10 | ZPAQSYLZ4: a v3 or v5 block |
| 11 | a chunk header cut by the end of the tokens |
| 12 | a chunk's `n` past the token stream |
| 13 | offsets left over |
| 14 | the tail: literals left != bytes missing |
| 15 | a new-offset token with no offset left |
| 16 | v2: the token stream ends inside a sequence |
| 17, 25 | a literal run / a match past the original size |
| 18 | a literal run past the literals |
| 19 | a distance over the bytes decoded (also for a match of 0, and the previous offset 1 at the start) |
| 20, 21 | an update with no count byte, or longer than the tokens left |
| 22, 23, 24 | an update entry with bits 12-15, literals 17..30, match 33..62 |
| 30, 31 | an extension past its chunk; an extension sum past the original size |
| 40, 41 | a code length over 11; lengths that are not a complete code |
| 42, 43 | a stream past the block; a stream whose codes end past its size |
| 50, 51 | a literal chunk past the block (its mode byte; a raw chunk's bytes) |
| 52 | a chunk mode other than 0 and the format's (2 in v3, 3 in v5; so mode 1 too) |
| 53, 54 | a Huffman chunk under 256 symbols; its header past the block |
| 55 | the chunks do not end where the block does |

On any of them: no more output, C = 0, halt.

## Against the reference (syc's tools/sylz_ref.py)

Same bytes for everything both accept. Differences, all on the strict side (the test `reference` counts
them on about 24,900 damaged blocks per variant and fails on any other):

1. a v3 block with a mode-1 literal chunk: the reference decodes it, ZPAQSYLZ5 rejects it (asked for);
2. ZPAQSYLZ4 rejects every v3 and v5 block (asked for);
3. an original size of 2^31 or more is rejected (the reference has no limit). The 2^29 limit the wiki
   allows a decoder to enforce on v4/v5 is **not** enforced: a larger block decodes if it is well formed;
4. a block of size 0 gives no output whether it is accepted or not (`C0 00 00 00` with size 0, the case
   `bad-v5-empty-header`, is rejected by the program, but nothing tells that from outside).

Nothing is laxer: no block the reference rejects is decoded. A rejected block's partial output may be
longer than what the reference would have produced before raising (it raises before returning anything);
the literal chunks are checked as the sequences reach them, not all first.

## Surprises, and what the cases do not cover

- **The 59 cases have no good block of one chunk with an update** (header bits 29 and 28 both set, token
  bytes after the update). My first version computed that chunk's length before its update instead of
  after and still passed all 59 cases; syc's vectors (`max-length-codes`, `generated-text`) and the real
  encoder (2393 chunks with an update) caught it. Worth a case in `tools/sylz_cases.py`.
- A complete code (Kraft sum = 2^11 with lengths 1..11) always has two symbols or more (one symbol gives at
  most 2^10), so "over at least two symbols" needs no separate check.
- The reference's "truncated offset count ... shift == 35" cannot happen: at shift 28 a byte over 15 is
  rejected and a byte under 128 ends the count. A count of 6 bytes is rejected as "over 32 bits".
- v4/v5 let the offset be read before the extensions (separate streams), v2 has it between the token and
  the extensions: reading it first in both is what lets one loop serve all four formats.
- A v2/v3 header has bits 28 and 29 inside `ctrlLen` (a control stream of 256 MiB or more): they are not
  flags there.
- `sylz5` never wrote a v3 block with a raw (mode 0) chunk on my data (its v3 blocks are small, one Huffman
  chunk); they are covered by `sylzec`'s output (362 chunks), syc's vectors (26) and one case.

## Limits

- original size below 2^31; segment at most 2^31 - 65536 (ZPAQSYLZ4) or 2^31 - 131072 (ZPAQSYLZ5) bytes;
- distances 1..65536 (the format's);
- v3 mode 1 is not read;
- tested with real blocks up to 212 MB in one segment (pm 28) and M up to pm 31 with small segments; a
  segment over 2^28 bytes was not run.

## Tests

`./run_tests.sh` rebuilds the headers, mkcont, syc's vectors (fpc, pure Pascal build of a copy of syc's
sources under tmp/) and the 8296 segments of the real encoder (kept under tmp/cont, 2.3 GB), then runs
the groups of `tests.py`; `myrun.log` has the last complete run. Groups: build, cases, vectors, encoder,
model, pm, e2e, corrupt, reference, speed.
