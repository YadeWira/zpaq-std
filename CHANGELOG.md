### [1.8.0] - 2026-10-25

**`-ma:sylzec`** (experimental), **`-franztime`**, PJA 0.0.4 with **`pjax`** for `-sa`, a **bounds-checked libbsc decoder**, syc v0.4.2 (sylz and sylzec in one plugin) and lz6 1.7.0.

#### `-ma:sylzec`: sylz with Huffman-coded literals (experimental)

```bash
zpaq-std a backup.zpaq /data -ma:sylzec        # level 1
zpaq-std a backup.zpaq /data -ma:sylzec:9
```

- **What it is:** sylz's format v3, from [syc](https://github.com/YadeWira/syc) v0.4.2: the same LZ as `-ma:sylz`, with the literals Huffman-coded. On Silesia (203 MB): 80.7 MB at level 1 against sylz's 94.6 MB (−14.7%), and 71.4 MB at level 9 against 76.5 MB (−6.7%). It compresses slower than sylz (level 1: 2.4 s against 1.6 s with 8 threads).
- **Portable:** every block carries ZPAQSYLZ3 (`compressors/zpaqsylz3/`, with its reference decoder `ref3.py`), so any zpaq extracts it. It reads format v3, and v2 when v3 would not be smaller.
- **Install:** Free Pascal, so a plugin only. It is in the same file as sylz: `codecs/sylz.dll` or `sylz.so`, in the `extra-codecs` download.
- **Experimental:** its compression and levels may change (00603). Archives already written stay readable: the format is frozen under this tag.

#### `-franztime`: what zpaq-std used

At the end of any command, to stderr: wall time, CPU (user, kernel, average cores), memory (peak and final), page faults and I/O, as Franco Corbelli's [franztime](https://github.com/fcorbelli/franztime) reports for a program it runs. zpaq-std measures itself, so it works on Linux too. On Windows it starts on Windows 7 (the memory call is resolved at run time).

#### `-sa`: PJA 0.0.4 and `pjax` (still experimental, not recommended yet)

```bash
zpaq-std a photos.zpaq /photos -sa            # PJA's family: pjax, pja, pjals
zpaq-std a photos.zpaq /photos -sa:pjals      # one codec only
```

- **`pjax`:** JPEG that needs PJA's format v6: MPO and Ultra HDR photos (big JPEGs after the first image's end), 12-bit JPEG, a height in a DNL, a DRI without restart markers. On two 3D-camera MPOs (19.2 MB) it gives 73–74%. Its ZPAQL decoder is 57,709 bytes; any zpaq extracts its blocks.
- **The family:** a plugin file's name now stands for all its codecs: `-sa` and `-sa:pja` use pjax, pja and pjals, in that order (the same blocks as `-sae:pja:pjax+2:pja+2:pjals+2`). `-sa:pjax` and `-sa:pjals` pick one.
- **pja and pjals:** byte for byte those of 1.7.0 (PJA 0.0.1). On the 79 JPEG and JPEG-LS files of our test corpus pjax takes nothing big enough to pay its decoder, and the archive is that of 1.7.0's size.
- **Older versions:** zpaq-std 1.7.0 with PJA 0.0.1's plugin, and 1.6.0, run the pjax blocks' ZPAQL and read them correctly.
- `-sa` now warns that it is experimental (00737).

#### libbsc: a bounds-checked decoder (`-ma:bsc`)

libbsc 3.4.0 trusts the sizes inside a block, and its Adler-32s only stop accidental damage. Fuzzing real `-ma:bsc` blocks under AddressSanitizer and UBSan found writes past the output, reads past the input, unbounded loops, an unchecked block table and index, and the inverse sort transform following links outside the block. zpaq-std now carries its own patch: every one of those cases ends as a clean "data corrupt" error. The encoder is untouched, so `-ma:bsc` writes the very bytes of 1.7.0, and ZPAQBSC is unchanged. Details: `compressors/bsc/PATCHES`. The idea and some seeds came from tovyCT, another agent of this lab.

#### Codec updates

| Codec | Version | What changes for zpaq-std |
|---|---|---|
| sylz | syc v0.4.2 | One plugin file with both codecs (sylz and sylzec); sylz writes the very bytes of before, and 1.7.0 loads sylz from the new file. |
| `-ma:lz6` | lz6 1.7.0 | lz6's first stable release. It fixes a pointer that wrapped at low buffer addresses (32-bit without ASLR), which could give another (valid) stream in about 1% of runs, and a 1-byte over-read in its decoder. At normal addresses `-ma:lz6` writes the very bytes of before, levels 0 to 15. |
| PJA | 0.0.4 | pjax, above. |

#### Downloads

As in 1.7.0: the full program, `extra-codecs.zip` (sylz, now with sylzec, and pja) and `plugins.zip`, per platform, plus `THIRD-PARTY-LICENSES.txt` and `SHA256SUMS.txt`.

#### Known differences between x86 and x64

