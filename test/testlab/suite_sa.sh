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
# se rechaza; (7) desde 1.7.0, con un codec cuyo ZPAQL acepta varios segmentos
# (rles, ZS_QUERY_SEGMENTS), los archivos consecutivos que toma van JUNTOS en un
# bloque, un segmento cada uno (etiqueta zpaqstd-sm[et]), y todo sigue volviendo
# identico: con y sin plugin, en zpaq 7.15, en 1.6.0 con el plugin (que no conoce
# la etiqueta y corre el ZPAQL) y extrayendo un solo archivo del medio.
# Usa tools/plugin_example (rle con ZPAQL, rlenz sin, rles con segmentos), que
# toma los archivos con al menos la mitad de los bytes en rachas de 3 o mas.
#
#   OLD160=<zpaq-std 1.6.0> agrega la prueba de 1.6.0 con el plugin
#   PJAPLUG=<pja.so> agrega -sa (la familia oficial: pjax, pja, pjall, pjals y pjalsx) sobre copias de
#   JPEG y JPEG-LS del corpus: -sa = -sa:pja = -sae:pja:pjax+2:pja+2:pjall+2:pjals+2:pjalsx+2 byte a byte, extrae con
#   y sin plugin y en zpaq 7.15, y sin el plugin -sa se niega (00730)
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
import os
os.makedirs('src2', exist_ok=True)
for i, n in enumerate([150000, 3000000, 40000, 1200000, 700]):
  open('src2/m%d.rle' % i,'wb').write(rl(n))
open('src2/z.txt','w').write('texto sin rachas ' * 2000)
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
# (7) varios archivos por bloque
con/zpaq-std a g1.zpaq src2 -sat:example:rles -t8 $TS >lg.log 2>&1
r=ok; n=$(strings -a g1.zpaq | grep -cE "zpaqstd-smt:example:rles:"); [ "$n" = 1 ] || r="etiquetas-sm=$n"
strings -a g1.zpaq | grep -qE "zpaqstd-smt:example:rles:[^ ]*:5:[0-9]+/[0-9]+,[0-9]+/[0-9]+,[0-9]+/[0-9]+,[0-9]+/[0-9]+,[0-9]+/[0-9]+ " || r="$r sin-5-segmentos"
grep -q 'in 5 files, one segment each.*ZPAQL OK' lg.log || r="$r sin-verificacion"
rm -rf x; con/zpaq-std x g1.zpaq -to x >lgx.log 2>&1; diff -r src2 x/src2 >/dev/null || r="$r plugin-mal"
grep -q 'decoded by the plugin' lgx.log || r="$r no-fue-nativo"
rm -rf y; sin/zpaq-std x g1.zpaq -to y >/dev/null 2>&1; diff -r src2 y/src2 >/dev/null || r="$r zpaql-mal"
if command -v zpaq >/dev/null; then rm -rf w; zpaq x g1.zpaq -to w >/dev/null 2>&1; diff -r src2 w/src2 >/dev/null || r="$r zpaq715-mal"; fi
ok "-sat rles: 5 archivos en un bloque, extrae en todos" "$r"
for t in 1 2; do con/zpaq-std a g1_t$t.zpaq src2 -sat:example:rles -t$t $TS >/dev/null 2>&1; done
r=ok; cmp -s g1.zpaq g1_t1.zpaq || r="t1-distinto"; cmp -s g1.zpaq g1_t2.zpaq || r="$r t2-distinto"
ok "varios por bloque: mismo archivo con -t1, -t2 y -t8" "$r"
r=ok
for f in m1 m3 m4; do
  rm -rf p; con/zpaq-std x g1.zpaq src2/$f.rle -to p/$f.rle -space >/dev/null 2>&1; cmp -s src2/$f.rle p/$f.rle || r="$r plugin-$f"
  if command -v zpaq >/dev/null; then rm -rf p; zpaq x g1.zpaq src2/$f.rle -to p/$f.rle >/dev/null 2>&1; cmp -s src2/$f.rle p/$f.rle || r="$r zpaq715-$f"; fi
done
ok "varios por bloque: un solo archivo del medio y el ultimo" "$r"
con/zpaq-std a g2.zpaq src2 -sae:example:rles $TS >/dev/null 2>&1
r=ok; n=$(strings -a g2.zpaq | grep -cE "zpaqstd-sme:example:rles:"); [ "$n" = 1 ] || r="etiquetas-sm=$n"
rm -rf y; sin/zpaq-std x g2.zpaq -to y >/dev/null 2>&1; diff -r src2 y/src2 >/dev/null || r="$r zpaql-mal"
if [ -n "${OLD160:-}" ] && [ -x "$OLD160" ]; then
  rm -rf o16; mkdir -p o16/codecs; cp "$OLD160" o16/zpaq-std; cp con/codecs/example.so o16/codecs/
  rm -rf v; o16/zpaq-std x g2.zpaq -to v >/dev/null 2>&1; diff -r src2 v/src2 >/dev/null || r="$r 1.6.0-con-plugin-mal"
