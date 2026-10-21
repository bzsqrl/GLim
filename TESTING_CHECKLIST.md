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
- `stoy_abstractGlassyField`, `stoy_abstractPlane`, `stoy_alienTech`, `stoy_ancientTemple` use ISF `IMPORTED` texture images, which aren't embedded yet, so their textures read black.
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
