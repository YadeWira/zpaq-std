# Laboratorio de pruebas de zpaq-std

Los **scripts** viven acá (versionados). Los **datos** (corpus, golden, binarios
de referencia) viven en `/mnt/IA_LAB/agentes/ZPAQ-STD/testlab/`, que es un solo
disco sin redundancia y **explícitamente no es un respaldo** — por eso los
manifiestos de sha256 están acá: si los datos se corrompen o cambian, se detecta.

## Las cuatro herramientas, y por qué son cuatro

Miden cosas distintas y ninguna reemplaza a otra.

### `difftest.sh <binA> <binB> [tag]` — equivalencia entre dos binarios

Corre los dos sobre el corpus y verifica 4 propiedades: bit-exactitud del
archivo, A lee lo de B, B lee lo de A, y mismo veredicto de `l`/`t`.

**Su límite**: regenera el archivo de A con el binario de **hoy**, así que no
ancla nada a los bytes que existen en producción. Y compara el stdout de `l`
únicamente, filtrado.

**La bit-exactitud es un diagnóstico, no un requisito** — ver la cabecera del
script. Hay que leer el CSV por columna, no el veredicto agregado.

### `golden_gate.sh gen|check|list` — compatibilidad con la era de producción

Archivos `.zpaq` escritos por binarios **publicados** (pre9 en Linux y pre9 x64
bajo wine), que cada build candidato tiene que extraer con contenido idéntico y
`t` en 0.

Es lo único que verifica que el build de hoy lee lo que escribió una versión
liberada. Existen archivos de 46 GB en producción (caso CLAAS) y hasta ahora
ningún test cubría eso.

Dos guardas que abortan la corrida: si un golden cambió respecto de su sha256, o
si el corpus no es el que se usó para generarlos.

Y una **lista de fallos esperados** por set (`KNOWN_FAIL`): golden que no pueden
pasar porque el bug está en los bytes del archivo histórico y no en el binario
que los lee. Sin declararlos, un gate con fallos permanentes se lee como ruido y
deja de servir. La lista sólo **degrada** un fallo real: un lector que sí pase
ese caso lo sigue contando como éxito.

### `os_msgs.sh <binA> <binB> [tag]` — formas de destino y mensajes numerados

25 casos. Cubre lo que `difftest` no mira: los mensajes numerados (`00067!`,
`00071:`, `00877!`, `00935!`…) y las **formas de destino** que produjeron los
bugs de `v64.8j-pre9` — nombre relativo desnudo, cadena inexistente, ruta sin
ancestro, UTF-8, ruta larga, symlink, directorio sin permiso de escritura. Más
6 casos de `-append` sobre archivo existente, que es el use-after-free de `vf`.

Validación de la propia suite: **25/25 contra sí mismo**, **25/25 entre pre9 y
pre10** (que son equivalentes en comportamiento), y **6 detecciones** contra el
binario previo a los arreglos. Una suite que no falla en el binario con bugs no
prueba nada.

## `pin_corpus.sh [verify]` — sin esto lo demás no vale

Las suites `suite_cmds/robust/extra/ytool` **regeneran** su corpus base con
`find | head`, que elige archivos distintos entre corridas. Eso ya invalidó una
comparación de tamaños: dos binarios "distintos" que en realidad habían
comprimido entradas distintas. `golden_gate.sh` se niega a correr si el corpus no
coincide con el manifiesto.

## Lo que el golden gate encontró en su PRIMERA corrida

Dos grupos de 16 fallos, con causas distintas. Ninguno es una regresión de pre10:
los dos existen en las versiones publicadas.

### `wtou` no combinaba pares surrogados — ARREGLADO

Encontrado por `golden_gate.sh` en su primera corrida y **arreglado el mismo
día**: los 16 golden del caso `intl` escritos por el binario de **Windows**
fallaban al extraerse en **Linux**, en todos los métodos. `x` y `t` daban 0; lo
que difería era el nombre del archivo.

```
original / escrito en Linux:  emoji-🎉🔥.txt   f0 9f 8e 89  f0 9f 94 a5
escrito en Windows:           emoji-????.txt   ed a0 bc ed be 89  ed a0 bd ed b4 a5
```

Eso es **CESU-8**, no UTF-8: cada surrogate va como su propia secuencia de 3
bytes. `wtou` (zpaq-std.cpp:23715) emite 3 bytes para toda unidad UTF-16 ≥ 2048,
**incluidos los surrogates U+D800–U+DFFF**, sin combinarlos. Su inverso `utow`
(:2526) **sí** los maneja bien, con código explícito para las secuencias de 4
bytes — el par es asimétrico.

