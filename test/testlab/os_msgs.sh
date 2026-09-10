#!/bin/bash
# ============================================================================
# os_msgs.sh — matriz de FORMAS DE DESTINO y mensajes numerados.
#
# POR QUE EXISTE: difftest.sh compara el stdout de 'l' unicamente, y filtrado.
# El stdout de 'a', 'x' y 't' va a su log y NADIE lo diffea. O sea que los
# mensajes numerados (00067! 00071: 00072! 00877! 00878! 00935!) no estaban
# verificados por nada -- y son justo lo que una migracion de la capa del SO
# tiene que preservar. Peor: las formas de destino que produjeron los 4 bugs de
# v64.8j-pre9 no estaban en ninguna matriz.
#
# Las formas de abajo son EXACTAMENTE esas: nombre relativo desnudo, cadena de
# directorios inexistente, ruta sin ancestro salvo '/', UTF-8, ruta larga,
# symlink, directorio sin permiso de escritura.
#
# TODO corre con -t1. NO es cosmetico: myprintf no es thread-safe, y con -debug3
# y varios hilos la salida sale ENTRELAZADA a nivel de caracter (se ven pedazos
# de dos lineas mezclados). Sin -t1 esta suite falla contra SI MISMA.
#
# TRES ASERCIONES SEPARADAS, porque miden cosas distintas:
#   1. esqueleto de mensajes identico  (digitos borrados: el valor de espacio
#      libre se mueve entre corridas y daria falso positivo)
#   2. valor de espacio libre dentro del 1%   (f_bavail se mueve de verdad)
#   3. mismo codigo de salida
#
#   uso: os_msgs.sh <binA> <binB> [etiqueta]
#        os_msgs.sh <bin> <bin>            <- control: debe pasar siempre
# ============================================================================
set -u
A="${1:?falta binA}"; B="${2:?falta binB}"; TAG="${3:-osmsgs}"
# ABSOLUTOS, obligatorio: los binarios corren dentro de un `cd "$CWD"`, y una
# ruta relativa como "./zpaq-std-pre9" ahi no resuelve. Cuando eso paso, los dos
# lados daban rc=127 con salida vacia y TODOS los casos "pasaban" -- un test que
# aprueba porque no corrio. De ahi tambien el guarda de vacuidad de mas abajo.
A=$(readlink -f "$A") || { echo "no existe: $1"; exit 2; }
B=$(readlink -f "$B") || { echo "no existe: $2"; exit 2; }
[ -x "$A" ] || { echo "no ejecutable: $A"; exit 2; }
[ -x "$B" ] || { echo "no ejecutable: $B"; exit 2; }
W=/mnt/IA_LAB/agentes/ZPAQ-STD/testlab
OUT=$W/$TAG; rm -rf "$OUT"; mkdir -p "$OUT"
LOG=$OUT/os_msgs.log
CSV=$OUT/os_msgs.csv
TMO=${TMO:-120}

printf 'A = %s\nB = %s\n\n' "$A" "$B" | tee "$LOG"
echo "caso,comando,forma,rc_A,rc_B,esqueleto,espacio,resultado" > "$CSV"

# --- fuente chica y fija -----------------------------------------------------
SRC=$OUT/src
mkdir -p "$SRC"
printf 'contenido de prueba\n' > "$SRC/a.txt"
printf 'segundo archivo\n'      > "$SRC/b.txt"
mkdir -p "$SRC/sub"
printf 'anidado\n' > "$SRC/sub/c.txt"

ARC=$OUT/base.zpaq
"$A" a "$ARC" "$SRC" -m1 -nomore >/dev/null 2>&1

# --- andamiaje de las formas -------------------------------------------------
# Los binarios corren con cwd = $OUT/cwd, para que un destino RELATIVO ("out")
# caiga dentro del directorio de la corrida y no en el del testlab. Sin esto,
# "-to out" resolvia contra el cwd compartido: la corrida de A lo creaba, la de B
# lo encontraba lleno, y el caso 01 fallaba contra si mismo de forma persistente.
CWD=$OUT/cwd;           mkdir -p "$CWD"
EXIST=$OUT/existe;      mkdir -p "$EXIST"
NOWR=$OUT/sinescritura; mkdir -p "$NOWR"; chmod 500 "$NOWR"
LINKT=$OUT/destino_link; mkdir -p "$LINKT"
ln -sfn "$LINKT" "$OUT/link_a_dir"
LARGO=$OUT/$(printf 'l%.0s' $(seq 1 240))
SHM=/dev/shm/zpaqstd-osmsgs-$$
UTF8="$OUT/café/日本"

ok=0; bad=0

