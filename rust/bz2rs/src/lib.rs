//! bzip2 en Rust puro para zpaq-std, como archivo estatico con la API C de libbz2.
//!
//! No hace falta codigo propio: re-exportar el crate alcanza para que sus
//! `#[export_name]` extern "C" queden en el .a. La feature `export-symbols` de
//! libbz2-rs-sys es la que aplica esos `export_name`; sin ella los simbolos
//! salen mangleados en Rust y el enlazador de C no los encuentra.
//!
//! # Windows de 32 bits: hay que declarar la API cdecl
//!
//! `bzlib.h` declara toda su API como `BZ_API(f)` == `WINAPI f` cuando esta
//! definido `_WIN32`, o sea `__stdcall`. En i686 eso decora los nombres con
//! `@<bytes de argumentos>`, asi que zpaq-std pide
//! `_BZ2_bzBuffToBuffDecompress@24` mientras este crate exporta el simbolo cdecl
//! sin decorar, y el enlace falla. En x86_64 no existe la decoracion (hay una
//! sola convencion) y enlaza directo: el problema aparece SOLO en 32 bits.
//!
//! La solucion es compilar zpaq-std con `-DBZ_RS_CDECL` (ver bzlib.h en esta
//! rama), que declara la API cdecl. Es lo razonable igual: el header pertenece a
//! la libreria que estamos reemplazando.
//!
//! Lo que NO funciona, y conviene que quede escrito: exportar shims
//! `extern "stdcall"` con los nombres decorados. Enlazan bien -- se puede
//! comprobar que el .a define `_BZ2_bzBuffToBuffDecompress@24` -- y despues el
//! binario muere en un `ud2` en tiempo de ejecucion, sin mensaje de panico, solo
//! en la ruta de bzip2 (`-m1` y `-ma:zstd` funcionan). Dos detalles del camino:
//! Rust decora solo los `extern "stdcall"`, asi que poner el `@N` a mano produce
//! `..._@24@24`; y con el `@N` correcto igual crashea. No se investigo mas
//! porque cdecl resuelve el caso de raiz.
pub use libbz2_rs_sys::*;