fi
ok "-sae rles: zpaqstd-sme, 1.6.0 con el plugin corre el ZPAQL" "$r"
con/zpaq-std a g3.zpaq src2 -sat:example:rle $TS >/dev/null 2>&1
r=ok; n=$(tags g3.zpaq t); [ "$n" = 5 ] || r="etiquetas=$n"; strings -a g3.zpaq | grep -q "zpaqstd-smt" && r="$r agrupo-sin-permiso"
ok "rle (sin ZS_QUERY_SEGMENTS): uno por bloque, como antes" "$r"
if [ -n "${PJAPLUG:-}" ] && [ -f "$PJAPLUG" ]; then
  rm -rf pj src3; mkdir -p pj/codecs src3; cp "$Z" pj/zpaq-std; cp "$PJAPLUG" pj/codecs/
  CO=/mnt/OSR_D3/fileFormatSamples/fileFormatSamples/image
  # por el contenido (JPEG: FF D8 FF), no por el nombre: en el corpus hay ".jpg" que no lo son
  python3 -I -c "
import os, sys
co=sys.argv[1]; out=[]
for d, _, fs in sorted(os.walk(co)):
  for f in sorted(fs):
    p=os.path.join(d, f)
    try:
      n=os.path.getsize(p)
      if '\\n' not in p and 20000<n<400000 and f.lower().endswith(('.jpg','.jpeg','.jls')) and open(p,'rb').read(3)==b'\\xff\\xd8\\xff':
        out.append(p)
    except OSError: pass
jls=[p for p in out if p.lower().endswith('.jls')][:4]
jpg=[p for p in out if not p.lower().endswith('.jls')][:12]
open('pj.lista','w').write(''.join(x+'\\n' for x in jpg+jls))
" "$CO"
  i=0; while IFS= read -r f; do i=$((i+1)); cp -- "$f" "src3/$(printf %02d $i).${f##*.}"; done < pj.lista
  pj/zpaq-std a s1.zpaq src3 -sa $TS >ls1.log 2>&1; pj/zpaq-std a s2.zpaq src3 -sae:pja:pjax+2:pja+2:pjall+2:pjals+2:pjalsx+2 $TS >/dev/null 2>&1
  pj/zpaq-std a s4.zpaq src3 -sa:pja $TS >/dev/null 2>&1
  r=ok; cmp -s s1.zpaq s2.zpaq || r="distinto-de-sae"; cmp -s s1.zpaq s4.zpaq || r="$r sa:pja-no-es-la-familia"; grep -q 00732 ls1.log && r="$r aviso-no-oficial"
  n=$(strings -a s1.zpaq | grep -cE "zpaqstd-s[am]e:pja:"); [ "$n" -ge 1 ] || r="$r sin-bloques-pja"
  rm -rf x; pj/zpaq-std x s1.zpaq -to x >/dev/null 2>&1; diff -r src3 x/src3 >/dev/null || r="$r plugin-mal"
  rm -rf y; sin/zpaq-std x s1.zpaq -to y >/dev/null 2>&1; diff -r src3 y/src3 >/dev/null || r="$r zpaql-mal"
  if command -v zpaq >/dev/null; then rm -rf w; zpaq x s1.zpaq -to w >/dev/null 2>&1; diff -r src3 w/src3 >/dev/null || r="$r zpaq715-mal"; fi
  ok "-sa (familia pja: pjax, pja, pjall, pjals, pjalsx) = -sa:pja = -sae: $(wc -l < pj.lista) archivos, extrae en todos" "$r"
  pj/zpaq-std a s5.zpaq src3 -sa:pja:pjals >ls5.log 2>&1; rc=$?
  [ $rc = 2 ] && grep -q 'pjals is written twice' ls5.log && r=ok || r="rc=$rc"; ok "-sa:pja:pjals: la familia ya trae pjals, se niega" "$r"
  sin/zpaq-std a s3.zpaq src3 -sa >ls3.log 2>&1; rc=$?
  [ $rc = 2 ] && grep -q 'needs codecs/pja' ls3.log && r=ok || r="rc=$rc"; ok "-sa sin el plugin: se niega (00730)" "$r"
fi
echo "--- $casos casos, $((casos-malos)) bien, $malos a revisar ---"
echo DONE_SA
