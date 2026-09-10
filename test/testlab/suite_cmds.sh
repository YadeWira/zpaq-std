#!/bin/bash
Z=${Z:-/home/forum/git/zpaq-std/zpaq-std}
W=/mnt/IA_LAB/agentes/ZPAQ-STD/testlab
CORPUS=$W/corpus
OUT=$W/${RUN:-run1}; mkdir -p $OUT
CSV=$OUT/cmds.csv; LOG=$OUT/cmds.log
echo "cmd,prueba,rc,señal,resultado" > "$CSV"
: > "$LOG"
ok(){ printf '  %-13s %-34s rc=%-4s %-22s %s\n' "$1" "$2" "$3" "$4" "$5"; echo "$1,\"$2\",$3,\"$4\",$5" >> "$CSV"; }
# corre y devuelve rc; guarda salida en $O
O=$OUT/cmd_out.txt
T(){ : > $O; timeout 240 "$@" > $O 2>&1 </dev/null; return $?; }
G(){ grep -icE "$1" $O; }   # cuenta lineas que matchean

d=$OUT/cmds; rm -rf $d; mkdir -p $d/src $d/empty
cp -r $CORPUS/text/. $d/src/
cp -r $CORPUS/intl/. $d/src/ 2>/dev/null
$Z a "$d/a.zpaq" "$d/src" -m3 -summary >/dev/null 2>&1
$Z a "$d/a.zpaq" "$d/src" -m3 -summary >/dev/null 2>&1   # 2a version
NF=$(find $d/src -type f | wc -l)
echo "  (base: $NF archivos, archivo de $(stat -c%s $d/a.zpaq) bytes, 2 versiones)"
echo

########## informativos ##########
T $Z i "$d/a.zpaq";            ok i "versiones del archivo" $? "versiones=$(G 'version')" "$([ $? -eq 0 ] && echo OK)"
T $Z i "$d/a.zpaq" -stat;      ok i "-stat (cuenta y tamaño)" $? "lineas=$(wc -l<$O)" OK
T $Z l "$d/a.zpaq";            ok l "listado simple" $? "archivos=$(G '\.txt|\.c$|\.h$')" OK
T $Z l "$d/a.zpaq" -all;       ok l "-all (todas las versiones)" $? "lineas=$(wc -l<$O)" OK
T $Z l "$d/a.zpaq" -n 5;       ok l "-n 5 (primeras 5)" $? "lineas=$(wc -l<$O)" OK
T $Z l "$d/a.zpaq" -find server; ok l "-find server" $? "coincidencias=$(G 'server')" OK
T $Z dirsize "$d/a.zpaq" src;  ok dirsize "tamaño de carpeta en archivo" $? "lineas=$(wc -l<$O)" OK
T $Z dir "$d/src";             ok dir "clon de dir sobre carpeta" $? "lineas=$(wc -l<$O)" OK
T $Z tree "$d/src";            ok tree "clon de tree" $? "lineas=$(wc -l<$O)" OK
T $Z find "$d/src" "*.txt";    ok find "buscar *.txt" $? "hits=$(G '\.txt')" OK
T $Z redu "$d/src";            ok redu "examen tecnico rapido" $? "lineas=$(wc -l<$O)" OK

########## hashing / comparacion ##########
T $Z hash "$d/src";            ok hash "SHA-1 por default" $? "lineas=$(wc -l<$O)" OK
T $Z hash "$d/src" -sha256;    ok hash "-sha256" $? "lineas=$(wc -l<$O)" OK
T $Z hash "$d/src" -xxh3;      ok hash "-xxh3" $? "lineas=$(wc -l<$O)" OK
T $Z hash "$d/src" -blake3;    ok hash "-blake3" $? "lineas=$(wc -l<$O)" OK
T $Z sum "$d/src";             ok sum "hash+dupes+SHA256 global" $? "global=$(G 'global|GLOBAL')" OK
T $Z count "$d/src/*.md" 0;    ok count "contar cadenas" $? "lineas=$(wc -l<$O)" OK

########## verificacion profunda del archivo ##########
T $Z t "$d/a.zpaq";            ok t "test normal" $? "veredicto=$(G 'VERDICT')" OK
T $Z p "$d/a.zpaq";            ok p "test PARANOICO (decompresor de referencia)" $? "lineas=$(wc -l<$O)" OK
T $Z pp "$d/a.zpaq";           ok pp "test paranoico de hashes" $? "lineas=$(wc -l<$O)" OK
T $Z collision "$d/a.zpaq";    ok collision "buscar colisiones SHA-1" $? "lineas=$(wc -l<$O)" OK