Consecuencias:

| camino | resultado |
|---|---|
| Windows → Windows | funciona **por casualidad**: `utow` deshace la misma conversión rota |
| Windows → archivo → Linux u otra herramienta | **nombre corrupto**, y el archivo guarda UTF-8 inválido |
| Linux → archivo → Windows | correcto (`utow` está bien) |

Afecta a todo nombre con un carácter fuera del BMP: emoji, CJK a partir de la
extensión B, buena parte de los símbolos matemáticos y musicales, y varias
escrituras históricas. Ni ș/ț rumanos ni CJK del BMP ni griego ni cirílico se
ven afectados — por eso no se había notado.

Es de la misma familia que el caso CLAAS: la frontera con el sistema operativo.

**El arreglo**: `wtou` combina el par y emite 4 bytes. Un surrogate **huérfano**
(alto sin bajo, o bajo suelto) se deja **a propósito** en su forma de 3 bytes:
no es representable en UTF-8, NTFS los admite, y esa forma es exactamente la que
`utow` revierte — mapearlo a `'?'` (que es lo que `utow` hace con entrada
inválida) perdería el nombre del archivo.

Medido: nombres correctos **2/5 → 5/5** (emoji, matemáticos y CJK extensión B);
bytes guardados `ed a0 bc ed be 89` → `f0 9f 8e 89`; y un archivo **viejo** con
nombres en CESU-8 leído por el binario arreglado **sigue dando los nombres
originales**, o sea que no repara retroactivamente los bytes de un `.zpaq` ya
creado pero tampoco rompe su lectura.

**Los golden pre-arreglo no pueden pasar y no deben**: el bug está en los bytes
del archivo histórico, no en el lector. Están declarados en
`golden-pre9-win64-KNOWN_FAIL.txt`. La prueba de punta a punta es el set
`win64-postfix`, escrito con el binario arreglado: **116/116 sin un solo fallo
esperado**, contra 16 del set anterior.

### Archivos que difieren sólo en mayúsculas — ARREGLADO

Los otros 16 fallos son el caso `mixed` leído por un binario de **Windows**.
`corpus/mixed` tiene `demo.PQL` y `Demo.PQL`.

Que un filesystem case-insensitive no pueda tener los dos a la vez es una
limitación inherente, no un defecto: **el árbol extraído nunca va a ser idéntico
al original**, así que esos 16 golden fallan para siempre y está bien. Están
declarados en `golden-*-KNOWN_FAIL.txt`.

Lo que **sí** era un defecto es lo que pasaba con la colisión, y tenía tres
causas en las mismas 30 líneas de `Jidac::casekollision`:

1. **El nombre corregido se construía sobre `rename(p->first)`** —la ruta de
   SALIDA, con el `-to` ya aplicado— y se guardaba como **clave de `dt`**, que
   vuelve a pasar por `rename()` al extraer. El prefijo quedaba aplicado dos
   veces, y con tres nombres colisionando hasta **tres**:

   ```
   ./tmp/x/src/DEMO.pql                                        <- 1 de 3
   ./Z/tmp/x/o/tmp/x/src/Demo_00000001.PQL                     <- duplicada
   ./Z/tmp/x/o/Z/tmp/x/o/.../demo_00000001_00000001.PQL        <- triplicada
   ```

2. **La unicidad del candidato se probaba hasheando `rifatto` crudo**, cuando el
   set guarda el nombre de salida en minúsculas: nunca podía coincidir, así que
   se aceptaba siempre el primer candidato y dos colisiones distintas se
   quedaban las dos con `_00000001`.

3. **`rifatto` no se reiniciaba** dentro del bucle cuando el archivo está en la
   raíz del archivo, así que el nombre se acumulaba entre iteraciones.

Y el reporte: `casekollision()` llena su lista de "no arreglados" **sólo** cuando
`i_fix` es false, y `extract()` la llama con true. La lista quedaba siempre vacía,
así que la corrida decía `00903: No unfixed case collision` mientras renombraba
archivos, y el mensaje `00902` era inalcanzable. Ahora dice
`00902: Case collisions renamed N files`.

