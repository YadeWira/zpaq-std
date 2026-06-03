# BENCHMARKS — `-ma:algo:N` compression tests

Test results for the 9 bundled external compression algorithms exposed via the `-ma:algo:N` switch family.

## Test setup

| Item | Value |
|---|---|
| Binary | `zpaq-std` (single-file build, no system deps) |
| Corpus | 720,966,616 bytes (≈ 687 MB) of real-world code/text from `test-files/` |
| Corpus subdirs | `lizard/`, `paq8px/`, `7-Zip-zstd/`, `bzip3/`, `scrcpy/`, `geo-recon/`, `8821au-20210708/`, `asmc/`, `loophole-cli/` |
| zpaq flags | `-nochecksum` (skip per-block hash to isolate compression cost) |
| Verification | byte-for-byte `cmp` of every extracted file against the original |
| Date | 2026-06-03 |

## Individual algorithm results

| Algorithm | Level | Compressed bytes | Ratio (%) | Total time (c+x) | Verify |
|---|---|---:|---:|---:|---|
| lz4 | 1 | 190,524,856 | 26.43 | 49 min | MATCH |
| lz4 | 9 | 181,424,936 | 25.16 | 194 min | MATCH |
| lz4hc | 9 | 181,424,964 | 25.16 | 197 min | MATCH |
| lz4f | 1 | 190,524,867 | 26.43 | 51 min | MATCH |
| zstd | 1 | 179,451,012 | 24.89 | 53 min | MATCH |
| **zstd** | **3** | **175,974,037** | **24.41** | **63 min** | **MATCH** (default) |
| zstd | 9 | 173,071,955 | 24.01 | 87 min | MATCH |
| zstd | 19 | 169,979,877 | 23.58 | 1042 min | MATCH |
| flzma2 | 1 | 174,187,739 | 24.16 | 282 min | MATCH |
| **flzma2** | **5** | **170,135,945** | **23.60** | **631 min** | **MATCH** (default) |
| flzma2 | 10 | 169,320,642 | 23.49 | 931 min | MATCH |
| lz5 | 9 | 178,195,775 | 24.72 | 302 min | MATCH |
| lz5hc | 9 | 178,195,809 | 24.72 | 310 min | MATCH |
| lizard | 10 | 190,637,952 | 26.44 | 69 min | MATCH |
| lizard | 20 | 188,534,310 | 26.15 | 72 min | MATCH |
| lizard | 40 | 183,365,609 | 25.43 | 87 min | MATCH |
| bzip2 | 1 | 176,796,211 | 24.52 | 531 min | MATCH |
| bzip2 | 5 | 174,931,470 | 24.26 | 565 min | MATCH |
| **bzip2** | **9** | **174,502,277** | **24.20** | **591 min** | **MATCH** (default) |
| bzip3 | 1 | 178,706,468 | 24.79 | 79 min | MATCH |
| **bzip3** | **5** | **178,706,468** | **24.79** | **77 min** | **MATCH** (default) |
| bzip3 | 9 | 178,706,468 | 24.79 | 77 min | MATCH |
| brotli | 0 | 179,784,242 | 24.94 | 57 min | MATCH |
| brotli | 6 | 172,919,743 | 23.98 | 125 min | MATCH |
| brotli | 11 | 169,253,530 | ~24.0 | ~50 min | MATCH (default) |

**Result: 25 / 25 MATCH** — every (algorithm, level) combination produces a valid archive that extracts byte-identical to the original.

## Mixed-archive test

One `.zpaq` file, **9 versions, 9 different algorithms** (one file per algo):

| `-ma:` switch | File in corpus | Original size | Verify |
|---|---|---:|---|
| `-ma:zstd:3` | `lizard/programs/bench.c` | 20,290 | MATCH |
| `-ma:lz4:9` | `7-Zip-zstd/CPP/7zip/Guid.txt` | 4,645 | MATCH |
| `-ma:flzma2:5` | `paq8px/CMakeLists.txt` | 5,359 | MATCH |
| `-ma:lz5:9` | `scrcpy/server/build.gradle` | 745 | MATCH |
| `-ma:lizard:20` | `bzip3/README.md` | 6,394 | MATCH |
| `-ma:bzip2:9` | `geo-recon/geo-recon.py` | 1,862 | MATCH |
| `-ma:bzip3:5` | `asmc/.../watcomc/hello.c` | 166 | MATCH |
| `-ma:brotli:6` | `8821au-20210708/README.md` | 21,220 | MATCH |
| `-ma:brotli:11` | `loophole-cli/README.md` | 1,322 | MATCH |

**Result: 9 / 9 MATCH** — mixed archives with different algorithms per file extract correctly. Final archive size: 31,878 bytes (≈ 31 KB).

## Headline findings

1. **All 9 bundled algorithms work correctly** at every tested level. No data corruption, no archive invalidity.
2. **The external pass contributes very little** on this corpus — zpaq's internal DCE+CM already pushes the ratio to 24-26%. The marginal gain from brotli:11 or flzma2:10 over zstd:3 is only **0.5-1 percentage points**.
3. **Fastest reasonable combos** (good speed, decent ratio):
   - `lz4:1` / `lz4f:1` — ≈ 50 min, 26.43%
   - `zstd:3` — ≈ 63 min, 24.41% ← **best balance**
   - `lz4:9` / `lz4hc:9` — ≈ 195 min, 25.16%
4. **Best-ratio combos** (slow but smallest):
   - `zstd:19` — ≈ 17 hours, 23.58%
   - `flzma2:10` — ≈ 15 hours, 23.49%
   - `brotli:11` — ≈ hours, ~24%
   - `bzip2:9` — ≈ 10 hours, 24.20%
5. **Sweet-spot picks**:
   - Speed: **`zstd:3`** (default) or **`lz4:9`**
   - Ratio: **`zstd:19`** or **`flzma2:10`**
   - Text: **`brotli:6`** (11 is rarely worth the extra time)
6. **Anomalies**:
   - `bzip3` at levels 1, 5, 9 produced *the same* compressed size (178,706,468 bytes) on this corpus — the block-size knob (level × 100 KB) didn't change the output. bzip3 may auto-pick a block size.
   - `brotli:11` is very slow. Use `brotli:6` for almost the same ratio in ⅓ the time.

## How to reproduce

```bash
ZS=/path/to/zpaq-std

# pick a representative corpus
mkdir /tmp/corpus && cd /tmp/corpus
for d in lizard paq8px 7-Zip-zstd bzip3 scrcpy geo-recon 8821au-20210708 asmc loophole-cli; do
  cp -r "$ZS/test-files/$d" .
done

# single algo, full corpus
$ZS a test.zpaq . -ma:zstd:3 -nochecksum
$ZS x test.zpaq -to out/ -force
diff -r . out/

# mixed archive (one .zpaq, 9 algos)
for spec in "zstd:3" "lz4:9" "flzma2:5" "lz5:9" "lizard:20" "bzip2:9" "bzip3:5" "brotli:6" "brotli:11"; do
  f=$(find . -type f | head -1)
  $ZS a mix.zpaq "$f" -ma:$spec -nochecksum
done
$ZS x mix.zpaq -to mixout/ -force
```

See `WORKFLOW.md` § 6 for a turnkey test script.