# normaliza: borra corridas de digitos, rutas absolutas del OUT, y el tiempo
esqueleto() { # $1=archivo  $2=binario que lo produjo
    # Dos cosas hay que borrar o esta suite falla sin que nada este mal:
    #  - "unecrypted on [ENCRYPT @ N]" del -debug3 de 'a' vuelca BYTES ALEATORIOS
    #    (la zona de sal/clave), distintos en cada corrida por diseno.
    #  - "FULL exename <<...>>" es argv[0], o sea la ruta del binario bajo prueba,
    #    que por definicion difiere entre A y B. No es comportamiento.
    # Y las corridas de espacios se colapsan: las lineas de progreso alinean por
    # columnas, asi que al normalizar los digitos queda distinto PADDING para el
    # mismo mensaje (p.ej. la tasa de "file/s").
    LC_ALL=C sed -e "s|$OUT|@OUT@|g" \
        -e "s|$2|@BIN@|g" \
        -e '/unecrypted on \[ENCRYPT/d' \
        -e '/FULL exename/d' \
        -e 's/[^[:print:][:space:]]/./g' \
        -e 's/-\?[0-9][0-9.,:]*/#/g' \
        -e 's/[[:space:]][[:space:]]*/ /g' \
        -e '/^[[:space:]]*$/d' "$1" | sort
}
# saca el valor de "is <espacios> N" del bloque de espacio libre
libre() { grep -oE '^is +[0-9.]+' "$1" | head -1 | grep -oE '[0-9.]+' | tr -d '.,'; }

correr() { # $1=nombre  $2=comando(a|x|repack)  $3=forma-de-destino  $4=flags extra
    local nombre="$2/$1" cmd="$2" dest="$3" extra="${4:-}"
    local oa=$OUT/a.$$.txt ob=$OUT/b.$$.txt

    # Limpia TODOS los destinos que toca la matriz. Si no, la corrida de B ve lo
    # que dejo la de A y los mensajes difieren legitimamente (fue el caso de
    # 07-dir-existente y 12-tmpfs, que fallaban contra si mismos).
    limpiar() {
        chmod 700 "$NOWR" 2>/dev/null
        rm -rf "$OUT/out" "$OUT/café" "$LARGO" "$OUT/rep.zpaq" "$OUT/na.zpaq" \
               "$EXIST" "$LINKT" "$NOWR/sub" "$SHM" "$OUT/out.zpaq" "$CWD" 2>/dev/null
        mkdir -p "$EXIST" "$LINKT" "$CWD"
        chmod 500 "$NOWR" 2>/dev/null
    }

    limpiar
    case "$cmd" in
      x)      ( cd "$CWD" && timeout $TMO "$A" x "$ARC" -to "$dest" -force -debug3 -nomore -t1 $extra ) >"$oa" 2>&1; local ra=$? ;;
      a)      ( cd "$CWD" && timeout $TMO "$A" a "$OUT/na.zpaq" "$SRC" -to "$dest" -m1 -debug3 -nomore -t1 $extra ) >"$oa" 2>&1; local ra=$? ;;
      repack) ( cd "$CWD" && timeout $TMO "$A" repack "$ARC" "$dest" -debug3 -nomore -t1 $extra ) >"$oa" 2>&1; local ra=$? ;;
    esac
    rm -f "$OUT/na.zpaq"
    limpiar
    case "$cmd" in
      x)      ( cd "$CWD" && timeout $TMO "$B" x "$ARC" -to "$dest" -force -debug3 -nomore -t1 $extra ) >"$ob" 2>&1; local rb=$? ;;
      a)      ( cd "$CWD" && timeout $TMO "$B" a "$OUT/na.zpaq" "$SRC" -to "$dest" -m1 -debug3 -nomore -t1 $extra ) >"$ob" 2>&1; local rb=$? ;;
      repack) ( cd "$CWD" && timeout $TMO "$B" repack "$ARC" "$dest" -debug3 -nomore -t1 $extra ) >"$ob" 2>&1; local rb=$? ;;
    esac
    rm -f "$OUT/na.zpaq"

    { echo "########## $nombre  dest=<<$dest>> extra=<<$extra>>"; echo "--- A (rc=$ra) ---"; cat "$oa"
      echo "--- B (rc=$rb) ---"; cat "$ob"; } >> "$LOG"

    local esq=OK; esqueleto "$oa" "$A" > "$oa.n"; esqueleto "$ob" "$B" > "$ob.n"
    cmp -s "$oa.n" "$ob.n" || esq=DISTINTO
    local esp=OK la lb
    la=$(libre "$oa"); lb=$(libre "$ob")
    if [ -n "$la" ] && [ -n "$lb" ] && [ "$la" != "0" ]; then
        # dentro del 1%
        awk -v x="$la" -v y="$lb" 'BEGIN{d=(x>y?x-y:y-x); exit !(d<=x*0.01)}' || esp="FUERA_1%($la vs $lb)"
    elif [ "$la" != "$lb" ]; then
        esp="uno_reporto_otro_no($la vs $lb)"
    fi
    local rcs=OK; [ "$ra" = "$rb" ] || rcs=DISTINTO

    # Un caso donde NINGUNO de los dos produjo salida no es un exito: es un caso
    # que no corrio. Sin este guarda, un error de invocacion (rc=127) hacia que
    # toda la matriz "pasara".
    local vac=""
    if [ ! -s "$oa" ] && [ ! -s "$ob" ]; then vac="NO_CORRIO(rc=$ra)"; fi

    local res=PASA
    [ -z "$vac" ] && [ "$esq" = OK ] && [ "$esp" = OK ] && [ "$rcs" = OK ] || res=FALLA
    [ -n "$vac" ] && esq="$vac"
    [ "$res" = PASA ] && ok=$((ok+1)) || bad=$((bad+1))

    printf '%-26s %-6s rc=%-3s/%-3s esq=%-9s esp=%-22s %s\n' \
      "$1" "$cmd" "$ra" "$rb" "$esq" "$esp" "$res"
    echo "$1,$cmd,\"$dest\",$ra,$rb,$esq,$esp,$res" >> "$CSV"
    rm -f "$oa" "$ob" "$oa.n" "$ob.n"
}