Both read everything the other writes, but a few levels compress differently on 32-bit Windows (inherited, not new in 1.8.0): `-ma:lz6:0` (from LZ4's fast mode), and `-ma:sylz` at levels 0 and 1, about 20% bigger on x86 (the same as in 1.7.0).

#### Checked

- **libbsc patch:** every crashing case found (ours and tovyCT's seeds, with libbsc's static, adaptive and fast coders) ends as "data corrupt" with no sanitizer report, and 2,400,000 fuzzed blocks gave no report. `-ma:bsc` at levels 1, 3, 4, 6, 7 and 9, with `-m1` and `-m5` blocks, writes the very bytes of 1.7.0, and 1.7.0's archives read.
- **sylzec:** `suite_sylz` 8/8 for sylz and 8/8 for sylzec (plugin, ZPAQL, zpaq 7.15); ZPAQSYLZ3 against its reference decoder on 220 test vectors; sylz from the unified plugin writes the very bytes of the previous one.
- **PJA 0.0.4:** vendored from its tag (`v0.0.4`, commit `ceae7c7`, the tarball checked by its SHA-256), unmodified. `suite_sa` 16/16: `-sa`, `-sa:pja` and `-sae:pja:pjax+2:pja+2:pjals+2` write the same archive, which extracts with and without the plugin and with zpaq 7.15, and `-sa:pja:pjals` is refused. The 79 JPEG and JPEG-LS files of the corpus extract identically with the plugin, without it and with zpaq 7.15.
- **lz6 1.7.0:** `-ma:lz6` levels 0 to 15 write the same bytes as before.
- **Windows 7 x64 and x86**, release binaries and the extra-codecs DLLs:
  - `-ma:lzh:1`, `-ma:lzfse`, `-ma:hs:1`, `-ma:lz6` (0, 9, 15), `-ma:bsc` (1, 9) and `-m1`: 36/36 extractions identical in Windows, and the archives made there extract on Linux with zpaq 7.15, zpaqfranz, 1.7.0 and 1.8.0.
  - sylz and sylzec at levels 0 and 10, with and without the DLL: 30/30.
  - `-sa` and `-sat` with pjax, pja and pjals: x64 and x86 write the same archive. The 79-file corpus and two MPOs taken by pjax extract identically in Windows, and on Linux with zpaq 7.15, 1.6.0, 1.7.0 with PJA 0.0.1's plugin, and 1.8.0 with and without the plugin.
  - `-mae`/`-mat`: 12/12; `-sae`/`-sat` with the example plugin: 16/16.
  - `-franztime` on `a` and `t`, x64 and x86.
- **Full test battery:** every suite has 0 cases to review; golden archives: 0 unexpected failures; `difftest` against 1.7.0: 182 comparisons, 0 divergences.

### [1.7.0] - 2026-10-23

**JPEG and JPEG-LS with `-sa`** (**experimental, not recommended yet**): zpaq-std's first codecs for specific formats, from [PJA](https://github.com/YadeWira/PJA) 0.0.1. Also several files per block for these codecs, and codec updates: syc v0.2.10, heatshrink-ex 0.7.0, fast-lzma2 1.1.2 and ultra-fast-lzma2 1.6.4.

#### `-sa`: JPEG and JPEG-LS, losslessly (experimental)

> **Experimental: not recommended yet.** PJA is new. Its archives open in any zpaq, but until it has had more use, keep another copy of what you archive with `-sa`. zpaq-std 1.7.0 does not say so when `-sa` runs; the next version warns.

```bash
zpaq-std a photos.zpaq /photos -sa                   # pja and pjals, with their defaults
zpaq-std a photos.zpaq /photos -sa:pja+2 -ma:zstd    # only JPEG; the rest with zstd
```

- **What it compresses:** `pja` takes JPEG (baseline, progressive and arithmetic-coded) and `pjals` takes JPEG-LS. Both rebuild the original byte for byte.
- **How files are chosen:** by their contents, never by name or extension. It works on top of any `-m`/`-ma`, and everything the codecs do not take is compressed as usual. `-sa` alone uses both codecs.
- **Install:** PJA is written in Free Pascal, so it ships as a plugin. Put the `codecs/` folder of the `extra-codecs` download, which has `pja.dll` or `pja.so`, next to zpaq-std. The `plugins` download has it too.
- **Portable archives:** every block carries PJA's ZPAQL decoder, so **any zpaq extracts the archive without the plugin**. Without it, extraction is slow, because the decoder is big. zpaq-std with the plugin decodes natively.
- **Safety:** every block is decoded back by the plugin before it is written. A block that does not come back identical is compressed as `-m` says.
- **Compatibility:** `-sa` writes the very same blocks as `-sae:pja:pja+2:pjals+2`, so zpaq-std 1.4.0 to 1.6.0 read them too.
- **Size:** on 79 JPEG and JPEG-LS files of the test corpus (22 MB), the archive is 19.5 MB, against 21.5 MB with `-m1`.

#### Several files per block (`-sa`, `-sae`, `-sat`)

Every block of a codec for specific formats carries the codec's ZPAQL decoder, and PJA's are about 60 KB. That is often more than a small photo saves.

- **Grouping:** when a codec's decoder can start afresh at the end of each segment, zpaq-std now puts consecutive files that codec takes into one block, one segment each. The decoder is written once per block instead of once per file.
- **Result:** on the corpus above, 1.9% smaller than one file per block. With many small photos the difference is much larger: 12.8 MB down to 8.1 MB in PJA's own test.
- **Older versions:** these blocks have a new tag, `zpaqstd-sm<e|t>:`. zpaq-std 1.4.0 to 1.6.0 do not know it, so even with the plugin they run the block's ZPAQL instead of their native decoder, and they read the archive correctly.
- **Plugin authors:** a codec opts in by answering 1 to `query(ZS_QUERY_SEGMENTS)`, new in `compressors/plug/zs_codec.h`. One that does not gets one file per block, byte for byte as in 1.6.0. The example plugin has a codec that does, `rles`.

#### Codec updates

| Codec | Version | What changes for zpaq-std |
|---|---|---|
| sylz | syc v0.2.10 | Levels 9 and 10 compress better and faster (Silesia, level 9: 36.37% → 36.04%). Format v2 is the same, so ZPAQSYLZ reads it as before. Plugin only, in `extra-codecs`. |
| `-ma:hs` | heatshrink-ex 0.7.0 | 0.6.0 and 0.7.0 change only heatshrink-ex's command line tool. The library is the same, and the archives are byte for byte those of 1.6.0. |
| `-ma:flzma2` | fast-lzma2 1.1.2 | A level above the maximum now clamps to it instead of silently giving the default. zpaq-std already clamped the level before calling it, so its archives do not change. |
| `-ma:uflzma2` | ultra-fast-lzma2 1.6.4 | The same fix as fast-lzma2. The archives do not change. |

#### Downloads

As in 1.6.0: the full program, `extra-codecs.zip` and `plugins.zip`, per platform, plus `THIRD-PARTY-LICENSES.txt` and `SHA256SUMS.txt`.

- `extra-codecs.zip` has the plugin-only codecs: sylz and, new, pja.
- `plugins.zip` has every codec as a plugin.
- THIRD-PARTY-LICENSES has PJA's licence and its notices: IJG for the arithmetic-coded JPEG, and CharLS for JPEG-LS.

#### Checked

- **PJA 0.0.1:** vendored from its tag (`v0.0.1`, commit `0776d32`, the tarball checked by its SHA-256), unmodified, and built by zpaq-std's Makefile. The plugin built here writes the very archive that PJA's own build writes.
- **`-sa`:**
  - `test/testlab/suite_sa.sh`: 15/15. This includes `-sa` on JPEG and JPEG-LS copies of corpus files, picked by their contents, which writes the same archive as `-sae:pja:pja+2:pjals+2` and extracts with and without the plugin and with zpaq 7.15. Five cases cover several files per block, including zpaq-std 1.6.0 with the plugin and one file extracted from the middle of a block.
  - 79 JPEG and JPEG-LS files of the corpus: every file back identical with zpaq-std 1.7.0 with and without the plugin, with 1.6.0 and the plugin, and with zpaq 7.15.
- **Codec updates:** `-ma:hs` (levels 0–2), `-ma:flzma2` (1, 5, 10, 11) and `-ma:uflzma2` (1, 5, 11, 12) write the very bytes of the previous build. sylz: `suite_sylz` 8/8, and levels 8–10 extract identically with zpaq 7.15.
- **Windows 7 x64 and x86**, release binaries and the extra-codecs DLLs:
  - `-sa` and `-sat` with pja: x64 and x86 write the same archive (8 JPEGs in one block, ZPAQL OK). The archives extract identically in Windows, and on Linux with zpaq 7.15, 1.6.0 and 1.7.0: 15/15 files each.
  - `-ma:lzh:1`, `-ma:lzh:4`, `-ma:lzfse`, `-ma:hs:1`, `-ma:lz6:15` and `-m1`: 24/24 extractions identical.
  - sylz with the DLLs: 15/15.
  - `-mae`/`-mat`: 12/12.
  - `-sae`/`-sat` with the example plugin: 16/16.
  - PJA's own test, on Windows 10 x64 and x86 with 38 files (JPEG of every kind, MPO, JPEG-LS of every interleave and near-lossless): 76/76 identical on each.
- **Full test battery:**
  - every suite has 0 cases to review;
  - golden archives: 0 unexpected failures;
  - `difftest` against 1.6.0: 182 comparisons, 0 divergences.

### [1.6.0] - 2026-10-23

`-ma:lzh` moves to LZHAM 1.0 (lzham-ex) with a new portable decoder. `-ma:lzfse` and `-ma:hs` move to maintained forks that write the same streams. Also lz6 v1.6.14-pre, syc v0.2.8 for sylz, and plugin decoders sized per block.

#### `-ma:lzh`: LZHAM 1.0, through lzham-ex 1.0.2

**zpaq-std's LZHAM was not LZHAM 1.0.** codecinfo, the README and the source comments all said it was, but the sources came from LZHAM's older "alpha" line (`LZHAM_DLL_VERSION` 0x1008, with polar codes). Its format is not compatible with LZHAM 1.0 in either direction. LZHAM 1.0 now comes from [lzham-ex](https://github.com/YadeWira/lzham-ex), the maintained fork of LZHAM 1.0.

- **New archives:** `-ma:lzh` writes LZHAM 1.0 blocks, tagged `lzh10`. Each block carries a new decoder written for this format, **ZPAQLZHAM10**. It is smaller than the old one (17.5 KB instead of 23.7) and faster in other zpaqs: 32–94 MB/s with a JIT, 2.7–8.5 without, against 5–50 and 0.4–4. zpaq 7.15, zpaqfranz and zpaq-std 1.5.1 extract them.
- **Archives from 1.5.1 and earlier** still extract with 1.6.0. lzham-ex cannot read the alpha format, so zpaq-std no longer decodes those blocks natively. It runs the ZPAQLZHAM decoder each block carries, as any other zpaq does, which is slower.
- **Size:** about the same. On 100 files of the test corpus, 0.07% smaller at level 1 and 0.59% bigger at level 4. The alpha format chose among 64 literal tables by the previous bytes; 1.0 uses one.
- **Levels:** codecinfo said level 4 was LZHAM's "uber" level. Levels 1 to 4 are LZHAM's fastest, faster, default and **better**.

#### `-ma:lzfse`: lzfse-ex 1.0.3

[lzfse-ex](https://github.com/YadeWira/lzfse-ex) is a maintained fork of Apple's LZFSE, which has had no release since 2017.

- It fixes a read past the input in the decoder on damaged data, inherited from Apple's code and found with zpaq-std's `codec_check`.
- It also fixes an undefined shift in the encoder.
- The stream is the same: `-ma:lzfse` writes the very bytes of 1.5.1, and ZPAQLZFSE does not change.

#### `-ma:hs`: heatshrink-ex 0.5.0

[heatshrink-ex](https://github.com/YadeWira/heatshrink-ex) is a maintained fork of heatshrink 0.4.1, unchanged upstream since 2015.

- It fixes a crash on empty input, a loop in the window-15 encoder, and the decoder with an exactly sized buffer.
- The stream is the same: every `-ma:hs` level writes the very bytes of 1.5.1, and ZPAQHS does not change.

#### lz6 and sylz

- **lz6 v1.6.14-pre** (and v1.6.13-pre before it): lz6's changes are in its newer "seq" engine. The portable profile that `-ma:lz6` writes is untouched: the same bytes as 1.5.1.
- **sylz from syc v0.2.8:** levels 4 to 8 use lz4hc's parser, with an x86-64 assembly match search, and compress a little better (Silesia: level 4 38.80% instead of 39.35%, level 8 36.38% instead of 36.60%). Format v2 is the same, so ZPAQSYLZ reads it as before. As always, sylz is a plugin only, in `extra-codecs.zip`.

#### Plugins (`-mae`, `-mat`, `-sae`, `-sat`)

- **Decoders sized per block.** A plugin's ZPAQL decoder can take `$3`, `$4` and `$5`, which the codec fills for each block through the new `query(ZS_QUERY_ZPAQL_ARGS)`. A decoder whose memory depends on the data then asks for just enough, instead of a fixed worst case. Such a decoder is given through `data(ZS_DATA_ZPAQL_ARGS)`. zpaq-std 1.4.0 to 1.5.1 cannot fill `$3`..`$5`, so they see no decoder at all and never write a block with the wrong sizes. See `compressors/plug/zs_codec.h` and the `rlea` codec of the example plugin.
- **The decoder now counts in the no-gain check.** Every external block carries its ZPAQL decoder. When the decoder was larger than what the codec saved, the block came out larger than `-m` would have made it. Now such a block falls back to `-m`. On 44 real JPEGs with a JPEG plugin, the archive went from 30.1 to 29.4 MB.

#### Downloads

As in 1.5.1: the full program, `extra-codecs.zip` (the plugin-only codecs, sylz) and `plugins.zip` (every codec as a plugin), per platform; `THIRD-PARTY-LICENSES.txt` and `SHA256SUMS.txt`.

#### Checked

- **ZPAQLZHAM10:** 400 lzham-ex streams (100 corpus files up to 12 MB, plus random data, zeros, runs, empty and one-byte inputs, × levels 1–4) decode identically with zpaqd 7.15. Its Python reference matches lzham-ex's decoder and lzham-ex's own reference.
- **`-ma:lzh`** at levels 1–4: new archives extract identically with zpaq 7.15, zpaqfranz, 1.5.1 and 1.6.0, and 1.5.1's archives (alpha format) with 1.6.0.
- **lzham-ex, lzfse-ex and heatshrink-ex:** `codec_check` under AddressSanitizer and UBSan (exact-size buffers, damaged input). lzham-ex: 46,426 blocks; lzfse-ex: 23,146; heatshrink-ex: about 69,000. 0 memory errors.
- **`-ma:lz6`** at levels 0–15, `-ma:lzfse` and `-ma:hs`: byte for byte the archives of 1.5.1. **`-ma:sylz`** at levels 3–8 extracts identically with zpaq 7.15.
- **Windows 7 x64 and x86**, release binaries:
  - `-ma:lzh:1`, `-ma:lzh:4`, `-ma:lzfse`, `-ma:hs:1`, `-ma:lz6:15` and `-m1`: 24/24 extractions identical, and what Windows wrote extracts on Linux with zpaq 7.15, zpaqfranz, 1.5.1 and 1.6.0;
  - `-ma:lzh` archives from 1.5.1: identical;
  - sylz with the extra-codecs DLLs: 15/15;
  - `-mae`/`-mat`: 12/12;
  - `-sae`/`-sat`: 16/16.
- **Full test battery:**
  - every suite has 0 cases to review;
  - golden archives: 0 unexpected failures;
  - `difftest` against 1.5.1: 182 comparisons, 0 divergences.

### [1.5.1] - 2026-10-22

fast-lzma2 1.1.1, snappy 1.3.1 with its level 2 as the default, and `codecinfo <codec>`.

#### `-ma:flzma2`: fast-lzma2 1.1.1

fast-lzma2 now comes from the `fast-lzma2/` directory of [ultra-fast-lzma2](https://github.com/YadeWira/ultra-fast-lzma2), where Conor McCarthy's 1.0.1 is maintained with the fixes found while fuzzing ultra-fast-lzma2: in the decoder, the match finder and the thread pool, and for small inputs.

- Until now zpaq-std used 1.0.1 with a patch of its own that carried three of those decoder fixes. In 1.1.1, `lzma2_dec.c` is byte for byte the patched one, so the patch is gone.
- 1.1.0 is not used: its `lzma2_dec.c` lacked those fixes. `codec_check` under AddressSanitizer caught it, and ultra-fast-lzma2 published 1.1.1 the same day.
- `-ma:flzma2` writes the very bytes of 1.5.0.

#### `-ma:snappy`: snappy 1.3.1, and level 2 by default

- snappy 1.3.1 fixes an overflow in the decompressor on malformed input. Since 1.2.2 it also fixes a data corruption when the compressed size exceeds 4 GB.
- **Levels now work.** snappy's C API has had levels only since 1.3.0, so until now every `-ma:snappy` level wrote level 1. **The default is now 2**, which made the test corpus about 4% smaller, with the same decompression speed.
- The format is the same at both levels. ZPAQSNAPPY, zpaq 7.15 and zpaq-std 1.5.0 all extract level 2, and `-ma:snappy:1` writes the very bytes of 1.5.0.

#### `codecinfo <codec>`

`codecinfo zstd` showed the general help instead of the codec. Now `codecinfo <codec>` shows that codec's card, the same as `codecinfoex <codec>`. The codec can be a `-ma` name, an external plugin file (all its codecs) or `file:codec`. `h codecinfoex` has its own help, the command list includes `codecinfoex`, and the `-ma` help points to `codecinfo`.

#### Downloads

As in 1.5.0: the full program, `extra-codecs.zip` (the plugin-only codecs, sylz) and `plugins.zip` (every codec as a plugin), per platform; `THIRD-PARTY-LICENSES.txt` and `SHA256SUMS.txt`.

#### Checked

- fast-lzma2 1.1.1: `codec_check` under AddressSanitizer and UBSan (exact-size buffers, damaged input), 700 real files: 69,285 blocks, 0 failures (1.1.0, by the same test, read past its input on damaged blocks). `-ma:flzma2` at levels 1, 3, 5, 7 and 10, with `-m1`, `-m5` and `-m16` blocks: byte for byte the archives of 1.5.0.
- snappy 1.3.1, the same test: 22,789 blocks, 0 failures. `-ma:snappy:1`, also with `-m16` blocks, writes the archives of 1.5.0. Level 2 extracts identically with zpaq 7.15, zpaq-std 1.5.0 and 1.5.1.
- `codecinfo <codec>`: `test/testlab/suite_codecinfo.sh`, now 7/7.
- Windows 7 x64 and x86, release binaries:
  - `-ma:flzma2:5`, `-ma:flzma2:10`, `-ma:snappy` (level 2), `-ma:snappy:1` and `-m1`: 20/20 extractions identical, and what Windows wrote extracts on Linux with zpaq 7.15, zpaqfranz, 1.5.0 and 1.5.1;
  - sylz with the extra-codecs DLLs: 15/15;
  - `-mae`/`-mat`: 12/12;
  - `-sae`/`-sat`: 16/16.
- Full test battery:
  - every suite has 0 cases to review;
  - golden archives: 0 unexpected failures;
  - `difftest` against 1.5.0: the only divergences are the 5 `-ma:snappy` cases, now level 2 by default and smaller; each version reads the other's archives.

### [1.5.0] - 2026-10-22

Codec updates, two of them security fixes: **brotli 1.2.1** (CVE-2026-111497) and **bzip3 1.5.5**. Also LZMA SDK 26.05 and libbsc 3.4.0. **Updating is recommended for everyone**, and especially if you extract `-ma:brotli` or `-ma:bzip3` archives that you did not make yourself.

Nothing changes in what zpaq-std writes. Every `-ma:brotli`, `bzip3`, `lzma`, `lz`, `bsc` and `ppmd` archive tested is byte for byte the one 1.4.0 writes, and archives from any earlier version read as before.

#### Security

- **brotli 1.2.1** fixes CVE-2026-111497, an out-of-bounds write in its decoder. zpaq-std 1.4.0 and earlier decode `-ma:brotli` blocks natively with brotli 1.2.0, so a crafted archive could exploit it while being extracted. Other zpaqs decode those blocks through ZPAQBROTLI, whose ZPAQL cannot write outside its own memory.
- **bzip3 1.5.5** fixes two signed overflows in its decoder, in the LZP match length and the MRLE run length (bzip3 #191 and #192), and checks block headers more strictly. In C these overflows are undefined behaviour, reachable with a crafted `-ma:bzip3` block.
- **bzip3's `bz3_bound()`** is too small for incompressible inputs of 64 to about 1,500 bytes: `bz3_compress()` writes up to 4 bytes past a buffer of that size. This was found while testing 1.5.5 and is reported upstream as [bzip3 #193](https://github.com/iczelia/bzip3/issues/193). It is also in 1.5.4. zpaq-std's blocks never reached it in testing, because their list of fragments always compresses a little. Even so, zpaq-std now reserves 64 bytes more than `bz3_bound()`. bzip3 itself is not patched, and its output is the same.

#### Other updates

- **LZMA SDK 26.05**, from 7-Zip 26.05. Of the files zpaq-std uses, only the version and one macro change. The vulnerabilities fixed in 7-Zip 26.04 and 26.05 are in archive formats that zpaq-std does not use.
- **libbsc 3.4.0**, with libsais 2.12.1 and faster LZP and QLFC. With zpaq-std's settings (one thread, no LZP, sort transforms ST3 to ST5) it writes the very bytes of 3.3.12, so the ZPAQBSC decoder does not change. Its fix for corrupted multithreaded compression does not concern zpaq-std, which runs bsc in one thread.

#### Downloads

As in 1.4.0: the full program, `extra-codecs.zip` (the plugin-only codecs, sylz) and `plugins.zip` (every codec as a plugin), per platform; `THIRD-PARTY-LICENSES.txt` (new versions) and `SHA256SUMS.txt`.

#### Checked

- brotli 1.2.1 under AddressSanitizer and UBSan (`codec_check`, exact-size buffers, damaged input), 700 real files: 53,517 blocks, 0 failures.
- bzip3 1.5.5, the same: no memory error once the output buffer has the 64-byte margin (without it, the `bz3_bound()` overflow described above). The two signed-overflow fixes come from bzip3 itself.
- libbsc 3.4.0 against 3.3.12, with zpaq-std's settings: 315 streams from 105 files at ST3, ST4 and ST5, plus 16 MB and 64 MB blocks, byte for byte identical, and each version decodes the other's.
- `-ma:brotli` 5 and 11, `bzip3` 1 and 9, `lzma` 6 and 9, `bsc` 1 and 9, `lz` 6 and `ppmd` 6 on 60 MB of mixed files: byte for byte the archives of 1.4.0.
- Windows 7 x64 and x86, release binaries:
  - `-ma:brotli:11`, `-ma:bzip3:9`, `-ma:bsc:5`, `-ma:lzma:9`, `-ma:zxc:3` and `-m1`: 24/24 extractions identical, and what Windows wrote extracts on Linux with zpaq 7.15, zpaqfranz, 1.4.0 and 1.5.0;
  - sylz with the extra-codecs DLLs: 15/15;
  - `-mae`/`-mat`: 12/12;
  - `-sae`/`-sat`: 16/16.
- Full test battery:
  - every suite has 0 cases to review;
  - golden archives: 0 unexpected failures;
  - `difftest` against 1.4.0: 0 divergences.

### [1.4.0] - 2026-10-22

Codecs for specific formats from plugins (`-sae` and `-sat`), two commands that describe every codec (`codecinfo` and `codecinfoex`), `-ma:zxc` is no longer experimental, and bz2-ng a655623.

#### `-sae` and `-sat`: codecs for specific formats

Some codecs only make sense for one kind of file, such as a JPEG recompressor. `-sae` and `-sat` do for them what `-mae` and `-mat` do for general codecs: the codec compresses only the files it takes, and the rest of the archive is compressed as `-m`/`-ma` say.

```
zpaq-std a test.zpaq files -sat:<file>:<codec>[+<level>][:<codec>[+<level>]...]     test
zpaq-std a data.zpaq files -sae:<file>:<codec>[+<level>][:<codec>[+<level>]...]     external
```

- **The plugin decides which files are its own, by their contents, never by their name.** It exports one more function, `zpaqstd_detect_v1`, which zpaq-std calls with each whole file (up to 64 MB) from the threads that read the files ahead of the main one. Each file goes to the first codec, in the order written, that takes it.
- **Each such file goes alone in its block.** The codec runs in the compressing threads, several files at once. The archive is byte for byte the same with any number of threads.
- **Every block is decoded back before it is written,** by the plugin (and, with `-sat`, by its ZPAQL decoder too). A block that does not come back identical (`00735!`), or that the codec cannot make smaller, is compressed as `-m` says. A file that is already partly in the archive is deduplicated as usual and does not go through the codec.
- **`-sae` (external) requires the codec's ZPAQL decoder** and says (`00732!`) that the codec is not official. **`-sat` (test)** allows a codec without one; its blocks then fail cleanly in any other zpaq, as with `-mat`. It shows which codec took each file, the sizes, the times, and how each block decoded back.
- `-sa` itself is reserved for zpaq-std's own codecs for specific formats. The first will be [pja](https://github.com/YadeWira/PJA), a JPEG and JPEG-LS recompressor, once its ZPAQL decoder is ready.

`tools/plugin_example/zs_example.c` now also has a detection function, and `compressors/plug/README.md` describes the interface.

#### `codecinfo` and `codecinfoex`

- **`codecinfo`** lists the 28 `-ma` switches: whether each is stable or experimental, its levels and default, its ZPAQL decoder, the library and version, and whether it is built in, a plugin, or missing. Then it lists the plugins in `codecs/` that are not part of zpaq-std, marked as such.
- **`codecinfoex [codec]`** shows each codec's card: author, repository, licence, the release or commit it comes from, format, levels, and three hashes: the commit of its source, the SHA-256 of its plugin file (computed by zpaq-std, not taken from the plugin), and the SHA-256 of each of its ZPAQL decoders.
- **A plugin can give its own card** with `data(ZS_DATA_INFO)`, as `key=value` lines. It is optional, and the plugin interface stays at version 1.

#### `-ma:zxc` is no longer experimental

No more `00603!` warning. Before it left experimental, zxc 0.15.0 went through the following:
- blocks of 16, 67 and 163 MB at every level, extracted identically by zpaq 7.15, zpaqfranz, and zpaq-std both natively and through ZPAQZXC;
- 1,424 real files (13 kinds, 503 MB) at every level, with the same result;
- 33,600 damaged blocks, none of them hanging or writing past the original size;
- the library under AddressSanitizer, 236,800 blocks;
- Windows 7 x64 and x86, a 64 MB block included.

The rule for leaving experimental no longer requires a frozen format (see [issue #3](https://github.com/YadeWira/zpaq-std/issues/3)). Each format of a codec has its own ZPAQL decoder and tag (`zxc9`), so if zxc changes its format, archives written before stay readable.

#### `-ma:bz2`: bz2-ng a655623

bz2-ng goes from commit b2fbb2f to a655623 (it still has no release). This brings a faster sorter, encoder and decoder, and three more libsais patches. The output is the same: `-ma:bz2` at levels 1, 5 and 9 writes the archives of 1.3.0 byte for byte.

#### Also

- The help lists `-mae`, `-mat`, `-sae` and `-sat` after the `-ma` codecs, not in the middle of them.

#### Known issue: brotli

brotli 1.2.1 (2026-10-21) fixes CVE-2026-111497, an out-of-bounds write in its decoder. zpaq-std 1.4.0 and earlier decode `-ma:brotli` blocks natively with brotli 1.2.0, so do not extract `-ma:brotli` archives from untrusted sources with them. The fix comes in 1.5.0, with other codec updates. Other zpaqs decode those blocks through ZPAQBROTLI, whose ZPAQL cannot write outside its own memory.

#### Downloads

As in 1.3.0: the full program, `extra-codecs.zip` (the plugin-only codecs, sylz) and `plugins.zip` (every codec as a plugin), per platform; `THIRD-PARTY-LICENSES.txt` and `SHA256SUMS.txt`.

#### Checked

- `-sae`/`-sat` (`tools/plugin_example`, which now takes the files where at least half of the bytes are in runs), Linux release binary: every taken file goes alone in its block, is decoded back by the plugin and its ZPAQL (`OK`), and the archive extracts identically with the plugin, with zpaq-std without it and with zpaq 7.15. A codec without ZPAQL fails cleanly without the plugin (`31321`), and `-sae` refuses it (`00731!`). The archive is byte for byte the same with `-t1`, `-t2` and `-t8`; a repeated file is deduplicated, not compressed twice; and `-sae` runs together with `-ma:zstd`. New `test/testlab/suite_sa.sh`: 8/8.
- `codecinfo`/`codecinfoex`, in the full program and in the plugins download (where it names each plugin and its SHA-256, identical to `sha256sum`'s): new `test/testlab/suite_codecinfo.sh`, which also checks every level range and default against the README's table: 6/6.
- zxc: the tests listed above.
- bz2-ng a655623: `codec_check` under AddressSanitizer, 8,211 blocks, 0 failures; its streams equal libbz2 1.0.8's on 736 of 738 file and level pairs (the other two are the exactly periodic case bz2-ng documents).
- Windows 7 x64 and x86, release binaries:
  - `-ma:zxc:3`, `-ma:zxc:7`, `-ma:bz2:9` and `-m1`: 16/16 extractions identical, and what Windows wrote extracts on Linux with zpaq 7.15, zpaqfranz, 1.3.0 and 1.4.0;
  - sylz with the extra-codecs DLLs: 15/15;
  - `-mae`/`-mat`: 12/12;
  - `-sae`/`-sat`: 16/16, x64 and x86 write the same archives, and without the DLL a codec without ZPAQL stops with `31321`;
  - `codecinfo`: 28 switches, zxc stable.
- Full test battery:
  - every suite has 0 cases to review;
  - golden archives: 0 unexpected failures;
  - `difftest` against 1.3.0: 0 divergences.

### [1.3.0] - 2026-10-21

Codecs that are not part of zpaq-std can now be used without rebuilding it: `-mae` for finished external codecs, `-mat` for testing one while it is being written.

#### `-mae` and `-mat`

Put the codec's plugin in `codecs/` next to zpaq-std and name it, without the extension:

```
zpaq-std a test.zpaq files -mat:<file>:<codec>[:<level>]     test
zpaq-std a data.zpaq files -mae:<file>:<codec>[:<level>]     external
```

The plugin uses the same interface as zpaq-std's own codec plugins (`compressors/plug/zs_codec.h`), with two optional additions: one file may hold several codecs, and a codec may give its own ZPAQL decoder, which every block then carries.

- **`-mae` (external)** is for finished codecs from third parties. It **requires** the codec's ZPAQL decoder, so the archive opens in any zpaq even if the plugin is lost or changes; without one it refuses (`00620!`). Each time it says (`00606!`) that the codec is **not an official zpaq-std codec and its support is not guaranteed**.
- **`-mat` (test)** is for the codec's developer. It shows the plugin (the codecs in the file, library, interface, levels, its ZPAQL decoder) and, for every block, sizes, ratio and times, decoding it back with the plugin and with the ZPAQL decoder and comparing. Extracting says, for every block, which of the two decoded it.
- **A `-mat` codec without a ZPAQL decoder** is allowed, so that a compressor can be tried before its decoder is written. **For safety**, its blocks carry a decoder that writes nothing: any other zpaq reports them as damaged instead of handing back the compressed bytes as if they were the file, and only zpaq-std with that plugin extracts them (`31321` names the plugin it needs).
- zpaq-std decodes a block with the plugin only if the block's ZPAQL decoder is, byte for byte, the one the plugin gives now; otherwise the block's own decoder runs. Plugin names may hold only letters, digits, `_`, `-` and `.`: a codec is loaded from `codecs/` and nowhere else.

`tools/plugin_example/zs_example.c` is a complete plugin with two codecs (one with its ZPAQL decoder, one without), and `compressors/plug/README.md` and the wiki (Adding a compressor) describe the interface.

#### Checked

- `tools/plugin_example` (two RLE codecs, `rle` with its ZPAQL decoder and `rlenz` without), Linux, release binary: with `-mat:example:rle` every block is decoded back by the plugin and by its ZPAQL (`OK`), and the archive extracts identically with the plugin, with zpaq-std without it and with zpaq 7.15; with `rlenz`, zpaq-std without the plugin stops with `31321` and zpaq 7.15 gives no wrong data; `-mae` warns (`00606!`) and extracts; `-mae` without a ZPAQL decoder is refused (`00620!`); a plugin name with a path is refused (`00619!`). Same with the small program of the plugins download. New `test/testlab/suite_ext.sh`, in the battery: 5/5.
- Windows 7 x64 and x86, release binaries with the example built as a DLL: `-mat` and `-mae` compress (one external block each, `plugin OK; ZPAQL OK`), and the four archives test and extract identically with the x64 DLL, the x86 DLL and without any (12/12); on Linux, zpaq 7.15 and zpaq-std, with and without the plugin, extract them identically.
- Windows 7: `-ma:zxc:3`, `-ma:zstd:19`, `-ma:bz2:9` and `-m1`: 16/16 extractions identical; sylz with the extra-codecs DLLs: 15/15.
- Full test battery:
  - every suite has 0 cases to review;
  - golden archives: 0 unexpected failures;
  - `difftest` against 1.2.0: 0 divergences.

### [1.2.0] - 2026-10-19

A new experimental codec, `-ma:zxc`; sylz updated to syc v0.2.7, with its levels renumbered 0 to 10; and lz6 v1.6.12-pre.

#### `-ma:zxc` (experimental)

[zxc](https://github.com/hellobertrand/zxc) 0.15.0 by Bertrand Lebonnois (BSD-3-Clause), a fast LZ built for decompression speed. Levels 1 to 7, default 3; levels 6 and 7 add Huffman coding.

- It is C, so it is inside the full program, and a plugin in the plugins download. Its core is built once per instruction set (default, AVX2, AVX-512) and the right one is chosen at run time, as zxc itself does.
- **Any zpaq opens its archives.** Every block carries ZPAQZXC, a decoder in ZPAQL written for zpaq-std from zxc's format specification (format 9): its block types, RLE and Huffman literals, and Huffman tokens. zpaq 7.15 and zpaqfranz extract every level.
- **Damaged blocks end quickly.** The decoder checks the Huffman tables and never writes more than the block's original size.
- **It is experimental:** zpaq-std says so (`00603!`) each time it is used, and you use it at your own risk. zxc is at 0.x; a later format gets a new decoder, and archives already written stay readable through the decoder they carry.

#### `-ma:sylz`: syc v0.2.7, levels 0 to 10

- syc renumbered sylz's levels: `-ma:sylz:0` is now the fastest, up to `-ma:sylz:10`; the default is still 1. A level written with a leading zero is refused.
- The plugin and zpaq-std both refuse a sylz block that claims to be sylz's newer format (v3). Such a block can only come from a crafted archive, and syc 0.2.4 to 0.2.6, never released in zpaq-std, wrote one byte out of bounds on one.
- The format is the same (v2): ZPAQSYLZ does not change, and archives from 1.1.0 extract as before.

#### `-ma:lz6`: lz6 v1.6.12-pre

lz6's changes are in its newer "seq" engine. `-ma:lz6` writes lz6's portable profile, and its archives are byte for byte those of 1.1.0 at every level.

#### Downloads

As in 1.1.0: the full program, `extra-codecs.zip` (the plugin-only codecs, sylz, to put next to it) and `plugins.zip` (every codec as a plugin), per platform; `THIRD-PARTY-LICENSES.txt` (zxc and rapidhash added) and `SHA256SUMS.txt`.

#### Checked

- zxc's decoder in ZPAQL (4,804 bytes): 574 blocks (82 mixed files, levels 1 to 7) decode identically to the library, as frames of 512 KB and 2 MB blocks too; 600 damaged frames end in at most 0.03 s, never past the original size. In zpaq 7.15 it runs at 58–73 MB/s at level 3 and 27–33 MB/s at level 7 (with JIT).
- Linux, release binary: `-ma:zxc` at every level passes `a`, `t` and `x`, and zpaq 7.15 and zpaqfranz 65.4m extract it identically; the full program and the plugins download write byte-identical archives (zxc 3 and 7, sylz 3).
- sylz: the plugins are byte for byte those of syc's v0.2.7 release on all three platforms; `suite_sylz.sh` (levels 0, 1, 2, 3, 6, 10, with the plugin, without it and in zpaq 7.15): 8/8; a crafted sylz2 block marked as v3 is refused (31319) and the plugin never sees it; `-ma:sylz` archives written by 1.1.0 extract with 1.2.0, with and without the plugin.
- lz6: `-ma:lz6` at levels 0 to 15 writes byte for byte the archives of 1.1.0.
- Windows 7 x64 and x86, with the release binaries: `-ma:zxc:3`, `-ma:zxc:7`, `-ma:lz6:9` and `-m1`: 16/16 extractions identical, and archives made on Windows extract on Linux with zpaq 7.15, zpaqfranz, 1.1.0 and 1.2.0; `-ma:sylz:0` and `:10` with the extra-codecs DLLs: 15/15, and without the DLL `a` stops with `00605!`.
- Full test battery:
  - every suite has 0 cases to review (`suite_ma_corre` 39/39 and `suite_ma_hostil` 29/29, both with zxc now);
  - golden archives: 0 unexpected failures;
  - `difftest` against 1.1.0: 0 divergences.

### [1.1.0] - 2026-10-18

A new experimental codec, `-ma:sylz`, and a new rule: codecs written in Rust or Free Pascal ship only as plugins, never inside the program.

#### `-ma:sylz` (experimental, plugin only)

[sylz](https://github.com/YadeWira/syc) is syc's fast LZ codec, written in Free Pascal with x86-64 assembler in its hot paths (format v2, syc v0.2.2, MIT). Levels 1 to 12, default 1.

- **It is a plugin**, `codecs/sylz.dll` or `codecs/sylz.so` next to the program, in both the full program and the plugins download. Without it, `-ma:sylz` stops with `00605!`.
- **Any zpaq opens its archives, plugin or not.** Every block carries ZPAQSYLZ, a decoder written in ZPAQL and generated from sylz's own token table: zpaq 7.15, zpaqfranz and zpaq-std without the plugin extract it, more slowly. With the plugin, zpaq-std decodes natively.
- **Damaged blocks end quickly.** The decoder never writes more than the block's original size, which zpaq-std stores in front of the block: a damaged block, even one crafted to expand, fails at once instead of writing gigabytes.
- **It is experimental:** zpaq-std says so (`00603!`) each time it is used, and you use it at your own risk. Its format may change in a later release; blocks are tagged with their format (`sylz2`), the native decoder is used only with a plugin of that same format, and archives already written stay readable through the decoder they carry.
- On 32-bit Windows, level 1 writes different bytes than on 64-bit systems (it hashes 4 bytes instead of 5). Every build reads every other's archives.

#### Rust and Free Pascal codecs: always plugins

From now on a codec written in Rust or Free Pascal is never linked into zpaq-std. The full program now also loads such codecs from `codecs/`, and `make fpc-plugins` builds the Free Pascal ones (sylz) with `fpc`; for Windows x86 it takes a cross `ppc386`, built from Debian's `fpc-source` without installing anything (see the wiki, Building). The plugins built here are byte for byte the ones in syc's own release.

#### Downloads

Per platform there are now three:

- `zpaq-std-v1.1.0-<platform>`: the full program, every C and C++ codec inside.
- `zpaq-std-v1.1.0-<platform>-extra-codecs.zip`: `codecs/` with the plugin-only codecs (today sylz), to unpack next to the full program.
- `zpaq-std-v1.1.0-<platform>-plugins.zip`: the small program and every codec as a plugin, sylz included.

Plus `THIRD-PARTY-LICENSES.txt` (sylz, MIT, added) and `SHA256SUMS.txt`.

#### Checked

- sylz's decoder in ZPAQL: 246 blocks (82 mixed files, levels 1, 6 and 12) decode identically to the plugin; 200 randomly damaged blocks end in at most 0.01 s; a crafted 1 MB block that would expand to 255 MB stops at the original size (0.03 s with JIT, 0.17 s without).
- Linux, with the release binary and the extra-codecs plugin: `-ma:sylz` at levels 1, 6 and 12 passes `t` and extracts identically with the plugin, with zpaq-std without the plugin, with zpaq 7.15, zpaqfranz 65.4m and 65.11; without the plugin, `a` stops with `00605!`; the full program with extra-codecs and the plugins download write byte-identical archives. New `test/testlab/suite_sylz.sh`, in the battery: 5/5.
- The sylz plugins in the downloads are byte for byte those of syc's v0.2.2 release, on all three platforms.
- Windows 7 x64 and x86, with the release binaries and the extra-codecs DLLs: `-ma:sylz:1` and `:12` compress; archives made on Windows and on Linux test and extract with x64, x86 and without the DLL (15/15 identical), and those made on Windows extract on Linux with zpaq 7.15, zpaqfranz and zpaq-std. Without the DLL, `a` stops with `00605!`. `-ma:bz2:9`, `-ma:zstd:19`, `-ma:lz5:9` and `-m1`: 16/16 extractions identical, and they extract on Linux with zpaq 7.15, zpaqfranz, 1.0.2 and 1.1.0.
- Full test battery:
  - every suite has 0 cases to review;
  - golden archives: 0 unexpected failures;
  - `difftest` against 1.0.2: 0 divergences.

### [1.0.2] - 2026-10-17

One fix for control-C, inherited from zpaqfranz 65.4m (ZF's BUG-022 and BUG-023, the part that pre63 did not cover).

#### Control-C after the archive was closed

At the end of an `add`, the archive was closed through the add's own copy of its handle, and the copy that the control-C handler uses kept pointing to the closed file. A control-C after that moment closed it a second time. With `backup` the moment is long: the MD5 of the new part is computed after the part is closed. glibc detects the second close only now and then, as `free(): double free detected`: in ZF's scripts, about one control-C in a hundred ended that way. The archive itself was not damaged, and the next `backup` ran.

Now exactly one side closes the archive: the add when it ends, or the handler. Both take it out of the shared handle atomically, and only the one that gets it closes it.

#### Checked

- Linux, control-C sent to `backup` the moment it prints "Creating MD5": 1.0.1 closes the archive a second time every time (AddressSanitizer: double-free in the handler), 1.0.2 never does, removes its `.pid`, and the next `backup` runs.
- Control-C at random moments during `a`: the archive is rolled back to the original byte for byte and passes `t`; with AddressSanitizer, 40 runs, no error.
- New `test/testlab/suite_sigint.sh`, in the battery from now on: 11/11 (1.0.1: 6/11, the five control-C during the MD5).
- Windows 7 x64 and x86, with the release binaries: `-ma:bz2:9`, `-ma:zstd:19`, `-ma:lz5:9` and `-m1`: `t` and `x` pass, all 16 extractions have identical sha256, and archives made on Windows extract on Linux with zpaq 7.15, zpaqfranz, 1.0.1 and 1.0.2. A control-C cannot be sent to a Windows console over SSH, so control-C itself is still untested on Windows.
- Full test battery:
  - every suite has 0 cases to review;
  - golden archives: 0 unexpected failures;
  - `difftest` against 1.0.1: 0 divergences.

### [1.0.1] - 2026-10-17

Two library updates, `-ma:bz2` (experimental) to a newer bz2-ng and `-ma:lz5` to lz5-ex 1.5.3, and the licence notices that the Windows binaries were missing.

#### `-ma:bz2`: bz2-ng b2fbb2f

[bz2-ng](https://github.com/tfenne/bz2-ng) goes from commit 63987e0 to b2fbb2f (it has no release yet): a new decoder, encoder and block sorter. Inside zpaq-std, on 22 MB of mixed files with one thread, `-ma:bz2:9` extracts about 10% faster than in 1.0.0 and compresses about as fast; against `-ma:bzip2:9` it is about 2.4× as fast to compress and 2× as fast to extract, for the same size.

- The format is bzip2's, so the ZPAQL decoder (ZPAQBZ2) does not change: every zpaq extracts these archives as before, and `-ma:bz2` archives are byte for byte those of 1.0.0.
- bz2-ng now applies three patches of its own to libsais. The build applies them to a copy, as bz2-ng's CMake does, and checks the result against bz2-ng's SHA-256 sums.
- New in THIRD-PARTY-LICENSES.txt: sais-lite 2.4.1 (Yuta Mori, MIT), used by bz2-ng's sorter.

`-ma:bz2` stays **experimental** until bz2-ng has a release: zpaq-std says so (`00603!`) every time it is used, and you use it at your own risk. Archives already written stay readable, by zpaq-std and by any other zpaq.

#### `-ma:lz5`: lz5-ex 1.5.3

[lz5-ex 1.5.3](https://github.com/YadeWira/lz5-ex/releases/tag/v1.5.3) changes its `lz5` program and `lz5frame.c`, which zpaq-std does not bundle; `lz5.c` and `lz5hc.c` are those of 1.5.2. `-ma:lz5` archives are byte for byte those of 1.0.0.

#### Licences: the mingw-w64 runtime in the Windows binaries

The Windows binaries and plugin DLLs link the mingw-w64 runtime statically, and its notices were missing from THIRD-PARTY-LICENSES.txt: the CRT and libmingwex (ZPL-2.1), gdtoa (Lucent, David M. Gay), the printf family (Keith Marshall) and winpthreads (MIT, with `pthread.h` under BSD-3-Clause, Lockless Inc.). They are now its part 3. This applies to the binaries of every earlier release too. Reported by the maintainer of the zpaq-std GUI.

#### Checked

- Linux, with the release binary: `-ma:bz2` at levels 1, 2, 5 and 9 and `-ma:lz5` at 1, 9 and 15, `lz5f` and `lz5hc` write archives byte for byte identical to 1.0.0's; the `-ma:bz2` plugin writes the same archive as the full binary. An archive of 82 mixed files written with `-ma:bz2:9` extracts identically with zpaq 7.15, zpaqfranz 65.4m and 65.11.
- bz2-ng b2fbb2f, built as zpaq-std builds it: `codec_check` under AddressSanitizer, 840 blocks at levels 1, 5 and 9, 0 failures; its streams equal libbz2 1.0.8's on 736 of 738 file and level pairs, and the other two (an exactly periodic input at levels 1 and 2) are the case bz2-ng documents, decode identically, and are the same with the bz2-ng of 1.0.0.
- Windows 7 x64 and x86, with the release binaries: `-ma:bz2:1`, `-ma:bz2:9`, `-ma:lz5:9`, `-ma:lz5f` and `-m1`: `t` and `x` pass, all 20 extractions have identical sha256, and archives made on Windows extract on Linux with zpaq 7.15, zpaqfranz, 1.0.0 and 1.0.1: 20/20.
- Full test battery:
  - every suite has 0 cases to review;
  - golden archives: 0 unexpected failures;
  - `difftest` against 1.0.0: 0 divergences.

### [1.0.0] - 2026-10-17

The first stable release of zpaq-std, after 64 pre-releases. It is the same program as 0.0.1-pre64, plus one fix for `-tar` inherited from zpaqfranz 65.4m (ZF's BUG-021).

zpaq-std is zpaqfranz 65.4m (its "open" build) with 20 bundled compression libraries behind `-ma:<codec>:<level>` (26 switches), no system dependencies, and every `-ma` block readable by any zpaq through its own ZPAQL decoder. It runs on Windows 7 or later (x86 and x64) and Linux x64. See the [README](https://github.com/YadeWira/zpaq-std#readme) and the [wiki](https://github.com/YadeWira/zpaq-std/wiki).

#### Version numbers

From now on versions are `MAJOR.MINOR.PATCH`: MAJOR for big changes in zpaq-std itself, MINOR for a small update of the zpaqfranz base or a small new feature, PATCH for bug fixes. The banner reads `zpaq-std v1.0.0 | zf v65.4m-...`, the zpaqfranz base underneath.

#### `-tar`: hard links across versions

A hard link group was decided inside each `add`, and the names that did not change were not written again. So:

- a new link to a file already in the archive was stored as the first name of the group, while the other names still linked to the old first name;
- deleting the first name left the other names linked to a name that is gone.

`x -tar -until N` then gave independent copies instead of hard links, for every version after the one where the group changed. The data were always right: only the links were lost. zpaqfranz 65.11 does the same.

Each `add` now checks every name of a group against the archive, and writes a new version of each name whose link changed: just the index, as for a `chown`, the data are not read again. The first name stays the archived one while it exists, so a new link writes only the new name; when the first name is deleted, the other names of the group are written again, linked to the new first name. The format does not change: zpaqfranz 65.4m and 65.11, and pre64, extract archives written by 1.0.0 with the right links.

#### Downloads

- `zpaq-std-v1.0.0-<platform>`: the full program, every codec inside.
- `zpaq-std-v1.0.0-<platform>-plugins.zip`: a small program and one plugin (DLL or .so) per codec in `codecs/`. Without a codec's plugin you cannot compress with it, but its blocks still extract through their ZPAQL decoder.
- `THIRD-PARTY-LICENSES.txt`: the licences of everything from other authors in these binaries; redistribute it with them.
- `SHA256SUMS.txt`. The builds are reproducible.

#### Checked

- Linux, with the release binary, ZF's BUG-021 script: every version of the archive extracts identical to the original (type, mode, size, mtime, content and hard link group of each entry); pre64 gave copies from the second version on. The archive written by 1.0.0 extracts with the right links with zpaqfranz 65.4m, zpaqfranz 65.11 and pre64, and with zpaq 7.15 (as copies, it has no `-tar`).
- `suite_tar.sh` now runs in the battery, with four versions of a hard link group (a link added, the first name deleted, a group left with one name): 7/7 (pre64: 4/7).
- Windows 7 x64 and x86, with the release binaries: `-ma:bz2:9`, `-ma:zstd:19`, `-m1` and `-ma:lzma:5`: `t` and `x` pass, all 16 extractions have identical sha256, and archives made on Windows extract on Linux with zpaq 7.15, zpaqfranz, pre64 and 1.0.0: 16/16. Both banners read `zpaq-std v1.0.0`.
- Full test battery:
  - every suite has 0 cases to review;
  - golden archives: 0 unexpected failures;
  - `difftest` against pre64: 0 divergences.

### [0.0.1-pre64] - 2026-10-17

Two fixes for `k` (delete what is not in the archive), both inherited from zpaqfranz 65.4m (ZF's BUG-002 and BUG-003).

#### `k`

- **Without `-to`, `k` crashed** (segmentation fault). It now says that it needs `-to`, the folder to clean up, with an example (`95282!`), and returns 2.
- **A folder that cannot be removed made `k` loop for ever.** `k` removes folders pass after pass, inner ones first; one it could not remove (for instance inside a read-only folder) kept it going. It now stops when a pass removes nothing, names each folder left (`95283!`) and returns 1, as it already did for files.

#### Checked

- Linux, ZF's script, with the release binary: `k` without `-to` returns 2 with the message (pre63: 139, a crash); with a read-only folder, `k` returns 1 and names both folders it could not remove (pre63: still running after the timeout). A normal `k` still removes extra files and nested extra folders and leaves the rest.
- Windows 7 x64 and x86, with the release binaries:
  - `k` without `-to`: the message, return code 2; a normal `k`, with its captcha, removes an extra file and an extra nested folder and leaves the archived ones;
  - `-ma:bz2:9`, `-ma:zstd:19` and `-m1`: `t` and `x` pass, all 12 extractions have identical sha256, and archives made on Windows extract on Linux with zpaq 7.15, zpaqfranz, pre63 and pre64: 12/12.
- Full test battery:
  - every suite has 0 cases to review;
  - golden archives: 0 unexpected failures;
  - `difftest` against pre63: 0 divergences.

### [0.0.1-pre63] - 2026-10-17

Control-C during `a` and `backup` stops cleanly again, and a backup that died no longer blocks its set. Both inherited from zpaqfranz 65.4m (ZF's BUG-022 and BUG-023).

#### Control-C during `a`

The control-C handler closed and truncated the archive while the writer thread could still be writing to it: now and then the program ended with `free(): invalid pointer` instead of a clean stop. The handler now stops new writes first and waits for the one in progress (at most about 3 seconds) before it closes anything; a second control-C during the clean-up is ignored. The rollback itself works as before.

#### Control-C during `backup`, and a stale `.pid`

- `backup` closed its `.pid` lock file twice on control-C: `double free`, and the `.pid` stayed behind, so every later `backup` and `testbackup` quit with "backup seems running" until the file was deleted by hand. It is closed once now, and removed.
- A backup that dies anyway (killed, a crash) also leaves its `.pid`. The `.pid` now says which process on which machine wrote it, and a `.pid` of this machine whose process is gone is dropped, with a message (`95281!`). A `.pid` of another machine, or one written by pre62 or older, still counts as a running backup, as before: mixing versions can only refuse a backup, never run over a live one.

#### Checked

- Linux, with the release binary:
  - control-C during `a`, ZF's script: 0 aborts in 60 runs; in 20 more, every rolled-back archive is the original byte for byte and passes `t`;
  - control-C during `backup`, ZF's script: 0 aborts in 10 runs, the `.pid` removed each time, and the next backup runs;
  - after `kill -9` during a backup, the next backup drops the stale `.pid` and runs.
- Before the release build, same source: control-C during `a`, 100 runs, 0 aborts (pre62: 1 of 40); control-C during `backup`, 10 runs, 0 aborts, `.pid` removed and the next backup runs (pre62: 7 of 10 aborted, the `.pid` stayed and the next backup was refused). After 30 control-C rollbacks the archive was the original byte for byte and passed `t`.
- `.pid` and versions: pre62 refuses a new-format `.pid` (as it refuses any); the new version refuses an old-format `.pid`, one of another machine and one of a running process, and drops one of a process that is gone (after `kill -9`, `backup` and `testbackup` go on).
- Windows 7 x64 and x86, with the release binaries:
  - `.pid`: two backups in a row, a `.pid` of a process that is gone on this machine is dropped, one of another machine still blocks, `testbackup` passes;
  - `-ma:bz2:9`, `-ma:zstd:19` and `-m1`: `t` and `x` pass, all 12 extractions have identical sha256, and archives made on Windows extract on Linux with zpaq 7.15, zpaqfranz, pre62 and pre63: 12/12.
  - Control-C itself was not tested on Windows (it cannot be sent to a console program over SSH).
- Full test battery:
  - every suite has 0 cases to review;
  - golden archives: 0 unexpected failures;
  - `difftest` against pre62: 0 divergences.

### [0.0.1-pre62] - 2026-10-17

Three fixes for `-chunk` (multi-part archives with a size limit per part), all inherited from zpaqfranz 65.4m, found with ZF.

#### `-chunk`

- **Parts no larger than the limit.** A whole write buffer (up to 64 KB) was written before changing part, so every part could end up to 64 KB over the limit: 1,114,112 bytes with `-chunk 1MB`. A part now holds at most the limit, and with `-key` the 32-byte salt at the start of the first part counts towards it.
- **The last part is not deleted.** When the header of the transaction is written again in the first part, the part being written was left open instead of being closed. Its last bytes could stay unwritten, the check that removes an empty last part found it empty, and deleted it with the end of the archive inside. It showed with small parts; zpaqfranz 65.6 has the same fix.
- **A second version with `-key` extracts.** On Linux, a pattern without a folder (`a "part_???.zpaq" ...`) made the program look for the existing parts in the root folder instead of the current one. A second version did not see the first, and with `-key` its part was encrypted at the wrong position: it did not extract (`00966! UKONE`), with zpaq-std or zpaqfranz. The parts are now looked for in the current folder. Ported from zpaqfranz 65.6; ZF found the change by bisecting 65.5 to 65.6.

Archives written before still extract as they did; a two-version `-chunk -key` archive written by pre61 or older keeps its wrongly encrypted second version.

#### Checked

- `-chunk` on Linux, with the release binary: 1000, 7777, 100000 bytes and 1 MB, with and without `-key`, two versions in the current folder: every part at most the limit; without `-key`, the parts put together equal the same archive written without `-chunk`, byte for byte (fixed `-timestamp`); both versions extract with pre62 and with zpaqfranz 65.11.
- With the same source before the release build: also two versions in another folder, with and without `-key`; and a `-chunk -key` archive written by zpaqfranz 65.11 extracts with zpaq-std, and one written by zpaq-std with zpaqfranz 65.11.
- Windows 7 x64 and x86, with the release binaries:
  - `-chunk 100000`, two versions, with and without `-key`, in the current folder: both versions extract, every part at most 100000 bytes;
  - `-ma:bz2:9`, `-ma:zstd:19` and `-m1`: `t` and `x` pass, all 12 extractions have identical sha256, and archives made on Windows extract on Linux with zpaq 7.15, zpaqfranz, pre61 and pre62: 12/12.
- Reproducible build: the Windows `.exe` files and the three plugin zips were built twice from the same source, with the same sha256.
- Full test battery:
  - every suite has 0 cases to review;
  - golden archives: 0 unexpected failures;
  - `difftest` against pre61: 0 divergences.

### [0.0.1-pre61] - 2026-10-16

The `-ma` codecs can now also come as plugins, like 7-Zip-zstd's codec DLLs: besides the usual binaries, every platform gets a zip with a smaller program and one plugin per codec. The usual self-contained binaries do not change: they write the same archives as pre60, byte for byte.

#### Codecs as plugins

- `zpaq-std-v0.0.1-pre61-<platform>-plugins.zip` holds `zpaq-std` (about 5 MB instead of 10) and `codecs/` with 20 plugins (`zstd.dll`, `brotli.dll`, `kanzi.dll`… or `.so` on Linux), plus `LICENSE` and `THIRD-PARTY-LICENSES.txt`. Unzip it and run `zpaq-std` from its folder.
- With a codec's plugin, everything is as in the full binary: the same archives, byte for byte, and a speed within a few percent.
- Without it, `-ma:<codec>` stops with `00605! -ma:<codec> needs its plugin`, and archives that already hold that codec's blocks still extract: every `-ma` block carries its own ZPAQL decoder, which runs instead (slower). `-m0` to `-m7`, `-ma:lz4` and `-ma:lzav` need no plugin.
- zpaq-std loads the plugins only from the `codecs` folder next to the executable, by absolute path, once at start-up: never from the current folder or the `PATH`. On Windows they import only `KERNEL32` and `msvcrt` and run on Windows 7, x64 and x86.
- `make plugins` builds them (after `make clean`); the interface is a few C functions, `compressors/plug/zs_codec.h`, described in [`compressors/plug/README.md`](https://github.com/YadeWira/zpaq-std/blob/main/compressors/plug/README.md). One plugin, `lz5`, serves `-ma:lz5`, `lz5hc` and `lz5f`.
- Inside the program every `-ma` codec now goes through this interface, also in the full binary; the archives do not change.

#### Documentation

- The README linked zpaq's page at an address that no longer exists; it points to mattmahoney.net/dc/zpaq.html, and counts 20 libraries and 26 `-ma` switches.

#### Checked

- Full binary (Linux, the release one): byte for byte the binary that passed the full battery (every suite 0 cases to review, golden archives 0 unexpected failures, `difftest` against pre60 0 divergences); with a fixed `-timestamp`, it writes the same archives as pre60 for 21 methods covering every codec.
- Plugins, against the full binary, for 20 methods (every codec): on Linux, from the release zip, 20/20 identical archives that extract correctly; on Windows x64 and x86 (under Wine, against the pre60 `.exe`) 21/21. Without each plugin, compressing stops with 00605 and extracting through ZPAQL gives the original files (21/21, Linux).
- Windows 7 x64 and x86:
  - full binaries: `-ma:bz2:9`, `-ma:zstd:19`, `-ma:kanzi:5` and `-m1`; `t` and `x` pass, all 16 extractions have identical sha256, and archives made on Windows extract on Linux with zpaq 7.15, zpaqfranz, pre60 and pre61: 16/16;
  - the release plugin zips, unzipped: `-ma:zstd`, `brotli`, `kanzi`, `bsc`, `ppmd`, `lz5hc`, `bz2`, `uflzma2`, `flzma2`, `lzh` and `bzip3` compress, test and extract correctly; without `codecs`, 00605, and a zstd archive still extracts.

### [0.0.1-pre60] - 2026-10-16

zpaq-std gets a version of its own: **v0.0.1** (still a pre-release). A new experimental codec, `-ma:bz2`, compresses bzip2 streams with bz2-ng, about twice as fast as `-ma:bzip2`. The licence and credit files are corrected, and the built-in help documents `-ma` where it is looked for.

#### Version 0.0.1

The version line was zpaqfranz's: `zpaq-std-open v65.4m-JIT67,...,(2026-09-24)`, with the date of zpaqfranz 65.3y. It is now

```
zpaq-std v0.0.1 | zf v65.4m-JIT67,-L,HW SHA1/2,4,(2026-10-16)
```

zpaq-std's own version, the zpaqfranz version it is based on (`zf`), and zpaq-std's release date. Programs that recognise the old `zpaq-std-open ` prefix need updating; the new line starts with `zpaq-std v` and a digit. Releases are tagged `v0.0.1-preN` until the first stable one.

#### `-ma:bz2` (experimental): bzip2 with bz2-ng

- [bz2-ng](https://github.com/tfenne/bz2-ng) rewrites libbz2 1.0.8's encoder and decoder and keeps its format and its API. `-ma:bz2` uses it; `-ma:bzip2` keeps libbz2 1.0.8. Levels 1 to 9 as bzip2, default 9.
- It writes the same bytes as libbz2 (checked on every level), so the compression ratio is the same. Inside zpaq-std, with one thread on 52 MB, it compresses about 2 times as fast as `-ma:bzip2` and extracts about 1.5 times as fast.
- Its blocks carry their own decoder, **ZPAQBZ2** (ZPAQBZIP2 with one instruction more, to give it an identity of its own): zpaq 7.15, zpaqfranz and older zpaq-std versions extract them.
- Experimental because bz2-ng has no release yet: zpaq-std bundles commit 63987e0, unmodified. Archives already written stay readable whatever happens to it.

#### Licences and credits

zpaq-std's first commit had renamed "zpaqfranz" to "zpaq-std" everywhere, also in text that belongs to zpaqfranz:

- a quoted request of Franco Corbelli to Igor Pavlov, in the credits inside `zpaq-std.cpp` (and `THIRD-PARTY-LICENSES.txt`), named the wrong fork; it reads as he wrote it again;
- `LICENSE` described Franco Corbelli's copyright as "the original zpaq-std codebase"; it is zpaqfranz's;
- `COPYING` called zpaq-std a fork of zpaq 7.15 and linked a repository that does not exist; it now says what zpaq-std is forked from, points to `THIRD-PARTY-LICENSES.txt`, and lists three entries (libfuse, WinFsp, LZAV) that `zpaq-std.cpp` already credited;
- `CONTRIBUTORS` is rewritten: it named a "zpaq-std" by Franco Corbelli that does not exist, gave the wrong authors for LZ5 and Snappy and the wrong licence for LZHAM, and missed half of the bundled compressors;
- the part of the changelog that is zpaqfranz's own (63.3b and older) is zpaqfranz's text again, with its links to github.com/fcorbelli/zpaqfranz;
- the Makefile's download targets and the man page pointed to addresses that never held zpaq-std.

#### Built-in help

- `-ma` was documented only in `h voodoo`. It is now in `h main` and `h a` too, with examples; `h voodoo` keeps the list of every codec and level.
- `-popgui` (legacy name `-innosetup`) is in `h a` on Windows.
- Examples that ran the program as `zpaqfranz` run `zpaq-std`, and descriptions that called this program zpaqfranz name zpaq-std. What describes zpaqfranz's formats and history stays.

#### Checked

- `-ma:bz2`:
  - bz2-ng writes the same bytes as zpaq-std's libbz2 1.0.8 on 81 files at every level from 1 to 9, including all-zero and periodic blocks, and each library decodes the other's output;
  - [codec_check](https://github.com/YadeWira/zpaq-std/tree/main/tools/codec_check) under AddressSanitizer and UndefinedBehaviorSanitizer: 3,294 blocks at the 9 levels, damaged copies included, 0 failures;
  - with the release binary, levels 1, 5 and 9 extract identically with zpaq 7.15 and pre59 (both run ZPAQBZ2) and with pre60.
- Windows 7 x64 and x86, with the release binaries: `-ma:bz2` 1 and 9, `-ma:bzip2:9`, `-m1`, `-ma:zstd:19` and `-ma:uflzma2:11`; `t` and `x` pass, all 24 extractions have identical sha256, and archives made on Windows extract on Linux with zpaq 7.15, zpaqfranz, pre59 and pre60: 24/24. The new version line and the `-ma` and `-popgui` lines of `h a` show on both.
- Full test battery, with `-ma:bz2` added to its round-trip suites:
  - every suite has 0 cases to review;
  - golden archives: 0 unexpected failures;
  - `difftest` against pre59: 0 divergences.
- `THIRD-PARTY-LICENSES.txt`, attached, adds bz2-ng (and its bzip2, libdeflate and libsais parts) and has the corrected quote.

### [65.4m-pre59] - 2026-10-14

Two fixes for `-to` when adding on Windows, both inherited from zpaqfranz, and one for
a debug message. Archives and compressed bytes do not change.

#### `-to` on Windows: a folder with a trailing slash, and a different case

- A folder given with a trailing slash, as in `a arc.zpaq C:/x/folder/ -to folder/`,
  was scanned as `folder/*`: its contents only. The folder entry itself was not
  stored, and an empty folder added nothing at all (`QUIT: total size,file/folder
  count == zero`). On Linux, and on Windows without the slash, the folder is stored
  too. Now one trailing slash is dropped on Windows as well, except on a root
  (`C:/`, `//?/C:/`, `//server/share/`), where the name without it means something
  else.
- A folder written with a different case than on disk, as in
  `a arc.zpaq C:/x/DOCS -to DOCS` for a folder called `Docs`: the files were
  selected, since Windows paths are not case sensitive, but `-to` was not applied
  and they were stored with their full path. `-to` now matches the same way the
  selection does.
- Wildcards (`folder/*`), double slashes (`folder//`) and roots behave as before.
- Reported by the zpaq-std GUI; both confirmed in zpaqfranz 65.11.

#### `-debug3` printed garbage in message 00228

With `-debug3`, message `00228` printed a file name that is only filled with
`-debug4`: uninitialised bytes, different on every run, and a read that could run
past the buffer. It now prints an empty name.

#### For codec authors

`tools/codec_check/codec_check.h` declares its functions `extern "C"`, so an adapter
can be written in C++.

#### Checked

- `-to` on Windows 10 and Windows 7 (x64 and x86), pre58 against pre59: a folder
  with a trailing slash, an empty folder with a trailing slash, a different case,
  no slash; pre59 stores the folder entry and applies `-to` in every case, and the
  control without a slash is unchanged. Wildcards, double slashes and a drive root
  (`subst`) give the same entries as pre58 on Windows 10.
- `00228` with `-debug3` and `-key`: two runs print the same line (pre58 printed
  different bytes each time).
- Windows 7 x64 and x86, with the release binaries: `-m1`, `-m5`, `-ma:zstd:19` and
  `-ma:uflzma2:11`; `t` and `x` pass, all 16 extractions have identical sha256, and
  archives made on Windows extract on Linux with zpaq 7.15, zpaqfranz, pre58 and
  pre59: 16/16.
- Full test battery:
  - every suite has 0 cases to review;
  - golden archives: 0 unexpected failures;
  - `difftest` against pre58: 0 divergences.

### [65.4m-pre58] - 2026-10-09

#### lz5-ex 1.5.2

- `-ma:lz5`, `lz5hc` and `lz5f` move from lz5-ex commit 5541227 (pre56 and pre57) to
  [lz5-ex 1.5.2](https://github.com/YadeWira/lz5-ex/releases/tag/v1.5.2). Same block
  format and the same ZPAQLZ5 decoder; pre57 and older versions extract the new
  blocks.
- Fixed in the decoder, which zpaq-std uses natively:
  - it checked match offsets by comparing pointers, which wraps around with an
    output buffer at a low address and could read outside its buffers (LZ5 1.5,
    in zpaq-std up to pre55, has the same defect);
  - it could read past the end of its input in more cases (literals near the end,
    one-byte and empty inputs).
- Level 0 could write up to 3 bytes past a tight output buffer; zpaq-std passes a
  buffer the size of the block's original data, so it was not affected.
- Measured on 96 MB (text, executable, image, audio, incompressible, mixed),
  against pre57:
  - `-ma:lz5` with its default level 9 writes the same bytes and compresses about
    9% faster; `lz5hc` 3, 4, 5 and 11 compress 11-21% faster;
  - `lz5f` and `lz5hc` 4, 6 to 10 and 12 to 15 write the same bytes;
  - `lz5hc` 1, 2, 3, 5 and 11 write blocks 0.07-1.1% larger (up to 3.2% on one
    file at level 1); against LZ5 1.5 (pre55) they stay within 0.2% or smaller;
  - extraction runs at the same speed.

#### The LZMA2 decoders reject one more kind of corrupt chunk

- The maintainer of ultra-fast-lzma2 found, with a differential fuzzer, a corrupt
  stream on which the decoders of `-ma:flzma2` and `-ma:uflzma2` disagreed: an LZMA
  chunk that declares more packed bytes than its data uses. The one-shot decoder,
  the one zpaq-std uses, returned the data up to that chunk as valid, while the
  multi-threaded stream decoder read on. Such a chunk is now rejected as corrupt, as
  the LZMA SDK does.
- `-ma:uflzma2` moves to ultra-fast-lzma2
  [1.6.2](https://github.com/YadeWira/ultra-fast-lzma2/releases/tag/v1.6.2);
  `-ma:flzma2` gets the same fix in its fast-lzma2 1.0.1 patch, backported by
  ultra-fast-lzma2's maintainer (`compressors/fl2/PATCHES`).
- Only the decoders change: compressed bytes are the same. In zpaq-std the block
  header also records the original size, which the decoded size must match.

#### `-ma:uflzma2` is no longer experimental

- ultra-fast-lzma2 had its stability release (1.6.1, in pre57), and its blocks have
  been byte-identical since 1.5.1, where it entered zpaq-std. The warning
  `00603! uflzma2 is EXPERIMENTAL` is gone, and the README lists it with the stable
  codecs. `-ma:lz6` stays experimental.

#### For codec authors: `tools/codec_check` and a proposal form

- `tools/codec_check` runs the checks zpaq-std makes before bundling a compressor,
  so that its author can run them first: round trips from exact-size buffers,
  determinism, output caps and a few hundred damaged copies of every block, under
  AddressSanitizer and UndefinedBehaviorSanitizer. The author fills in a small
  adapter; `examples/adapter_lz5.c` is a complete one. lz5-ex 1.5.2 passes it, and
  it catches the decoder over-read of LZ5 1.5.
- A "Propose a compressor" issue form, and the wiki page
  [Adding a compressor](https://github.com/YadeWira/zpaq-std/wiki/Adding-a-compressor)
  now says what is required, what helps, what happens when a bug is found, and when
  an experimental codec becomes stable.

#### Checked

- lz5-ex 1.5.2:
  - its six library files are identical to tag v1.5.2 (commit 1bcccdd) on GitHub;
  - 180 combinations (`lz5f` and `lz5hc` at levels 1 to 15, six inputs) extract
    identically with zpaq 7.15 (ZPAQLZ5) and natively;
  - pre57 extracts the new blocks;
  - 1,200 damaged blocks, decoded natively under AddressSanitizer: every one
    reported, no memory error; zpaq 7.15 handled all of them too;
  - compression and decompression with buffers of the exact size, under
    AddressSanitizer and UndefinedBehaviorSanitizer: clean.
- LZMA2 decoders:
  - seven reproducer streams (the three new ones and the four of pre57), against
    zpaq-std's own copies of both libraries, with AddressSanitizer and
    UndefinedBehaviorSanitizer and with the assembler decoder: "Corrupted block
    detected" in every build; before, the three new ones decoded as "ok";
  - same bytes as pre57, extracted by pre58, by pre57 and by zpaq 7.15:
    `-ma:flzma2` levels 1 to 10 on six inputs, plus `-m5` blocks: 66/66;
    `-ma:uflzma2` levels 1 to 11 on six inputs: 66/66.
  - 900 damaged `flzma2` and `uflzma2` blocks, decoded natively under
    AddressSanitizer: every one reported, no memory error.
- `suite_ma_hostil` 25/25 under AddressSanitizer.
- Windows 7 x64 and x86, with the release binaries:
  - `-ma:lz5hc` 1, 3, 4 and 11, `-ma:lz5:9` (also with `-m5`), `-ma:uflzma2:11` and
    `-ma:flzma2:10`;
  - `t` and `x` pass, and all 32 extractions have identical sha256;
  - archives made on Windows extract on Linux with zpaq 7.15, zpaqfranz, pre57 and
    pre58: 32/32.
- Full test battery:
  - every suite has 0 cases to review;
  - golden archives: 0 unexpected failures;
  - `difftest` against pre57: 0 divergences.

### [65.4m-pre57] - 2026-10-08

#### Fixed: the LZMA2 decoders of `-ma:flzma2` and `-ma:uflzma2` accepted two kinds of corrupt chunks

zpaq-std decodes these blocks natively, with fast-lzma2 1.0.1 and ultra-fast-lzma2.
Both decoders had two defects, which ultra-fast-lzma2's maintainer found in a
stability campaign:
- a corrupt LZMA chunk could make the decoder read up to 20 bytes past the end of
  its input;
- a chunk without properties after a dictionary reset was accepted, leaving `pb`
  uninitialized. The C decoder then shifted by out-of-range amounts, and the
  assembler decoder of ultra-fast-lzma2, the one the x86_64 builds use, crashed
  (SIGSEGV).

Both kinds of chunk are now rejected as corrupt, as the LZMA SDK does:
- `-ma:uflzma2` moves to ultra-fast-lzma2 **1.6.1**, its stability release;
- `-ma:flzma2` keeps fast-lzma2 1.0.1 with a patch to its decoder, backported by
  ultra-fast-lzma2's maintainer (`compressors/fl2/PATCHES`).

Compressed bytes do not change, so archives written before and after are the same.
Random damage to `-ma:flzma2` and `-ma:uflzma2` archives was always detected
before too; these two defects need a deliberately crafted stream.

#### Checked

- The reproducers (four LZMA2 streams) against zpaq-std's own copies of both
  libraries, with AddressSanitizer and UndefinedBehaviorSanitizer and with the
  assembler decoder:
  - before: heap-buffer-overflow, "shift exponent 190" and SIGSEGV;
  - now: "Corrupted block detected" in every build.
- Same bytes as pre56, extracted by this build, by pre56 and by zpaq 7.15:
  - `-ma:flzma2` levels 1 to 10 on six inputs, plus `-m5` blocks (66/66);
  - `-ma:uflzma2` levels 1 to 11 on six inputs (66/66).
- 900 damaged `flzma2` and `uflzma2` blocks, decoded natively under
  AddressSanitizer: every one reported, no memory error; `suite_ma_hostil` 25/25
  under AddressSanitizer.
- Windows 7 x64 and x86, with the release binaries: `-ma:flzma2`, `uflzma2` and
  `lz5`, also with `-m5`; `t` and `x` pass, all 28 extractions with identical
  sha256; archives made on Windows extract on Linux with zpaq 7.15, zpaqfranz,
  pre56 and pre57 (28/28).
- Full test battery: every suite has 0 cases to review; golden archives: 0
  unexpected failures; `difftest` against pre56: 0 divergences.

### [65.4m-pre56] - 2026-10-02

#### `-ma:lz5` uses lz5-ex instead of LZ5 1.5

- [lz5-ex](https://github.com/YadeWira/lz5-ex) (commit 5541227) is a maintained fork
  of LZ5 1.5 with the same block format. The ZPAQLZ5 decoder that every `-ma:lz5`
  block carries does not change, so archives from before and after extract with
  both versions and with any zpaq.
- Measured on 96 MB (text, executable, image, audio, incompressible, mixed):
  - `lz5hc` levels 1 to 11, and `-ma:lz5` with its default level 9, write blocks
    0.1-1.2% smaller;
  - `lz5f`, `-ma:lz5:1` to `:4` and `lz5hc` 12 to 15 write the same bytes as
    before;
  - level 15 compresses about 5% slower; the other levels measured, and
    extraction, run at the same speed.
- Two out-of-bounds reads in LZ5 1.5 are gone. `LZ5_decompress_safe` could read
  1-2 bytes past the end of its input, and the HC match finder 1 byte past the end
  of the data. Neither showed in zpaq-std, whose buffers have spare capacity, but
  AddressSanitizer finds both in LZ5 1.5 with buffers of the exact size.

#### ultra-fast-lzma2 1.6.0

- `-ma:uflzma2` moves from 1.5.1 to 1.6.0. The codec itself (encoder, match finder,
  LZMA2 decoder, assembler) did not change and the blocks are byte-identical; 1.6.0
  adds .xz streaming features that zpaq-std does not use.

#### Checked

- lz5-ex:
  - its six library files are identical to commit 5541227 on GitHub;
  - 180 combinations (`lz5f` and `lz5hc` at levels 1 to 15, six inputs) extract
    identically with zpaq 7.15 (ZPAQLZ5) and natively;
  - pre55 extracts the new blocks;
  - 1,200 damaged blocks, natively under AddressSanitizer: every one reported or
    harmless, no memory error, hang or silent corruption; zpaq 7.15 handled all
    of them too;
  - the exact-size buffer test: clean, also with `LZ5_compressBound` as the
    output limit, which overflowed in LZ5 1.5.
- ultra-fast-lzma2 1.6.0: levels 1 to 11 on the six inputs, byte-identical to 1.5.1
  (66/66) and extracted by zpaq 7.15 and natively.
- Windows 7 x64 and x86, with the release binaries: `-ma:lz5`, `lz5hc`, `lz5f` and
  `uflzma2` (also with `-m5`); `t` and `x` pass, all 28 extractions with identical
  sha256; archives made on Windows extract on Linux with zpaq 7.15, zpaqfranz,
  pre55 and pre56 (28/28).
- Full test battery: every suite has 0 cases to review; `suite_ma_hostil` 25/25;
  golden archives: 0 unexpected failures; `difftest` against pre55: the only
  differences are `-ma:lz5` blocks (new bytes), each version reading the other's.

### [65.4m-pre55] - 2026-10-01

#### Fixed: `-to` was ignored when a file argument had wildcards

- zpaq maps a name to its `-to` destination by replacing the file argument as a
  literal prefix. A pattern such as `dir/carpeta/*` or `C:\dir\carpeta\*.txt` is
  never a literal prefix of the names it matches, so `-to` was silently skipped.
  This comes from zpaq 7.15 and zpaqfranz:
  - `a archive "dir/carpeta/*" -to carpeta/` stored the full path instead of
    `carpeta/...`, with no warning;
  - `x archive "dir/data/*" -to restore/` extracted to the stored path instead of
    `restore/`. With `-force` it **overwrote the original files**.
- Now, when an argument has `*` or `?` and a name matches the pattern, the literal
  part of the pattern (up to the last `/` before the first wildcard) is replaced
  by the `-to` destination, with a `/` between them. Without wildcards, or without
  `-to`, nothing changes.

  | command | before | now |
  |---|---|---|
  | `a "dir/carpeta/*" -to carpeta/` | full path | `carpeta/a.txt`, `carpeta/sub/b.txt` |
  | `a "dir/carpeta/*.txt" -to x/` | full path | `x/a.txt` |
  | `x "data/*" -to restore/ -force` | overwrote the originals | extracts to `restore/` |

- zpaqfranz 65.6i and later refuse that `x` command with `71386!` instead; `a`
  still ignores `-to` there.

#### Checked

- Linux, and Windows 7 x64 and x86: with `\` and `/` and with the pattern in a
  different case from the folder on disk.
- Five new cases in `suite_glob`: four fail with pre54 and all pass now.
- Full test battery: every suite has 0 cases to review; golden archives: 0
  unexpected failures; `difftest` against pre54: 0 divergences.

### [65.4m-pre54] - 2026-10-01

#### Fixed: damaged kanzi archives could take minutes to fail in other zpaqs

- Every `-ma:kanzi` block carries its own ZPAQL decoder, so any zpaq can extract
  it. Fuzzing that path with zpaq 7.15 (1,350 archives with flipped bits in the
  block data, 150 per level) gave 296 extractions that ran past 2 minutes instead of
  reporting the damage: 57 to 119 of 150 at levels 3, 4 and 5, one at level 2.
- The cause was loops whose count comes from the block. With damaged data the count
  could start at 0, so the loop ran about 4 billion times before the checksum
  caught the result:
  - TEXT copied a dictionary entry of length 0;
  - TEXT's static dictionary hashed an empty word when damage left fewer than
    1024 words;
  - UTF read a length from outside its table;
  - DNA read an alphabet size of 0;
  - Huffman accepted a code length above 12 and filled its table about 2 billion
    times. That is now an error, as in kanzi.
- New blocks carry new decoders with those loops guarded: **ZPAQKANZI1B** (levels
  1–2), **ZPAQKANZI3B** (3–4), **ZPAQKANZI5C** (5–6), **ZPAQKANZI7B** (7) and
  **ZPAQKANZI8B** (8–9). Intact data never made any of those counts 0, so they
  decode exactly what the previous decoders do, which stay frozen and recognised
  for the archives that already carry them.
- zpaq-std itself was not affected: it decodes kanzi natively and reported the same
  damaged archives at once.

#### `-ma:kanzi` is no longer experimental

- kanzi stays pinned at 2.6.0. Its levels 1 to 9 are kanzi's own, and every
  block carries a decoder that any zpaq can run, so the warning
  `00603! kanzi is EXPERIMENTAL` is gone.

#### Checked

- Fuzzing the new decoders with zpaq 7.15: 2,700 archives, 300 per level, now
  flipping bits anywhere in the block data, including the header and the static
  dictionary. Every one either reported the damage or extracted correctly (21 flips
  had no effect). 0 extractions over 2 minutes, 0 crashes, 0 wrong output
  without an error.
- With intact data, the new decoders on the streams that checked the old ones, with
  zpaqd 7.15: 118 at levels 1–2, 210 at 3–4, 210 at 5–6, 114 at 7, 222 at 8–9. All
  identical to the input, except two at levels 5–6 that a test-name collision makes
  fail with the old decoder too.
- Large blocks: six inputs of about 70 MB at levels 1 to 9, with default and `-m5`
  blocks, extracted by zpaq 7.15 and by zpaq-std: 108/108 identical.
- Windows 7 x64 and x86, with the release binaries: kanzi levels 1 to 9 and 9 with
  `-m5`; `t` and `x` pass on everything, all 40 extractions with identical sha256.
  Archives made on Windows extract on Linux with zpaq 7.15, zpaqfranz, pre53 and
  pre54 (40/40). pre53 reads pre54 archives by running the decoder in the block.
- Full test battery: every suite has 0 cases to review; `suite_ma_hostil` 25/25;
  golden archives: 0 unexpected failures; `difftest` against pre53: 0 divergences.

### [65.4m-pre53] - 2026-10-01

#### The 32-bit Windows build compresses again

- From 64.7g-pre15 to pre52 the x86 build was extract-only: `a` stopped with
  `65000: compression is not supported on the 32-bit build`. It creates and updates
  archives again, with every method.
- Two limits keep it inside a 32-bit address space:
  - it compresses with **at most 2 threads**, also when `-t` asks for more
    (`65000: 32-bit build: compressing with 2 threads`);
  - the `.exe` is now **large-address-aware**, so on 64-bit Windows it gets 4 GB of
    address space instead of 2.
- The measured worst case per thread is about 1.2 GB (`-ma:lz5:15`), then
  `-ma:kanzi:9` with 64 MB blocks and `-m5`. Of the reasons for the old limit,
  `-pc` is gone since pre14 and the prefetch pool already had a smaller cap on
  32 bits.
- Checked on Windows 7 with the 32-bit build, on 118 MB of data (two 63 MB blocks
  in flight with `-m5`): `-m1` to `-m5` and 25 `-ma` codecs at their top levels,
  each with default and `-m5` blocks, extracted again by the same build and
  identical by sha256. The heaviest seven ran again limited to 2 GB of address
  space, as on 32-bit Windows, with the same result.

#### Fixed: running out of memory while decoding kanzi was reported as bad data

- When kanzi's native decoder ran out of memory, zpaq-std said `31319 kanzi
  decompression failed` and skipped the block. It happened on the 32-bit build
  with 2 GB of address space, decoding two `-ma:kanzi:9` blocks of 64 MB at once.
- Now it is treated as out of memory: the block goes back to the queue and another
  thread decodes it once memory is free, as zpaq-std already did for its own
  blocks. The archive was never damaged.

### [65.4m-pre52] - 2026-10-01

#### `-ma:kanzi`: levels 8 and 9, the last ones

- **`-ma:kanzi:8`** (EXE + RLT + TEXT + UTF + DNA, TPAQ) and **`-ma:kanzi:9`** (the same
  with TPAQX): exactly kanzi's own levels 8 and 9. All of kanzi's levels, 1 to 9, are
  available now, and every one opens in any zpaq.
- On 10 MB of English text (dickens) they give 21.8% and 21.3%; in the same run level
  7 gives 22.1%, and zpaq's `-m5` 20.6% while taking about 10 times longer to
  compress.
- Their blocks carry a new ZPAQL decoder, **ZPAQKANZI8**, for both levels. It
  decodes TPAQ, kanzi's PAQ8-style context-mixing coder: bit histories in hashed
  context slots (orders 0 to 3, a sparse context and a word/record context, plus one
  more for TPAQX), a match model, a neural mixer of 8 inputs and one or two adaptive
  probability maps. It also decodes RLT, EXE, TEXT, UTF and DNA, every block type and
  every combination of skipped transforms.
- **Slow and large in other zpaqs.** zpaq 7.15 decodes them at about 1 MB/s with
  JIT. A 16 MB block needs about 400 MB of memory at level 8 and 1.5 GB at level 9,
  because TPAQ sizes its tables from the block and TPAQX makes them 4 times larger.
  zpaq-std decodes natively.
- Written from a Python reference that was checked against kanzi's decoder, then
  verified with zpaq 7.15 on 222 streams: 99 inputs x levels 8 and 9, plus 24 blocks
  rebuilt to exercise other combinations of skipped transforms, all checked with
  kanzi's own decoder.

### [65.4m-pre51] - 2026-10-01

#### `-ma:kanzi`: level 7

- **`-ma:kanzi:7`** (LZP + TEXT + UTF + BWT + LZP, CM): exactly kanzi's own level 7.
  On 10 MB of English text (dickens) it gives 22.1%; in the same run level 6 gives
  22.5% and level 5 23.7%. Levels 1 to 7 are all available now; 8-9 still say so
  (`00605`) and use 7.
- Its blocks carry a new ZPAQL decoder, **ZPAQKANZI7**, so they open in any zpaq. It
  decodes CM (kanzi's binary context-mixing coder: order-0 and order-1 counters with
  a run flag and an adaptive probability map, behind the 56-bit binary arithmetic
  decoder), LZP, BWT, UTF and TEXT, every block type and every combination of skipped
  transforms. In zpaq 7.15 it runs at 4-7 MB/s with JIT; zpaq-std decodes natively.
- Written from a Python reference that was checked against kanzi's decoder (99
  streams), then verified with zpaq 7.15 on 114 streams: 99 inputs, among them an
  18 MB block, plus 15 blocks rebuilt to exercise other combinations of skipped
  transforms, all checked with kanzi's own decoder.

#### Fixed: `-ma:kanzi` levels 5 and 6 with blocks over 16 MB

- With a method that makes blocks larger than 16 MB (`-m5` makes 64 MB blocks), a
  `-ma:kanzi:5` or `-ma:kanzi:6` archive could not be extracted by another zpaq:
  zpaq 7.15 stopped with a checksum failure. zpaq-std always extracted it (it decodes
  natively), and with the default method blocks stay under 16 MB, so the default case
  was not affected.
- The cause was in ZPAQKANZI5 (since pre48): its BWT inverse packs a position and a
  byte into one 32-bit word, which only holds 2^24 positions.
- Levels 5 and 6 now write a new decoder, **ZPAQKANZI5B**: ZPAQKANZI5 with the BWT
  inverse of ZPAQKANZI7, which keeps the position alone and rebuilds the bytes from
  the first column. ZPAQKANZI5 stays frozen and recognised, so archives written since
  pre48 keep extracting in zpaq-std as before; blocks over 16 MB written by pre48-pre50
  still open only in zpaq-std.
- Verified with zpaq 7.15 on 212 streams, blocks of 18 and 20 MB among them, and
  `-m5` archives of 63 MB blocks at levels 5, 6 and 7, all identical.

#### `-catpaqmode`: real progress, once a second

- `-catpaqmode` (the telemetry for a GUI: `@SPK@EXT@` / `@SPK@PRG@` lines) printed
  about one line per run. Its numbers came from the console progress, which moves
  only when a file is read (`a`) or when a whole block is done (`x`, `t`).
- A ticker now prints one line a second:
  - for `a`, from what has really been compressed, as the `-innosetup` window does;
  - for `x` and `t`, from how far each block's decoding has got, out of what the
    blocks to decode hold.
  The percentage never goes back, and nothing is printed below 1,000,000 bytes done.
- The `@DEC@DEC@` line is now `@SPK@DEC@`, as documented. Its total is the archive
  size, and its time field no longer reads an uninitialised clock (it printed huge
  negative numbers).

### [65.4m-pre50] - 2026-10-01

#### `-ma:kanzi`: levels 3 and 4

- **`-ma:kanzi:3`** (TEXT + UTF + PACK + MM + LZX, Huffman) and **`-ma:kanzi:4`** (TEXT +
  UTF + EXE + PACK + MM + ROLZ, no entropy coder): exactly kanzi's own levels 3 and 4.
  On 10 MB of English text (dickens) they give 30.8% and 27.4%; in the same run level
  2 gives 38.9% and level 5 23.7%. Levels 1 to 6 are all available now; 7-9 still say
  so (`00605`) and use 6.
- Their blocks carry a new ZPAQL decoder, **ZPAQKANZI3**, so they open in any zpaq.
  ZPAQKANZI and ZPAQKANZI5 are untouched. The block is the same as for levels 5-6,
  with kanzi's static dictionary as a data prefix.
- ZPAQKANZI3 decodes:
  - TEXT (kanzi's word dictionary), UTF, PACK (the alias codec) and LZX;
  - MM (kanzi's FSD codec): delta and xor, plain and bucketed;
  - EXE: the x86 and ARM64 branch filters;
  - ROLZ (ROLZCodec1): match length 3, 4 or 7, both kinds of keys, literals with
    order-0 or order-1 ANS, and 16 MB chunks;
  - every block type and every combination of skipped transforms.
- It runs at 13-39 MB/s with JIT in zpaq 7.15. Memory in another zpaq for a 16 MB
  block: about 96 MB for level 3 (M 64 MB + H 32 MB) and 160 MB for level 4 (M 128
  MB + H 32 MB). zpaq-std decodes natively.
- Written from a Python reference that was checked against kanzi's decoder (198
  streams), then verified with zpaq 7.15 on 210 streams: 99 inputs x 2 levels, plus 12
  blocks rebuilt to exercise other combinations of skipped transforms and FSD's xor
  modes, which kanzi's encoder never writes, all checked with kanzi's own decoder.

### [65.4m-pre49] - 2026-10-01

#### The old `-ma` format is no longer read

- Before the ZPAQL decoders, `-ma` blocks carried no decoder: zpaq-std's own
  post-processing type 2 and a `zpaqstd-ma:` tag, readable only by zpaq-std. Every
  codec wrote that up to pre23, and some until they became portable (bsc, lzh and ppmd
  until pre40–pre42). zpaq-std now stops on them with
  `31320 old -ma block format, no longer supported`; zpaq-std pre48 or older still
  reads them.
- The code that read them is gone: 17 tag readers and 16 native decode paths.
- The last path that could still write that format is gone too: a Lizard block too
  large for its ZPAQL decoder's memory now stays a native zpaq block.
- Archives with ZPAQL decoders (`zpaqstd-ma2:`) and native ones are not affected.
- Test lab: the golden archives that hold old-format `-ma` blocks are now expected
  failures. All 145 stop with 31320, and every native golden archive passes.

### [65.4m-pre48] - 2026-10-01

#### `-ma:kanzi`: levels 5 and 6

- **`-ma:kanzi:5`** (TEXT + UTF + BWT + RANK + ZRLT, ANS0) and **`-ma:kanzi:6`** (TEXT +
  UTF + BWT + SRT + ZRLT, FPAQ): exactly kanzi's own levels 5 and 6, its English word
  dictionary (TEXT) and UTF-8 alias transform included. On 10 MB of English text
  (dickens) they give 23.4% and 22.3%; level 2 gives 38.7%. Levels 3, 4 and 7-9 still
  say so (`00605`) and use the nearest available one.
- Their blocks carry a new ZPAQL decoder, **ZPAQKANZI5**, so they open in any zpaq.
  Levels 1-2 keep ZPAQKANZI, untouched.
- ZPAQKANZI5 decodes:
  - both variants of kanzi's TEXT transform: the 1024-word static dictionary, which
    travels as a 5,487-byte data prefix in each block, plus the dynamic dictionary,
    rebuilt with kanzi's hash, its slot handling and its expansions;
  - UTF, BWT (with its chunk indexes), RANK, SRT and ZRLT;
  - order-0 rANS with 4 states, and FPAQ with its 56-bit range coder;
  - every block type and every combination of skipped transforms.
- It runs at 2.6-12 MB/s with JIT in other tools. Memory there is large: the BWT
  inverse needs 4 bytes per byte of block, so a 16 MB block takes about 192 MB (H
  128 MB + M 64 MB) in another zpaq. zpaq-std decodes natively.
- Written from a Python reference that was checked against kanzi's decoder (156
  streams), then verified with zpaq 7.15 on 194 streams: 78 inputs x 2 levels, plus 38
  blocks rebuilt to exercise other combinations of skipped transforms and a
  one-symbol ANS chunk, all checked with kanzi's own decoder.

### [65.4m-pre47] - 2026-09-30

#### New codec: `-ma:kanzi` (experimental)

- **`-ma:kanzi:N`** compresses with [kanzi](https://github.com/flanglet/kanzi-cpp)
  2.6.0 by Frederic Langlet (Apache 2.0). Levels **1** (LZX) and **2** (DNA + LZ +
  Huffman, the default), the two that have a ZPAQL decoder so far; a higher level
  says so (`00605`) and uses 2. On 3.86 MB of text, level 2 gives 16.9% and level 1
  19.3%, both in a few hundredths of a second.
- Its blocks carry their own ZPAQL decoder, **ZPAQKANZI**, written for kanzi's
  bitstream 7: every block type (normal, raw copy, transformed copy) and every
  combination of skipped transforms, Huffman with 4 interleaved streams, LZX with
  repeat distances, and all of DNA's packings. zpaq 7.15, zpaqfranz and every
  zpaq-std from pre20 on extract them (25-73 MB/s with JIT); zpaq-std decodes
  natively.
- **Experimental**: kanzi's format changes about once a year (bitstream 6 in 2.4.0,
  7 in 2.6.0), so this copy stays pinned; a later format comes in with a new ZPAQL
  decoder next to this one. What an archive already holds does not change.
- More levels (5-6, BWT with ANS/FPAQ, next) come when they have their decoder.

### [65.4m-pre46] - 2026-09-27

- **`-ma:lz5` and `-ma:lz6` could corrupt memory and abort `a`** on data that LZ
  cannot compress, a whole block at a time (measured with 16 MB of base64 of random
  bytes). The HC parsers of LZ5 1.5 (level 9 on, and 9 is `-ma:lz5`'s default) and
  lz6 (level 10 on) can write MORE than their own `compressBound()`, up to 732 KB
  past the buffer; they only check the output limit when it is below that bound, and
  zpaq-std gave them exactly the bound. `a` died with `free(): invalid size`,
  `double free` or a segfault. zpaq-std now gives them the original size as the
  limit (an output that large is useless anyway), so they stop and the block stays
  native. Same output bytes as before, except for lz6 level 2 on some inputs, where
  lz6 parses slightly differently with the limit on (a few bytes smaller; it
  decodes the same). The bug itself is lz6's and LZ5's; it was reported to lz6.
  In every case measured `a` aborted instead of writing the archive. If an older
  version did finish an `-ma:lz5` / `-ma:lz6` archive of such data, `t` checks it:
  it recomputes the SHA-1 of every fragment, so memory damaged by the overflow would
  show up there.
- A new test, `suite_ma_hostil.sh`, covers it: under AddressSanitizer, every `-ma`
  codec on data LZ cannot compress. Only lz5 and lz6 overflowed.
- **`-ma:lz5` and `-ma:lizard` output depended on the state of the heap.** Their
  hash/chain tables come from `malloc` and the parsers read entries before writing
  them (valgrind: every `-ma` codec checked; only Lizard, LZ5 and lz6's HC levels
  did this). The output was always valid, but the same input could compress to
  different bytes. They are now built with the libraries' own `LZ5_RESET_MEM` /
  `LIZARD_RESET_MEM`, which reset the tables first. lz6 fixed both bugs on its
  side (bundled lz6 moves from 1dd4bec to 52076b2), with the same output as before
  whenever it fits.
- **`-ma:lizard` was built without optimisation**, since the first release: its
  Makefile rule never matched, so make used its built-in rule (plain `cc -c`, no
  `-O3`). It is now 1.8x faster at level 10 and 3.4x at levels 29 and 49, with the
  same output.

### [65.4m-pre45] - 2026-09-27

#### New codec: `-ma:uflzma2` (experimental)

- **`-ma:uflzma2:N`** compresses with [ultra-fast-lzma2](https://github.com/YadeWira/ultra-fast-lzma2)
  1.5.1, a fork of Conor McCarthy's fast-lzma2 (most of the code is his). Its output
  is standard LZMA2, byte for byte the same as fast-lzma2 1.0.1 at levels 1 to 10;
  level **11** also picks lc/lp/pb per block (3/0/2, 4/0/1 or 1/2/2). Levels 1–11,
  default 5. It is a codec of its own, next to `-ma:flzma2`, which stays on
  fast-lzma2.
- Its blocks carry their own ZPAQL decoder, **ZPAQUFLZMA2**, so they open in any
  zpaq: zpaq 7.15, zpaqfranz, and every zpaq-std from pre20 on. It is ZPAQFLZMA2's
  program with one more instruction, which gives uflzma2 a decoder of its own: the
  LZMA2 walk already reads the properties of every chunk, so every lc/lp/pb
  (lc+lp up to 4) decodes. zpaq-std decodes natively, with ultra-fast-lzma2's
  assembler decoder on x86_64.
- **Experimental**: its encoder may still change between releases; what an archive
  already holds does not.
- The two libraries share internal symbol names, so ultra-fast-lzma2 is linked into
  one relocatable object with only its `UF2_*` API left global.
- The README now lists the experimental codecs (lz6, uflzma2, and zpaqfranz's LZ4
  and LZAV) in a table of their own.

### [65.4m-pre44] - 2026-09-26

A round of deep testing (four test agents: damaged archives, every command and
switch, the `-ma` codecs at their limits, stress and interruptions; plus Windows).
The bugs that turned out to be zpaqfranz's own (33, reproduced against the
original 65.4m) were handed to zpaqfranz's side to list and report. These are the
ones that were zpaq-std's, all fixed here:

- **A damaged `-ma` block could hang `x` and `t` forever.** When the damage fell
  inside the block's ZPAQL decoder, zpaq-std no longer recognised it and ran it: a
  corrupted ZPAQL program may never end (19 hangs out of ~4,000 damaged blocks, in
  ppmd, lzh, bzip2, deflate, lz5, lz6, lzma and zstd). A decoder that is the same
  size as one of zpaq-std's and differs in a few bytes is now reported as damaged
  (`damaged ZPAQL decoder in a -ma block`), and the rest of the archive extracts.
- **`-ma:lizard`: a damaged block could crash zpaq-std** (heap overflow). Lizard's
  own decoder did not count uncompressed blocks against the output size, so the next
  block could write past the end. Fixed in the bundled Lizard (one line; valid
  streams decode as before). zpaqfranz and zpaq 7.15 were not affected (they run the
  ZPAQL).
- **`-ma:hs` could not read back its own blocks past ~128 MB compressed**: a fixed
  iteration cap in zpaq-std's heatshrink wrapper. It now scales with the data.
- **`-ma` blocks were written with a comment the zpaq format does not expect**
  (`size jDC\x01 zpaqstd-ma2:...`: a journaling comment must END in `jDC\x01`).
  Extraction worked everywhere, but the strict tester `p` failed on every `-ma`
  archive, `dump` could not see the blocks, and recovery of a damaged `-ma`
  archive was far worse than of a `-m` one (a missing index block: 0 files instead
  of all of them). The tag now goes before `jDC\x01`, and zpaq-std also accepts the
  old form, so **archives written by pre20 to pre43 recover as well as `-m` ones
  now**. Every version from pre20 on, zpaq 7.15 and zpaqfranz read the new form.
- **`-ma` levels**: `ppmd:16` to `32` were silently capped at 15; `brotli:0`,
  `deflate:0` and `lz:0` (documented) were silently raised to 1; a level that is
  not a number (`-ma:zstd:abc`, `:3x`, `:-5`) and a bare `-ma` were accepted
  without a word. They now do what the help says, or stop with a clear message.
- `x -to <new folder>` printed `00067! Path does not exists` although it worked;
  now only with `-debug`. `dir` and `tree` glued their progress line to the header.

### [65.4m-pre43] - 2026-09-25

#### `-innosetup` is now `-popgui`

The progress window switch is now **`-popgui`**. **`-innosetup` keeps working**
as its legacy name (same switch), so installers already built with it need no
change. The window's buttons lose their heavily rounded, jagged corners: the
radius was 8 px on a 28 px button, drawn by GDI without anti-aliasing; it is now
3 px, like Windows 10/11 buttons, and the focus border is drawn inside the
button instead of being clipped at its edge (checked on Windows 10, light theme).
The switch's help line said "else print progress %%"; off Windows the switch is
ignored, and the help now says so.

#### `-ma:lz6` has its own decoder, ZPAQLZ6

Up to pre42, `-ma:lz6` blocks carried ZPAQLZ5, the `-ma:lz5` decoder, because lz6's
portable profile is the same LZ5 v1.5 block format. Now lz6 has its own program,
**ZPAQLZ6**, as a precaution: lz5 and lz6 no longer share a decoder, so if either
ever needs a new one the other is not touched. Nothing changes for users: the
blocks are the same, archives still open in any zpaq, and old `-ma:lz6` archives
(tag `zpaqstd-ma2:lz5-lz6:`) still extract.

ZPAQLZ6 decodes exactly what ZPAQLZ5 decodes. Its bytecode had to be different:
pre24 to pre42 recognise ZPAQLZ5 byte for byte and skip running it, and with a tag
they do not know they would have returned the compressed bytes. With a bytecode
they do not know, they run the ZPAQL and get the data right. The only change is in
the match copy loop (it counts with another register); the speed is the same
(measured, with and without the JIT).

Checked here: lz6's 23 test vectors (fast and HC, windows 2^16 to 2^24) decode
identically with ZPAQLZ6 and ZPAQLZ5 in zpaqd 7.15; archives written at levels 0,
1, 9 and 12 extract identically with zpaq 7.15, zpaqfranz, pre20, pre24, pre25,
pre27, pre30, pre35, pre39, pre42 and this build; pre42's `-ma:lz6` archives
extract with this build.

#### `-ma:lz6:13`–`15` no longer crawl on repetitive data

Levels 13 to 15 could take minutes on a block with a long repetitive run: 1 MB
of a repeated pattern took about 26 s at `-ma:lz6:15` (0.02 s at 12), and 9.8 MB
more than half an hour. It was in lz6's optimal parser, and only showed up in
zpaq-std because every zpaq block ends with its fragment table, so the run never
reaches the end of the buffer. Found here and reported to lz6, which fixed it;
the vendored lz6 goes from a8e1b51 to **1dd4bec**. That block now takes 0.23 s.
**The output is byte-identical**: checked against a8e1b51 on 36 inputs at levels
0 to 15, 64 and 32 bits (576 cases), so archives do not change. lz6 v1.6.4 to
this commit write the same bytes for what `-ma:lz6` uses.

### [65.4m-pre42] - 2026-09-25

#### `-ma:ppmd` opens in any zpaq (ZPAQPPMD): all 23 `-ma` switches are portable

`-ma:ppmd` blocks now carry **ZPAQPPMD**, a PPMd var.H decoder written in ZPAQL
(Ppmd7 from the 7-Zip SDK, with 7z's range coder), so zpaq 7.15, zpaqfranz and
every zpaq-std from pre20 on extract them. zpaq-std decodes them natively, as
before. With this, **all 23 `-ma` switches write archives that any zpaq
extracts.** The old blocks (`zpaqstd-ma:ppmd`, pre41 and earlier) still extract.

PPMd was the hardest: its model lives in a heap and its behaviour depends on the
memory allocator (it compares heap offsets, glues free blocks together and
restarts the model when the memory runs out). So the decoder reproduces the
SDK's 64 MB heap byte for byte: the same 12-byte units, free lists,
GlueFreeBlocks and RestartModel. A Python reference decoder was written first
and checked against the SDK, including the restart and glue paths (forced with
small memories); the ZPAQL was then checked against both. The 7z stream has
neither the model order nor the original size, so a portable block starts with
a 9-byte header carrying them and the model memory.

For other tools the decoder runs at 0.6-3.5 MB/s with the ZPAQL JIT (0.1-0.2
without it), and needs 128 MB of memory per block (the 64 MB model plus the
stream). zpaq-std decodes natively.

Checked here: 213 PPMd streams decode byte for byte with zpaqd 7.15 (49 corpus
files at orders 2, 6, 16 and 32 with 64 MB; 16 MB blocks, where order 32
restarts the model 6 times and glues free blocks 12,107 times; and memories
from 4 KB to 4 MB). Archives written at orders 2, 6, 16 and 32 extract
identically with zpaq 7.15, zpaqfranz, pre20, pre30, pre35, pre38, pre39,
pre40, pre41 and this build.

`-ma:ppmd` also gets its missing line in the help (`h voodoo`).

### [65.4m-pre41] - 2026-09-25

#### `-ma:bsc` opens in any zpaq (ZPAQBSC)

`-ma:bsc` blocks now carry **ZPAQBSC**, a libbsc decoder written in ZPAQL, so
zpaq 7.15, zpaqfranz and every zpaq-std from pre20 on extract them. zpaq-std
decodes them natively with libbsc, as before. That makes **22 of the 23 `-ma`
switches portable**; only ppmd is left. The old blocks (`zpaqstd-ma:bsc`, pre40
and earlier) still extract.

zpaq-std calls libbsc without LZP, so a block is the sort transform (ST3, ST4 or
ST5 by level) and the static QLFC coder: a range coder where every bit is
predicted by a fixed mix of three adaptive counters, followed by the inverse
sort transform. A Python reference decoder was written first and checked
against libbsc; the ZPAQL was then checked against both. Every block carries
QLFC's two state tables as a fixed 40 KB data prefix (like brotli's
dictionary); a block that does not win with it stays native.

For other tools the decoder runs at 2-9 MB/s with the ZPAQL JIT (0.3-0.6
without it), and needs about 12 bytes of memory per byte of the block (192 MB
for a 16 MB block). zpaq-std decodes natively.

Checked here: 177 bsc streams (59 inputs up to 17.5 MB, ST3/ST4/ST5) decode byte
for byte with zpaqd 7.15; archives written at levels 1, 4, 7 and 9 extract
identically with zpaq 7.15, zpaqfranz, pre20, pre30, pre35, pre38, pre39, pre40
and this build.

Also fixed: libbsc was initialised on first use without a lock, from several
extraction threads at once. It is now initialised exactly once. The help text
no longer says `-ma:bsc` uses LZP (zpaq-std never enabled it).

### [65.4m-pre40] - 2026-09-25

#### `-ma:lzh` opens in any zpaq (ZPAQLZHAM)

`-ma:lzh` blocks now carry **ZPAQLZHAM**, an LZHAM 1.0 decoder written in ZPAQL,
so zpaq 7.15, zpaqfranz and every zpaq-std from pre20 on extract them. zpaq-std
decodes them natively with LZHAM, as before. That makes **21 of the 23 `-ma`
switches portable**; only bsc and ppmd are left. The old blocks
(`zpaqstd-ma:lzh`, pre39 and earlier) still extract.

LZHAM is the hardest of the lot to carry: besides the LZ layer (12 states, four
rep distances, delta literals after a match) and a binary arithmetic coder, it
has 134 **quasi-adaptive Huffman tables** that rebuild themselves every few
hundred symbols, and the decoder has to rebuild them exactly as the encoder
did: the same stable sort by frequency, the same code lengths (polar codes at
levels 1-3, Moffat-Katajainen Huffman at level 4), the same length limit and the
same rescaling. A Python reference decoder was written first and checked
against LZHAM itself; the ZPAQL was then checked against both.

Checked here: 240 LZHAM streams (61 inputs, levels 1-4) decode byte for byte
with zpaqd 7.15; archives written at every level extract identically with zpaq
7.15, zpaqfranz, pre20, pre30, pre35, pre38, pre39 and this build.

The help text said level 4 was LZHAM's "uber"; it is "better" (as it always
was). The level mapping did not change.

### [65.4m-pre39] - 2026-09-25

**zpaq-std now builds on zpaqfranz 65.4** (the release's own `zpaqfranz.cpp`,
65.4m). Everything upstream added comes in; see
[zpaqfranz 65.4](https://github.com/fcorbelli/zpaqfranz/releases/tag/65.4). The
main points:

- **Fixed: `-ma` archives with many small, nearly incompressible files could
  fail to extract** (`31319 flzma2 decompression failed`, also zstd, bzip2, lz5,
  lizard, lzh...). The archive was always fine; the reader stopped reading such
  a block too early and handed the codec a truncated stream. Found on a real
  3 GB archive (10,515 files in 3 `-ma:flzma2:9` blocks), which now extracts
  and tests clean. zpaq 7.15 and zpaqfranz were never affected (they run the
  ZPAQL decoder). New `test/testlab/suite_ma_frag.sh` covers it: 7 failures on
  pre38, 0 now.

- **`l` in a fraction of a second on huge archives** with `-filelist`: the
  history of the archive is kept inside it. `l` is also about 3 times faster
  without it. Checked here: the file list is the same with and without
  `-filelist`.
- **`-tar`** (*nix): owners, permissions, symlinks, hard links, FIFOs, devices
  and nanosecond times, stored and given back.
- **`-turbo N`**: how many threads. Checked here: `-turbo 8` with `-ma` (zstd,
  bzip3, brotli, lz5) writes the same archive as without `-turbo`.
- The `-silent` / `-out` / DLL formatter for `%Z %K %H` (#289, found by **ZF**)
  is now upstream's own `zpaqfranz_vformat`; it replaces the version zpaq-std
  carried since pre32. zpaq-std keeps its own addition on top: errors and
  warnings still go to stderr and to the `-innosetup` window when everything
  else is silent.
- `x` never writes through a symlink, a FIFO or a device; one temporary folder
  per user; the Windows ADS file list is gone (`-filelist` replaces it).

#### A hang that the merge would have introduced

zpaq-std's parallel read-ahead (the front-end pool, since pre20) opens every file
of an `a` with `fopen()`. Under the new `-tar` that **followed symlinks** (storing
the target's data instead of the link) and, on a **FIFO, waited forever**: the
`a` never ended. Upstream's `add()` avoids opening those files; the pool did not
know. Now the pool leaves symlinks, FIFOs and devices to the main thread, as
upstream does. With `-t1` (no pool) it already worked, which is why it slipped
past the merge. A new test, `suite_tar.sh`, checks symlinks, hard links, FIFOs,
permissions and data with 1, 4 and the default threads; the build without the
fix hangs in 2 of its 3 cases.

The version string is now `65.4m`.

### [65.3y-pre38] - 2026-09-25

#### `-ma:bzip3` opens in any zpaq (ZPAQBZIP3)

`-ma:bzip3` blocks now carry **ZPAQBZIP3**, a bzip3 decoder written in ZPAQL, so
zpaq 7.15, zpaqfranz and every zpaq-std from pre20 on extract them. zpaq-std
decodes them natively with libbz3, as before. That makes **20 of the 23 `-ma`
switches portable**; only bsc, lzh and ppmd are left. The old blocks
(`zpaqstd-ma:bzip3`, pre37 and earlier) still extract.

bzip3 is BWT plus a small context-mixing coder: an order-0 table by bit context,
an order-1 table by the previous byte, and an APM with interpolation, over a
32-bit arithmetic coder. Two details had to match C exactly:

- the coder's 32×32→64 multiply, which ZPAQL (32-bit registers) cannot do in one
  step: it is split so no partial product passes 32 bits;
- the APM's shift of a negative number, which C floors.

After the coder come the inverse BWT (libsais' convention: the sentinel sits in
the row of the primary index), bzip3's LZP and its run-length step, block by
block, plus the raw blocks bzip3 writes under 64 bytes.

**2,272 bytes** of bytecode. It is the slowest portable decoder for other tools,
**~5 MB/s** with the JIT and ~0.2 MB/s without, because every bit goes through
the model; zpaq-std itself decodes natively. The reader needs 8 MB of H (ph = 21)
and two block buffers in M.

Checked:

- zpaqd 7.15 on 77 bzip3 streams: 26 inputs × levels 1, 5 and 9 (12 MB at
  level 1 is 120 blocks of 100 KB), and blocks under 64 bytes.
- zpaq 7.15, zpaqfranz, pre20 through pre37 and this version extract levels 1
  and 9 identically, and `t` passes.
- The help said "BWT+ANS": bzip3 is BWT+CM. Fixed.

### [65.3y-pre37] - 2026-09-25

#### `-ma:brotli` opens in any zpaq (ZPAQBROTLI)

`-ma:brotli` blocks now carry **ZPAQBROTLI**, a brotli decoder written in ZPAQL for
zpaq-std **from the specification** (RFC 7932). It does not derive from zpaqlpy's
decoder, which is GPL-3. zpaq 7.15, zpaqfranz and every zpaq-std from pre20 on
extract these blocks; zpaq-std decodes them natively with libbrotli, as before.
That makes **19 of the 23 `-ma` switches portable**; only bzip3, bsc, lzh and ppmd
are left.

brotli reads prefix codes in many places, and ZPAQL has no subroutines, so the
program is a **state machine**: one loop, where "calling" the prefix-code reader
means saving the state to return to. Symbols, literals, copies and dictionary words
stay inline. It supports:

- every meta-block type, simple and complex prefix codes, and block switching;
- context maps with RLE and inverse move-to-front, and the four literal context
  modes;
- NPOSTFIX/NDIRECT and the distance ring buffer;
- static-dictionary words with all 121 transforms;
- any window size.

**9,535 bytes** of bytecode and **40–44 MB/s** with the JIT (2.3–2.5 without);
zpaqlpy's decoder measured 63 KB and 1.6 MB/s.

Each block carries a **fixed 126 KB data prefix** in front of the stream: the
122 KB static dictionary, the context table, the transforms and constant tables.
zpaq-std builds it from libbrotli itself. When the prefix would eat the gain
(blocks under ~130 KB), the block stays native instead, and is still portable.
The old `zpaqstd-ma:brotli` blocks (pre36 and earlier) still extract.

Checked:

- zpaqd 7.15 on 182 streams: 22 inputs × qualities 0, 1, 5, 9, 10 and 11, 38 more
  texts at quality 11, and windows 10, 16 and 24.
- Hand-made streams for the transforms the encoder never writes (omit first 1–9):
  libbrotli's own decoder accepts them with the same output. The transform logic
  also matches libbrotli's in 30,734 cases.
- zpaq 7.15, zpaqfranz, pre20 through pre35 and this version extract qualities 1
  and 11 identically, and `t` passes.

#### The warning for `-ma:lz4` / `-ma:lzav` was wrong

Since pre32 `-ma:lz4`, `lz4hc`, `lz4f` and `lzav` write zpaqfranz's `-m6` / `-m7`,
which any zpaq extracts. `00596!` still said they would "NOT open in any other
zpaq". They now print `00604` ("is written as -m6 … any zpaq can extract it"), and
the list of portable options in `00596!` is up to date. Reported by the user.

#### A lighter README

The README went from 560 to 224 lines. Each portable decoder's detail moved to a
new wiki page,
[Portable codecs](https://github.com/YadeWira/zpaq-std/wiki/Portable-codecs), and
the `compressors/` tree and the 32-bit notes moved to
[Building](https://github.com/YadeWira/zpaq-std/wiki/Building).

The `.zpqs` extension (issue #1) is dropped: with 19 of 23 codecs portable, a
`.zpaq` written by zpaq-std opens in any zpaq unless one of the four remaining
codecs is chosen, and those warn.

### [65.3y-pre36] - 2026-09-25

#### `-ma:zstd` and `-ma:lzfse` open in any zpaq (ZPAQZSTD, ZPAQLZFSE)

`-ma:zstd` and `-ma:lzfse` blocks now carry their own ZPAQL decoders, so zpaq
7.15, zpaqfranz and every zpaq-std from pre20 on extract them. zpaq-std
recognises the programs and decodes natively with libzstd and liblzfse, as
before. The old blocks (`zpaqstd-ma:zstd`, `zpaqstd-ma:lzfse`, pre35 and
earlier) still extract.

**ZPAQZSTD** (zstd, RFC 8878) supports:

- raw, RLE and compressed blocks;
- raw, RLE, Huffman and treeless literals, with 1 or 4 streams;
- sequences with predefined, RLE, transmitted and repeated FSE tables;
- the three repeat offsets, including the "offset − 1" case;
- several frames, skippable frames and the checksum.

The literals' Huff0 and the FSE table code are ZPAQLIZARDH's.
`compressors/zpaqlizard/huff0.py` was split into pieces so both programs share
them; ZPAQLIZARDH still comes out byte for byte. **7,505 bytes** (mostly the
constant tables), **47–70 MB/s** with the JIT, 3.5–4 MB/s without.

**ZPAQLZFSE** (Apple lzfse) is a decoder of its own: lzfse's FSE is not zstd's
(each symbol gets a contiguous run of states, and the L/M/D decoders read the
state and extra bits in one pull). It supports:

- the bit-packed block header;
- the frequency tables with lzfse's fixed prefix code;
- literals from four interleaved states;
- L/M/D, with D = 0 repeating the last distance;
- the LZVN blocks lzfse writes for inputs under 4 KB (every opcode);
- raw blocks.

**4,931 bytes**, **~48 MB/s** with the JIT, ~3.5 MB/s without.

Both keep the frame or stream in M with the whole output behind it (matches
look back into it); the reader needs ph = 13.

Checked:

- zpaqd 7.15: 506 zstd frames (23 inputs × levels 1–22), plus a stream of two
  frames (one with checksum) around a skippable frame; 37 lzfse streams
  (including cuts around the 4 KB LZVN/FSE threshold, random data and 12 MB).
- zpaq 7.15, zpaqfranz, pre20 through pre35 and this version extract
  `-ma:zstd` (levels 3 and 19) and `-ma:lzfse` identically, and `t` passes. A
  3 KB archive (an LZVN block) opens in all of them too.
- `suite_ma_corre` now requires zpaq 7.15 to extract both.

### [65.3y-pre35] - 2026-09-24

#### `-ma:bzip2` opens in any zpaq (ZPAQBZIP2)

`-ma:bzip2` blocks now carry **ZPAQBZIP2**, a bzip2 decoder written in ZPAQL,
so zpaq 7.15, zpaqfranz and every zpaq-std from pre20 on extract them. zpaq-std
recognises the program and decodes natively with libbzip2, as before.

bzip2 blocks are not byte-aligned, so the whole stream is kept in M and decoded
at the end of the segment. Per block:

- the byte map, the selectors (unary + MTF) and the code lengths (deltas);
- canonical Huffman decoded one bit at a time (the ZPAQDEFLATE method);
- MTF and RUNA/RUNB;
- the inverse BWT with a 32-bit `tt[]` in H (libbzip2's fast mode: the byte in
  the low 8 bits, the pointer above);
- the final run-length step.

The output goes straight out with OUT. Several blocks and several
concatenated streams are handled.

**1,964 bytes** of bytecode. It is the slowest portable decoder for other
tools: **~17 MB/s with the JIT, ~1 MB/s without** (12 MB of text). The reader
needs 4 MB of H (ph = 20, a 900 KB block).

The old blocks (`zpaqstd-ma:bzip2`, pre34 and earlier) still extract.

Checked:

- zpaqd 7.15 on 198 streams (22 inputs × levels 1–9), on two concatenated
  streams, and on 12 MB at levels 1, 5 and 9.
- Levels 1, 5 and 9: zpaq 7.15, zpaqfranz, pre20 through pre34 and this version
  extract them identically, and `t` passes.
- `suite_ma_corre` now requires zpaq 7.15 to extract `-ma:bzip2`.

### [65.3y-pre34] - 2026-09-24

#### `-ma:lizard` levels 30–49 open in any zpaq (ZPAQLIZARDH)

Levels 30–49 of Lizard add Huffman, and until now they were the part of
`-ma:lizard` that stayed non-portable. Now their blocks carry **ZPAQLIZARDH**,
a new ZPAQL decoder: the ZPAQLIZARD program (fastLZ4 at 30–39, LIZv1 at 40–49)
plus **Huff0**, the Huffman coder of zstd 1.4 that Lizard 2.1 embeds:

- the code weights, coded with FSE (header with zero runs and low-probability
  symbols, a two-state backward stream) or raw at 4 bits each;
- the canonical code, decoded one bit at a time (like ZPAQDEFLATE);
- four bit streams read backwards, with a 6-byte jump table;
- or a single repeated byte (RLE).

Each Huffman stream is decoded into M behind the compressed data (at most four
of 128 KB per Lizard block), and then the same LIZv1/fastLZ4 loop runs. The
four streams go through one loop, so the Huff0 decoder appears once:
**3,651 bytes** of bytecode (ZPAQLIZARD: 1,210), **42–102 MB/s** with the JIT
and 3–8.5 MB/s without, on 6 MB of text.

It is a program of its own: levels 10–29 keep ZPAQLIZARD, and their archives
are byte for byte the ones pre33 writes. The tag is still `zpaqstd-ma2:lizard`,
so pre31–pre33 (and pre20 onwards, like zpaq 7.15 and zpaqfranz) extract levels
30–49 by running the ZPAQL; this version takes the native shortcut.

Checked:

- zpaqd 7.15 on 1,402 Lizard streams: 35 inputs × levels 10–49, plus
  hand-made RLE streams, also checked against Lizard's own decoder.
- Levels 30, 39, 40, 45 and 49: zpaq 7.15, zpaqfranz, pre20 through pre33 and
  this version extract them identically, and `t` passes.
- `suite_ma_corre` and `difftest` now include `-ma:lizard:45`.

Generated by `compressors/zpaqlizard/gen.py --huff` (the Huff0 part in
`huff0.py`); without `--huff` gen.py still writes the frozen ZPAQLIZARD, byte
for byte.

### [65.3y-pre33] - 2026-09-24

#### `-turbo` works with every `-ma` codec

pre32 sent `-turbo` with a `-ma` codec (other than lz4/lzav) through the normal
`add` with notice `00605`, because `add2()` — upstream's copy of `add()` that
`-turbo` runs — had none of zpaq-std's `-ma` branches. Now the whole `-ma`
chain lives in a single function, `ma_comprimir_bloque()`, and `add()` and both
block flushes of `add2()` call it. `00605` is gone.

Checked: with each of the 23 codecs, `-turbo` writes **byte for byte the same
archive** as without it (fixed `-timestamp`), on 8.6 MB and on 214 MB in many
blocks, with `-t1` too; it extracts and `t` passes. `suite_ma_corre` now checks
this for each codec (a `turbo` column). A negative control — `add2` built
without the call — gets caught: 19 of 23 marked (lz4/lzav do not go through the
chain, they are `-m6`/`-m7`).

What `-turbo` speeds up is the fragmenter and the SHA-1, not the codec: with a
slow codec the gain is small (214 MB: `-ma:lz5` 15.0 s → 14.3 s; `-ma:lzma` and
`-ma:zstd` about the same).

### [65.3y-pre32] - 2026-09-24

**zpaq-std now builds on zpaqfranz 65.3.** Everything upstream added in 65.3
comes in, and `-ma:lz4` / `-ma:lzav` become another way of writing its new
`-m6` / `-m7`.

The base is the source of the 65.3 release tag, **65.3y** (the release ships
no source asset, and its binaries report a later build, 65.3z; when that
source is published it gets merged too).

#### What comes from 65.3

See [zpaqfranz 65.3](https://github.com/fcorbelli/zpaqfranz/releases/tag/65.3)
for the details. The main points:

- **`a` is faster**, writing the very same archive (Franco measured 34.4 s →
  25.3 s on 12.9 GB).
- **`-turbo`**: the fragmenter and the fragment SHA-1 in parallel; the same
  archive, faster. Checked here: `-turbo` writes the same archive as without it
  with `-m1`, `-m7` and `-ma:lzav`.
- **`-m6` (LZ4) and `-m7` (LZAV)**: fast methods whose blocks carry a ZPAQL
  decoder, so any zpaq extracts them; zpaqfranz and zpaq-std decode them
  natively. Levels: `-m6hN` (HC 1–12), `-m6aN` (fast, acceleration N), `-m7h`
  (LZAV "hi"); the digit after 6/7 is the block size (`-m66`, `-m76`: 64 MB).
- The hash healing of #282 in upstream's own version (it replaces ours) and a
  better `-touch`. Checked: a hash poisoned by pre20 heals, a hash-algorithm
  change re-reads, a clean file does not, an unreadable one still warns.
- LZ4 1.10 and LZAV 5.17 embedded in their own namespaces (`zlz4`, `zlzav`).

`mount`, `-franzen`, the P7M checks and the other `ZPAQFULL` parts stay out,
as in upstream's own "open" build (rule 1).

#### `-ma:lz4` and `-ma:lzav` = `-m6` and `-m7`

They are **another way of writing the same thing**: the block is byte for byte
the one `-m6`/`-m7` write (checked with `cmp` on every mapping), with
zpaqfranz's ZPAQL decoder inside. So zpaqfranz 65.3 decodes what zpaq-std
writes natively and vice versa, there is one LZ4 and one LZAV in the binary,
and compression runs in the normal threads (and with `-turbo`).

| `-ma` | is |
|---|---|
| `-ma:lz4:1…4` | `-m6aN` |
| `-ma:lz4:5…12`, `-ma:lz4` | `-m6hN` (default 9) |
| `-ma:lz4hc:N` | `-m6hN` |
| `-ma:lz4f:N` | `-m6aN` |
| `-ma:lzav:0` | `-m7` |
| `-ma:lzav:1`, `-ma:lzav` | `-m7h` |

The block size is the one the user's `-m` gives, by upstream's rule.
`-ma:lz4` archives written before (non-portable) and `-ma:lzav` archives
written by pre29–pre31 (ZPAQLZAV) still extract. `compressors/lz4/` and
`compressors/lzav/` are gone, and so is the stripped LZ4 1.9 that Windows used
— under which, it turns out, `-ma:lz4hc` on Windows was never HC at all.

#### `-turbo` with the other `-ma` codecs

`-turbo` runs `add2()`, upstream's copy of `add()`, which has none of
zpaq-std's `-ma` branches. So `-turbo` with any `-ma` other than lz4/lzav would
have written native blocks without a word. Now it says `00605` and runs the
normal `add`, which keeps the codec.

#### `-silent` / `-innosetup` messages, fixed for real

pre26 made `%Z` print the file name in silent mode, but it was only part of the
bug. The silent path formatted with a plain `vsnprintf()`, which knows none of
zpaqfranz's own specifiers: `%K` and `%H` came out literally too (`!= size
internal %21K external %21K`), and since `%Z` does not consume its argument in
glibc, the arguments after it were shifted. Now the silent path decodes them
exactly as the console does: `!= size internal 100.000 external 150.000`.

Diagnosis and fix by **ZF**, working on the clean zpaqfranz fork
(YadeWira/zpaqfranz), measured on untouched zpaqfranz 65.3y on Linux and
Windows; it replaces zpaq-std's partial `%Z` rewrite.

#### Also

- The `00590` notice ("mount is disabled in this build") never printed: an
  extra `#ifdef ZPAQMOUNT` hid it. Fixed.

### [65.2k-pre31] - 2026-09-24

**`-ma:lizard` opens in any zpaq at levels 10–29 (ZPAQLIZARD).** Twelve
portable `-ma` switches now.

A Lizard 2.1 decoder in ZPAQL, written for zpaq-std, for the two modes without
Huffman: fastLZ4 (levels 10–19, the default 17 among them) and LIZv1 (20–29,
with repeated 16-bit offsets, 24-bit offsets and long matches). Each Lizard
block holds five streams (lengths, 16- and 24-bit offsets, tokens, literals),
each with its length in front, so the whole block is kept in M and decoded at
the end. Like ZPAQDEFLATE, the program is generated
(`compressors/zpaqlizard/gen.py`).

- 1,210 bytes of bytecode; 70–95 MB/s in other tools with the JIT, 10–12 MB/s
  without.
- **Verified** with zpaq 7.15 on 110 Lizard streams (11 inputs × levels 10, 12,
  15, 17, 19, 20, 22, 25, 27, 29), every token class and stored blocks among
  them.
- **Levels 30–49** add Huffman and stay non-portable: those blocks keep the old
  tag and the `00596!` warning, and zpaq 7.15 rejects them cleanly.
- **Compatibility:** every zpaq-std from pre20 on extracts the new blocks
  (measured on pre20, pre23–pre30); `-ma:lizard` archives written before still
  extract.

### [65.2k-pre30] - 2026-09-24

**`-ma:deflate` and `-ma:hs` open in any zpaq (ZPAQDEFLATE, ZPAQHS).** Eleven
portable `-ma` switches now.

#### ZPAQDEFLATE: `-ma:deflate`

A raw DEFLATE (RFC 1951) decoder in ZPAQL, written for zpaq-std, and the first
portable codec here with Huffman coding that is our own. Canonical Huffman is
decoded one bit at a time from per-length counts — the method of Mark Adler's
puff.c, rewritten in ZPAQL — so there are no big tables. Stored, fixed and
dynamic blocks, with the 16/17/18 repeat codes.

- ZPAQL has no subroutines, so the program is generated by
  `compressors/zpaqdeflate/gen.py`: bit reading, symbol decoding and table
  building are macros expanded in place.
- 2,898 bytes of bytecode; 35–54 MB/s in other tools with the JIT, 2.1–2.7 MB/s
  without.
- **Verified** with zpaq 7.15 on 143 libdeflate streams: 11 inputs × levels
  0–12, all three block types among them.
- The block holds the original size (4 bytes) and libdeflate's raw deflate;
  zpaq-std decodes it natively with libdeflate.

#### ZPAQHS: `-ma:hs`

heatshrink's bit stream decoded one byte at a time, 265 bytes of bytecode,
~64 MB/s with the JIT. The window is the circular M with pm = the window bits
(11, 13 or 14), which starts zeroed like heatshrink's own buffer. Verified on 15
streams, the three levels.

The help text and the README said `-ma:hs` level 2 uses a 32 KB window; it is
16 KB (the wrapper caps it at 14 bits).

#### Compatibility

Every zpaq-std from pre20 on extracts the new blocks (measured on pre20,
pre23–pre29); archives written before with `deflate` or `hs` still extract.

### [65.2k-pre29] - 2026-09-24

**`-ma:lzav` opens in any zpaq (ZPAQLZAV).** Nine portable `-ma` switches now.

A decoder for LZAV's format 3 (what 5.17 writes), in ZPAQL, one byte at a time,
written for zpaq-std. 644 bytes of bytecode; about 100 MB/s in other tools with
the JIT, 10 MB/s without.

The subtle part of the format is its offset carry: literal blocks hold 2 bits of
the *next* reference's offset, 2- and 3-byte offsets hold more in their high
bits, and a reference that follows a literal block may carry no offset bytes at
all — its offset is the carry alone. That is how LZAV's offsets reach far beyond
its nominal 2 MB window; they never go before the start of the block, so the
decoder's window covers the whole block (a foreign zpaq needs the block size in
memory per thread). The block also holds the original size (4 bytes), because
LZAV pads small streams with zeros and the size is what stops the decoder.

- **Verified** with zpaq 7.15 on 22 LZAV streams (11 inputs × both levels),
  checked against a Python port of LZAV's own decoder first.
- **Compatibility:** every zpaq-std from pre20 on extracts the new blocks
  (measured on pre20, pre23–pre28); `-ma:lzav` archives written before still
  extract.
- The help text and the `00602` notice name it ZPAQLZAV.

### [65.2k-pre28] - 2026-09-24

**Three more `-ma` codecs open in any zpaq — `flzma2`, `lz` and `snappy` — and
the portable codecs get names.**

#### ZPAQFLZMA2: `-ma:flzma2`

fast-lzma2 writes LZMA2: LZMA cut into chunks of up to 2 MB, each with its own
header, which can restart the decoder, change properties, reset the dictionary
or be stored uncompressed. No LZMA2 decoder in ZPAQL existed, so zpaq-std wrote
one on top of kaitz's LZMA1 decoder (zpaqf, public domain): his per-symbol loop
is kept verbatim, except that posState and the lp bits count from the last
dictionary reset, and a chunk walker goes around it.

- **Verified** with zpaq 7.15 (zpaqd) on 80 fast-lzma2 streams — 8 inputs ×
  levels 1–10 — which between them use every chunk type: dictionary resets in
  mid-stream (low levels, small dictionaries), state and property resets, and
  uncompressed chunks.
- 2,155 bytes of bytecode; 22–40 MB/s in other tools with the JIT, 1.6–2.3 MB/s
  without.
- The block holds the original size (4 bytes) and FL2_compress's output as is;
  zpaq-std decodes it natively with fast-lzma2.

#### ZPAQLZIP: `-ma:lz`

An lzip member is plain LZMA1 (lc=3 lp=0 pb=2) between a 6-byte header and a
20-byte trailer. zpaq-std now keeps only the LZMA inside, with the header
ZPAQLZMA reads, so **the same ZPAQLZMA program** extracts it in any zpaq, and
zpaq-std decodes it with the LZMA SDK. The blocks are tagged like `-ma:lzma`
blocks, with `:lzip` at the end: pre27 recognises ZPAQLZMA and skips it, so it
needs a tag it knows to decode natively. With a new tag it would have handed
back raw LZMA (the lz6 lesson from pre25).

#### ZPAQSNAPPY: `-ma:snappy`

A decoder for snappy's raw block, written for zpaq-std: one byte at a time, with
a 64 KB circular window, since snappy never emits an offset of 64 KB or more.
307 bytes of bytecode; 50–100 MB/s in other tools with the JIT, 13 MB/s
without. Checked also on the cases snappy does not produce but the format
allows: 4-byte offsets, 3- and 4-byte literal lengths.

#### Names

Each portable codec is named after the ZPAQL decoder its blocks carry, in the
help text, in the `00602` notice and in the README: **ZPAQLZ5** (`lz5`),
**ZPAQLZMA** (`lzma`), **ZPAQLZIP** (`lz`), **ZPAQFLZMA2** (`flzma2`),
**ZPAQSNAPPY** (`snappy`). The switches do not change. `lz6` uses ZPAQLZ5 and
gets its own name when it stops being experimental.

#### Compatibility

- Every zpaq-std from pre20 on extracts the new `flzma2`, `lz` and `snappy`
  blocks (measured on pre20, pre23–pre27): they run the decoder.
- Archives written before with these three codecs (non-portable, tagged
  `zpaqstd-ma:`) still extract: both readers stay.

#### Correction

pre27 said kaitz's LZMA decoder is "about 300 bytes" of bytecode. It is
**1,998**: the 300 came from zpaqd's listing, which does not give the size.
ZPAQLZ5's 433 was right.

### [65.2k-pre27] - 2026-09-24

**New `-ma:lzma`: LZMA that any zpaq can extract, with kaitz's ZPAQL decoder.**

#### `-ma:lzma`

Each block is compressed with the LZMA SDK (26.03, public domain) and carries
**kaitz's LZMA1 decoder written in ZPAQL**, taken unchanged from his
[zpaqf](https://github.com/kaitz/zpaqf) (public domain), where it serves his own
`-m3`. zpaq 7.15 and zpaqfranz extract these archives byte for byte. Thanks to
kaitz, who pointed us to it in issue #1.

- The program zpaq-std compiles is **byte-identical** to the one zpaqf writes.
  Its body is the same for every block size and level; only the `comp` line
  changes (`ph=15` for lc=3 lp=0, `pm` = 2 × the dictionary).
- About **2 KB** of bytecode per block (1,998 bytes; pre27 said ~300, a measuring error). In other tools it decodes at
  13–36 MB/s with the ZPAQL JIT and 0.8–2.3 MB/s without, and needs 2 × the
  dictionary per thread (32 MB for a 16 MB block).
- zpaq-std recognises the program and decodes LZMA natively.
- Levels 0–9 as in the LZMA SDK; default **6**, as xz.

What it adds is LZMA's ratio **and** fast extraction, readable anywhere: on
samba (21.6 MB) it gives 3.93 MB against 4.05 MB for `-m3`, which takes 5 s to
extract against about 0.5 s.

**The native shortcut now needs the tag.** Until pre26 zpaq-std skipped a
program as soon as it recognised the bytecode. zpaqf's own `-m3` blocks carry
this very LZMA program, without any zpaq-std tag, so a zpaq-std that recognised
it would have handed back raw LZMA for them. The shortcut is now allowed only
when the reader has seen a `zpaqstd-ma2:` tag in the block comment; any other
block runs its program as before. Checked: zpaqf `-m3` archives still extract
identically.

**Compatibility.** Tagged `zpaqstd-ma2:lzma:`, which no released version knows,
so every zpaq-std from pre20 on runs the decoder and extracts correctly
(measured on pre20, pre23, pre24, pre25 and pre26).

#### `-innosetup`

- In dark mode, the "Loading..." bar of the first seconds was light: Windows
  only animates a themed marquee, and themed means light. In dark mode the
  marquee is now drawn by zpaq-std, in the bar's own dark trough and green.
- On failure, "Remaining time" shows `-` instead of its last value.

#### Tests

`suite_ma_corre` covers 23 codecs and requires zpaq 7.15 to extract `lzma`;
`difftest` covers `-ma:lzma`.

### [65.2k-pre26] - 2026-09-23

**The `-innosetup` window shows real progress, and a failure looks like one.**
Also shorter, aligned `-ma` notices.

#### `-innosetup`: real progress

With `-m5`, the window jumped to 99% within a second and stayed there for the
whole compression, with "Remaining 0.0 s", the read speed instead of the real
one, and "Compressed size" at `...`: it looked hung. Measured on 43 MB: 2 min
27 s at 99%.

Progress was driven by bytes READ, and one `-m5` block is read in a second and
compressed in minutes. It now counts what has been compressed: libzpaq reports
every 16 KB of input it codes, each block ends by crediting exactly its bytes,
and deduplicated fragments count as done when read. The window recomputes the
percentage, speed and remaining time from that every 80 ms. Checked: the count
closes exactly (compressed = queued, nothing pending) for `-m0`, `-m1`, `-m3`,
`-m5`, `-ma`, one thread and deduplication; on Windows the same 43 MB now climbs
from 11% to 100% over the run.
"Compressed size" still reads `...` until the first block is written: before
that, its real size is not known.

#### `-innosetup`: failures

A failing run looked exactly like a good one: the bar was forced to 100%, green,
and the window closed after a second. The reason only went to stderr, which an
installer hides. Measured: a corrupt archive showed "Extracting... 100%" with
20 of 43 MB processed; a missing archive showed "Compressing... 100%".

Now, when the run returns non-zero:

- the title says **"Extraction failed"** (or Compression / Test), the bar and
  the taskbar button turn **red**, and the window flashes;
- the **first** error or warning is shown in red, without its code — the first
  one is the cause (`bad checksum`), what follows are consequences;
- "Background" goes away and "Cancel" becomes **"Close"**, which closes without
  asking;
- the window stays until closed, **or 10 s**, so an unattended (`/VERYSILENT`)
  install never hangs on it. The exit code is unchanged.

The verb in the title was guessed from the data, because the window opens before
the command is parsed; it is now set from the command.

#### `-silent` / `-innosetup`: file names in messages

In both modes every message naming a file printed a literal `%Z` (or `%`)
instead of the name, on stderr too: `UKONE [very bad] 0/207 %Z`. The silent
path formatted with `vsnprintf()`, which does not know zpaq-std's own `%Z`; it
now rewrites it to `%s`, as the DLL path already did.

#### Shorter `-ma` notices

Creating an archive with a non-portable `-ma` codec printed 9 lines on every
`a`, and its continuation lines came out misaligned:

```
the -ma blocks are marked with a post-processing type no other zpaq
       knows, so zpaq, zpaqfranz and the plugins skip them saying 'unknown
```

A message whose code ends in `:` loses the code on screen (it only shows with
`-debug`), while one ending in `!` keeps it; the continuation lines were indented
for a code that was no longer there. The same was true of the lz5/lz6 notices
added in pre24 and pre25.

Now:

```
00596! -ma:flzma2: this archive will NOT open in any other zpaq, and older zpaq-std
       versions may not read it either: upgrade the machine that RESTORES first.
       Use -m0..-m5, -ma:lz5 or -ma:lz6 if the archive has to be portable
```

- It also names `-ma:lz5` and `-ma:lz6` as the portable alternatives.
- `-ma:lz5`/`lz6` print one line (`00602`), and `-ma:lz6` adds two aligned
  lines (`00603!`) saying lz6 is experimental.
- The detail that was dropped (other zpaq tools reject these blocks cleanly and
  still list the archive) stays in the README.

### [65.2k-pre25] - 2026-09-23

**New `-ma:lz6`: a fast, low-CPU codec whose archives open in any zpaq.**

> **lz6 is experimental and subject to major changes.** What can change is lz6's
> *encoder*: its ratio, speed and levels, so `-ma:lz6` may compress differently
> from one zpaq-std release to the next, and its levels may be renumbered. What
> cannot change is the *block format* `-ma:lz6` writes, which lz6 froze as its
> portable profile: every archive already written carries its own decoder and
> stays readable, by zpaq-std and by any other zpaq. Any future lz6 format would
> get a new name, never this one.

#### `-ma:lz6`

[lz6](https://github.com/YadeWira/lz6) (BSD-2) writes the same block format as
LZ5 v1.5, frozen by lz6 as its portable profile. So `-ma:lz6` blocks carry the
same ZPAQLZ5 decoder as `-ma:lz5`, unchanged, and zpaq 7.15 and zpaqfranz extract
them byte for byte.

- **Level 0 (default)** is lz6's fast encoder: low CPU, the use case of backups
  of servers and VMs. **1–15** are its HC levels.
- The window is capped at **4 MB** (lz6's `*_window` API), so a foreign zpaq
  needs 4 MB per thread, not 16. lz6 measured the cost at +0.13% (dickens) and
  +0.75% (samba) for the fast encoder.
- The code is copied unmodified from lz6 commit `a8e1b51` (`v1.6.4-pre` plus a version-number fix), in `compressors/lz6/`
  (see `VERSION`). Every global symbol is `LZ6`-prefixed, so it links next to
  LZ5 without clashes.

Measured on 19.9 MB (text, binary, 3 MB of random data), one thread:

| method | archive | CPU | opens in zpaq 7.15 |
|---|---|---|---|
| `-m1` | 8.47 MB | 1.11 s | yes |
| `-ma:lz4f` | 13.96 MB | 0.26 s | no |
| `-ma:lz5f` | 10.52 MB | 0.31 s | yes |
| **`-ma:lz6`** | **10.22 MB** | **0.31 s** | **yes** |
| `-ma:lz6:15` | 8.34 MB | 5.70 s | yes |

**Compatibility.** The blocks are tagged `zpaqstd-ma2:lz5-lz6:`. pre24
recognises the ZPAQLZ5 bytecode and does not run it, so it needs to find
`zpaqstd-ma2:lz5` in the comment to decode natively; with a plain `lz6` tag it
would have handed back the compressed bytes. With this tag pre24 decodes them
with its LZ5 decoder, which reads lz6 blocks identically (checked on lz6's 23 test
vectors). **Every version from pre20 on extracts `-ma:lz6` archives** (measured
on pre20, pre23 and pre24).

#### Tests

`suite_ma_corre` covers 22 codecs and requires zpaq 7.15 to extract `lz6`;
`difftest` covers `-ma:lz6`.

### [65.2k-pre24] - 2026-09-23

**`-ma:lz5` archives open in any zpaq: zpaq 7.15, zpaqfranz, and older
zpaq-std.** It is the first `-ma` codec that is portable.

#### ZPAQLZ5: the block carries its own decoder

Every `-ma:lz5`, `-ma:lz5hc` and `-ma:lz5f` block now carries an LZ5 block
decoder written in ZPAQL as its post-processor, the same way zpaq's own `-m1`
carries its LZ77 decoder. Any zpaq runs it without knowing what LZ5 is.

- About **430 bytes** of bytecode per block. The window (4 MB) is declared in
  the block header, not in the program.
- In other tools it decodes at **62–103 MB/s** with the ZPAQL JIT and 11 MB/s
  without.
- **zpaq-std does not run it.** When the post-processor loads a program that
  matches the canonical ZPAQLZ5 bytecode byte for byte, it switches to
  pass-through and decodes LZ5 natively. The paranoid `p` command keeps no such
  shortcut, on purpose.
- The segment SHA-1 is the original data's, which is what a foreign zpaq checks.
- The program is **frozen**: every archive carries its own copy and zpaq-std
  recognises it byte for byte. A different decoder would be added alongside.
- zpaq-std prints `00602:` instead of the non-portable warning `00596!` when it
  creates these archives.

The other 18 `-ma` codecs stay non-portable, still marked so other tools reject
them cleanly. The roadmap for the rest is in issue #2.

**Compatibility.** The new blocks are tagged `zpaqstd-ma2:` instead of
`zpaqstd-ma:`. With the old tag, pre21–pre23 would run the ZPAQL and then decode
LZ5 a second time (measured: `31319`). No released version knows the new tag, so
**every version from pre20 on extracts the new archives** (measured on pre20 and
pre23). Old `-ma:lz5` archives still open in pre24. Each block is about 437
bytes larger.

#### Tests

- `suite_ma_corre` also checks that zpaq 7.15 extracts `lz5`, `lz5hc` and
  `lz5f`; against pre23 it reports all three `NO-PORTABLE`.
- `difftest` also covers `-ma:lz5`.

### [65.2k-pre23] - 2026-09-23

**`-ma:bzip3` works for the first time. It never compressed with bzip3 before —
not once, since the initial commit — and every test said it was fine.**

#### `-ma:bzip3` was dead, and nothing noticed

Asking for `-ma:bzip3` produced an archive **byte-identical to `-m1`**, at every
level. The call to `bz3_compress()` passed `out_size = 0`, and libbz3 reads that
argument as the **capacity** of the output buffer ("make sure to set out_size to
the size of the output buffer"); it returned `BZ3_ERR_DATA_TOO_BIG` every time,
and the block silently fell back to the native method.

It went unnoticed because a codec that does nothing is perfectly reversible:
storing the block natively round-trips too. `suite_core` checked `-ma:bzip3` in
all 263 of its cases and passed. The symptom that gave it away was a README
cell — the documented default level made no difference, because no level did.

Fixing it exposed **two bugs in libbz3 1.5.3** itself, both fixed upstream in
**1.5.4**, which is what now ships:

- when the input is an **exact multiple** of the block size, the compressor wrote
  the **last block empty** (`size = in_size % block_size` is 0) — data that
  cannot be recovered;
- the decompressor **rejected incompressible blocks** (it compared a block's
  compressed size against the uncompressed block size instead of
  `bz3_bound(block_size)`).

Neither ever reached an archive in the field, for the same reason the first bug
was invisible: zpaq-std had never written a bzip3 block. So updating costs no
compatibility. Measured after the fix, on the difftest corpus: text −29 %,
binary −22 %, images −25 %, mixed −9 %.

**Compatibility.** A new `-ma:bzip3` archive **may not open in pre21 or pre22**:
their decoder is 1.5.3, which rejects incompressible blocks. Measured: level 1
over data with random content fails there with `31319 bzip3 decompression
failed` — loudly, never with wrong data. Upgrade the machine that restores first.

#### A test that checks the codec actually ran

`test/testlab/suite_ma_corre.sh`: over compressible text, each of the 21 `-ma`
switches must leave its `zpaqstd-ma:<algo>:` comment in the archive **and** come
back byte for byte. Validated against pre22, where it reports exactly the bug
this release fixes:

```
bzip3    marca=0  ida_vuelta=OK    NO-CORRE
```

The round trip passes and the suite still catches it. `difftest.sh` now covers
`-ma:bzip3` as well.

#### README defaults, all four now match the binary

`lzh` is 4 (the README said 1), `bzip3` is 9 (said 5), `lzfse` is 1 (said 0, and
0 and 1 give the same output — it has one internal level). None of the three
ever had an explicit default in the code; `git log -S` shows the README rows were
written with nothing behind them, so the behaviour users have always had is the
code's, and the README is what changed. (`bsc` was the opposite case, fixed in
the code in pre21.)

#### Reproducible Windows builds

The `.exe` builds are now byte-identical from one build to the next. Before, two
builds of the same source differed in 4 bytes: the PE link timestamp and the
checksum derived from it. `-Wl,--no-insert-timestamp` alone does not fix it —
the post-link `strip` rewrites the header with the current time — so `strip` runs
with `SOURCE_DATE_EPOCH` (default 0). The published binary can now be checked
against the tested one with `sha256sum`.

#### Verification

Full battery green: suite_core 263, flags 117, cmds 38, extra 15, glob 11,
robust 24, **ma_corre 21/21**; golden gate 136/136, 100/100, 116/116; os_msgs
25/25; both pinned corpora clean. `difftest` against pre22: 119 comparisons, 5
divergences, **all of them `-ma:bzip3`, none native**. Real Windows 7 SP1, x64
and x86: bzip3 compresses at levels 1 and 9 over data with random content and an
exact-multiple block, `t` and `x` pass on both, the archives return to Linux
matching by sha256, and they carry the bzip3 comment — the codec really ran.

### [65.2k-pre22] - 2026-09-22

**One fix: an archive whose hashes an older version had already zeroed never
recovered, and `v` reported those files as FAILED forever.**

This is a follow-up to upstream issue #282, whose original symptom was already
fixed in 65.1 and therefore in pre21: when **only a file attribute** changes (not
size, not date), the file is not re-read, and older versions stored a zero hash
and printed `ERROR expected N getted 0 bytes`. It affected **Linux and Windows**
alike, in every release up to and including pre20.

65.1 fixed it by **carrying the hash over** from the previous version instead of
re-reading. That is correct whenever the previous hash is good. When it is not,
`carryoverhash()` rightly refuses it — and the code then wrote the zero anyway.
Two consequences, both measured on pre21:

- **An archive already damaged by pre20 or earlier never heals.** Every later
  attribute-only change carries the zero into the new version, so `v` keeps
  failing no matter which version wrote the latest entry.
- **Changing the hash algorithm between runs** and then changing an attribute
  produces the same zero, on a clean archive.

The root cause is two decisions that do not talk to each other: *which files to
re-read* looks at date and size; *which entries to write* also looks at the
attribute. An attribute-only change falls between them. The fix goes at the
first one: when only the attribute changed **and there is no usable previous
hash**, re-read the file. The content did not change, so dedup finds the same
fragments — it costs one read, not space. The attribute test is **the same
expression** the write side uses, on purpose: if the two drift apart, the gap
reopens.

Verified on Linux and on real Windows 7 SP1 with `attrib -A` (the trigger from
the original report):

| case | pre21 | pre22 |
|---|---|---|
| archive damaged by pre20, then an attribute change | `v` FAIL | `v` OK, 1 re-read |
| hash algorithm changed, then an attribute change | `v` FAIL | `v` OK |
| healthy archive, attribute change | OK | OK, **0 re-reads** |
| file genuinely unreadable | reported | **still reported** |

The last two rows are the ones that must not change: a healthy archive keeps the
fast path, and a file that really cannot be read is still an error.

Full battery green; `difftest` against pre21 gives **0 divergences** — the fix
changes no archive bytes outside the attribute-only path.

Note for archives already affected: the **old** versions keep their zero hash,
because a journaling archive never rewrites history. What heals is the latest
entry, which is what `v` checks. Any change that makes zpaq-std re-read the file
repairs it; an attribute change now does too.

### [65.2k-pre21] - 2026-09-22

**The base moved to zpaqfranz 65.2, two codecs were brought up to date, and an
`-ma` archive now says what it is instead of looking like a corrupt zpaq.**

#### `-ma` archives declare themselves (issue #1, kaitz)

An archive holding `-ma` blocks cannot be extracted by any other zpaq — the
payload is compressed by a codec no other implementation has. That much is
inherent. What was wrong is that it did not *say so*: same `.zpaq` name, same
magic bytes, a header that is byte-for-byte standard, and `zpaq l` listing the
correct original sizes and printing `all OK`. Only extraction failed, and it
failed on a fragment hash — which is what a genuinely corrupt archive looks like.

Two changes, both measured against zpaq 7.15 and zpaqfranz 64.8j:

- **The `-ma` blocks are now tagged with a post-processing type no zpaq knows**,
  so other tools reject them by name: `skipping [2..2] at 1319: unknown post
  processing type`. They still list the archive correctly and, in a mixed
  archive, still recover the native files. Exit status is non-zero and **no file
  is ever written** — verified in every case.
- **Creating one prints a warning** (`00596!`) naming what it means, because that
  is the one moment where choosing `-m0`…`-m5` is still free.

The tag is placed **per block, from the block's own `zpaqstd-ma:` comment** — not
from a global flag. That matters: the first attempt marked by a global and caught
the index blocks too, which corrupted the listing other tools produce (`N
fragments have unknown size`, wrong file count). It also means a block is tagged
only when it really carries external payload: incompressible input under
`-ma:zstd` produces zero tags and stays universally readable. Attempts to forge
the tag through `-comment` or a filename do not work — the field is ours.

**Compatibility is one-way, in the useful direction.** This version reads
everything written before it (verified over pre9…pre20 × 7 codecs, plus native,
on Linux and on Windows 7 x64/x86); older zpaq-std versions cannot read the new
`-ma` blocks. Native `-m0`…`-m5` output is unchanged, so old versions and every
other zpaq still read it. In a mixed or appended archive an old version still
recovers everything it could recover before, file by file. **Upgrade the machine
that restores before the one that compresses.**

Giving these archives their own extension was tried and **backed out**: renaming
breaks two paths that build names by hand — multipart wrote parts zpaq-std itself
could no longer find, and the backup index assumes the exact length of
`_00000001.zpaq`. That is the naming machinery behind the 46 GB CLAAS case, so it
gets its own change and its own test pass.

#### Codecs up to date (rule 3)

- **libdeflate 1.24 → 1.26.** Changes no output at all: the only edit to
  `deflate_compress.c` is accepting level −1 as an alias for 6, the rest is build
  and portability work. `-ma:deflate` is bit-exact against pre20 at every level.
  Note 1.26 now **requires a C11 compiler** — it dropped its own `restrict`
  fallback. All three toolchains here report `__STDC_VERSION__ 201710L`.
- **lzav 5.8 → 5.17.** This one does change its output: archives come out ~0.5%
  smaller at the default level, ~0.3% at `-ma:lzav:1`. Old archives keep working
  in both directions — `LZAV_FMT_MIN` is 2 and the 5.17 decompressor still
  handles format 2 and 3, while 5.8 already wrote format 3.

Both vendored trees were verified pristine against upstream before being
replaced, so nothing local was lost.

#### `-ma:bsc` ran at the wrong default

The clamp block carried `if (g_ma_level<1) g_ma_level=3;`, which was **dead
code**: the generic `else if (g_ma_level<1) g_ma_level=1;` fifty lines above had
already raised the value, so the condition could never be true. A bare `-ma:bsc`
fell through to `else g_ma_level=9` and ran at ST5 instead of the documented ST3.
This is the same defect the `hs`/`lzav` comment in the same function describes
fixing for those two; it had stayed alive for bsc. The default now lives with the
other explicit defaults. It is a real behaviour change: a bare `-ma:bsc` is now
faster with a slightly worse ratio, which is what the README has documented all
along.

Two more README cells were wrong and are corrected: the default for `-ma:lzav`
and `-ma:hs` is 1, not 0 — both pinned to 1 in the source, and measured.

#### Verification

`difftest` covered neither of the codecs being updated — `-ma:deflate` and
`-ma:lzav` were missing from `METHODS`, so the differential tool was blind
exactly where it was needed. Both added. Three testlab scripts had also drifted
between their repo copy and the working copy; `pin_corpus.sh` was the old
one-corpus version, which is why `corpus-raster2` was going unverified.

Full battery green on the release binary: suite_core 263, flags 117, cmds 38,
extra 15, glob 11, robust 24; golden gate 136/136, 100/100, 116/116; os_msgs
25/25; both pinned corpora clean. `difftest` divergences are confined to `-ma`
methods, none native, every one with the signature `bit=NO A_lee_B=NO B_lee_A=SI
l=SI t=SI`. Real Windows 7 SP1, x64 and x86: old archives read, new archives
written there return to Linux matching by sha256, and a native `-m5` written on
Win7 still opens in zpaq 7.15.

### [64.8j-pre20] - 2026-09-18

**Housekeeping. No change to compression and no change to any archive.**

- **The CUDA source in bsc is gone** — or rather, the half of it that could go.
  bsc ships optional GPU support (`libcubwt.cu`, `st.cu`) that this project never
  compiles: `LIBBSC_CUDA_SUPPORT` is defined nowhere, there is no `nvcc` in the
  Makefile, and the binary carries no CUDA symbol and links no CUDA library. The
  two `.cu` implementations (171 KB) are removed. The `.cuh` headers **stay and
  cannot go**: `bwt.cpp:41` and `st.cpp:43` include them with no preprocessor
  guard, so deleting them breaks the build — verified, not assumed. Recorded in
  `compressors/bsc/LEEME-cuda.md` so a future re-vendor knows this copy is no
  longer pristine.
- **`docs/PRECOMP-DESIGN.md` deleted**: the design of `-pc`, removed in pre14.
  Its own first line read "Status: DESIGN / not implemented", so it was
  misleading before the feature even went.
- **The five `## [Unreleased]` headings inherited from zpaqfranz** are relabelled
  `## Planned at the time of [60.x]`. They were never unreleased versions: each is
  a wish-list attached to the release below it, every entry starting with
  "Planned". Giving them version numbers would have been a nicer-looking lie.
- **Two Windows XP leftovers.** The alternate-streams APIs
  (`FindFirstStreamW`/`FindNextStreamW`) are still loaded through
  `GetProcAddress` because XP lacked them; the target is Windows 7 and those APIs
  exist since Vista, so the comment now says the dynamic load is vestigial rather
  than necessary. And the failure message said "Alternate streams not supported in
  Windows XP" — those APIs exist since Vista, so if they are missing it is not
  the version. It now states what the user actually needs: ADS are unavailable
  because `FindFirstStreamW` was not found. (The COM/OLE dynamic-load refactor
  stays deferred.)
- A Makefile comment still credited libdivsufsort's extraction to "fase 0 del
  plan de Rust"; that plan is cancelled and the extraction stands on its own.

Verified: `-m1`/`-m5`/`-ma:bsc`/`-ma:zstd` **bit-exact** against pre19 — `-ma:bsc`
in particular, since bsc is the library whose files were touched.

### [64.8j-pre19] - 2026-09-15

**`-ytool` removed.** It handed files to the external ytool binary to precompress
recompressible streams before fragmentation, never left the experimental stage,
and is gone: the `add()` hook, the container gating, the prefetch encode path,
the parallel reverse post-pass, `compressors/ytool/` and `suite_ytool.sh`.
About 506 lines and 49 KB of binary (6,951,960 → 6,902,808).

**With it goes the last external dependency.** The README used to carry an
exception — "`-ytool`, and only that flag, needs something installed on the
host". There is no exception now: every flag works with nothing installed.

Unlike `-mf`, a `-ytool` archive **does** need code to be read back: it stores the
`zYTL` container, not the original. So the reverse is gone but the *detection*
stays — a 4-byte magic check that warns per file (`00568!`) instead of leaving a
compressed file on disk behind an "all OK" summary. Same treatment `zPCF` already
had. Use pre18 or earlier to recover such files.

The prefetch pool survives, because it does two jobs and only one was `-ytool`:
the other is the front-end parallel fragmentation shipped in pre20. Renamed to
match what is left of it: `YtPrefetch`→`FrontPrefetch`, `YtConsumeGuard`→
`FrontConsumeGuard`, `yt_K`→`front_K`, and the `Kind` enum loses `CONTAINER`.

**A bad rename from the previous change, fixed.** `pc_info()` became `yt_info()`
in the `pc_*`→`yt_*` sweep. It was never the `-pc` precompressor: `pc` there meant
*PC*, the platform — it prints the Windows version, whether the CPU is Intel/AMD
and whether the JIT applies. It is now `platform_info()`. Applying a mechanical
rename without reading each symbol is exactly the failure this whole cleanup was
meant to prevent.

Also corrected: the `-pc` rejection message claimed "archives already made with
-pc still extract normally", which has been **false since pre14**, when the
decoder went. It now says they cannot be reversed by this build.

Verification: `-m0`..`-m5` plus `-ma:zstd`/`ppmd`/`bzip2` **bit-exact** against
pre18; suite_core 263, suite_flags 117, suite_cmds 34, suite_extra 14, suite_glob
11, suite_robust all verdicts correct; difftest 98 comparisons, 0 divergences;
golden gate 136+116+116 with 0 failures; both pinned corpora unchanged. os_msgs
reports 19 differences against pre18 and every one is the **same single line** —
the `-ytool` entry in the `-debug3` flag dump; the new binary against itself is
25/25.

**`pc_*` renamed to `yt_*`, and one dead function removed.** After `-pc` went in
pre14, the code that survived kept its `pc_` prefix even though every one of
those symbols now forwards to `-ytool`. That prefix is a trap: it already nearly
cost `-ytool` once, when `pc_reverse_file()` was about to be deleted by line
number during the `-pc` removal without reading it first — it handles `zYTL`
containers and `-ytool` depends on it.

Renamed, 76 occurrences: `PcfPrefetch`→`YtPrefetch`, `PcfConsumeGuard`→
`YtConsumeGuard`, `PcRev`→`YtRev`, and `pc_K`/`pc_reverse_file`/`pc_reverse_list`/
`pc_transform_encode`/`pc_take_or_encode`/`pc_membuf*`/`pc_tmpname`/`pc_info`/
`flagpc_file` to their `yt_` equivalents. The prefetch `Kind` enum went with
them: `NOTPC`→`NONE`, `PCF`→`CONTAINER`.

`pc_transform_candidate()` is **deleted**. It forwarded to `yt_magic_candidate()`
and nothing called it — the compiler had been saying `defined but not used` on
every build since pre14, and the comment above it claimed both it and its twin
were shared by the prefetch worker and the inline path, which was true of only
one of them.

Also corrected about 15 comments that still described live code in terms of
`preflate` and PCF, neither of which exists any more. The mentions that remain
are the ones that should: the record of the removal, and the `zPCF` magic check
that warns about archives this build can no longer reverse.

No behaviour change, and it is checkable rather than asserted: `-m0`..`-m5` plus
`-ma:zstd`/`ppmd`/`brotli`/`bzip2` are **bit-exact** against pre18.

### [64.8j-pre18] - 2026-09-15

**Last traces of `-mf` gone.** pre17 removed the feature but kept a rejection
handler and a README section for anyone who had used it. There is no one: it was
never used in production, so the compatibility scaffolding protected nobody.

With that out, **this source now differs from pre14 — which predates `-mf`
entirely — only in the 45 `seppuku()` → `seppuku(2)` exit codes from pre16**, and
two blank lines. The feature has left no trace in the code at all.

One consequence worth stating: `-mf5` is now an unrecognised flag like any typo.
It prints `00562! Unknown option ignored`, exits 0, and compresses with the
default method. The pre17 handler existed to stop exactly that; it is gone
because there are no scripts to protect.

`-m0`..`-m5` and `-ma:zstd`/`-ma:ppmd` remain bit-exact against pre17. The
CHANGELOG entries for pre15 through pre17 stay: they are the record that the
feature existed and why it went, which is the one thing worth keeping about it.

### [64.8j-pre17] - 2026-09-14

**`-mf` removed.** The zpaqf model set shipped as `-mf1`..`-mf5` in pre15 and
pre16 and is gone again: `makeConfigF`/`compressBlockF`, the LZMA reader, the
image detector, the `-mf`-gated text test, and `compressors/lzmasdk/` with it.
About 2,550 lines of source and 203 KB of binary (7,155,224 -> 6,951,984).

**Existing `-mf` archives are unaffected and need no old build to read.** A `-mf`
archive is an ordinary zpaq archive: the model travels inside the block header as
ZPAQL bytecode, so decoding never depended on any of the removed code. This was
verified while the feature still existed — pre13, which predates `-mf` entirely,
extracted all five levels across seven corpus shapes, 70 round-trips with zero
failures. That is the opposite of `-pc`, where the decoder *was* code and
removing it orphaned archives.

`-mf1`..`-mf5` now report `00574!` and exit 2 rather than falling through to the
generic "unknown option ignored", which would have silently compressed with the
default `-m1`: a script pinned to `-mf5` would have quietly lost the level.

Everything the feature was gated behind was additive, and the removal is
measurably clean: `-m0`..`-m5` and `-ma:zstd`/`-ma:ppmd`/`-ma:brotli` all produce
**bit-exact** archives against pre16.

Kept from the `-mf` work, because they stand on their own:

- `corpus-raster` is retired and replaced by `corpus-raster2`, filtered by magic
  instead of by extension. The old one had 8 of 10 files that were not the images
  their names claimed, so the raster figures in the pre15 notes measured
  something else. Reason recorded in `corpus-raster-RETIRADO.txt`.
- `pin_corpus.sh` now pins every corpus rather than only the main one, so neither
  can drift unnoticed.
- `suite_extra`'s version count expected 4 from a scenario whose four `a` calls
  include one over identical content, which writes no version -- exactly what the
  assertion one line above demands (`delta=0 bytes`). The test asked for a no-op
  add to both write nothing and create a version. Corrected to 3; pre13, pre16
  and this build all report 3, so it was never a regression.

### [64.8j-pre16] - 2026-09-13

**45 error paths reported failure with exit code 0.** `seppuku()` takes an exit
code that defaults to 0, and its own comment already says command-line errors
must pass a non-zero one — but 45 call sites printed an error and then called it
bare. A script checking `$?` saw success on a failed allocation, a null pointer,
an unreadable file, `cannot write on %s`, even "You must enter the exact
password TWICE". Nine of them were followed by a dead `return 2` that could
never run, which is what made the defect visible.

All 45 now pass 2. They were identified by the message marker the codebase
already uses — `!` for errors, `:` for information — and every one was read
before changing: all are genuine failures, none is a "job done, quit".

Reproducible against pre15, no special setup: give two different passwords when
creating an encrypted archive.

```sh
printf 'uno\ndos\n' | zpaq-std a new.zpaq file.txt -key
# pre15:  51852! You must enter the exact password TWICE   -> exit 0
# now:    51852! You must enter the exact password TWICE   -> exit 2
```

**`make clean` left 135 object files behind.** It removed only the binary, so a
cross build straight after a native one relinked the host's objects and died on
`undefined reference to franz_malloc(unsigned long)` — Linux's `size_t`
surviving in a mangled name MinGW spells differently. It now sweeps `*.o` by
name rather than by an explicit list of the `*OBJ` variables: the objects sit at
five different depths under `compressors/`, and a list goes stale the next time
a library is added, which is how this got in. Verified by running the sequence
that used to fail: native, `clean`, cross, `clean`, native.

### [64.8j-pre15] - 2026-09-13

**zpaqf model set as `-mf1`..`-mf5`.** `makeConfig` and `compressBlock` from
[zpaqf](https://github.com/kaitz/zpaqf) (Kaitz's fork of zpaq 7.15) are carried in
alongside ours as `makeConfigF`/`compressBlockF`, and `-mfN` routes data blocks
through them. Everything is additive: `-m1`..`-m5` are not touched and still
produce byte-identical archives to every previous release, verified by difftest
against pre13. `-mf` output is an ordinary zpaq archive — the model is ZPAQL
bytecode in the block header — and pre13 extracts every `-mf` level correctly.

Measured against `-mN`: `-mf5` is **−4.1% on text, −2.8% on binaries, −14.9% on
non-ASCII names**; `-mf3` is **−6.5% on binaries and −14.3% on raster** but +8.0%
on text; `-mf4` only helps on text; `-mf1`/`-mf2` come out byte-identical to
`-m1`/`-m2` (zpaqf did not change those two levels).

Most of the `-mf5` text gain turned out not to be the models at all but **one line
of type detection**: zpaq only scores a fragment as text when a letter, digit, `.`
or `,` is followed by a *space*, so newline-terminated source files score as binary
and never reach the text models. zpaqf adds the newline test. (Upstream writes it
as a condition ending in `|| '}' || '>'`, which are the constants 125 and 62, so
the whole guard is always true and the test is just the newline.) It is applied
under `-mf` only — applying it to `-m` would change the type byte, hence the
models, hence the bytes of every plain `-m` archive ever published.

`-mf3` needed the LZMA encoder that zpaqf's transform 14 assumes, so the LZMA SDK
(Igor Pavlov, **public domain**) is vendored at `compressors/lzmasdk/`, 6 sources
built single-threaded with `-DZ7_ST`. Only the encoder is involved: decoding is
the ZPAQL postprocessor stored in the archive, which is why `-mf3` archives read
back on binaries that have never heard of the SDK.

Two things from zpaqf are deliberately **not** here. **WBPE** (transform 13) is
GPL-3 against this project's MIT, so it is deleted from the source rather than
left behind an `#ifdef` — shipping it either way would relicense the project.
And zpaqf's image/stream detector is woven through its fragmentation loop instead
of being a liftable function; without it `-mf` never selects the image models,
which is why raster gains nothing at `-mf5` while `-mf3` (which reaches LZMA by a
different route) still gains 14%.

Verification: **70 round-trips** across all five levels and seven corpus shapes,
each extracted with both the new binary and pre13, which knows nothing about
`-mf`; **difftest 98 comparisons against pre13 with 0 divergences**; the golden
gate over all three sets (136 + 116 + 116) with 0 failures; os_msgs 25/25;
suite_core 263 round-trips and suite_flags 117 combinations, no failures. On
Windows: x64 compresses and extracts every `-mf` level under wine, and the
x86 build (extract-only by design) reads them back -- as does the published
pre13 x86.

Also noted while doing this: `make clean` only removes the binary, not the 131
`.o` files under `compressors/`, so a cross build straight after a native one
links host objects and fails with `undefined reference to franz_malloc(unsigned
long)`. Wipe `*.o` between targets.

### [64.8j-pre14] - 2026-09-10

**`-pc` removed entirely — decoder included.** pre13 kept the decoder so existing
`-pc` archives would still extract; that reasoning assumed archives in the field.
There are none, so the rest went too: `compressors/preflate/` and
`compressors/zlib/`, **87 source files and 2.3 MB**, and about **410 KB off the
binary** (7,357,480 -> 6,947,888 on Linux; similar on both Windows targets).

A `.zpaq` written with `-pc` by pre13 or earlier can no longer be reversed.
Extraction leaves the PCF container on disk and warns per file with `00566!`,
naming pre13 as the version that can still do it. Detecting that case needs only
the 4-byte `zPCF` magic, so the warning costs nothing.

What did **not** change: `pc_reverse_file()` and the parallel reverse post-pass
stay, because `-ytool` uses them. Reading that function before deleting it by line
number is the only reason `-ytool` did not break — it handles `zYTL` containers
first and only then fell through to PCF.

Tested across every algorithm: **263 core round-trips and 117 flag combinations
with no failures** (all 21 `-ma` codecs plus `-m0..-m5`), difftest 98 comparisons
against pre13 with 0 divergences, the golden gate 9 cross-checks with 0 failures,
and os_msgs 25/25.

The `pc-legacy` golden set is retired with its reason recorded: by design it can
no longer pass, and the archives are kept as evidence that the decoder existed.

---

### [64.8j-pre13] - 2026-09-10

**`-pc` removed as an encoder.** The older preflate/PCF precompressor no longer
creates anything; `-ytool` handles DEFLATE and more, so there is no reason to keep
two parallel paths through the compressor. Passing `-pc` (or `-pcc`) now says what
to use instead rather than reporting an unknown option.

**Archives already made with `-pc` still extract normally, and keeping that true
is why preflate and the vendored stock zlib stay compiled.** Reversing a PCF
container re-encodes it to prove the container is authentic — otherwise a verbatim
file that merely begins with the `zPCF` magic could be wrongly "reversed" — so the
decoder needs preflate's encoder and zlib. Dropping them would make existing
archives unreadable, so only the encoder is gone.

A golden set (`pc-legacy`) was created *before* the removal for exactly this: six
`-pc` archives written by pre12, which every later build must still extract
byte-for-byte. All three targets pass it 6/6.

Also fixed a real limitation in the golden gate found while adding that set: it
compared the **whole** corpus manifest, so adding a new corpus case invalidated
every earlier golden set — the corpus could never grow. It now compares only the
cases each set actually uses.

---

### [64.8j] - 2026-09-10

Eleven pre-releases. The first half added the `-ytool` precompressor and removed
`-sa`; the second half is almost entirely bug fixes, most of them found by
building a test harness and pointing it at the *published* binaries.

**The archive format is unchanged throughout.** One behaviour change is worth
calling out: since `pre11`, filenames with characters outside the Basic
Multilingual Plane are written correctly on Windows, so those bytes differ from
every earlier release (see below).

#### Filenames and the OS boundary

- **`pre11`** — `wtou()` (UTF-16 → UTF-8, Windows only) emitted a 3-byte sequence
  for every UTF-16 unit ≥ 2048, **surrogates U+D800–U+DFFF included, without
  pairing them**. A character outside the BMP *is* a surrogate pair, so it was
  stored as CESU-8 rather than UTF-8 — `f0 9f 8e 89` became
  `ed a0 bc ed be 89`. Its inverse `utow()` always handled the 4-byte case
  correctly, so Windows → Windows round-tripped by accident while
  Windows → archive → anywhere else produced a corrupted name. Affects emoji, CJK
  from extension B up, most mathematical and musical symbols. Romanian ș/ț, BMP
  CJK, Greek and Cyrillic were never affected, which is why it went unnoticed.
  A *lone* surrogate is deliberately left on the old 3-byte path: it cannot be
  represented in UTF-8 at all, and that encoding is exactly what `utow()`
  reverses — mapping it to `?` would lose the file's name. Archives written
  before this release keep their bytes and still extract as they did.

- **`pre8`** — seven Windows fixes, all found chasing a report that an archive
  "would not extract in Romanian". **It was never about the language**: a 46 GB
  multi-part archive, a destination without room for it, and an installer running
  the one mode that hides every error message. `fopen()` now goes through
  `_wfopen(utow(...))`, so paths outside the system codepage work; the free-space
  check measures the volume that actually contains the destination rather than
  truncating to the drive letter; a full disk aborts the run instead of
  continuing; and `-innosetup` no longer swallows errors and warnings.

- **`pre9`** — four pre-existing bugs. The serious one: `jidacreset()` cleared
  `edt` but not `vf`, which holds iterators *into* `edt`, so the next scan
  appended to a stale `vf` and `add()` read a file nobody had selected. On
  Windows `-append` died with an access violation and silently dropped the
  appended file; on Linux it segfaults or reports a bogus
  `HOUSTON expected/done`. The other three: the writability probe tested the
  filesystem **root** for any bare relative name, the POSIX branch of the
  free-space check reported 0 bytes free for any destination that did not exist
  yet, and the Windows branch gave up on a bare relative name.

#### Precompression

- **`pre4`** — new **`-ytool`**, superseding `-pc`. Instead of the built-in
  preflate path, zpaq-std shells out to
  [ytool](https://github.com/YadeWira/ytool) (a Free Pascal recreation of xtool),
  which detects far more embedded streams: gzip / zlib / ZIP / PDF DEFLATE
  **plus** JPEG, PNG, MP3, raw WAV/PCM and LZO. Measured **−12.1% vs plain and
  −5.2% vs `-pc`** on a mixed corpus with `-ma:flzma2`. Safe by construction: a
  file is stored as a ytool container only if `decode(encode(x)) == x` was proven
  byte-for-byte at encode time, and the container carries the original's size and
  CRC-32 so extraction re-checks the reversed bytes.
- **`pre5`** — container gating. `-ytool` used to look only at a file's first
  bytes, so a **`.tar`** was a no-op and the recompressible files inside it were
  invisible. Now a file with no offset-0 magic that looks like a container gets
  ytool's cheap detect-only `-scan` probe. Also made the output invariant across
  thread counts.
- **`pre3`** — **`-sa` removed entirely**, along with the vendored packJPG.
- **`pre2`** — `-pc` no longer touches the PNG family, reserved for a dedicated
  transform.

#### Other

- **`pre10`** — `libdivsufsort-lite` lifted out of the monolith into its own
  module and namespace. No behaviour change: byte-identical output, verified with
  84 differential comparisons. This unblocks separating the format core.
- **`pre6`** — six bugs from a full `-ma`/`-m` sweep: a `heatshrink` window size
  that overflowed its `int16_t` search index and spun forever on inputs ≥ 64 KB,
  short-alias flags in their space form, an invalid `-ma` name that carried on
  instead of stopping, password handling at EOF, and an exit code that claimed
  success after errors.
- **`pre7`** — `-innosetup` GUI: Cancel now runs the same abort path as Ctrl+C
  instead of killing the process, keyboard and `[x]` work, and the progress
  readouts are honest.
- **`pre1`** — version bump to 64.8j, and a password can be passed through the
  `FRANZKEY` environment variable.

#### Verification harness

Added under `test/testlab/`, and worth mentioning because two of the bugs above
were found by it rather than by a user: `golden_gate.sh` checks that the current
build still extracts `.zpaq` files written by *published* releases; `os_msgs.sh`
covers destination shapes and the numbered messages that nothing else looked at;
`difftest.sh` compares two binaries for byte-identical output and
cross-readability; `pin_corpus.sh` pins the corpus so a comparison cannot
silently run on different inputs.

---

### [64.7g] - 2026-06-22

The `-innosetup` progress window, the `-pc` speed arc, and a parallel front-end.

- **`-innosetup`** (`pre4`–`pre14`) — a native Win32 progress window for
  installer use, modelled on 7-Zip's 7zG and styled like an Inno Setup wizard
  page: comctl32 v6 progress bar, the verb and percentage in the title bar, two
  columns of stat rows, Background / Cancel buttons, and automatic dark/light
  theme detection. `-innosetup:FILE` writes progress to a file instead.
- **Parallel front-end** (`pre20`) — read, hash and fragment now run in a worker
  pool ahead of the main thread, which had been the bottleneck on many small
  files.
- **`-pc` speedups** (`pre15`–`pre18`, `pre22`) — DEFLATE streams under 4 KB are
  stored verbatim; cross-file prefetch overlaps preflate with the rest of
  compression (prefetch cap later raised 8 → 32, ~2.2×); the reverse pass at
  extract time is parallel and needs no temp file; the original is hashed in the
  prefetch worker; and a zlib fast-path tries stock zlib configurations before
  paying for preflate analysis. A `-pcc` deep-scan variant was tried and
  **reverted** — it did not pay for itself.
- **`-ma:ppmd`** (`pre3`) — PPMd var.H from the 7-Zip SDK as an external codec.
- **32-bit builds are extract-only** (`pre15`) — heavy compression does not fit a
  ~2 GB address space reliably, so `a` is disabled there.
- **packJPG** (`pre19`) was added as an `-sa` step and later removed together
  with `-sa` in 64.8j-pre3.

---

### [64.7g] - 2026-06-08

**`-pc` faster.** Two speedups for the precompressor: (1) DEFLATE streams smaller
than 4 KB are stored verbatim instead of run through preflate — tiny streams cost
the full analyze+verify pass but save almost nothing, so this removes most `-pc`
overhead on archives with many small streams (ZIP members, small PDF/PNG streams)
at negligible ratio cost; (2) on 64-bit, `-pc` now runs preflate on upcoming files
in a small worker pool *ahead* of the main loop (cross-file prefetch), overlapping
the expensive encode with the rest of compression — ~1.5× on deflate-heavy sets.
The pool size is tied to `-t` (so it honours `-t0` and the 32-bit core cap), uses a
bounded RAM cache, consumes results strictly in order, and falls back to inline for
large files. Round-trip is bit-exact and the archive format is unchanged.

**32-bit build is now extract-only.** Heavy compression (large `-ma` dictionaries,
`-pc` loading whole files into RAM) does not fit a ~2 GB address space reliably, and
the 32-bit binary's real use is extraction (old Windows, installers). On a 32-bit
build the `a` command now exits with a clear message; **extract / list / test /
`-innosetup x` are unchanged**. Create or modify archives with the 64-bit build.

**New `-ma:ppmd` external compressor** — PPMd var.H (public-domain Ppmd7 from the
7-Zip / LZMA SDK), bundled under `compressors/ppmd/`. A context-modeling (PPM) codec,
a different family from the existing LZ/LZMA/BWT set; strong on natural-language text
(beats brotli/flzma2 by ~20% on prose) and a good pair with `-pc`. `-ma:ppmd:N`
selects the model order (2–32, default 6); 64 MB model, thread-safe, round-trip
verified. Bundled external algorithms: 17 → 18.

**New `-pc` precompressor (preflate stream recompression).** Reversibly decodes
embedded DEFLATE streams to raw before compression and re-encodes them bit-exactly
on extraction, so the `-ma`/zpaq stage compresses the underlying data instead of an
opaque blob. Auto-detected by content: whole-file **gzip/zlib**, **ZIP** members
(so `.jar/.apk` and OOXML `.docx/.xlsx/.pptx/.odt`), **PDF** FlateDecode streams, and
**PNG** IDAT (re-split across the original chunks with recomputed CRC-32). Bundles
[preflate](https://github.com/deus-libri/preflate) (Apache-2.0) under
`compressors/preflate/`. Self-describing (auto-reverses on a plain extract) and safe
(verify-then-fallback: non-round-tripping streams are stored verbatim). The per-file
franz hash records the original (so `-test`/`-verify` work); `file_crc32` records the
stored PCF stream (so the `t` test passes). Composes with `-ma` and `-chunk`. Typical
gain ~12–18% on already-compressed inputs with a strong second stage (e.g.
`-ma:flzma2`). Verified bit-exact on Linux, Windows 10 and Windows 7 SP1, and across
x64/x86. Targets Windows 7+ (`_WIN32_WINNT 0x0601`).

**New `-innosetup` flag** — replaces all normal output with *only* the progress
percentage: a single integer `0..100` per line, written to stdout and flushed
only when it changes, ending with a guaranteed `100` on success. Implies
`-silent` so nothing else reaches stdout. Designed for an Inno Setup installer
that runs zpaq-std (compress or extract) and reads the pipe with `StrToInt()` to
drive a progress bar. Works for both `a` (add) and `x`/`t` (extract), since both
go through the shared `print_progress()` hook. On **Windows**, `-innosetup` shows
zpaq-std's **own native progress window**, modelled on 7-Zip's *7zG.exe* and styled
like an Inno Setup wizard page: a comctl32 v6 progress bar on its own thread (embedded
RT_MANIFEST `win/zpaq-std.manifest`, links comctl32) with the operation and percentage
in the **title bar** (`Compressing... NN%%` / `Extracting... NN%%`), two columns of stat
rows — **Elapsed time, Remaining time, Total size, Speed, Processed, Compressed size,
Compression ratio** (the last two on `a`; shown as `-` on extract) — and **Background**
(minimise, keep working) and **Cancel** (confirm, then abort) buttons. It **auto-detects the OS dark/light theme**: on Windows 10+ it reads
`AppsUseLightTheme` and, when dark, paints a dark background + dark title bar (via
`dwmapi`) and a dark progress trough (via `uxtheme`), both loaded at run time so there
is no extra link dependency; on **Windows 8.1 and older** (no such setting) it stays
light. On **non-Windows the flag is ignored** (runs as if not passed). Verified on Linux + a Win10 VM (headless: no
crash/hang, round-trip bit-exact; window appearance is visual). *(Earlier dev builds
had stdout/file progress reporting and a `-innosetup:FILE` form; those were dropped in
favour of the self-contained GUI window.)*

**`-ma:hs` (heatshrink) and `-ma:lzfse` restored** — they had been removed
(see 2026-06-07 below) after crashing on Windows, but that crash was the *same*
`CC` cross-prefix bug as the other Windows `-ma` failures. With it fixed they work
on Windows too, so they are back. Bundled algorithms: 15 → 17.

**Windows: full `-ma` parity (all bundled external compressors)**

- Fixed a Makefile bug where `CC` was not cross-prefixed (only `CXX` was), so the
  bundled **C** codecs (flzma2, lz5, lizard, bzip2, bzip3, brotli, libdeflate, lzlib)
  were compiled with the host `cc` into host ELF objects and linked into the Windows
  PE — their relocations were wrong for the target and the codec functions returned
  garbage, so `-ma` silently fell back to zpaq's internal codec. C++ codecs (zstd,
  snappy, bsc, lzham) were unaffected (they use `$(CXX)`). Now all bundled C codecs
  build as proper target objects.
- Fixed the Windows `LZ4_compress_fast` stub (512-byte workspace → full `LZ4_stream_t`),
  so `-ma:lz4/lz4hc/lz4f` apply instead of falling back.
- Result: **full `-ma` round-trip verified on real Windows 10**, matching Linux.

### [64.7g] - 2026-06-07

**Windows 7+ cross-compile support**

- `make CROSS_COMPILE=x86_64-w64-mingw32-` now produces a self-contained
  `zpaq-std.exe`: static MinGW runtime (`-static -static-libgcc -static-libstdc++`),
  links only `msvcrt` + core system DLLs, `.comment` section stripped post-link so
  the image loads. bzip2 built with `-DBZ_NO_STDIO` (+ `bz_internal_error()`).
- Fixed a real cross-platform bug: 16 `sscanf` sites read an `int64_t` with `%ld`
  (32-bit on Windows) — now `SCNd64` + an unconditional `#include <cinttypes>`.
- Verified on real Windows 10 LTSC: `lz4`, `lzav`, `bsc`, `lzh` round-trip with
  matching SHA-1. Native Linux build unchanged.

**Removed `-ma:hs` (heatshrink) and `-ma:lzfse`**

- Both crashed on the Windows build (access violation / heap corruption from a
  build-/ABI-specific bug; valgrind-clean and working on Linux). Rather than ship
  a platform-divergent feature set, both algorithms were dropped entirely — sources
  removed from `compressors/`, dispatch/validation/help removed from `zpaq-std.cpp`.
- Bundled algorithm count: 17 → 15. Use `-ma:lzh`/`-ma:bsc` for high ratio,
  `-ma:lzav`/`-ma:lz4` for speed.

### [64.7g] - 2026-06-03

**Bundled external compression algorithms (no system dependencies)**

- New `-ma:<algo>:<level>` switch family for 18 bundled compression algorithms
- All libraries copied verbatim into `compressors/` (no `apt install`, no system libs)
- Each algo adds ~10 lines of C++ glue around a single one-shot compress/decompress API
- Per-segment marker `zpaqstd-ma:<algo>:<level>:<origSize>` in segment comment, so archives are self-describing and tolerate mixed algos in the same .zpaq
- Default level per algo; if external output is larger than `orig - 16` the original is kept (no regression)
- **Fail-loud validation**: unknown `-ma:` algo name (e.g. `-ma:lz6:9`) now errors out with the full list of valid algos, instead of silently doing nothing (zpaq's internal DCE+CM still runs, masking the typo)

**Algorithms added**

| Switch | Lib | Levels | Default | Source files |
|---|---|---|---|---|
| `lz4` / `lz4hc` / `lz4f` | LZ4 v1.10.0 | 1–12 | 9 | 2 .c |
| `zstd` | zstd v1.5.7 (amalgamated) | 1–22 | 3 | 1 .c |
| `flzma2` | fast-lzma2 v1.0.1 | 1–10 | 5 | 13 .c |
| `lz5` / `lz5hc` / `lz5f` | LZ5 v1.5 | 1–15 | 9 | 2 .c |
| `lizard` | Lizard v2.1 | 10–49 | 17 | 10 .c |
| `bzip2` | bzip2 v1.0.8 | 1–9 | 9 | 7 .c |
| `bzip3` | bzip3 v1.5.3 (block_size = level × 100 KB) | 1–9 | 5 | 1 .c |
| `brotli` | brotli v1.2.0 | 0–11 | 11 | 35 .c |
| `snappy` | Snappy v1.2.1 (Google, BSD-3) | 1–2 | 1 | 9 .cpp/.h (C++ with C wrapper) |
| `deflate` | libdeflate v1.24 (ebiggers, MIT) | 0–12 | 6 | 39 .c (core + lib/x86 + lib/arm) |
| `lz` | lzlib v1.16 (lzip maintainers, BSD-2) | 0–9 | 6 | 14 .c (single-TU wrapper) |
| `lzav` | LZAV v5.8 (avaneev, MIT, header-only) | 0–1 | 0 | 1 .h |
| `hs` | heatshrink v0.4.1 (atomicobject, ISC) | 0–2 | 0 | 2 .c + 1 .h wrapper |
| `lzfse` | LZFSE (Apple, BSD-3) | 0–1 | 0 | 7 .c |
| `bsc` | libbsc v3.3.12 (IlyaGrebnov, Apache-2.0) | 1–9 | 3 | 12 .cpp + libsais |
| `lzh` | LZHAM (richgel999, Public Domain) | 1–4 | 1 | 19 .cpp |
| ~~`igzip`~~ | ~~igzip / Intel ISA-L~~ (~~x86_64 only, no 32-bit — skipped per portability goal~~) | — | — | — |
| ~~`zop`~~ | ~~zopfli~~ (~~KrzYmod fork's deflate output not parseable by libdeflate; removed in commit <sha>~~) | — | — | — |

**Compression ratios on 10KB `/usr/share/dict/words` (best level)**

| Algo | Compressed | Ratio |
|---|---|---|
| `zstd:22` (zpaqfranz default) | ~3.5KB | ~35% |
| `brotli:11` | ~3.4KB | ~33% |
| `lzh:3` | 3.83KB | 37.4% |
| `bsc:3` | 4.10KB | 40.0% |
| `lzfse` | 3.90KB | 38.0% |
| `hs:2` | 5.26KB | 51.3% |
| `lzav:1` | 110 bytes (header+segment, but deflate-better on dict/words) | varies |
| ~~`igzip`~~ | — | — |
| ~~`zop:N`~~ | — (removed) | — |

**32-bit support**

- `make m32` builds a 32-bit i386 ELF binary using `g++-multilib`. Auto-sets `CXXFLAGS=-m32 CFLAGS=-m32`.
- Requires `-D_GLIBCXX_USE_CXX11_ABI=0` to link against the older 32-bit C++ runtime (the new `std::__cxx11::` symbols are not exported in `libstdc++-32`). Applied via `ZPAQ_CXXFLAGS` and `ZPAQ_CFLAGS` in Makefile.
- Verified in wine: lzav:1, hs:2, lzfse, bsc:3, lzh:3 all round-trip on 5KB /usr/share/dict/words.
- **igzip is excluded from 32-bit** (it requires x86_64 nasm assembly).
- **zop is excluded from 32-bit** (zopfli removed entirely — see commit).

**Windows 7+ support (partial)**

- Cross-compile to Windows via `make CROSS_COMPILE=x86_64-w64-mingw32-` (or `i686-w64-mingw32-` for 32-bit).
- Requires `g++-mingw-w64-x86-64 g++-mingw-w64-i686 mingw-w64-tools nasm wine` packages.
- **Status: all 5 newly added algos (lzav, hs, lzfse, bsc, lzh) compile cleanly on Windows**, plus the existing 12 (lz4, zstd, flzma2, lz5, lizard, bzip2/3, brotli, snappy, libdeflate, lzlib). The pre-existing inline LZ4 code in `zpaq-std.cpp` (~1500 lines) collides with the newly bundled `compressors/lz4/lz4.c` (the codebase predates the bundled-compressors architecture). Full Windows support requires removing the inline LZ4 in favor of `compressors/lz4/lz4.c` — tracked as a separate refactor.

**Build system**

- Makefile extended with 4 pattern-rule styles: single-dir (lz4/zstd/lzlib), multi-dir (fl2/lz5/lizard), multi-subdir with disjoint static pattern rules (brotli common/enc/dec; libdeflate core/x86/arm), and C++ with `$(CXX)` (snappy uses Google C++ code with a C wrapper)
- All 3 brotli subdirs and 3 libdeflate subdirs use separate `*_OBJ` variables to avoid "overriding recipe" warnings
- `BZIP3INC` adds `-Wno-unused-function` to silence `libsais.h` static-include noise
- `SNAPPYINC` adds `-Wno-sign-compare` to silence Google's deliberate `unsigned < 0` checks
- lzlib single-TU wrapper pattern: 13 sub-`*.c` files all `#included` from one `lzlib.c` translation unit, exposing only `lzlib_compress_wrapper` / `lzlib_decompress_wrapper` to the rest of zpaq
- Bonus: fixed pre-existing `%.o: compressors/X/%.c` pattern rules (path only on prereq side) that silently matched the default `cc -c` rule and skipped our flags. The fl2/lz5/lizard .o files were only working because they were pre-built and never recompiled.

**Documentation**

- New `WORKFLOW.md` with a 5-step recipe for adding a new algorithm, a round-trip test script, and a troubleshooting section (for your siblings continuing the work)
- `README.md` rewritten to highlight the 12 bundled algos and the no-system-deps philosophy
- `BENCHMARKS.md` updated with per-algo and mixed-archive test results for all 12 algos
- `.gitignore` added (excludes `zpaq-std` binary, `tmp/`, `test-files/`, editor cruft)

**Tested**

- 11 single-algo round-trips on 4 MiB of zeros: all MATCH
- 1 mixed archive with 12 files (one per algo): all MATCH
- `-ma:lz6:9` (typo) now errors out with the list of valid algos
- Clean build with `make` produces 0 warnings, 0 errors
- Binary ~6.09 MB
- Total bundle: 93 source files, ~9.7 MB

<!-- Everything below is zpaqfranz's own changelog, by Franco Corbelli, up to the version
     zpaq-std forked from; its links point to github.com/fcorbelli/zpaqfranz. -->

### [63.3b] - 2025-09-23

FRANZEN Enhancements

**Added**
- Experimental FRANZEN function now stores CRC-32 of encrypted file blocks in the header.
- New `work crc32` command for quick integrity checks without requiring the encryption password.

**Improved**
- CRC-32 computation uses multi-threaded block processing, similar to zpaqfranz.
- Verification function skips the first 140 bytes (128 + 12) and processes the rest efficiently.
- Supports high-speed integrity checks for cloud transmission on standard machines.

**Notes**
- CRC-32 is **not cryptographic**; it only provides a fast integrity check.
- Full verification still requires `work test` with the encryption password.
- Additional checks are planned for future refinements.


### [63.2t] - 2025-09-22

## SFTP Bandwidth Limitation
SFTP bandwidth limitation, distributed across multiple threads, using the `-bandwidth` switch.

## New Switches and Features
- `-sparse`: On Windows, attempts to create a sparse file (typically for NTFS). This can halve the extraction time for gigantic files.
- `-huge`: Uses a different algorithm for file preparation. Useful for few but enormous files on filesystems that do not support sparse files.

Details: [Discussion #213](https://github.com/fcorbelli/zpaqfranz/discussions/213)

- In the `dir` command, the `-nodir` switch now displays only files, excluding folders.
- In the `hash` command, a new `-norecursion` switch performs as expected (non-recursive hashing).
- The `-always` switch forces adding files even if their timestamp has not changed. Conceptually similar to `-only`, it can be repeated and used with wildcards.

## Compatibility and Performance Improvements

- Enhanced `iswindowsxp` function for improved compatibility (in theory).
- Improved wide character support on Windows, including some emojis.
- Rewritten output function (potential for introduced bugs, but refactoring was necessary).
- Most source code comments are now in English.
- Improved local time handling, including for negative UTC offsets (e.g., USA).
- Added support for file hash calculations with an offset (implementation for future FRANZEN testing).

## New Functions and Builds

- New `kickstart` function for downloading files from the internet or extracting them (if available) on Windows.

Details: [Discussion #205](https://github.com/fcorbelli/zpaqfranz/discussions/205)

- Added release of `zpaqfranz-full.exe` (for 64-bit Windows), which includes statically linked resources (useful for offline systems; no other functional differences).

## FRANZEN Encryptor
Details: [Encode.su Thread](https://encode.su/threads/4431-sodio-file-encryption-my-way)

Essentially, this is an early (very immature) version of a future capability to encrypt zpaqfranz files (losing backward compatibility with zpaq) using a different encryption system and a separate password.

In the future (not yet implemented), it will enable **double encryption** for files: an outer layer (FRANZEN) and an inner layer (standard zpaq). This allows GDPR-compliant cloud storage where the provider knows the outer password, but only the user knows the inner one.

Key feature: Parallel integrity testing of the encrypted file. Instead of single-threaded hashing (reading one byte at a time to compute e.g., SHA-256), FRANZEN reads the encrypted file in blocks, achieving real-world performance exceeding 2GB/s on consumer hardware on non-spinning drives

This is a highly complex topic—treat it as experimental (which it is).

### [62.4e] - 2025-07-23

# New `sync` command
This command compares the content of an archive, or one of its subfolders, with a filesystem.  
It is generally recommended to use absolute paths rather than relative ones.  
It essentially serves two purposes:  
1) **Test or verification**: After performing an archive with the `a` command, a "heavy" verification can be done with the `sync` command (use `-quick` to skip hash checking and only compare sizes, or `-ssd` to enable multithreading on non-rotational disks).  
2) **Estimate data**: Estimate how much data would be archived if an update for a new version were performed.  
It differs from the `v` (verify) command because it also shows new files not present in the archive and those that are missing.

# Multithread support for the `t` (test) command
It is now possible to use all cores in the second phase (CRC-32 reconstruction).  
This has no significant impact if there are few archived files (e.g., a single virtual disk image), but it can reduce processing time by up to ten times in optimal cases (e.g., millions of small files, such as on a file server).  
**Note**: This feature is not extensively tested.

## Default progress is now displayed at one-second intervals  
Instead of updating based on ETA changes, this reduces console impact for very large jobs.

### Attempt (harder) to restore text color when pressing Ctrl+C

## Using `-stat` adds `|STAT|` to output lines  
This facilitates the removal of sensitive information for privacy purposes (e.g., using `grep`, `awk`, etc.) when sending logs via email.

### Renamed the key file for the `sftp` command to `-ssh`

### Further refactoring, likely introducing new bugs

### Various minor internal improvements

### [62.3a] - 2025-07-19
### Version Number Change for Macintosh Users
To address an issue affecting Homebrew users on Macintosh who were "stuck" due to a versioning error, a significant version number increment has been implemented. 
This should resolve the issue for those users. 
If you see version 62.3 instead of 61.7, know that it’s for a good cause.

### Internal Changes to Reduce False Positives in Kaspersky and Other Antivirus Software
Various program analysis systems use heuristics to detect viruses. 
After reverse-engineering Kaspersky’s detection methods, which flagged false positives for some versions of zpaqfranz, I introduced source code fixes. 
Unfortunately, due to known reasons, Kaspersky is no longer installed on any of my machines, so I hadn’t noticed this earlier.

### Autotest Command: Default Quick Hash Check for Moderate File Sizes
The `autotest` command now performs a quick hash check by default, even for moderately sized files. 
This should help detect errors like hexadecimal conversion issues.

### Autotest Command: Additional Information with `-all` Switch
The `autotest` command now displays additional details when using the `-all` switch, particularly the execution time of operations. 
This is useful for performance comparisons.

### Info Command (`i`): File Size Display for Encrypted Files
The `i` (info) command now shows the file size (or sizes for multipart archives) including the additional 32 bytes for encrypted versions. 
For example, if an archive is 10,000 bytes but encrypted, the actual size is 10,032 bytes, and this is now displayed.

### SFTP Command: Support for Key-Based Authentication
The `sftp` command now supports the `-key` option to use keys for connecting to an SFTP server. 
Significant changes to the SFTP interface are ongoing, with plans to make it the primary interface for ransomware-resistant systems in the future.

### SFTP Command: Bandwidth Limiting for Uploads
The `sftp` command now allows limiting the total upload bandwidth using the `-bandwidth` switch. 
Note that this limit is divided by the number of threads if using `-ssd`. For example, setting a 100K limit with 10 threads results in a 10K limit per thread.
Use -tX to cap to X threads (with -ssd)

### Fixed a Specific Case in the `t` Command for CRC32 Block Recalculation
A particular issue with the `t` command for recalculating CRC32 blocks has been addressed. 
This should resolve the issue permanently.
Who knows. 
In the future, a multithreaded checker might be developed.

### Refactoring from Static Analysis
Static analysis refactoring has been performed. 
While I hope it hasn’t introduced too many bugs, issues are possible. 
Compilation tests were limited to two environments (Windows and Debian). 
Full certification across all platforms will wait until the SFTP module is further developed.

### [61.6] - 2025-07-10
Fixed a bug due to refactoring, false positive in t

### [61.5] - 2025-07-10
There are many new features in this build, so particular attention should be paid to the possibility of new bugs being introduced.

## Main Change
The primary change is the overhaul of the interface with CURL and the management of SFTP commands, which now (mostly) support the `-ssd` switch for parallel operations.
### Supported commands for sftp
- **upload**: Uploads a single file to SFTP.
- **verify**: Quickly compares a local file to a remote file.
- **quick**: Retrieves the QUICK hash of a remote file.
- **ls**: Lists the contents of a remote folder.
- **delete**: Deletes a remote file.
- **size**: Retrieves the size of a remote file.
- **rsync**: Performs an rsync-like operation to sync local files to a remote folder (`-ssd` supported).
  - `-force`: Prevents appending.
- **1on1**: Quickly compares local files to a remote folder (`-ssd` supported).

## New Switches
- **-appendoutput**: Appends data to the `-out` file instead of recreating it each time.
- **-writeonconsole**: Writes output to stderr, allowing data to be displayed on the console even when redirected.
- **-last**: Operates on the last file in a selection, typically used for the last part of a multipart archive.
- **-home**: Now works with the `l` (list) command, showing the sizes of virtual folders inside an archive at one level deep.

## Other Additions
- Introduced `work devart` for highly visible on-screen text.
- In the `utf` command, the `-fix255` switch checks the maximum length of specified file names with `maxsize`.
- New `drive` command on Windows: Displays the list of connected physical disks with their respective numbers.
- The `-all` switch (with `-image`) on Windows operates on an entire disk image, similar to `dd`, rather than a single partition.
- New commands: `work datebig` and `work datetimebig`.

## Additional Features
It is now possible to extract only the files added in a specific version, marked with a textual comment, using the following example format:
```
c:\zpaqfranz\zpaqfranz x z:\2.zpaq -to z:\wherever -comment "something" -range
```

## Miscellaneous Changes
- Improved OpenBSD support.
- On Windows, `decodewinerror` is no longer hardcoded (now respects the local language).
- Fixed the `test` command to address occasional false positives.
- Improved alignment of help text lines.
- Removed comments from the CURL library and unused defines.

## Additional Notes
- Reduced the size of the source code.
  
### [61.4] - 2025-06-16

# - Many features in this release (e.g., `-image`, `-ntfs`, `ntfs` command, `work resetacl`) are experimental and not fully tested. Use with caution and report issues.

#### Added

##### For *nix (Linux, etc.)
- **`-image` Switch**: Added to the `a` (add) command to create a sector-by-sector copy of a device, similar to the `dd` command.
  - Restored images can be mounted on Linux using a snippet like:
    ```bash
    fdisk -l image.img
    losetup -fP _dev_sda.img
    losetup -a
    mkdir -p /ripristinato
    mount /dev/loop0p1 /ripristinato
    (...)
    umount /ripristinato
    losetup -d /dev/loop0
    ```
  - Experimental feature; not thoroughly tested.
- **`-tar` Switch**: Available during archive creation (`a`) and extraction (`x`) to preserve file access rights, group, and user metadata.
  - When used with the `l` (list) command, displays the added metadata.
  - Simplifies metadata restoration for *nix systems.
- **Improved ZFS Backup Handling**: Enhanced automatic integration with `pv` for better user feedback on backup progress during ZFS operations.

##### For Windows
- **`-ntfs` Switch**: When used with `-image`, stores only the used sectors of an NTFS partition in the zpaq archive.
  - Format is experimental and not yet optimized.
  - Intended for emergency image-based backups of Windows systems.
- **New `ntfs` Command**: Regenerates the original file from a zpaqfranz-created image, filling unused sectors with zeros.
  - Experimental and under active development.
- **`-ntfs` Switch (without `-image`)**: Scans an NTFS drive by reading and decoding its NTFS data directly, bypassing file-by-file enumeration.
  - Similar to the behavior of the "Everything" utility.
  - Significantly speeds up file enumeration on large, slow servers with magnetic disks.
- **New `work resetacl` Command**: Generates a batch file to reset folder permissions to administrators.
  - Useful for normalizing access after restoring NTFS folders with restricted permissions.
  - Experimental; intended to address post-restore access issues.

#### Changed
- **Code Refactoring**: Reduced compilation warnings for both Windows and *nix platforms.
- **Dropbox Cache Handling**: Skips `.dropbox.cache` folders during operations to avoid unnecessary processing.
- **Command Path Detection (*nix)**: Adopted a smarter strategy to locate *nix commands in likely directories, improving reliability.

#### Notes
- The `-ntfs` switch is designed for specific use cases like large server enumeration or emergency backups but may evolve in future releases.
- The `-tar` switch enhances metadata handling for *nix, making it easier to restore complex file permissions.
- The `pv` integration for ZFS backups improves user experience but requires `pv` to be installed.
- Feedback and bug reports are welcome via GitHub issues.

  

## [61.3] - 2025-04-05

### Added
- **Power-Saving Features**: Introduced new switches and functions to reduce energy consumption during operations.
  - **`-slow` Switch**: Disables TurboBoost on modern CPUs (tested on AMD, untested on Intel) to limit maximum frequency.
    - Reduces power consumption by up to 30% during deduplication-heavy tasks (e.g., SHA1 calculation) with minimal impact on execution time.
    - Decreases noise on systems with variable cooling (fans, pumps).
    - Reliable on Windows; experimental on Linux (hardware interaction varies).
  - **`-monitor` Switch (Windows only)**: Puts the monitor into standby mode to save power during long sessions.
    - Not tested on multi-monitor setups (planned for future testing).
    - Not implemented for non-Windows systems due to complexity (X, non-X, consoles, etc.).
  - **`-shutdown` Switch**: Performs a "merciless" system shutdown after completing an `add` command.
    - Windows: Attempts to terminate all processes (success not guaranteed).
    - Non-Windows: Uses heuristic methods to handle `sudo` availability (not universally present).
  - **New `work` Commands**:
    - `zpaqfranz work shutdown`: Triggers a merciless system shutdown.
    - `zpaqfranz work big turbo`: Activates CPU turbo mode.
    - `zpaqfranz work big noturbo`: Deactivates CPU turbo mode (same as `-slow`).
    - `zpaqfranz work monitoroff`: Turns off the monitor (Windows only).
    - `zpaqfranz work monitoron`: Turns on the monitor (Windows only).
- **Example Usage**: `zpaqfranz a z:\1.zpaq c:\pippo -slow -monitor -shutdown`

### Changed
- **Shutdown Logic**: Improved system shutdown mechanism with platform-specific heuristics (e.g., `sudo` detection on non-Windows systems).

### Notes
- The `-slow` switch is most effective when deduplication dominates over compression, offering power savings with negligible performance impact.
- The `-monitor` feature is Windows-only due to the complexity of non-Windows display systems; no plans to extend it currently.
- The `-shutdown` feature may not always succeed on Windows due to process termination challenges.
- Feedback or suggestions are welcome via GitHub issues or direct contact.

---

## [61.2] - 2025-04-05

### Added
- **New `mysqldump` Command**: Introduced a new command to automatically generate backup scripts for MySQL/MariaDB databases, saving each database as a separate file within a single `.zpaq` archive.
  - Default behavior: Dumps all databases (excluding system databases like `information_schema`, `performance_schema`, and `sys`) as the root user.
  - Filtering options:
    - `-only <pattern>`: Include only databases matching the specified pattern (e.g., `-only 2015` matches `db2015`, `test2015prod`).
    - `-not <pattern>`: Exclude databases matching the specified pattern (e.g., `-not temp` excludes `temporary`, `temp_db`).
  - Compression and encryption support via `-mX` (compression level 0-5) and `-key <pwd>` (archive encryption).
  - Heuristic executable detection:
    - **Windows**: Searches `c:\program files` for `mysql.exe` and `mysqldump.exe`. Use `-space` to download 64-bit versions from [www.francocorbelli.it](http://www.francocorbelli.it/) or `-bin <path>` to specify a custom location.
    - **Non-Windows**: Searches typical directories (`/bin`, `/usr/local/bin`, etc.) or allows manual specification with `-bin <path>`.
  - Connection options: `-u <user>`, `-p <password>`, `-h <host>`, `-P <port>`.
  - Verbose mode with `-verbose`.
  - Example usage:
    - Windows: `mysqldump z:\1.zpaq -u root -p pluto -h 127.0.0.1 -P 3306 -key pippo -m2`
    - Linux: `mysqldump /tmp/test.zpaq -u root -p pluto -bin "/bin"`
    - Filtered: `mysqldump test.zpaq -u root -p pluto -only prod -not backup`
- **Solaris Compatibility**: Added support for Solaris systems.
- **ESXi Support**: Included compatibility improvements for ESXi environments.

### Changed
- **Deduplication Optimization**: Emphasized that deduplication occurs before compression, significantly speeding up subsequent backups of unchanged databases, especially with high compression levels like `-m4`.

### Fixed
- Minor bug fixes (details not specified in the release notes).

### Notes
- The `mysqldump` command is still under development but already provides significant utility.
- The `-fragment` switch is not compatible with this command due to its piping mode.
- Parallel dumping was considered but not implemented to maintain a single `.zpaq` file per RDBMS for convenience.
- Suggestions and issues can be reported via GitHub or direct contact.

---

## [61.1] - 2025-02-14

### Added
- **SFTP Support with libcurl**: Enabled SFTP functionality by compiling with `-DSFTP` to dynamically use the libcurl library.
  - **Windows**: Automatically downloads `libcurl-x64.dll`/`libcurl.dll` from the author's website (`zpaqfranz sftp`) if not found.
  - **Non-Windows**: Requires manual installation of `libcurl.so` (e.g., `apt install libcurl` on Debian, `pkg install curl` on FreeBSD). Searches heuristically in common paths (`/usr/lib/`, `/usr/local/lib/`, etc.).
  - **Use Case**: Direct uploads to SFTP servers (username/password only; key file support planned), reducing ransomware risks compared to Samba shares.
  - **Note**: Do not use `-static` with `-DSFTP` on *nix systems due to inconsistent behavior across platforms.
- **TUI Command**: Added a minimal text-based user interface (`tui`) to list, select, and extract files from archives.
  - Replaces the previous ncurses-based GUI with a simpler, DOS-like interface.
  - Works on most *nix systems (not very old ones). Use `h` or `?` for help.
  - Development status: ~50% complete, with many edge cases still needing debugging.
- **LS Command**: Introduced the `ls` command to navigate `.zpaq` archives like a filesystem.
  - Supports `ls (/dir)` to list directories, `cd` to change directories, and `get` to extract files.
  - Development status: ~30% complete, very immature, lacks TAB support and requires significant work.
  - Use `help` or `?` for command list.
- **New Switches**:
  - `-noonedrive`: Disables Windows OneDrive placeholders to prevent automatic downloads to the local drive.
  - `-norecursion` with `-only` in `list`: Prevents recursion into folders when listing with `-only` (fixes [issue #156](https://github.com/fcorbelli/zpaqfranz/issues/156)).
  - `-DNOLM` (experimental): Uses a software implementation for numeric functions, bypassing the `lm` library for compatibility with unusual systems.

### Removed
- **Server Code**: Dropped `zpaqfranz-over-TCP` functionality, replaced by SFTP.
- **Windows GUI with ncurses**: Replaced by the new `tui` command.

### Fixed
- **Linuxsettime Issues**: Addressed some unspecified bugs in `linuxsettime` functionality.

### Changed
- **Branch Introduction**: This release marks the start of branch 61 with significant new features and potential instability.

### Notes
- **Development Status**:
  - `sftp`: ~70% complete and tested.
  - `tui`: ~50% complete, needs extensive debugging.
  - `ls`: ~30% complete, highly experimental.
- **User Feedback**: As this is the first release of branch 61, bugs are expected. Please report issues on GitHub to help improve stability and functionality.
- **SFTP Installation Examples**:
  - Debian: `apt install libcurl`
  - Fedora: `dnf install libcurl`
  - FreeBSD: `pkg install curl`
  - macOS: `brew install curl`
  - See documentation for full list of package manager commands.

## Planned at the time of [60.10]
- Planned SFTP key file support.
- Multi-monitor testing for future releases.
- Enhanced `tui` and `ls` functionality (e.g., TAB support for `ls`).

---

## [60.10] - 2024-12-20

### Added
- **`-tmp` Switch**: Now enabled by default for backups. Creates archives with a `.tmp` extension during compression, renaming them to `.zpaq` only upon successful completion.
  - Mitigates corruption risks from unexpected shutdowns or crashes by ensuring incomplete archives remain as `.tmp`.
  - On restart, existing `.tmp` files are "parked," allowing the process to resume and complete.
- **`-notrim` Flag**: Disables automatic correction of incomplete transactions in the last transaction, restoring zpaq 7.15 behavior.
- **`-destination` Switch in `consolidate` Command**: Allows renaming of `.zpaq` backup files (e.g., from `pippo` to `pluto`).
  - Complements the existing `-to` switch, which merges multipart files into a single file (labeled 01).
  - **Warning**: Always use full paths (e.g., `c:\zpaqfranz\pippo.zpaq`) with `consolidate`.
- **Enhanced `i` (info) Command**:
  - Now displays totals by default.
  - Added `-n` switch to show the last few lines of info output.
- **`-nopid` Switch**: Disables creation of `.pid` files during backups to prevent multiple executions.
- **Windows Progress Display**: Shows download progress in the calling console during updates from the author's website.
- **`-big` Switch Enhancement**: During backups, displays the last day of the backup in a larger format for easier log checking.

### Changed
- **Default Backup Behavior**: Backup command now uses `.tmp` files by default to protect against corruption from interruptions.
- **Incomplete Transaction Handling**: 
  - zpaqfranz now issues a prominent warning for incomplete transactions.
  - Automatically attempts to correct the archive if the interrupted transaction is the last one (unless `-notrim` is used).
  - For severe cases, users can use `consolidate` (multipart) or `trim` (single file) to remove corrupted parts.

### Fixed
- **`-stdin` Bug**: Resolved an issue that disabled the deduplicator when using `-stdin`.
- **Windows XP Support**: Restored compatibility for the 32-bit version on Windows XP.
- **Minor Source Code Fixes**: Addressed various unspecified issues in the codebase.

### Notes
- The `.tmp` feature addresses zpaq's historical fragility with corrupted archives due to shutdowns or crashes, improving reliability for both single and multipart backups.
- For further details or to report issues, refer to the GitHub issues section.
- Future plans include a switch to convert "normal" `.zpaq` archives directly into backups.

## Planned at the time of [60.9]
- Planned switch to convert "normal" `.zpaq` archives into backups.

---

## [60.9] - 2024-11-13

### Added
- **`-nojit` Switch**: Replaces the `-DNOJIT` compilation flag. Automatically detects JIT support at both CPU and OS levels (e.g., NetBSD may block `PROT_EXEC`).
  - JIT accelerates data extraction (compression speed unaffected).
  - Not fully tested on virtualized systems with "fake" CPUs; a `forcejit` switch is planned for the future.
- **`-tmp` Switch for Multipart Files**: Names multipart files as `.tmp` during creation, renaming them to `.zpaq` upon completion.
  - Enables parallel testing/updates and compatibility with file-sync tools like Syncthing.
- **Improved Password Handling**: Enhanced `-key` switch with support for delete key and cursor movement.
  - Prompts for password twice during archive creation to ensure consistency (e.g., `zpaqfranz a z:\1.zpaq *.cpp -key`).
- **1980 Timestamp**: Sets file dates to 1/1/1980 during creation, updated only when the `jidac` header is written, aiding identification of incomplete files.
- **Windows Placeholders**: Added filename placeholders `$pcname`, `$computername`, and `$username` (e.g., `zpaqfranz a z:\pippo_$username c:\nz`).
- **ZETA Hasher with `-backupzeta`**: New pseudo XXHASH64 hash calculation during backup generation.
  - Avoids re-reading large multipart files (e.g., virtual disks) for integrity checks, also calculates CRC-32.
  - Not yet supported for encrypted multipart archives (planned for future).
- **`-nomore` Switch**: Disables the internal `more` command for faster external text processing (e.g., `zpaqfranz h h -nomore | less`).
  - On 64-bit Windows, enables experimental LargePages support (no noticeable improvement; may be removed).
- **Common Switches List**: Accessible via `zpaqfranz h common`.
- **P7M Signature Check**: Windows option to verify FEQ digital signatures for hash files during updates (see [wiki](https://github.com/fcorbelli/zpaqfranz/wiki/Windows-update)).
- **IPv6 Support**: Experimental support with `-DIVP6` compilation flag for the upgrade command (untested due to lack of IPv6 environment).

### Changed
- **JIT Handling**: Moved from compile-time `-DNOJIT` to runtime `-nojit` switch for broader compatibility.
- **Command Rename**: `consolidatebackup` renamed to `consolidate`.

### Fixed
- **Old Compiler Compatibility**: Minor fixes for very old compilers (e.g., Slackware) and 32-bit systems.
- **HPPA CPU Support**: Resolved a potential CRC-32 alignment issue on strict-memory CPUs (e.g., 32-bit HP RISC), slightly slower but more reliable.

### Notes
- **Compatibility Efforts**: Ongoing support for old systems and compilers remains a challenge but is maintained with minimal divergence from modern versions.
- **ZETA Hasher Details**: See GitHub issues for a full explanation of `-backupzeta` functionality.
- **IPv6**: Untested due to lack of test environment; feedback welcome.
- **Hints**: Additional context for changes can be found in [GitHub issues](https://github.com/fcorbelli/zpaqfranz/issues?q=is%3Aissue).
- **Request**: Testing on Apple Silicon (Mx) systems is desired; contact the author if you can provide access.

## Planned at the time of [60.8]
- Planned `forcejit` switch for overriding JIT detection.
- Support for `-backupzeta` with encrypted multipart archives.
- Potential removal of `-nomore` LargePages experiment.

---


## [60.8] - 2024-10-21

### Added
- **`-backupzeta` Switch**: Generates checksums (almost XXHASH64 and CRC-32) on-the-fly during `.zpaq` file creation in the backup command.
  - Saves time by avoiding post-creation reads, especially on slow HDDs.
  - Future support planned for encrypted volumes ([issue #139](https://github.com/fcorbelli/zpaqfranz/issues/139)).
- **Creation Date Set to 1/1/1980**: `.zpaq` archives are now stamped with 1/1/1980 to easily identify incomplete files ([issue #138](https://github.com/fcorbelli/zpaqfranz/issues/138)).
- **New Hash Algorithms**: Added ZETA and ZETAENC, selectable with `-zeta` and `-zetaenc`.
  - Details in [issue #139, comment](https://github.com/fcorbelli/zpaqfranz/issues/139#issuecomment-2425010093).
- **`-destination` Switch**: Allows loading multiple `-to` options from a text file for batch processing.
  - Explanation in [issue #136, comment](https://github.com/fcorbelli/zpaqfranz/issues/136#issuecomment-2422947782).
- **`-nodelete` Switch**: Prevents marking files as deleted if not found during path scanning, useful for bulk file list manipulation.
  - Details in [issue #136, comment](https://github.com/fcorbelli/zpaqfranz/issues/136#issuecomment-2416220823).
- **`-salt` Switch**: Forces an empty salt (32 zero bytes) for development purposes (not recommended for general use).
- **`-hdd` Switch**: Uses RAM (including virtual memory/swap) to buffer extracted data before sequential writing to HDD.
  - Reduces seek times on HDDs, halving extraction time for medium-sized files (not suitable for very large files).
  - Details in [issue #135](https://github.com/fcorbelli/zpaqfranz/issues/135).
- **`-ramdisk`**: Internal support for `-hdd` functionality.

### Changed
- **Build Compatibility**: Improved support for BSD operating systems:
  - OpenBSD
  - NetBSD
  - DragonFly BSD
- **Warnings Display**: Warnings are now highlighted in yellow for better visibility.

### Fixed
- **`-input` Bug**: Minor fix for Windows-specific issue with the `-input` switch.

### Notes
- The `-backupzeta` switch significantly improves performance on slow drives by eliminating the need to re-read files for checksums.
- The `-hdd` switch leverages RAM/SSD speed for faster HDD writes but is limited by available memory for large files.
- The `-salt` switch is intended for development and debugging, not end-user scenarios.
- Additional context and explanations for many features can be found in the linked GitHub issues.

## Planned at the time of [60.7]
- Planned support for `-backupzeta` with encrypted volumes.

---

## [60.7] - 2024-10-08

### Added
- **`-errorlog` Switch**: Creates a file listing errors to reduce log clutter.
- **`-nocaptcha` Switch**: Bypasses captchas during operations.
- **`-ht` Switch**: Overrides the default use of physical CPU cores (no Hyperthreading) to revert to the previous Hyperthreading-enabled method.
- **`-input` Switch**: Loads a list of files to be added from a specified input file.
- **`-715` Switch in `l` (list) Command**: Restores an output nearly identical (binary-wise) to zpaq 7.15.
- **`-to` Switch in `sfx` Command (Windows)**: Extracts the `.zpaq` file from a self-extracting executable.
- **`-home` Switch in `sum` Command**: Replaces the previous `-checksum` switch.
- **`-fixreserved` Switch (Windows)**: Removes the `:` character from filenames during extraction to handle reserved character issues.
- **Memory Usage Tracking**: Displays approximate memory usage in the final output line.
- **UTF8 Output Work Command**: Added a new `work` command for improved UTF8 file output handling on Windows.

### Changed
- **License Update**: Modified the license of one component to comply with Fedora policies.
- **CPU Detection**:
  - Now defaults to using physical CPU cores only (no Hyperthreading); use `-ht` to revert.
  - Improved CPU count detection on Solaris (untested).
- **Error Messages**: 
  - Displayed in red by default for better visibility.
  - More descriptive messages for out-of-memory errors caused by overly small fragments.
- **UTF8 File Output**: Completely rewritten for Windows to enhance compatibility and functionality.
- **Output Lines**: Renumbered for clarity.
- **Backup Naming**: Heuristically adopts the name of an existing backup in some cases.

### Notes
- This release introduces numerous features; expect potential bugs as testing continues.
- The wiki is being updated with more details; for now, this changelog provides a high-level overview.
- Feedback and bug reports are welcome via [GitHub issues](https://github.com/fcorbelli/zpaqfranz/issues).

---

## [60.6] - 2024-08-25

### Added
- **Improved `-stdin` Management**: Files added via `-stdin` are now deduplicated as efficiently as manually added files.
- **`comparehex` Command**: Compares hexadecimal hash codes between two files, exiting with "OK" if they match.
  - Ignores non-hex characters; optional hash length specification.
  - Example: `zpaqfranz comparehex z:\1.txt z:\2.txt "GLOBAL SHA256:" 64`
- **`count` Command**: Counts occurrences of a string across multiple files, returning "OK" if the count matches the expected value.
  - Defaults to counting "OK" with `-big` if no string is specified.
  - Example: `zpaqfranz count z:\*.txt 3 "all OK"`
- **`work` Command Verbs**: Added utility functions for log automation.
  - Examples: `work big "count the ok"`, `work pad 123 -n 4`, `work date "%year_%month_%day" -terse`.
- **`-crc32` Switch for `t` (test) Command**: Performs a triple CRC-32 check against the filesystem.
  - Compares original, recomputed, and re-read CRC-32 values for integrity verification.
  - Supports `-find`/`-replace` for path adjustments and `-ssd` for multithreading.
  - Example: `t z:\\1.zpaq -crc32 -find "x:/memme/" -replace "c:/nz/"`
- **`-terse` Switch**: Reduces output verbosity across commands for easier redirection.
- **`-csv` and `-csvhf` Switches for `l` (list) Command**: Outputs file lists in a CSV-like format.
  - `-csvhf` adds header/footer strings; uses `\t` for TABs.
  - Example: `l z:\1.zpaq -terse -csv "\",\"" -csvhf "\""`
- **`-external` Switch in `a` (add) Command**: Executes an external command before adding files, saving its output to a virtual file (e.g., `VFILE-l-external.txt`).
  - Useful for snapshots or independent hash checks (e.g., with `hashdeep`).
  - Example: `zpaqfranz a z:\2.zpaq c:\nz -external "c:\nz\hashdeep64 -r -c sha256 %files"`
- **`-external` Switch in `x` (extract) Command**: Extracts the virtual external file directly.
  - Example: `x z:\2.zpaq -external -silent > mygoodoutput.txt`
- **`-symlink` Switch in `a` (add) Command (Windows)**: Ignores NTFS symlinks during addition.
- **`-touch X` Switch**: Forces a specific timestamp (date or date+time) on files added during the `a` command, including `-stdin`.
- **Execution Dates in Backups**: Stores execution dates in backups; `testbackup` shows the latest date.
- **Franzomips CPU Support**: Added new CPUs to the `franzomips` list.

### Changed
- **Control-C Handling**: Improved cleanup of `-chunk` files and potential `.zpaq` rollback on termination (portability unconfirmed).
- **`gettempdirectory`**: Creates temporary files in timestamped subfolders to avoid collisions with multiple `zpaqfranz` instances.
- **Output with `-big`**: Ensures the final "OK" output remains visible even with reduced verbosity switches.
- **Maximum Versions in `i` Command**: Increased the limit of displayed versions.

### Fixed
- Various minor bugs (unspecified).

### Notes
- This release adds many features tailored to the developer's needs, potentially replicable with tools like `awk` or `grep`, but integrated for convenience in environments lacking such utilities (e.g., ESXi, NAS).
- New features may introduce bugs; users should verify archive integrity after use.
- Report issues or suggestions at [GitHub issues](https://github.com/fcorbelli/zpaqfranz/issues).

## Planned at the time of [60.5]
- Potential `.zpaq` rollback on Control-C termination.
- Future evolution of `-symlink` handling.

---


## [60.5] - 2024-07-20

### Added
- **Faster Windows 64-bit Binary**: Improved performance on AMD CPUs, with average speed gains of 5% and up to 20% in best cases.
  - Example: Compression time reduced from 21.938s (v60.1k) to 18.875s (v60.5d) for identical tasks.
- **`-stat` Switch in `a` (add) Command**: Displays statistics on files added, removed, or updated.
  - Example: `zpaqfranz a z:\test.zpaq c:\zpaqfranz\*.cpp -stat`
- **`-stat` Switch in `i` (info) Command**: Shows uncompressed data size (slower operation).
  - Example: `zpaqfranz i z:\test.zpaq -stat`
- **`-quick` Switch in `t` (test) Command with Paths**: Performs a quick test using only file size and date, skipping hash computation.
  - Example: `zpaqfranz t z:\test.zpaq c:\zpaqfranz\*.cpp -quick`
- **`testbackup` Command Enhancement**: Now displays a global SHA256 hash of backup hashes during verification.
  - Facilitates quick comparison between local and remote backups (e.g., Synology vs. FreeBSD server).
  - Example output shows identical SHA256 (`EDBEE1D3...`) for consistency checks.
  - Full rehashing available with `-verify` for thorough validation.

### Changed
- **`fclose()` De-overloading**: Modified to assist with debugging, reducing potential conflicts.

### Fixed
- **Chunked Add Bug**: Resolved a possible double file close issue in chunked addition operations.

### Notes
- Performance improvements are most notable on Windows 64-bit systems, particularly with AMD CPUs.
- The global SHA256 in `testbackup` provides a fast integrity check; use `-paranoid` or `-verify` for deeper verification, especially if backup paths differ.
- Report bugs or feedback at [GitHub issues](https://github.com/fcorbelli/zpaqfranz/issues).

---

## [60.4] - 2024-07-14

### Added
- **`-nosynology` Switch**: Excludes hidden Synology system folders during the `a` (add) command.
  - Ignores paths like `*/@recycle/*`, `*/#snapshot/*`, `*/@SynologyDrive/*`, etc. (full list in documentation).
- **`isjitable` in `b` (benchmark) Command**: Issues a warning if compiled without `-DNOJIT` but the CPU does not appear to be Intel/AMD (e.g., virtual or ARM CPUs).
  - Enhanced with `-debug` for additional CPU information (e.g., vendor ID, endianness).
  - Examples:
    - `zpaqfranz b` (normal Intel/AMD CPU detection).
    - `zpaqfranz b -debug` (detailed output with warning for non-Intel/AMD CPUs).
- **Celeron J4125 Benchmark**: Added `franzomips` support for Synology DS224+ NAS with Celeron J4125 CPU.

### Fixed
- **Compatibility Fixes**: Resolved issues for "strange" platforms, ensuring compilation and execution on:
  - Haiku
  - Macintosh
  - Solaris

### Notes
- The `-nosynology` switch improves usability on Synology NAS systems by skipping system-specific folders.
- CPU detection in `isjitable` is not fully reliable across all platforms due to portability challenges; future improvements are planned.
- Report bugs or suggestions at [GitHub issues](https://github.com/fcorbelli/zpaqfranz/issues).

---

## [60.3] - 2024-07-07

### Fixed
- **Microfixes for Compilability**: Applied small corrections to ensure compatibility across various systems.
  - Supported builds:
    - `zpaqfranz.exe`: Windows 64-bit
    - `zpaqfranz32.exe`: Windows 32-bit
    - `zpaqfranzhw.exe`: Windows 64-bit with SHA-1 assembly optimizations (AMD)
    - `zpaqfranz_armv8`: ARM-NAS compatible build (e.g., QNAP, Synology)
    - `zpaqfranz_esxi`: ESXi build
    - `zpaqfranz_freebsd`: FreeBSD 64-bit
    - `zpaqfranz_linux32`: Generic Linux 32-bit
    - `zpaqfranz_linux64`: Generic Linux 64-bit
    - `zpaqfranz_nas`: Generic Linux 64-bit for Intel-powered NAS
    - `zpaqfranz_openbsd`: OpenBSD 64-bit
    - `zpaqfranz_haiku`: Haiku 64-bit

### Notes
- No macOS build included in this release ("Sorry, no Mac today 😄").
- These microfixes enhance portability; specific changes are minor and focused on compilation stability.
- Report issues or feedback at [GitHub issues](https://github.com/fcorbelli/zpaqfranz/issues).


---

## [60.2] - 2024-07-03

### Added
- **Improved `dump` Command**: Enhanced to display archive technical details in a more readable format.
  - Shows archive format type and compatibility level:
    - `60+`: zpaqfranz v60 and later (circa July 2024).
    - `<60`: zpaqfranz up to v59.x.
    - `715`: Standard zpaq 7.15 or zpaqfranz with `-715`.
  - Switches:
    - **`-summary`**: Brief output.
    - **`-verbose`**: Detailed useful information.
    - **`-all`**: Deeper technical details.
  - Examples:
    - `zpaqfranz dump z:\715.zpaq -summary`: Identifies as `715 archive (original zpaq format)`.
    - `zpaqfranz dump z:\v59.zpaq -summary`: Shows `<60 archive (older zpaqfranz v59)` with `XXHASH64`.
    - `zpaqfranz dump z:\v60.zpaq -summary`: Shows `60+ archive (newer zpaqfranz v60)` with `XXHASH64B`.
    - `zpaqfranz dump z:\v60_mixed.zpaq -summary`: Detects mixed block sizes (`050`, `190`) and hash types (`WHIRLPOOL`, `XXHASH64B`), warns against `-frugal`.

### Fixed
- **Backup Command Bug**: Prevented creation of unnecessarily large backup files when no files were added.

### Notes
- The `dump` command is a debugging tool, not designed for large (multi-gigabyte) archives; it may crash due to its naive implementation. Future improvements are possible but not prioritized.
- Mixed block sizes/hashes (e.g., `v60_mixed.zpaq`) can cause crashes with `-frugal` unless explicitly managed. Use `-frugal` only if you understand the implications; automatic controls may be added later.

---

## [60.1] - 2024-07-01

### Added
- **New Binary FRANZBLOCK Format**: Smaller storage format for FRANZBLOCKs.
  - Slightly reduces archive size; default is `-xxhash64b`.
  - New switches with `b` suffix (e.g., `-blake3b`); old formats (e.g., `-blake3`) retained.
  - Warning: `-xxhash64b` is default; explicitly specify old formats (e.g., `-xxhash64`) for pre-v60 compatibility.
- **`-frugal` Switch**: Reduces memory usage for large archives (10M–100M files).
  - Risk of crashes if mixing FRANZBLOCK sizes/hashes (e.g., `blake3`, `whirlpool`, `sha3`).
  - Safe with consistent hashes; unnecessary for smaller archives.
- **`-date` Switch**: Stores file creation dates in new format.
  - Default on Windows; optional on *nix with `-date` (slower processing).
  - Uses heuristics for *nix birth dates (accuracy not guaranteed).
- **File Change Tracking**: Stores counts of added, modified, and deleted files per version.
- **Enhanced `l` (list) Command**: Rewritten with richer output.
  - Displays compression ratio, file counts (`+` added, `#` modified, `-` deleted).
  - Auto-resizes columns; uses colors (disabled with `NO_COLOR` or `-nocolor`).
  - Supports `-attr`, `-checksum` (e.g., `-crc32`), `-date`, `-terse`.
  - Slower due to added features; faster version may be considered later.
  - Details: [GitHub #111](https://github.com/fcorbelli/zpaqfranz/issues/111).
- **Backup with `-index`**: Detachable index files for Worm systems.
  - Indexes storable separately (e.g., `-index <path>`); fragile if mismatched.
  - Details: [GitHub #109](https://github.com/fcorbelli/zpaqfranz/issues/109).
- **Enhanced `t` (test) Command**: Supports `-test` with `-find`, `-replace`, `-to`.
  - Enables string substitution during testing; see [GitHub #112](https://github.com/fcorbelli/zpaqfranz/issues/112).
- **`-DNAS` Compilation Switch**: Optimizes memory usage for NAS (e.g., Synology, QNAP).
- **Extended `autotest`**: Enhanced `autotest -all -to <path>`.
  - More tests, including expected failures; requires ~15GB.
  - Tested on Windows, Debian, FreeBSD, QNAP ARM; untested on macOS, Solaris.
  - May produce false positives; runtime varies (minutes to hours on slow NAS).

### Changed
- **Backward Compatibility**: New format readable by zpaq and zpaqfranz ≤ v59 for listing, extraction, and addition.
  - Pre-v60 cannot test CRC32 or read hashes from v60 archives.
  - Use non-`b` switches (e.g., `-xxhash64`) for full v59 compatibility.
- **`l` (list) Command**: Slower due to enhanced features and operations.

### Notes
- This branch introduces new features and potential bugs; use with caution.
- `-frugal` is for advanced users with consistent hashes and massive file counts; avoid mixing hash types.
- ADS management not yet updated for new format; recalculation can be forced.
- Autotest reliability depends on system; feedback encouraged for untested platforms.

---

## [59.9] - 2024-06-22

### Added
- **`-index` for `backup` Command**: Allows storing backup indexes in a separate folder for WORM storage.
  - User must ensure correct file pairing.
  - Example: `zpaqfranz backup z:\pippo *.cpp -index c:\temp`.
- **`-thunderbird` Flag (Windows)**: Automatically includes Thunderbird folders from `AppData\Local` and `AppData\Roaming`.
  - Optionally terminates `thunderbird.exe` before backup with `-kill`.
  - Example: `zpaqfranz a z:\email.zpaq c:\users\utente -thunderbird -kill`.
- **NO_COLOR Support on *nix**: Disables output coloring via shell variable `NO_COLOR`.

### Fixed
- Resolved an error when listing non-standard hashes.

### Notes
- Use `-index` with caution to avoid mismatching indexes and `.zpaq` files.

 ---

## [59.8] - 2024-06-19

### Added
- **`-ifexist <X>` Switch in `a` (add)**: Prevents adding files if folder `X` does not exist.
  - Useful for *nix systems to avoid backups to local disk when external mounts (e.g., NFS) fail.
  - Example: `zpaqfranz a /monta/mygoodnas/thebackup.zpaq /home -ifexist /monta/mygoodnas/rar`.
- **Console Color Support on *nix**: Adds color output to console; intended to work across most *nix systems.
- **`-nocolors` on Redirect**: Automatically disables colors when output is redirected to a file.

### Changed
- **New `l` (list) Format**: Updated display format.
  - Autosizes file size column.
  - Shows estimated compression ratio.
  - Provides enhanced details with `-all`; hides attributes by default.
  - Reverts to old format with `-attr`.
- **Win32/Win64hw Updates**: `zpaqfranz32.exe` (32-bit) and `zpaqfranzhw.exe` (64-bit SHA-1 ASM-accelerated) now support automatic updates via the `upgrade` command.

### Notes
- `-ifexist` helps prevent disk saturation on *nix by checking for sentinel folders (e.g., `/monta/mygoodnas/rar`) on mounted filesystems.
- Visual examples of the new `l` format and `-attr` behavior available in GitHub assets: [Image 1](https://github.com/fcorbelli/zpaqfranz/assets/77727889/df8e60c6-a6a3-4071-93c8-31c9982fb467), [Image 2](https://github.com/fcorbelli/zpaqfranz/assets/77727889/242b07ec-941f-462d-877d-ecd44c17fd11), [Image 3](https://github.com/fcorbelli/zpaqfranz/assets/77727889/3164b036-f779-4be9-be60-cf80b543434c).

---

## [59.7] - 2024-06-06

### Added
- **`zfssize` Command**: Displays the size of ZFS snapshots quickly.
- **`-pause` Switch in `a` (add)**: Pauses the archiver, waiting for a keystroke before proceeding.
- **Runhigh with VSS (Windows)**: Automatically elevates privileges for `-vss` add operations from a non-elevated command line.
- **AMD 3950X Benchmark**: Added performance benchmark for AMD Ryzen 3950X.

### Changed
- **Reduced RAM Usage for File Enumeration**: Now uses ~400 bytes per file on average.
  - Example: ~4GB RAM for 10 million files.
  - Details: [GitHub #104](https://github.com/fcorbelli/zpaqfranz/issues/104).
- **VSS Info Update**: Less alarming messages displayed during Volume Shadow Copy Service (VSS) operations.
- **Compiler Compatibility**: Refactored code for better support with modern compilers and fortification layers.


---

## [59.6] - 2024-05-17

### Fixed
- Minor bugs resolved, including warnings encountered with some cross-compilers.
- Improved Debian compatibility for better integration with Debian-based systems.

### Notes
- Released on a Friday the 17th.

---

## [59.5] - 2024-05-14

### Added
- **`hash` Command**: New simplified command for file hashing.
  - Outputs hashes as computed with alphabetical sorting (unlike `sum` which processes all files first).
  - Supports: `-ssd` (multithread), `-xxh3`, `-sha256`, `-stdout`, `-out <file>`.
  - Examples:
    - `hash z:\knb`: SHA1 of all files.
    - `hash z:\knb -ssd -xxh3`: XXH3 multithreaded.
    - `hash z:\knb -ssd -sha256 -stdout -out 1.txt`: SHA256 to file.
  - Without `-ssd`, hashes are written immediately.
- **`-home` Switch in `s` Command**: Calculates total folder size from depth 1.
  - Useful for sizing `/home`, `/users`, or VM stores.
  - Example: `zpaqfranz s c:\users -home -ignore`.
- **`-orderby` in `hash` Command**: Sorts output (e.g., by size with `-desc`).
  - Example: `zpaqfranz sum * -xxh3 -orderby size -desc`.
- **`-ignore` Switch**: Suppresses error messages (e.g., permission issues) during scanning.
  - Example: `zpaqfranz hash c:\users -ignore` vs. verbose errors with `-ssd`.

### Changed
- **Time Format**: Simplified `timetohuman` output (e.g., `00:00:00` instead of `0:00:00:00`).
- **Speed Units**: Replaced `/sec` with `/s` in speed information.

### Fixed
- Minor issues in `-noeta` switch.
- Improved update command on *nix systems.
  - Provides clearer update availability info (e.g., `Your 59.5h (2024-05-14) is not older...`).

### Notes
- Released version: `zpaqfranz v59.5h-JIT-GUI-L,HW BLAKE3,SHA1/2,SFX64 v55.1`.
- `-ignore` is risky as it hides errors; use cautiously.

---

## [59.4] - 2024-05-11

### Added
- **`crop` Command**: Deletes the latest version(s) from a non-multipart archive.
  - Dry run by default (test only).
  - Switches:
    - **`-kill`**: Performs an effective (wet) run.
    - **`-to <file>`**: Outputs to a new file (e.g., `tiny.zpaq`).
    - **`-until X`**: Discards versions beyond `X`.
    - **`-maxsize X`**: Cuts at size `X` (risky).
    - **`-force`**: Crops in-place without backup (very risky).
  - Examples:
    - `crop z:\1.zpaq`: Dry run info.
    - `crop z:\1.zpaq -to d:\2.zpaq -until 100 -kill`: Reduce to version 100.
    - `crop z:\1.zpaq -to d:\2.zpaq -maxsize 100k -kill`: Reduce to 100,000 bytes.
    - `crop z:\1.zpaq -until 2 -kill -force`: In-place crop to version 2.
- **Range in `l` (list) Command**: Filters files by version range.
  - Syntax:
    - `-range X:Y`: Versions X to Y.
    - `-range X:`: Versions X to last.
    - `-range :X`: Versions 1 to X.
    - `-range X`: Single version X.
    - `-range ::X`: Last X versions.
  - Examples:
    - `l z:\1.zpaq -range 2:3`: Files from versions 2–3.
    - `l z:\1.zpaq -range ::1`: Files from last version.
- **`-sfx` Flag (Win32)**: Creates a self-extracting archive directly.
  - Example: `zpaqfranz a z:\test.zpaq *.cpp -sfx`.
- **`-nomac` Flag**: Skips macOS `.DS_Store`, `Thumbs.db`, and similar files.
- **Cortex `franzomips` Benchmark**: Added benchmark for QNAP low-cost NAS CPUs.
- **`-verbose` in `dump` Command**: Now displays block offsets from file start.

### Changed
- **`c` Command**: Renamed `-verify` switch to `-checksum` to avoid collisions.

### Fixed
- **Backup Command on *nix**: Improved `./` auto-add functionality.
- **VSS Filename Handling (Win32)**: Automatically renames Volume Shadow Copy Service files.

### Notes
- Use `-force` and `-maxsize` in `crop` with caution due to risk of data loss.
- `-nomac` addresses clutter from macOS files on Samba NAS shares.

---

## [59.3] - 2024-04-19

### Added
- **`update`/`upgrade` Command**: Checks for newer zpaqfranz versions across platforms; downloads and updates on Win64.
  - Default source: `http://www.francocorbelli.it/zpaqfranz`.
  - Examples:
    - `zpaqfranz update`: Check for updates (all platforms).
    - `zpaqfranz update -force`: Update if newer (Win64).
    - `zpaqfranz update -force -kill`: Force download (Win64).
    - `zpaqfranz update <hash_url> <exe_url>`: Custom source (e.g., `https://www.pippo.com/ugo.sha256 http://www.pluto.com/zpaqnew.exe`).
- **`download` Command (Win64)**: Downloads files with optional hash verification.
  - Supports MD5/SHA-1/SHA-256; detects hash type by length (32=MD5, 40=SHA-1, 64=SHA-256).
  - Defaults: No overwrite (use `-force`), checks output path (use `-space` to bypass).
  - Examples:
    - `zpaqfranz download https://www.1.it/2.cpp ./2.cpp`: Download to `./2.cpp`.
    - `zpaqfranz download http://www.1.it/3.cpp z:\3.cpp -checktxt http://www.1.it/3.sha256`: Download with SHA-256 check.
    - `zpaqfranz download http://www.francocorbelli.it/zpaqfranz/win64/zpaqfranz.exe ./thenewfile.exe -checktxt http://www.francocorbelli.it/zpaqfranz/win64/zpaqfranz.md5`: Download with MD5 check.
- **Enhanced `ads` Command (Windows)**: Manages Alternate Data Streams (ADS).
  - Options: List (`ads z:\1.zpaq`), remove all (`-kill`), remove specific (`-only <name> -kill`), rebuild (`-force`).
  - Example: `zpaqfranz ads z:\*.zpaq -kill`.
- **`-fasttxt` with ADS**: Stores updated CRC-32 in ADS for archive integrity checks without decryption.
  - Example: `zpaqfranz a z:\pippo.zpaq c:\dropbox -fasttxt -ads -key pippo`, then `zpaqfranz versum z:\pippo.zpaq`.
- **`pause` Command Enhancement**: Waits for a specific keypress.
  - Example: `zpaqfranz pause -find z` (waits for 'z').
- **Updated `franzomips` Benchmark**: Added AMD Ryzen 7950X3D CPU results.

### Fixed
- Improved compatibility and stability for Windows 7 64-bit.

### Notes
- **Security Warning**: Use trusted sources for `update`/`download` (e.g., GitHub, SourceForge, or `https://www.francocorbelli.it/zpaqfranz/win64/`).
- `ads` command is under development; expect further refinements.
- `-fasttxt` enables fast integrity checks (e.g., >2GB/s on NVMe) without needing encryption keys; Samba/PAKKA integration in progress.
- `franzomips` disables HW-acceleration by default; use specific flags (e.g., `-sha256`) for HW benchmarks.

---

## [59.2] - 2024-02-23

### Added
- **`pakka` Command**: Integrates with PAKKA, a Windows GUI for zpaqfranz.
  - Supports newer PAKKA versions without requiring `zpaqlist`.
  - Features in development: file addition, testing, and full functionality beyond extraction.
  - Examples:
    - `zpaqfranz pakka h:\zarc\1.zpaq -out z:\default.txt`: Lists to file.
    - `zpaqfranz pakka h:\zarc\1.zpaq -all -distinct -out z:\default.txt`: Lists without deduplication.
    - `zpaqfranz pakka h:\zarc\1.zpaq -until 10 -out z:\10.txt`: Lists up to version 10.

### Fixed
- Minor unspecified issues.

### Notes
- PAKKA is a freeware Windows GUI available at [https://www.francocorbelli.it/pakka/build/latest/pakka_latest.zip](https://www.francocorbelli.it/pakka/build/latest/pakka_latest.zip) with built-in auto-update functionality.
- Ongoing development includes online help and ADS (Alternate Data Stream) support for small NAS systems like TrueNAS.
- PAKKA, written in Delphi, evolves faster than zpaqfranz core.

---
## [59.1] - 2024-01-16

### Added
- **`-chunk` Switch in `a` (add)**: Creates fixed-size multipart archives.
  - Supports sizes: raw numbers (e.g., `2000000`), `K`/`M`/`G`, `KB`/`MB`/`GB` (e.g., `-chunk 1G`, `-chunk 500MB`).
  - Chunks approximate multiples of 64KB; not fully integrated (e.g., unsupported in `backup`).
  - Examples:
    - `zpaqfranz a z:\ronko_?? whatever-you-like -chunk 1G`.
    - `zpaqfranz a z:\ronko_?? who-knows -chunk 500m`.
- **ADS Filelists (Windows, NTFS)**: Stores file lists in Alternate Data Streams for unencrypted archives.
  - Uses LZ4 compression for speed and chunked storage.
  - Example: `zpaqfranz a z:\1.zpaq *.cpp -ads`, then `zpaqfranz l z:\1.zpaq`.
  - Force standard listing: `zpaqfranz l z:\1.zpaq -ads`.
- **`ads` Command (Windows)**: Manipulates ADS filelists.
  - Show: `ads z:\1.zpaq`.
  - Rebuild: `ads z:\1.zpaq -force`.
  - Remove: `ads z:\*.zpaq -kill`.
- **`-fast` Switch in `a` (add)**: Experimental feature to store a partial file list in the archive.
  - Aims for faster extraction; maintains compatibility with zpaq 7.15.
  - Example: `zpaqfranz a z:\1.zpaq c:\dropbox -fast`, then `zpaqfranz l z:\1.zpaq` (auto-detects `-fast`, else `-fast` to force).
- **Console Colors (Windows)**: Limited color support for black-background consoles.
  - Disabled with `NO_COLOR` env variable or `-nocolor` switch.
- **Debug Switches**: Enhanced debugging options.
  - `-debug`, `-debug2`, `-debug3`: Increasing verbosity.
  - `-debug4`: Writes debug files to `z:\` if available.
- **`-longpath` for Files**: Rudimentary support for individual files >255 characters on Windows.
  - Uses `GetFinalPathNameByHandleW` from `KERNEL32.DLL`.
  - Details: [GitHub #90](https://github.com/fcorbelli/zpaqfranz/issues/90).

### Changed
- **Password Prompt**: Unified at the file-handling class level.
  - Applies to all commands (e.g., `dump`); prompts if `-key` omitted, avoiding command history exposure.

### Notes
- This is a new branch with untested features; bugs are expected—report them at [GitHub Issues](https://github.com/fcorbelli/zpaqfranz/issues).
- `-chunk` aims for optical media compatibility (e.g., Blu-ray); Ctrl+C handling and part estimation are incomplete.
- ADS with LZ4 enables potential filesystem mounting in future; encryption support untested.
- `-fast` is experimental and currently provides minimal utility; full implementation is complex.
- Color support on *nix is under consideration but challenging due to interoperability.
- Additional discussions: [Color Support](https://encode.su/threads/4182-Color-or-not), [Format Hacking](https://encode.su/threads/4178-hacking-zpaq-file-format-(!)), [Data Storage](https://encode.su/threads/4168-Virus-like-data-storage-(!)).

---
 
## [58.12.s] - 2023-12-08

### Changed
- Improved execution speed and deduplication (`redup`).
- Utilizes point-in-time copy mechanisms (e.g., hourly snapshots), eliminating the need to scan the entire filesystem.
- Previously, ZFS backup support operated at the block level, requiring full restoration to recover individual files. The new `-dataset` switch enables efficient file-level updates by leveraging ZFS snapshots.
- Ideal for large fileservers or systems with magnetic disks where filesystem scans are slow (e.g., tar, 7z, srep, etc.).

### Performance Example
- For a mid-sized file server with 1M files:
- Spinning drives: ~500 files/sec → ~30 minutes just to enumerate files.
- SSDs: ~5K files/sec.
- NVMe: ~30K files/sec.
- Traditional tools require full enumeration before processing, making frequent backups (e.g., every 10 minutes) impractical.
- With `-dataset`, `zpaqfranz` uses ZFS snapshots to identify changes instantly, enabling rapid updates.

### How It Works
- On first run: Creates a base snapshot (e.g., `tank/d@franco_base`).
- Subsequent runs: Generates a temporary snapshot (e.g., `tank/d@franco_diff`), compares it with the base, and processes only changed files.
- Example output:
---


## [58.11.s] - 2023-11-10

## Big "news": Developing (underway) to handle SHA-1 collisions
- Work in progress to address SHA-1 collision handling in `zpaqfranz`.

### Disclaimer: Is this a real issue? Can my backups become broken?
- SHA-1 collisions have been demonstrated in controlled lab environments, but in real-world scenarios, they are extremely unlikely (bordering on impossible).
- Backups made with `zpaqfranz` are considered safe. The `t` command has included collision detection for years, ensuring archive integrity.
- The new `collision` command offers a faster collision-specific test compared to the comprehensive `t` command, which also checks file integrity.
- Paranoid-level commands and switches are available for extra caution.
- Maintaining backward compatibility with `zpaq 7.15` remains a significant challenge.

## New switch `-collision` in add
- `zpaqfranz` can now recover from SHA-1 collisions within the current archive version, ensuring correct file extraction for paranoid users.

### Collision-aware `zpaqfranz` in action: Detecting and fixing
#### Older `zpaqfranz` (default behavior):
- No collision detection by default:

---


## [58.10] - 2023-09-21

## New `-home` switch for add
- Enables archiving different folders into separate `.zpaq` files, useful for splitting individual users (e.g., within `/home` or `c:\users`) into distinct archives.
- Examples:
```
  zpaqfranz a z:\utenti.zpaq c:\users -home
  zpaqfranz a /temp/test1 /home -home -not franco
  zpaqfranz a /temp/test2 /home -home -only "*SARA" -only "*NERI"
```

## Support for selections in `r` (robocopy) command
- File selection now mirrors the `add` command functionality.
- Examples:
```
  zpaqfranz r c:\d0 z:\dest -kill -minsize 10GB
  zpaqfranz r c:\d0 z:\dest -kill -only *.e01 -only *.zip
```

## Fixes and Improvements
### Fix for Mac PowerPC
- Added support for compiling `zpaqfranz` on PowerPC Macs.

### Improved compatibility with ancient compilers on Slackware
- Enhanced support for very old GCC versions commonly used in Slackware.

### Workaround for buggy GCC versions
- Addressed issues in newer GCC releases.

### Refactoring
- Codebase cleaned up for better maintainability, though slightly slower.

## Variable Replacements
### Replaced `$` with `%` in variables
- Linux scripts do not handle `$` well, so variables now use `%`.
- Supported variables:
- `%hour`
- `%min`
- `%sec`
- `%weekday`
- `%year`
- `%month`
- `%day`
- `%week`
- `%timestamp`
- `%datetime`
- `%date`
- `%time`
- Example:
```
  zpaqfranz r c:\d0 z:\backup_%day -kill
```

## Enhanced `-orderby` switch in `add`
- Examples:
```
  zpaqfranz a z:\test.txt c:\dropbox -orderby ext;name
  zpaqfranz a z:\test.txt c:\dropbox -orderby size -desc
```

## Filecopy with variable buffer size (`-buffer`)
- Added for testing across different platforms.

## Updated `versum` command
- Now processes only files starting with `|`.

## New Disclaimer After Help
- Added reminder to use double quotes for arguments:
```
  ************ REMEMBER TO USE DOUBLE QUOTES! ************
  *** -not .cpp    is bad,    -not ".cpp"    is good ***
  *** test_???.zpaq is bad,    "test_???.zpaq" is good ***
```



## [55.6] - 2022-07-26

### Added
- **HW-Accelerated SHA1 (Windows 64)**: New executable `zpaqfranzhw.exe` with `-hw` switch.
  - Utilizes CPU SHA1 instructions (common on AMD Ryzen since 2017; limited Intel support).
  - Modest performance gain; requires `-hw` on supported CPUs.
- **Advanced Error Reporting (Windows)**: Filesystem errors logged after `add()`.
  - Brief output with `-verbose`; detailed with `-debug`.
  - Example:
    - `-verbose`: `Error 00000032 #1 |sharing violation|`
    - `-debug`: Includes file attributes (e.g., `c:/pagefile.sys>> ARCHIVE;HIDDEN;SYSTEM;`).
- **Refactored Help**: Improved readability and conciseness.
  - "No command" output tightened.
  - Help accessible via `/?`, `h`, or `-h`.
- **C: Drive Backup Commands (`g` and `q`)**: Refined with default exclusions:
  - `c:\windows`, `RECYCLE BIN`, `%TEMP%`, `ADS`, `.zfs`, `pagefile.sys`, `swapfile.sys`, `System Volume Information`, `WindowsApps`.
  - Switches:
    - `-frugal`: Excludes `Program Files` and `Program Files (x86)`.
    - `-forcewindows`: Includes `C:\WINDOWS`, `$RECYCLE.BIN`, `%TEMP%`, `ADS`, `.zfs`.
    - `-all`: Includes all except `pagefile.sys`, `swapfile.sys`, `System Volume Information`, `WindowsApps`.
- **Reparse Point Support**: Initial implementation for handling Windows special files (e.g., in `WindowsApps`).

---

## [55.4] - 2022-07-20

### Added
- **`q` (paQQa) Command (Windows)**: Archives C: drive with exclusions (`swap files`, `System Volume Information`, `Windows`).
  - Requires admin rights; deletes pre-existing VSS; creates `C:\FRANZSNAP`.
  - Example: `zpaqfranz q z:\pippo.zpaq -only *.cpp -key mightypassword`.
  - Supports most `add()` switches except `-to`.
  - `-forcewindows`: Adds `c:\windows`, `%TEMP%`, `ADS`.

### Notes
- Not a bare-metal backup; optimized for fast snapshot archiving (~2 minutes for 200GB on test PC).
- Some folders (e.g., Windows Defender) inaccessible; under investigation.

---

## [55.2] - 2022-07-16

### Changed
- **`r` (robocopy) Command**: Tentative `-longpath` support on Windows (use with caution).
- Source code converted to Unix text format (no CR/LF) for compatibility with old `make` systems.

### Fixed
- Minor help text corrections.

---

## [55.2] - 2022-07-15

### Added
- **`-touch` Switch in `a` (add)**: Forces timestamp changes to convert zpaq 7.15 archives to zpaqfranz format in-place.
  - Example: `zpaqfranz a z:\1.zpaq c:\nz\ -touch` then `zpaqfranz a z:\1.zpaq c:\nz\`.

### Changed
- Improved ETA computation accuracy.
- Enhanced `-verify` handling for legacy zpaq 7.15 archives.
- **`-verbose`**: Shows progress for files >100MB (10%) or >1GB (1%).

### Notes
- Addresses lack of feedback during large file updates (e.g., virtual disks).

---

## [55.1] - 2022-07-09

### Added
- **OpenBSD 6.6+ and OmniOS Support**: Compilation support added.
- **SFX Module Update (Windows)**: Prompts for extraction location if `-to` omitted.
- **`-flagflat`**: Uses mime64-encoded filenames for NTFS reserved word issues.
- **`-fixcase` and `-fixreserved` (Windows)**: Handles case collisions and reserved filenames.
- **`-ssd`**: Replaces `-all` for multithread computation.
- **`d` Command**: Supports various hashes (e.g., `-blake3`).
  - Example: `zpaqfranz d c:\dropbox\ -ssd -blake3`.
- **`dir` Command**: Hash-based duplicate detection.
  - Example: `zpaqfranz dir c:\dropbox\ /s -checksum -blake3`.
- **`a` (add) Debug Switches**:
  - `-debug -zero`: Adds zero-filled files.
  - `-debug -zero -kill`: Adds 0-byte files for debugging.
- **`i` (info)**: ~30% faster; `-stat` shows collision stats.
- **`rd` Command (Windows)**: Deletes stubborn folders.
  - Switches: `-force`, `-kill`, `-space`.
- **`w` Command**: Chunked extraction/testing to disk or RAM.
  - Scenarios:
    1. HDD extraction: `zpaqfranz w z:\1.zpaq -to p:\muz7\ -ramdisk -longpath`.
    2. Hash checking: `zpaqfranz w z:\1.zpaq -ramdisk -test -checksum -ssd -frugal -verbose`.
    3. Large archive check: `zpaqfranz w z:\1.zpaq -to z:\muz7\ -paranoid -verify -verbose -longpath`.
    4. SSD/RAM check: `zpaqfranz w z:\1.zpaq -to z:\kajo -ramdisk -paranoid -verify -checksum -longpath -ssd`.
  - Switches: `-maxsize`, `-ramdisk`, `-frugal`, `-ssd`, `-test`, `-verbose`, `-checksum`, `-verify`, `-paranoid`.

### Changed
- Reduced execution output; controlled with `-noeta`, `-pakka`, `-summary` (less) or `-verbose`, `-debug` (more).
- **`dir` Command**: Defaults to European date format (e.g., `25/12/2022`).
- Disabled slow checks; re-enabled with `-stat`.

### Notes
- Primarily tested on Windows; BSD/Linux focus planned for 55.2+.
- `w` command designed for large archives and HDDs; requires empty `-to` folder.

---

## [54.10] - 2021-12-20

### Added
- Media full check.
- `franzomips` support.
- **`-checksum` in `t` (test)**.

---

## [54.9] - 2021-11-04



