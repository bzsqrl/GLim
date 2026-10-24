# Test batch v1: checklist

Location: `output/test_batch_v1/`. It contains 79 FFGL `.dll` files plus 40 `.fs` ISF exports. The build log is `output/batch_v1_log.txt`.

## Resolume (7.21.3+)

1. Copy the `.dll` files into a folder Resolume scans for FFGL plugins, then restart Resolume.
2. Look for them in **Sources** (generators) and **Effects**. ISF transitions (`vv_circleCrop`, `vv_circleOpen`, `vv_butterflyWaveScrawler`) are built as **mixers**, so look under the blend-mode / mixer lists.

For each plugin, check the following and note anything odd:

| Check | What "good" looks like |
| :-- | :-- |
| Loads | Appears in the browser; no error in Resolume's log |
| Renders | Shows an image, not black or transparent |
| Animates | Generators move. Animation speed shouldn't change with frame rate. |
| Speed slider | Changes animation speed smoothly, with no jump when you move it |
| Parameters | Sliders show real values and ranges; dropdowns show labels; color pickers start at the right color |
| Effects | Process the clip underneath. Check that the image isn't offset or scaled wrongly, and is the right way up. |
| Mixers | The crossfader / transition drives `progress` |
| Resize | Changing the composition resolution doesn't break anything |

A few interesting ones to try first:
- `new_fluidFrame3`: multi-pass feedback; the old version rejected it
- `vv_brokenLCD`: dropdowns, color pickers, many params
- `vv_chromaMask`: multi-pass effect
- `stoy_topologica`: Shadertoy effect using the clip input
- `cc0_oversaturatedWeb_cdccRl`: constants turned into sliders
- `vv_circleOpen`: transition as a mixer

Known gaps (expected, not bugs):
- *(Fixed since v1.)* `stoy_abstractGlassyField`, `stoy_abstractPlane`, `stoy_abstractWaterTunnel`, `new_fireworks` and `vv_70tiesMaelstrom` reference `IMPORTED` images that aren't in `sample-shaders/`. Rebuilt now, they get a noise texture plus a warning; with the image files present, the images are embedded.
- `vv_butterflyWaveScrawler` renders flat colors. The original shader computes `pow()` of a negative number, which gives NaN on NVIDIA in any host.

## MadMapper (ISF exports)

Load the `.fs` files from the same folder. Check that they compile, render and animate, and that inputs (Speed, sliders, colors) behave. Shadertoy effects expect an input image (`inputImage`).


---

# Test batch v2: new features

Location: `output/test_batch_v2/`. It has 7 FFGL plugins, the matching ISF files, and the `img/` folder that `imported_texture.fs` needs.

| Plugin | What to check |
| :-- | :-- |
| `imported_texture` | A dark-blue image with a **red band at the top**. This checks that embedded images are the right way up. |
| `isf_vertex_blur` | Effect. Blurs the clip; the **Width** slider changes the blur amount. Uses a `.vs` vertex shader. |
| `shadertoy_channels` | Effect. Left half shows the clip, right half shows a repeating red/blue image, plus a little noise shimmer. |
| `shadertoy_multipass` | An orange dot leaving a **fading trail**. Buffer feedback works if the trail persists; the **Trail** slider sets its length. |
| `shadertoy_mult~2` | Same shader, built from the Shadertoy **JSON** form. Should look identical. |
| `shadertoy_audio` | Spectrum bars that react to music. |
| `isf_audiofft` | Spectrum bars that react to music; the **Gain** slider scales them. |

**Audio in Resolume:** the plugins have an **Audio Spectrum** parameter. Resolume feeds it from the composition or layer audio, or whatever audio source you assign in the parameter's audio settings. With no audio playing, the bars stay flat. That's expected.

**MadMapper:** load the `.fs` files from the same folder. Keep the `.png`, `.vs` and `img/` files next to them. `shadertoy_multipass.fs` exercises ISF multi-pass feedback; the two audio files need MadMapper's audio input.

---

# Test batch v3: sampler settings and tempo

Location: `output/test_batch_v3/` (rebuild with `venv/bin/python -m ffstudio --to both --out output/test_batch_v3 tests/fixtures/shadertoy_sampler.txt tests/fixtures/shadertoy_buffer_sampler.txt tests/fixtures/shadertoy_tempo.txt`). It has 3 FFGL plugins and the matching ISF files.

| Plugin | What to check |
| :-- | :-- |
| `shadertoy_sampler` | Three panels, left to right: a **sharp** 4×4 checker with a red square top-left; the same image **soft and tiled 2×2**; sharp again but **upside down** (red square bottom-left). |
| `shadertoy_buffer` | Left half: **16 small orange discs**, smooth-edged. Right half: **one disc** in the bottom-left corner, black elsewhere. |
| `shadertoy_tempo` | Left half brightens over each **bar**, then drops; right half **flashes on every beat**. Change Resolume's BPM and both follow. |

**MadMapper:** load the `.fs` files from the same folder, keeping the `.png` files next to them. `shadertoy_sampler` should look the same as in Resolume (the tiled panel may show faint seams at tile edges). In `shadertoy_buffer` the small discs may look a little more jagged, since ISF has no mipmaps. `shadertoy_tempo` has a **BPM** slider; at 120 the right half flashes twice a second.

---

# Test batch v4: smooth sliders and `#define` channels

Location: `output/test_batch_v4/`. Rebuild it with the command in [MAC_UPDATE.md](MAC_UPDATE.md), step 4. It has 4 FFGL plugins and the matching ISF files. Windows: all four pass FFStudio's test host. macOS: all four pass the test host, and the user confirmed them in Resolume and MadMapper (2026-10-21). Resolume finds plugins in a saved set by their FFGL plugin ID, not their bundle ID: a set still loads a rebuilt plugin after its bundle ID changed (checked on macOS, 2026-10-23).

| Plugin | What to check |
| :-- | :-- |
| `bare_fractalSymetry` | Moving **Speed**, **Time Scale** or **View Rotation Factor Input** changes the speed **without jumping** the animation. |
| `bare_lopyfrac3dOrthofractalEvolution` | **Speed** and **Rotation Speed X/Y/Z** change the speed without jumps. |
| `shadertoy_rate_params` | **Rate**, **Rate2** and **Wobble** change the speed without jumps. |
| `shadertoy_define_channel` | A blue dot circling with a fading trail, brighter with audio. Its channels are only used inside `#define`s. |

**MadMapper:** the `.fs` files render like the plugins, but the speed and rate sliders **still jump** the animation. That's expected: ISF exports keep the plain time × slider product.
