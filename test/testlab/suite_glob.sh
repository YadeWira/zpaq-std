#!/bin/bash
Z=${Z:-/home/forum/git/zpaq-std/zpaq-std}
W=/mnt/IA_LAB/agentes/ZPAQ-STD/testlab
OUT=$W/${RUN:-run1}; mkdir -p $OUT
CSV=$OUT/glob.csv; echo "prueba,esperado,obtenido,resultado" > "$CSV"
ok(){ printf '  %-30s esperado=%-6s obtenido=%-6s %s\n' "$1" "$2" "$3" "$4"; echo "$1,$2,$3,$4" >> "$CSV"; }
d=$OUT/gl; rm -rf $d; mkdir -p $d/data/sub; mkdir -p $d/work
for i in 1 2 3 4 5; do printf 'c%s\n' $i > $d/data/f$i.c; done
for i in 1 2 3; do printf 'h%s\n' $i > $d/data/f$i.h; done
printf 'x\n' > $d/data/sub/anidado.c
# los esperados se calculan del arbol real: "*" tambien matchea sub/ y recursa
E_C=$(ls $d/data/*.c | wc -l)
E_H=$(ls $d/data/*.h | wc -l)
E_ALL=$(find $d/data -type f | wc -l)
E_DIR=$E_ALL
cd $d/data
n(){ echo "${1:-0}" | grep -oE '[0-9]+' | head -1; }
# sum: cuenta archivos
for pat in "*.c:$E_C" "*.h:$E_H" "*:$E_ALL" "f?.c:$E_C" 'f1.*:2' '*.noexiste:0'; do
  p=${pat%%:*}; exp=${pat##*:}
  got=$(n "$($Z sum "$p" 2>&1 </dev/null | grep -oE '[0-9]+ +files' | head -1)")
  ok "sum \"$p\"" "$exp" "${got:-0}" "$([ "${got:-0}" = "$exp" ] && echo OK || echo FALLA)"
done
# add: cuenta archivos agregados
for pat in "*.c:$E_C" "*:$E_ALL"; do
  p=${pat%%:*}; exp=${pat##*:}; rm -f $d/work/a.zpaq
  got=$(n "$($Z a $d/work/a.zpaq "$p" -m1 -summary 2>&1 </dev/null | grep -oE 'Files added \+[0-9]+' | head -1)")
  ok "a \"$p\"" "$exp" "${got:-0}" "$([ "${got:-0}" = "$exp" ] && echo OK || echo FALLA)"
done
# cp
$Z cp "$d/data/*.c" -to "$d/work/dst" >/dev/null 2>&1 </dev/null
got=$(ls $d/work/dst 2>/dev/null | wc -l); ok 'cp "*.c" -to dst' "$E_C" "$got" "$([ "$got" = "$E_C" ] && echo OK || echo FALLA)"
# -to con comodin: el argumento con * nunca era prefijo literal de lo que expande, y -to
# se ignoraba (a: ruta completa; x: a la ruta guardada, encima de los originales con -force)
nom(){ $Z l "$1" 2>/dev/null </dev/null | grep -E '\.[ch]$' | awk '{print $NF}' | sort | tr '\n' ' ' | sed 's/ $//'; }
rm -f $d/work/t.zpaq; $Z a $d/work/t.zpaq "$d/data/*" -to dst/ -m1 >/dev/null 2>&1 </dev/null
got=$(nom $d/work/t.zpaq | tr ' ' '\n' | grep -vc '^dst/'); ok 'a "data/*" -to dst/ (fuera)' 0 "$got" "$([ "$got" = 0 ] && echo OK || echo FALLA)"
got=$(nom $d/work/t.zpaq | wc -w); ok 'a "data/*" -to dst/ (todos)' "$E_ALL" "$got" "$([ "$got" = "$E_ALL" ] && echo OK || echo FALLA)"
rm -f $d/work/t.zpaq; $Z a $d/work/t.zpaq "$d/data/*.h" -to hh -m1 >/dev/null 2>&1 </dev/null
got=$(nom $d/work/t.zpaq); exp=$(cd $d/data && ls *.h | sed 's|^|hh/|' | sort | tr '\n' ' ' | sed 's/ $//')
ok 'a "data/*.h" -to hh' "ok" "$([ "$got" = "$exp" ] && echo ok || echo "$got")" "$([ "$got" = "$exp" ] && echo OK || echo FALLA)"
rm -f $d/work/abs.zpaq; $Z a $d/work/abs.zpaq "$d/data" -m1 >/dev/null 2>&1 </dev/null
printf 'cambiado\n' > $d/data/f1.c; rm -rf $d/work/rest
$Z x $d/work/abs.zpaq "$d/data/*" -to $d/work/rest/ -force >/dev/null 2>&1 </dev/null
got=$(cat $d/data/f1.c); ok 'x "data/*" -to rest/ -force (original)' "cambiado" "$got" "$([ "$got" = cambiado ] && echo OK || echo FALLA)"
got=$(find $d/work/rest -type f 2>/dev/null | wc -l); ok 'x "data/*" -to rest/ -force (rest)' "$E_ALL" "$got" "$([ "$got" = "$E_ALL" ] && echo OK || echo FALLA)"
printf 'c1\n' > $d/data/f1.c
# que lo que ya andaba siga andando
got=$(n "$($Z sum "$d/data" 2>&1 </dev/null | grep -oE '[0-9]+ +files'|head -1)")
ok "sum <directorio>" "$E_DIR" "${got:-0}" "$([ "${got:-0}" = "$E_DIR" ] && echo OK || echo FALLA)"
got=$(n "$($Z sum "$d/data/f1.c" 2>&1 </dev/null | grep -oE '[0-9]+ +files'|head -1)")
ok "sum <archivo puntual>" 1 "${got:-0}" "$([ "${got:-0}" = "1" ] && echo OK || echo FALLA)"
cd /; rm -rf $d
echo DONE_GLOB