########## extraccion: variantes ##########
T $Z x "$d/a.zpaq" -to "$d/ox/" -force; r=$?
res=MATCH; diff -r $d/src "$d/ox$d/src" >>$LOG 2>&1 || res=MISMATCH
ok x "extraccion normal" $r "archivos=$(find $d/ox -type f|wc -l)" $res
mkdir -p $d/oe && (cd $d/oe && timeout 240 $Z e "$d/a.zpaq" > $O 2>&1 </dev/null); r=$?
ok e "extraer 'aca' (comando e)" $r "archivos=$(find $d/oe -type f|wc -l)" "$([ $(find $d/oe -type f|wc -l) -gt 0 ] && echo OK || echo VACIO)"
T $Z w "$d/a.zpaq" -to "$d/empty/"; r=$?
ok w "extraccion por chunks (w)" $r "archivos=$(find $d/empty -type f|wc -l)" "$([ $(find $d/empty -type f|wc -l) -gt 0 ] && echo OK || echo VACIO)"
rm -rf $d/ow2; mkdir -p $d/ow2
T $Z w "$d/a.zpaq" -to "$d/ow2/" -ramdisk; ok w "-ramdisk" $? "archivos=$(find $d/ow2 -type f|wc -l)" OK
T $Z x "$d/a.zpaq" -to "$d/ou1/" -until 1 -force; ok x "-until 1" $? "archivos=$(find $d/ou1 -type f 2>/dev/null|wc -l)" OK

########## comparacion de directorios (verifica la extraccion de otra forma) ##########
T $Z c "$d/src" "$d/ox$d/src"; ok c "comparar origen vs extraido" $? "iguales=$(G 'identical|iguali|EQUAL|OK')" OK
T $Z c "$d/src" "$d/oe$d/src" ; ok c "comparar origen vs 'e'" $? "lineas=$(wc -l<$O)" OK
T $Z versum "$d/a.zpaq" "$d/src"; ok versum "doble chequeo tipo hashdeep" $? "lineas=$(wc -l<$O)" OK

########## dry-runs no destructivos ##########
T $Z trim "$d/a.zpaq";         ok trim "dry-run (sin -kill)" $? "lineas=$(wc -l<$O)" "$([ -f $d/a.zpaq ] && echo ARCHIVO-INTACTO)"
T $Z crop "$d/a.zpaq" -until 1; ok crop "dry-run -until 1" $? "lineas=$(wc -l<$O)" "$([ -f $d/a.zpaq ] && echo ARCHIVO-INTACTO)"
T $Z d "$d/src/";              ok d "dedup dry-run (sin -force)" $? "lineas=$(wc -l<$O)" "$([ $(find $d/src -type f|wc -l) -eq $NF ] && echo NADA-BORRADO || echo BORRO-ALGO)"
mkdir -p $d/otro && cp $d/src/*.md $d/otro/ 2>/dev/null
T $Z 1on1 "$d/src" -deleteinto "$d/otro"; ok 1on1 "dry-run contra otra carpeta" $? "lineas=$(wc -l<$O)" "$([ $(find $d/otro -type f|wc -l) -gt 0 ] && echo NADA-BORRADO)"

########## copia y utilidades ##########
mkdir -p $d/cpdst
T $Z cp "$d/src/server.c" -to "$d/cpdst"; ok cp "copia amigable" $? "archivos=$(find $d/cpdst -type f|wc -l)" OK
T $Z utf "$d/src";             ok utf "chequeo utf de nombres" $? "lineas=$(wc -l<$O)" OK

########## backup multiparte gestionado ##########
rm -rf $d/bk; mkdir -p $d/bk
# backup NO acepta comodines ("do not use ?"): genera el .index/.txt y las
# partes a partir de un nombre plano
T $Z backup "$d/bk/b.zpaq" "$d/src" -m1 -summary; r=$?
np=$(ls $d/bk/ 2>/dev/null|wc -l)
ok backup "backup gestionado" $r "partes=$np" "$([ $np -gt 0 ] && echo OK || echo SIN-PARTES)"
T $Z testbackup "$d/bk/b.zpaq"; ok testbackup "verificar el backup" $? "lineas=$(wc -l<$O)" OK
T $Z testbackup "$d/bk/b.zpaq" -verify; ok testbackup "-verify (relee del disco)" $? "lineas=$(wc -l<$O)" OK
rm -rf $d
echo DONE_CMDS
