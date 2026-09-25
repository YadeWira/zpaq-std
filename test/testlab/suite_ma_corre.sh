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
# Lo que mide: sobre texto compresible, cada switch (lizard:45 = los niveles con
# Huffman, ZPAQLIZARDH, que el nivel por defecto no toca) tiene que
# (1) dejar su comentario zpaqstd-ma:<algo>: en el archivo -- prueba de que el
# codec escribio el bloque -- y (2) volver con los bytes exactos. Ademas, (3)
# -turbo (add2, la copia de upstream de add) tiene que dar el MISMO archivo byte
# a byte: hasta 65.3y-pre33 add2 no tenia ninguna rama -ma.
#
#   uso: suite_ma_corre.sh          (usa Z=... o el binario del repo)
# ============================================================================
set -u
Z=${Z:-/home/forum/git/zpaq-std/zpaq-std}
W=/mnt/IA_LAB/agentes/ZPAQ-STD/testlab
RUN=${RUN:-ma_corre}
OUT=$W/$RUN; rm -rf "$OUT"; mkdir -p "$OUT/src"
CSV=$OUT/ma_corre.csv
echo "codec,marca,ida_vuelta,zpaq715,turbo,resultado" > "$CSV"
# texto compresible, sin aleatorio: cualquier codec tiene que ganarle al original
python3 -c "
import random; random.seed(11); w='alfa beta gamma delta epsilon zeta eta theta iota kappa'.split()
open('$OUT/src/t.txt','w').write(' '.join(random.choice(w) for _ in range(120000)))"
REF=$(sha256sum < "$OUT/src/t.txt" | cut -d' ' -f1)
ALGOS="lz4 lz4hc lz4f zstd flzma2 lz5 lz5hc lz5f lz6 lzma lizard lizard:45 bzip2 bzip3 brotli snappy deflate lz lzav hs lzfse bsc lzh ppmd"
malos=0
for a in $ALGOS; do
  arch=$OUT/$a.zpaq; rm -f "$arch"
  timeout 300 "$Z" a "$arch" "$OUT/src" -t1 -ma:$a -timestamp 2026-01-01_00:00:00 </dev/null >/dev/null 2>&1
  # "zpaqstd-ma2:" = bloque que lleva su propio decodificador ZPAQL (ZPAQLZ5).
  # lz6 se etiqueta "zpaqstd-ma2:lz5-lz6:" (formato LZ5, compresor lz6), de ahi
  # el prefijo opcional; "lz5" no calza con "lz5-lz6:".
  n=$(strings -a "$arch" 2>/dev/null | grep -cE "zpaqstd-ma2?:([a-z0-9]+-)?$a:")
  # lz (lzlib) se guarda como el LZMA de adentro del miembro lzip, con la etiqueta
  # de -ma:lzma (ZPAQLZIP): "zpaqstd-ma2:lzma:<nivel>:<tamano>:lzip".
  [ "$a" = lz ] && n=$(strings -a "$arch" 2>/dev/null | grep -cE "zpaqstd-ma2:lzma:[0-9]+:[0-9]+:lzip")
  # Desde 65.3y-pre32, lz4/lz4hc/lz4f/lzav SON -m6/-m7 de zpaqfranz: no llevan etiqueta
  # zpaqstd-ma. La prueba de que corrieron es que el archivo sea byte a byte el de su
  # -m equivalente (misma fecha fija), con los niveles por defecto de cada uno.
  case "$a" in lz4|lz4hc) eq="-m6h9";; lz4f) eq="-m6a9";; lzav) eq="-m7h";; *) eq="";; esac
  if [ -n "$eq" ]; then
    rm -f "$OUT/eq.zpaq"
    timeout 300 "$Z" a "$OUT/eq.zpaq" "$OUT/src" -t1 $eq -timestamp 2026-01-01_00:00:00 </dev/null >/dev/null 2>&1
    n=0; cmp -s "$arch" "$OUT/eq.zpaq" && n=1
  fi
  rm -rf "$OUT/o"; mkdir -p "$OUT/o"
  timeout 300 "$Z" x "$arch" -to "$OUT/o" -force </dev/null >/dev/null 2>&1
  g=$(find "$OUT/o" -type f -name t.txt -print -quit)
  iv=FALLA; [ -n "$g" ] && [ "$(sha256sum < "$g" | cut -d' ' -f1)" = "$REF" ] && iv=OK
  if [ "$n" -gt 0 ] && [ "$iv" = OK ]; then r=OK
  elif [ "$n" -eq 0 ]; then r=NO-CORRE; malos=$((malos+1))
  else r=FALLA; malos=$((malos+1)); fi
  # Los -ma:lz5 y -ma:lz6 llevan su decodificador ZPAQL: zpaq 7.15 TIENE que extraerlos.
  # Si esto falla, se rompio la portabilidad de ZPAQLZ5 (el programa embebido, el
  # SHA-1 del original en el segmento, o el tamano original en el comentario).
  z715="-"
  case "$a" in lz4|lz4hc|lz4f|lz5|lz5hc|lz5f|lz6|lzma|lz|flzma2|snappy|lzav|deflate|hs|lizard|lizard:45|bzip2|zstd|lzfse)
    if command -v zpaq >/dev/null 2>&1; then
      rm -rf "$OUT/o715"; mkdir -p "$OUT/o715"
      timeout 300 zpaq x "$arch" -to "$OUT/o715/" -force </dev/null >/dev/null 2>&1
      g7=$(find "$OUT/o715" -type f -name t.txt -print -quit)
      z715=FALLA; [ -n "$g7" ] && [ "$(sha256sum < "$g7" | cut -d' ' -f1)" = "$REF" ] && z715=OK
      [ "$z715" = OK ] || { r=NO-PORTABLE; malos=$((malos+1)); }
    fi ;;
  esac
  rm -f "$OUT/turbo.zpaq"
  timeout 300 "$Z" a "$OUT/turbo.zpaq" "$OUT/src" -turbo -ma:$a -timestamp 2026-01-01_00:00:00 </dev/null >/dev/null 2>&1
  tb=OK; cmp -s "$arch" "$OUT/turbo.zpaq" || { tb=DISTINTO; [ "$r" = OK ] && { r=TURBO-DISTINTO; malos=$((malos+1)); }; }
  printf '  %-8s marca=%-2s ida_vuelta=%-5s zpaq715=%-5s turbo=%-8s %s\n' "$a" "$n" "$iv" "$z715" "$tb" "$r"
  echo "$a,$n,$iv,$z715,$tb,$r" >> "$CSV"
done
nc=$(echo $ALGOS | wc -w)
echo "--- $nc codecs, $((nc-malos)) corren y vuelven, $malos a revisar ---"
echo DONE_MA_CORRE