**Trampa al arreglarlo, que costó un cuelgue**: `changedtmapkey()` inserta en el
mismo `map` que el bucle está recorriendo, y la clave nueva puede ordenar después
del iterador actual — el bucle terminaba visitando la entrada que él mismo había
creado. Eso ya pasaba antes (de ahí el `_00000001_00000001`), pero al registrar
el hash del nombre elegido —necesario para arreglar la causa 2— se volvió un
**bucle infinito**: el binario colgaba, detectado con `rc=124`. La solución es
estructural: **acumular los renombres y aplicarlos DESPUÉS del recorrido**, así
el bucle no ve sus propias inserciones.

## El set `pc-legacy`: para qué existe

`-pc` se quitó como **encoder** en pre13, pero el **decoder** se queda: los
archivos ya creados contienen contenedores PCF, y revertirlos re-encodea para
probar que son auténticos (así un archivo verbatim que casualmente empieza con
`zPCF` no se "revierte" por error). Eso obliga a que preflate y la zlib
vendorizada sigan compilándose.

`golden/pc-legacy` son 6 archivos `-pc` escritos por **pre12**, el último binario
capaz de crearlos. Todo build posterior tiene que extraerlos byte a byte. Es la
única garantía de que los archivos que existen en producción no queden ilegibles,
y no se puede regenerar: hay que conservarlos.

Se generó ANTES de tocar el código, que es el único momento en que era posible.

## Trampas que cuestan horas si no están escritas

- **`myprintf` no es thread-safe.** Con `-debug3` y varios hilos la salida sale
  entrelazada **a nivel de carácter**. Toda comparación de stdout necesita `-t1`.
- **`-timestamp` no fija la fecha `jDC`.** Cada bloque journaling lleva
  `jDC` + `YYYYMMDDHHMMSS` del reloj, en 4 lugares. Dos corridas que cruzan un
  segundo dan 4 bytes distintos en archivos por lo demás idénticos. Lo normaliza
  `norm_jdc.py`, que usa `difftest.sh`.
- **El `-debug3` de `a` vuelca bytes aleatorios** en la línea
  `unecrypted on [ENCRYPT @ N]` (zona de sal/clave). No determinista por diseño.
- **`FULL exename` es `argv[0]`**: difiere entre A y B por definición.
- **`make clean` no borra los `.o`.** Entre cross-compiles:
  `find . -name '*.o' -delete && rm -f win/*.o`.
- **Ante una diferencia entre A y B, correr primero A contra A.**
- **No mutar un contenedor mientras se lo itera.** `changedtmapkey()` inserta en
  el `map` que el bucle recorre, así que el bucle visita sus propias
  inserciones. Un arreglo que además registraba el nombre elegido convirtió eso
  en un bucle infinito (`rc=124`). Acumular y aplicar después. Es lo que
  evitó atribuirle a Rust los 4 bytes del sello `jDC`.
- **Que Linux compile no significa que esté bien.** Un macro `MAX` que en Linux
  llegaba de glibc rompió los dos targets MinGW. Verificar los tres siempre.
- **Un `.exe` bajo wine no resuelve una ruta Linux desnuda como `-to`**:
  `getfreespace` devuelve 0 y aborta con `00935!`. wine mapea `/` en la unidad
  `Z:`, así que hay que prefijarlo. Sin eso los tres `.exe` fallan el 100% de los
  golden por culpa del harness. Lo hace `golden_gate.sh` solo.
- **`rc=$?` después de un pipe es el estado del último comando del pipe**, no del
  programa. Ya llevó a reportar un `-append` como exitoso cuando había fallado.

## Manifiestos acá

| archivo | qué fija |
|---|---|
| `corpus-MANIFEST.sha256` | los 2.147 archivos del corpus |
| `refbin-SHA256SUMS.txt` | los 6 binarios publicados de pre9/pre10 |
| `golden-pre9-linux.sha256` | 136 golden escritos por pre9 en Linux |
| `golden-pre9-win64.sha256` | 116 golden escritos por pre9 x64 en Windows (pre-arreglo de `wtou`) |
| `golden-win64-postfix.sha256` | 116 golden escritos con `wtou` arreglado — 116/116 en Linux |
| `golden-pc-legacy.sha256` | 6 golden hechos **con `-pc`** por pre12, el último binario que podía crearlos |
| `golden-*-KNOWN_FAIL.txt` | fallos esperados por set, con el motivo |
| `golden-*-ORIGEN.txt` | con qué binario y cuándo se generó cada set |
