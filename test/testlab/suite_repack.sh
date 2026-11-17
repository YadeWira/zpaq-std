#!/bin/bash
# suite_repack.sh: repack reads what zpaq-std itself writes. A -ma block's comment carries the
# codec's tag between the size and jDC, and a -sa block holds several segments; repack refused
# both up to 2.13.1 (03776, BUG-044). Each archive (two versions) is repacked, the result tested
# and extracted by zpaq 7.15 and compared with the source.
#   Z=<zpaq-std> [XC=<dir with pja.so/ppa.so>] [RUN=<name>] bash suite_repack.sh
set -u; export LC_ALL=C
Z=${Z:?Z=the zpaq-std to test}
T=/mnt/IA_LAB/agentes/ZPAQ-STD/testlab; OUT=$T/${RUN:-zf_repack}; rm -rf "$OUT"; mkdir -p "$OUT/src" "$OUT/bin/codecs"
cp "$Z" "$OUT/bin/zpaq-std"; [ -n "${XC:-}" ] && cp "$XC"/*.so "$OUT/bin/codecs/" 2>/dev/null
B=$OUT/bin/zpaq-std
python3 -c "
import random; random.seed(7); w='uno dos tres cuatro cinco seis siete ocho nueve diez'.split()
open('$OUT/src/t.txt','w').write(' '.join(random.choice(w) for _ in range(60000)))
open('$OUT/src/b.bin','wb').write(bytes(random.getrandbits(8) for _ in range(40000)) + b'abcd' * 20000)"
casos=0; bien=0
uno() { # name, source dir, switches...
  local n=$1 src=$2; shift 2; casos=$((casos+1))
  local a=$OUT/$n.zpaq r=$OUT/$n.r.zpaq
  ( cd "$(dirname "$src")" && "$B" a "$a" "$(basename "$src")" "$@" -timestamp 2026-01-01_00:00:00 </dev/null >/dev/null 2>&1
    printf 'second version\n' > "$src/v2.tmp"; "$B" a "$a" "$(basename "$src")" "$@" -timestamp 2026-01-02_00:00:00 </dev/null >/dev/null 2>&1; rm -f "$src/v2.tmp" )
  "$B" repack "$a" -all -to "$r" </dev/null > "$OUT/$n.log" 2>&1; local rc=$?
  local t=- v=FALLA
  if [ -f "$r" ]; then "$B" t "$r" </dev/null >/dev/null 2>&1; t=$?
    rm -rf "$OUT/o"; mkdir -p "$OUT/o"; zpaq x "$r" -to "$OUT/o/" -until 1 -force </dev/null >/dev/null 2>&1
    diff -r "$src" "$(find "$OUT/o" -type d -name "$(basename "$src")" | head -1)" >/dev/null 2>&1 && v=OK; fi
  if [ $rc = 0 ] && [ "$t" = 0 ] && [ $v = OK ]; then bien=$((bien+1)); echo "  $n: OK"; else echo "  $n: A REVISAR repack rc=$rc t=$t zpaq715=$v $(grep -a '^[0-9]*!' "$OUT/$n.log" | head -1 | cut -c1-100)"; fi
}
for m in -m1 -m3 -ma:lz4 -ma:zstd -ma:lzma -ma:flzma2 -ma:ppmd -ma:ppmd:8:128 -ma:bsc -ma:bsc:10 -ma:kanzi:5 -ma:brotli -ma:zxc -ma:lz6 -ma:bzip3 -ma:lzh -ma:deflate; do
  uno "$(echo "$m" | tr -d ':-')" "$OUT/src" $m
done
if [ -f "$OUT/bin/codecs/ppa.so" ] && [ -d /mnt/IA_LAB/agentes/ZPAQ-STD/int/ppa2100/png ]; then
  cp -r /mnt/IA_LAB/agentes/ZPAQ-STD/int/ppa2100/png "$OUT/png"; uno sa_png "$OUT/png" -sa
fi
if [ -f "$OUT/bin/codecs/pja.so" ] && [ -n "${JPG:-}" ] && [ -d "$JPG" ]; then
  cp -r "$JPG" "$OUT/jpg"; uno sa_jpg "$OUT/jpg" -sa
fi
echo "--- $casos casos, $bien bien, $((casos-bien)) a revisar ---"
echo DONE_REPACK
