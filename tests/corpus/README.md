# Test corpus

The shaders `tests/run_corpus.py` converts, compiles and renders by default. Every one is public domain (CC0), apart from the few small snippets listed under *Third-party snippets*, which are under permissive licences.

| Files | Source | Licence |
| :-- | :-- | :-- |
| `cc0_*.txt` | Shadertoy shaders by mrange. Each starts with its Shadertoy link and author, and the shader's own CC0 notice. | CC0 1.0 |
| `stoy_topologica.txt` | "Topologica" by Otavio Good, from Shadertoy. Its CC0 notice is at the top of the file. | CC0 1.0 |
| `glim_*.fs`, `glim_*.txt`, `llm_*` | Written for GLim. The `glim_` files each say which formats and features they test. | CC0 1.0 |

What the corpus covers, by dialect:

- **Shadertoy:** `mainImage`, `iMouse`, `iChannel`, constants promoted to parameters.
- **GLSL Sandbox / plain GLSL:** `time`, `mouse` and `resolution` uniforms with a `GL_ES` precision block (`glim_sandboxPlasma`, which also has a struct and a const array); `surfacePosition` / `surfaceSize` (`glim_sandboxSurface`); `u_time`, `u_resolution`, `u_mouse` in pixels (`glim_uniformRipples`).
- **ISF:** generators and effects; version 1 headers with `IDENTITY` values, `vv_FragNormCoord`, `IMG_THIS_PIXEL` and `DATE` (`glim_legacyTint`); transitions, which become 2-input mixers (`glim_wipeTransition`); multi-pass with and without persistent buffers (`glim_twoPassBloom`, `glim_feedbackTrails`, `glim_meltEcho`); bool, long, color, point2D and event inputs.

`tests/fixtures/` covers the rest: imported images, audio, ISF vertex shaders, multi-pass Shadertoy projects and channel directives.

## Third-party snippets

Some mrange shaders include small helper functions by others. Each is credited where it appears.

- **Inigo Quilez:** `pmin` in `cc0_2DAmoebasEdit`, `rot` and `box` in `cc0_crapMaxHeadroom`, and `dcross` in `cc0_levelsJerry`. From [iquilezles.org](https://iquilezles.org/articles/), under the MIT licence below.
- **Mercury (hg_sdf):** `mod2` in `cc0_2DAmoebasEdit` and `mod3` in `cc0_crapMaxHeadroom`. From [mercury.sexy/hg_sdf](https://mercury.sexy/hg_sdf/), offered as "MIT or CC BY-NC 4.0"; used here under the MIT licence below.
- **Sam Hocevar:** `hsv2rgb` in several files. From [Stack Overflow](https://stackoverflow.com/a/17897228/418488), under the WTFPL, which places no conditions on use.

The MIT licence for the Inigo Quilez and Mercury snippets:

> Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
>
> The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
>
> THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
