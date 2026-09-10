#!/bin/bash
export SUITE=flags
source /mnt/IA_LAB/agentes/ZPAQ-STD/testlab/harness.sh

echo "### D: flags de 'a' (esta vez NO se pasan a t/x)"
for f in "-nodedup" "-store" "-checksum" "-nochecksum" "-715" \
         "-sha256" "-blake3" "-sha3" "-md5" "-whirlpool" "-xxh3" "-crc32" "-xxhash" \
         "-fragment 4" "-fragment 64" "-fragment 128" \
         "-t 1" "-t 2" "-t 8" "-t 16" "-t1" "-threads 4" \
         "-m 5" "-method 3" "-nosort" "-noeta" "-touch" "-append" "-test" "-verify"; do
  for c in text edge; do run D "$c" "$f" "$f"; done
done

echo "### D2: flags que cambian el layout (solo round-trip, sin diff)"
# -minsize sobre intl (20 bytes en total) filtraria TODO: se usa un umbral
# que deja algo en cada caso
for f in "-nopath" "-norecursion" "-minsize 1" "-maxsize 100000" "-flat"; do
  for c in text intl; do run D2 "$c" "$f" "$f" "nodiff:$f"; done
done

echo "### E: cifrado x codecs"
for f in "-m1 -key Secreta123" "-m3 -key Secreta123" "-m5 -key Secreta123" \
         "-ma:zstd -key Secreta123" "-ma:flzma2 -key Secreta123" "-ma:ppmd -key Secreta123" \
         "-ma:bsc -key Secreta123" "-store -key Secreta123" "-m4 -key Secreta123 -t 4"; do
  for c in text intl mixed; do run E "$c" "$f" "$f"; done
done

echo "### F: datos pesados / muchos archivos / duplicados / sparse"
for m in "-m1" "-m3" "-m5" "-ma:zstd" "-ma:flzma2" "-ma:ppmd" "-ma:bsc" "-ma:lzh" "-ma:brotli"; do
  run F bigtext "$m" "$m"
done
for m in "-m1" "-m3" "-m5" "-ma:zstd"; do
  run F many "$m" "$m"
  run F dupes "$m" "$m"
done
for m in "-m1" "-m5" "-store"; do run F sparse "$m" "$m"; done
echo DONE_FLAGS
