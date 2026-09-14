#!/bin/bash
# Fija el corpus con un manifiesto de sha256.
#
# POR QUE: las suites (suite_cmds/robust/extra/ytool) REGENERAN su corpus base en
# cada corrida con `find | head`, que elige archivos distintos entre corridas.
# Eso ya invalido una comparacion de tamanos: dos binarios "distintos" que en
# realidad habian comprimido entradas distintas. El golden gate no puede depender
# de datos que se mueven, y difftest tampoco si se quiere comparar entre dias.
#
#   uso: pin_corpus.sh [verify]
#        sin argumento -> (re)genera el MANIFEST.sha256 de cada corpus
#        verify        -> compara los corpus actuales contra sus manifiestos
set -u
W=/mnt/IA_LAB/agentes/ZPAQ-STD/testlab

# corpus-raster2 se fija igual que corpus: los modelos de imagen de -mf eligen el
# modelo segun la CABECERA del archivo, asi que un corpus que se mueve cambia que
# ramas se ejercitan y no solo cuanto comprime. Su antecesor corpus-raster esta
# RETIRADO (ver corpus-raster-RETIRADO.txt): 8 de sus 10 archivos no eran las
# imagenes que su extension decia, porque se lo armo filtrando por extension.
DIRS="corpus corpus-raster2"

cd "$W" || exit 2

manifiesto() { echo "$W/$1/MANIFEST.sha256"; }
listar() { find "$1" -type f ! -name MANIFEST.sha256 -print0 | sort -z | xargs -0 sha256sum; }

rc=0
for d in $DIRS; do
    [ -d "$d" ] || { echo "$d: no existe, salteado"; continue; }
    M=$(manifiesto "$d")
    if [ "${1:-}" = "verify" ]; then
        [ -f "$M" ] || { echo "$d: no hay manifiesto: corre pin_corpus.sh primero"; rc=2; continue; }
        if listar "$d" | diff -q - "$M" >/dev/null; then
            echo "$d OK: $(wc -l < "$M") archivos coinciden con el manifiesto"
        else
            echo "$d CAMBIO respecto del manifiesto:"
            listar "$d" | diff "$M" - | head -20
            rc=1
        fi
    else
        listar "$d" > "$M"
        echo "$d: $(wc -l < "$M") archivos, $(du -sh "$d" | cut -f1)"
    fi
done
exit $rc
