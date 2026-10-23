#!/bin/bash
# ============================================================================
# suite_ext.sh -- -mae y -mat: codecs de plugins que no son parte de zpaq-std.
#
# POR QUE EXISTE: un archivo -mae/-mat tiene que abrirse sin el plugin cuando el
# codec da su ZPAQL (zpaq-std sin codecs/ y zpaq 7.15), y uno -mat sin ZPAQL tiene
# que fallar LIMPIO sin el plugin (31321 en zpaq-std; otro zpaq no devuelve datos
# falsos). -mae sin ZPAQL se rechaza. Un ZPAQL con $3..$5 (rlea) guarda sus
# valores en la etiqueta. Usa tools/plugin_example (rle, rlenz y rlea).
#
#   uso: suite_ext.sh          (usa Z=... o el binario del repo)
# ============================================================================
set -u
Z=${Z:-/home/forum/git/zpaq-std/zpaq-std}
EX=${EX:-/home/forum/git/zpaq-std/tools/plugin_example/zs_example.c}
PLUG=${PLUG:-/home/forum/git/zpaq-std/compressors/plug}
W=/mnt/IA_LAB/agentes/ZPAQ-STD/testlab
RUN=${RUN:-ext}
OUT=$W/$RUN; rm -rf "$OUT"; mkdir -p "$OUT/con/codecs" "$OUT/sin" "$OUT/src"; cd "$OUT"
cc -O2 -shared -fPIC -I"$PLUG" "$EX" -o con/codecs/example.so || { echo "no compila el ejemplo"; exit 1; }
cp "$Z" con/zpaq-std; cp "$Z" sin/zpaq-std
head -c 3000000 /dev/zero > src/z.bin; yes 'linea repetida' | head -c 1000000 > src/t.txt
malos=0; casos=0
ok() { casos=$((casos+1)); [ "$2" = ok ] || malos=$((malos+1)); printf '  %-44s %s\n' "$1" "$2"; }
con/zpaq-std a a1.zpaq src -mat:example:rle >l1.log 2>&1
r=ok; grep -q 'ZPAQL OK' l1.log || r="sin-verificacion"
rm -rf x; con/zpaq-std x a1.zpaq -to x >/dev/null 2>&1; diff -r src x/src >/dev/null || r="$r plugin-mal"
rm -rf y; sin/zpaq-std x a1.zpaq -to y >/dev/null 2>&1; diff -r src y/src >/dev/null || r="$r zpaql-mal"
if command -v zpaq >/dev/null; then rm -rf w; zpaq x a1.zpaq -to w >/dev/null 2>&1; diff -r src w/src >/dev/null || r="$r zpaq715-mal"; fi
ok "-mat con ZPAQL: plugin, sin plugin, zpaq 7.15" "$r"
con/zpaq-std a a2.zpaq src -mat:example:rlenz >/dev/null 2>&1
r=ok; rm -rf x; con/zpaq-std x a2.zpaq -to x >/dev/null 2>&1; diff -r src x/src >/dev/null || r="plugin-mal"
sin/zpaq-std x a2.zpaq -to y2 >l2.log 2>&1; grep -q 31321 l2.log || r="$r sin-31321"
if command -v zpaq >/dev/null; then rm -rf w; zpaq x a2.zpaq -to w >/dev/null 2>&1; diff -r src w/src >/dev/null 2>&1 && r="$r zpaq715-dio-datos"; fi
ok "-mat sin ZPAQL: falla limpio sin el plugin" "$r"
con/zpaq-std a a3.zpaq src -mae:example:rle >l3.log 2>&1
r=ok; grep -q 00606 l3.log || r="sin-aviso"; rm -rf x; con/zpaq-std x a3.zpaq -to x >/dev/null 2>&1; diff -r src x/src >/dev/null || r="$r mal"
ok "-mae con ZPAQL: aviso 00606 y extrae" "$r"
con/zpaq-std a a4.zpaq src -mae:example:rlenz >l4.log 2>&1; rc=$?
[ $rc = 2 ] && grep -q 00620 l4.log && r=ok || r="rc=$rc"; ok "-mae sin ZPAQL: se rechaza (00620)" "$r"
# rlea: el mismo ZPAQL por ZS_DATA_ZPAQL_ARGS, con $3 (tamano de H) de query(): la
# etiqueta lo guarda al final (:7) y el bloque abre sin el plugin y en zpaq 7.15
con/zpaq-std a a6.zpaq src -mae:example:rlea >l6.log 2>&1
r=ok; strings -a a6.zpaq | grep -qE 'zpaqstd-mae:example:rlea:[0-9:]+:1:7' || r="sin-\$3"
rm -rf y6; sin/zpaq-std x a6.zpaq -to y6 >/dev/null 2>&1; diff -r src y6/src >/dev/null || r="$r zpaql-mal"
if command -v zpaq >/dev/null; then rm -rf w6; zpaq x a6.zpaq -to w6 >/dev/null 2>&1; diff -r src w6/src >/dev/null || r="$r zpaq715-mal"; fi
ok "-mae con \$3 por query (ZS_DATA_ZPAQL_ARGS)" "$r"
con/zpaq-std a a5.zpaq src -mat:../codecs/example:rle >l5.log 2>&1; rc=$?
[ $rc = 2 ] && grep -q 00619 l5.log && r=ok || r="rc=$rc"; ok "nombre con ruta: se rechaza (00619)" "$r"
echo "--- $casos casos, $((casos-malos)) bien, $malos a revisar ---"
echo DONE_EXT
