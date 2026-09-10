#!/bin/bash
export SUITE=core
source /mnt/IA_LAB/agentes/ZPAQ-STD/testlab/harness.sh
CASES="text bin precomp img edge intl mixed"
ALGOS="lz4 lz4hc lz4f zstd flzma2 lz5 lz5hc lz5f lizard bzip2 bzip3 brotli snappy deflate lz lzav hs lzfse bsc lzh ppmd"

echo "### A: los 21 codecs -ma (nivel default) x $CASES"
for a in $ALGOS; do for c in $CASES; do run A "$c" "-ma:$a" "ma:$a"; done; done

echo "### B: -m0..-m5 nativos"
for m in 0 1 2 3 4 5; do for c in $CASES; do run B "$c" "-m$m" "m$m"; done; done

echo "### C: barrido de niveles (los extremos de cada codec)"
for spec in zstd:1 zstd:19 zstd:22 flzma2:1 flzma2:10 brotli:1 brotli:11 lizard:10 lizard:49 \
            bzip2:1 bzip2:9 bzip3:1 bzip3:9 ppmd:2 ppmd:15 ppmd:32 deflate:1 deflate:12 \
            lzh:1 lzh:4 bsc:1 bsc:9 hs:0 hs:1 hs:2 lzav:0 lzav:1 lzfse:0 lz:1 lz:9 \
            snappy:1 snappy:2 lz4:1 lz4:4 lz4:12 lz5:1 lz5:15; do
  for c in text bin; do run C "$c" "-ma:$spec" "ma:$spec"; done
done
echo DONE_CORE
