#!/bin/bash
# ============================================================================
# suite_sa.sh -- -sae y -sat: codecs de formatos especificos desde plugins.
#
# POR QUE EXISTE: un archivo que el codec toma (por su contenido) va SOLO en su
# bloque, comprimido por ese codec, y el resto como dicen -m/-ma. Lo que tiene
# que valer: (1) el codec CORRIO (etiquetas zpaqstd-sa[et] en el archivo, una por
# archivo tomado); (2) todo vuelve identico con el plugin, sin el plugin (ZPAQL)
# y en zpaq 7.15; (3) un -sat sin ZPAQL falla limpio sin el plugin (31321);
# (4) el archivo es byte a byte el mismo con -t1, -t2 y -t8 (el codec corre en
# los hilos de compresion, pero los bloques se escriben en orden); (5) un
# archivo repetido se deduplica y no se comprime dos veces; (6) -sae sin ZPAQL
# se rechaza. Usa tools/plugin_example (rle con ZPAQL, rlenz sin), que toma los
# archivos con al menos la mitad de los bytes en rachas de 3 o mas.
#
#   uso: suite_sa.sh          (usa Z=... o el binario del repo)
# ============================================================================
set -u
Z=${Z:-/home/forum/git/zpaq-std/zpaq-std}
EX=${EX:-/home/forum/git/zpaq-std/tools/plugin_example/zs_example.c}
PLUG=${PLUG:-/home/forum/git/zpaq-std/compressors/plug}
W=/mnt/IA_LAB/agentes/ZPAQ-STD/testlab
RUN=${RUN:-sa}
OUT=$W/$RUN; rm -rf "$OUT"; mkdir -p "$OUT/con/codecs" "$OUT/sin" "$OUT/src/sub"; cd "$OUT"
cc -O2 -shared -fPIC -I"$PLUG" "$EX" -o con/codecs/example.so || { echo "no compila el ejemplo"; exit 1; }
cp "$Z" con/zpaq-std; cp "$Z" sin/zpaq-std
# rachas (las toma rle), aleatorio y texto (no), una copia exacta (dedup), uno de
# 20 MB (mas que el bloque de -m1) y uno de 10 bytes (demasiado chico)
python3 -I -c "
import random
random.seed(5)
def rl(n):
  b=bytearray()
  while len(b)<n:
    c=random.randrange(256); b+=bytes([c])*random.randrange(1,40)
  return bytes(b[:n])
a=rl(300000)
open('src/a.rle','wb').write(a)
open('src/e_copia.rle','wb').write(a)
open('src/sub/b.bin','wb').write(rl(2000000))
open('src/f_grande.rle','wb').write(rl(20000000))
open('src/g_chico.rle','wb').write(b'x'*10)
open('src/c.rnd','wb').write(random.randbytes(500000))
open('src/d.txt','w').write(' '.join(random.choice('alfa beta gamma delta'.split()) for _ in range(100000)))
"
malos=0; casos=0
ok() { casos=$((casos+1)); [ "$2" = ok ] || malos=$((malos+1)); printf '  %-50s %s\n' "$1" "$2"; }
tags() { strings -a "$1" | grep -cE "zpaqstd-sa$2:example:"; }
TS='-timestamp 2026-01-01_00:00:00'
con/zpaq-std a a1.zpaq src -sat:example:rle -t8 $TS >l1.log 2>&1
r=ok; n=$(tags a1.zpaq t); [ "$n" = 3 ] || r="etiquetas=$n"
grep -q 'ZPAQL OK' l1.log || r="$r sin-verificacion"
rm -rf x; con/zpaq-std x a1.zpaq -to x >/dev/null 2>&1; diff -r src x/src >/dev/null || r="$r plugin-mal"
rm -rf y; sin/zpaq-std x a1.zpaq -to y >/dev/null 2>&1; diff -r src y/src >/dev/null || r="$r zpaql-mal"
if command -v zpaq >/dev/null; then rm -rf w; zpaq x a1.zpaq -to w >/dev/null 2>&1; diff -r src w/src >/dev/null || r="$r zpaq715-mal"; fi
ok "-sat con ZPAQL: 3 archivos tomados, extrae en todos" "$r"
for t in 1 2; do con/zpaq-std a a1_t$t.zpaq src -sat:example:rle -t$t $TS >/dev/null 2>&1; done
r=ok; cmp -s a1.zpaq a1_t1.zpaq || r="t1-distinto"; cmp -s a1.zpaq a1_t2.zpaq || r="$r t2-distinto"
ok "mismo archivo con -t1, -t2 y -t8" "$r"
con/zpaq-std a a2.zpaq src -sat:example:rlenz $TS >/dev/null 2>&1
r=ok; n=$(tags a2.zpaq t); [ "$n" = 3 ] || r="etiquetas=$n"
rm -rf x; con/zpaq-std x a2.zpaq -to x >/dev/null 2>&1; diff -r src x/src >/dev/null || r="$r plugin-mal"
sin/zpaq-std x a2.zpaq -to y2 >l2.log 2>&1; grep -q 31321 l2.log || r="$r sin-31321"
if command -v zpaq >/dev/null; then rm -rf w; zpaq x a2.zpaq -to w >/dev/null 2>&1; cmp -s src/a.rle w/src/a.rle && r="$r zpaq715-dio-datos"; fi
ok "-sat sin ZPAQL: falla limpio sin el plugin" "$r"
con/zpaq-std a a3.zpaq src -sae:example:rle -ma:zstd $TS >l3.log 2>&1
r=ok; grep -q 00732 l3.log || r="sin-aviso"; n=$(tags a3.zpaq e); [ "$n" = 3 ] || r="$r etiquetas=$n"
strings -a a3.zpaq | grep -q 'zpaqstd-ma2:zstd:' || r="$r sin-zstd"
rm -rf x; con/zpaq-std x a3.zpaq -to x >/dev/null 2>&1; diff -r src x/src >/dev/null || r="$r mal"
rm -rf y; sin/zpaq-std x a3.zpaq -to y >/dev/null 2>&1; diff -r src y/src >/dev/null || r="$r zpaql-mal"
ok "-sae + -ma:zstd: aviso 00732, los dos codecs corren" "$r"
con/zpaq-std a a3.zpaq src -sae:example:rle $TS >/dev/null 2>&1
r=ok; n=$(tags a3.zpaq e); [ "$n" = 3 ] || r="etiquetas=$n (la 2a version no agrega nada)"
ok "segunda version sin cambios: nada nuevo" "$r"
con/zpaq-std a a4.zpaq src -sae:example:rlenz >l4.log 2>&1; rc=$?
[ $rc = 2 ] && grep -q 00731 l4.log && r=ok || r="rc=$rc"; ok "-sae sin ZPAQL: se rechaza (00731)" "$r"
con/zpaq-std a a5.zpaq src -sat:../codecs/example:rle >l5.log 2>&1; rc=$?
[ $rc = 2 ] && grep -q 00730 l5.log && r=ok || r="rc=$rc"; ok "nombre con ruta: se rechaza (00730)" "$r"
con/zpaq-std a a6.zpaq src -sat:example:rle -mat:example:rle >l6.log 2>&1; rc=$?
[ $rc = 2 ] && grep -q 00730 l6.log && r=ok || r="rc=$rc"; ok "-sat con -mat: se rechaza (00730)" "$r"
echo "--- $casos casos, $((casos-malos)) bien, $malos a revisar ---"
echo DONE_SA