echo "===== formas de destino ====="
correr "01-relativo-desnudo"   x "out"
correr "02-relativo-barra"     x "out/"
correr "03-punto-barra"        x "./out/"
correr "04-cadena-inexistente" x "$OUT/out/hondo/mas/hondo/"
correr "05-sin-ancestro"       x "/no-existe-xyz-$$/x/"
correr "06-absoluto"           x "$OUT/out/"
correr "07-dir-existente"      x "$EXIST/"
correr "08-utf8"               x "$UTF8/"
correr "09-ruta-larga"         x "$LARGO/"
correr "10-symlink-a-dir"      x "$OUT/link_a_dir/"
correr "11-sin-permiso"        x "$NOWR/sub/"
correr "12-tmpfs"              x "$SHM/"

echo "===== con -space (bypass) ====="
correr "01-relativo-desnudo"   x "out"                      "-space"
correr "04-cadena-inexistente" x "$OUT/out/hondo/mas/hondo/" "-space"
correr "11-sin-permiso"        x "$NOWR/sub/"                "-space"

echo "===== otros comandos ====="
correr "01-relativo-desnudo"   a "out"
correr "04-cadena-inexistente" a "$OUT/out/hondo/"
correr "06-absoluto"      repack "$OUT/rep.zpaq"
correr "11-sin-permiso"   repack "$NOWR/rep.zpaq"

# --- casos que reprodujeron bugs y no son formas de destino ------------------
# -append sobre archivo EXISTENTE: el use-after-free de vf en jidacreset()
# (arreglado en 65729ab / v64.8j-pre9). En Windows crasheaba con 0xC0000005 y
# perdia el archivo agregado; en Linux se ve como un "02171$ HOUSTON" falso con
# rc=2 en una corrida que escribio todo bien. Se prueba con varias cantidades de
# archivos viejos porque el iterador colgante resolvia a nodos distintos del map
# segun lo que el allocator hubiera reusado.
append_caso() { # $1=N archivos viejos
    local n="$1" nombre="append-N$1"
    local d=$OUT/ap$n arc=$OUT/ap$n.zpaq
    local oa=$OUT/apa.txt ob=$OUT/apb.txt res
    local ra rb

    prep() { rm -rf "$d" "$arc"; mkdir -p "$d"
             local i; for i in $(seq 1 "$n"); do printf 'viejo%02d\n' "$i" > "$d/v$i.txt"; done
             "$1" a "$arc" "$d" -m1 -nomore -t1 >/dev/null 2>&1
             printf 'agregado\n' > "$d/nuevo.txt"; }

    prep "$A"; timeout $TMO "$A" a "$arc" "$d" -m1 -append -nomore -t1 >"$oa" 2>&1; ra=$?
    prep "$B"; timeout $TMO "$B" a "$arc" "$d" -m1 -append -nomore -t1 >"$ob" 2>&1; rb=$?

    { echo "########## append/$nombre"; echo "--- A (rc=$ra) ---"; cat "$oa"
      echo "--- B (rc=$rb) ---"; cat "$ob"; } >> "$LOG"

    local ha hb esq=OK
    ha=$(grep -c 'HOUSTON' "$oa"); hb=$(grep -c 'HOUSTON' "$ob")
    [ "$ha" = "$hb" ] || esq="HOUSTON A=$ha B=$hb"
    local rcs=OK; [ "$ra" = "$rb" ] || rcs=DISTINTO
    res=PASA; [ "$esq" = OK ] && [ "$rcs" = OK ] || res=FALLA
    [ "$res" = PASA ] && ok=$((ok+1)) || bad=$((bad+1))
    printf '%-26s %-6s rc=%-3s/%-3s esq=%-9s esp=%-22s %s\n' \
      "$nombre" "append" "$ra" "$rb" "$esq" "-" "$res"
    echo "$nombre,append,-,$ra,$rb,$esq,-,$res" >> "$CSV"
    rm -rf "$d" "$arc" "$oa" "$ob"
}
echo "===== -append sobre archivo existente (use-after-free de vf) ====="
for n in 1 4 6 7 8 12; do append_caso "$n"; done

chmod 700 "$NOWR" 2>/dev/null
rm -rf "$SHM" 2>/dev/null

echo
echo "===== $((ok+bad)) casos, $ok pasan, $bad fallan ====="
echo "  log: $LOG"
echo "  csv: $CSV"
echo DONE_OSMSGS
[ "$bad" -eq 0 ]
