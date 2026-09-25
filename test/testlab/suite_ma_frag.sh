#!/bin/bash
# ============================================================================
# suite_ma_frag.sh -- bloques -ma casi incompresibles con MUCHOS fragmentos.
#
# POR QUE EXISTE: hasta 65.4m-pre39 la extraccion dejaba de leer un bloque
# cuando juntaba output_size bytes = la suma de los fragmentos que necesita, SIN
# la tabla de fragmentos que va al final del bloque. En un bloque -ma con
# decodificacion nativa lo que sale del segmento es el flujo COMPRIMIDO; si el
# bloque es casi incompresible y tiene miles de fragmentos chicos, ese flujo es
# mas largo que output_size (la tabla le deja margen: se acepta con ganar 16
# bytes contra el original completo) y se cortaba -> "31319 <codec>
# decompression failed" sobre un archivo SANO. Visto en un archivo real de
# 3 GB (cache de Tech Tool, 10.515 archivos perdidos en 3 bloques flzma2:9).
# Los datos siempre estuvieron bien: zpaq 7.15 corre el ZPAQL y no se corta.
#
# Lo que mide: 4000 archivos de 600-1400 bytes aleatorios + 6 ceros, por codec;
# 't' tiene que dar 0 fallos y 'x' los bytes exactos. Con pre38 fallan al
# menos flzma2, zstd, bzip2, lz5 y lizard.
#
#   uso: suite_ma_frag.sh          (usa Z=... o el binario del repo)
# ============================================================================
set -u
Z=${Z:-/home/forum/git/zpaq-std/zpaq-std}
W=/mnt/IA_LAB/agentes/ZPAQ-STD/testlab
OUT=$W/${RUN:-ma_frag}; rm -rf "$OUT"; mkdir -p "$OUT/in"
python3 - "$OUT/in" <<'PY'
import random,sys
random.seed(7); d=sys.argv[1]
for i in range(4000):
    n=random.randint(600,1400)
    open(f'{d}/{i:05d}.bin','wb').write(random.randbytes(n)+b'\0'*6)
PY
mal=0
for alg in flzma2 zstd lz4 brotli bzip2 bzip3 lzma lz deflate snappy lz5 lz6 lizard lzfse hs lzav bsc lzh ppmd; do
  rm -rf "$OUT/a.zpaq" "$OUT/x"
  "$Z" a "$OUT/a.zpaq" "$OUT/in" -ma:$alg >/dev/null 2>&1
  tf=$("$Z" t "$OUT/a.zpaq" 2>&1 | grep -c "decompression failed\|skipping")
  "$Z" x "$OUT/a.zpaq" -to "$OUT/x" >/dev/null 2>&1
  src=$(find "$OUT/x" -type d -name in | head -1)
  if [ -n "$src" ] && diff -rq "$OUT/in" "$src" >/dev/null 2>&1; then xv=OK; else xv=BAD; fi
  if [ "$tf" = 0 ] && [ $xv = OK ]; then r=OK; else r=FALLA; mal=$((mal+1)); fi
  echo "$alg t_fallos=$tf x=$xv $r"
done
echo "== suite_ma_frag: $mal falla(s)"
[ $mal = 0 ]
