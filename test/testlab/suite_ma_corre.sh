#!/bin/bash
# ============================================================================
# suite_ma_corre.sh -- cada codec -ma tiene que CORRER, no solo ser reversible.
#
# POR QUE EXISTE: -ma:bzip3 no comprimio NUNCA, desde el commit inicial, y
# suite_core lo daba verde en sus 263 casos. Un codec que no hace nada pasa
# todas las pruebas de ida y vuelta, porque guardar el bloque en nativo tambien
# es reversible. El bug estaba en un "size_t bz3out=0" que libbz3 lee como
# capacidad del buffer: bz3_compress fallaba siempre y el bloque caia al
# metodo nativo sin avisar.
#
# Lo que mide: sobre texto compresible, cada uno de los 21 switches tiene que
# (1) dejar su comentario zpaqstd-ma:<algo>: en el archivo -- prueba de que el
# codec escribio el bloque -- y (2) volver con los bytes exactos.
#
#   uso: suite_ma_corre.sh          (usa Z=... o el binario del repo)
# ============================================================================
set -u
Z=${Z:-/home/forum/git/zpaq-std/zpaq-std}
W=/mnt/IA_LAB/agentes/ZPAQ-STD/testlab
RUN=${RUN:-ma_corre}
OUT=$W/$RUN; rm -rf "$OUT"; mkdir -p "$OUT/src"
CSV=$OUT/ma_corre.csv
echo "codec,marca,ida_vuelta,zpaq715,resultado" > "$CSV"
# texto compresible, sin aleatorio: cualquier codec tiene que ganarle al original
python3 -c "
import random; random.seed(11); w='alfa beta gamma delta epsilon zeta eta theta iota kappa'.split()
open('$OUT/src/t.txt','w').write(' '.join(random.choice(w) for _ in range(120000)))"
REF=$(sha256sum < "$OUT/src/t.txt" | cut -d' ' -f1)
ALGOS="lz4 lz4hc lz4f zstd flzma2 lz5 lz5hc lz5f lizard bzip2 bzip3 brotli snappy deflate lz lzav hs lzfse bsc lzh ppmd"
malos=0
for a in $ALGOS; do
  arch=$OUT/$a.zpaq; rm -f "$arch"
  timeout 300 "$Z" a "$arch" "$OUT/src" -t1 -ma:$a </dev/null >/dev/null 2>&1
  # "zpaqstd-ma2:" = bloque que lleva su propio decodificador ZPAQL (ZPAQLZ5)
  n=$(strings -a "$arch" 2>/dev/null | grep -cE "zpaqstd-ma2?:$a:")
  rm -rf "$OUT/o"; mkdir -p "$OUT/o"
  timeout 300 "$Z" x "$arch" -to "$OUT/o" -force </dev/null >/dev/null 2>&1
  g=$(find "$OUT/o" -type f -name t.txt -print -quit)
  iv=FALLA; [ -n "$g" ] && [ "$(sha256sum < "$g" | cut -d' ' -f1)" = "$REF" ] && iv=OK
  if [ "$n" -gt 0 ] && [ "$iv" = OK ]; then r=OK
  elif [ "$n" -eq 0 ]; then r=NO-CORRE; malos=$((malos+1))
  else r=FALLA; malos=$((malos+1)); fi
  # Los -ma:lz5 llevan su decodificador ZPAQL: zpaq 7.15 TIENE que extraerlos.
  # Si esto falla, se rompio la portabilidad de ZPAQLZ5 (el programa embebido, el
  # SHA-1 del original en el segmento, o el tamano original en el comentario).
  z715="-"
  case "$a" in lz5|lz5hc|lz5f)
    if command -v zpaq >/dev/null 2>&1; then
      rm -rf "$OUT/o715"; mkdir -p "$OUT/o715"
      timeout 300 zpaq x "$arch" -to "$OUT/o715/" -force </dev/null >/dev/null 2>&1
      g7=$(find "$OUT/o715" -type f -name t.txt -print -quit)
      z715=FALLA; [ -n "$g7" ] && [ "$(sha256sum < "$g7" | cut -d' ' -f1)" = "$REF" ] && z715=OK
      [ "$z715" = OK ] || { r=NO-PORTABLE; malos=$((malos+1)); }
    fi ;;
  esac
  printf '  %-8s marca=%-2s ida_vuelta=%-5s zpaq715=%-5s %s\n' "$a" "$n" "$iv" "$z715" "$r"
  echo "$a,$n,$iv,$z715,$r" >> "$CSV"
done
echo "--- 21 codecs, $((21-malos)) corren y vuelven, $malos a revisar ---"
echo DONE_MA_CORRE
