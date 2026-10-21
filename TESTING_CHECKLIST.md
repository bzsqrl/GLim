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
