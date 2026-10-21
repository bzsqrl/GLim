"""
Bulk-analyze all .fs files in isf-VidVox to understand:
- Pass counts (single vs multi-pass)
- Input types used
- ISF built-ins referenced
- IMAGES/inputs that reference textures (inputImage, etc.)
"""
import os, re, json, collections, sys

folder = r"C:\Users\beatf\Documents\Antigravity\FFMaker\isf-VidVox"
files = sorted(f for f in os.listdir(folder) if f.endswith(".fs"))

HEADER_RE = re.compile(r'/\*\s*\{(.*?)\}\s*\*/', re.DOTALL)

ISF_BUILTINS = [
    "isf_FragNormCoord", "RENDERSIZE", "PASSINDEX", "FRAMEINDEX",
    "TIMEDELTA", "IMG_NORM_PIXEL", "IMG_PIXEL", "gl_FragColor",
    "TIME", "DATE",
]

INPUT_TYPE_COUNTER = collections.Counter()
BUILTIN_COUNTER    = collections.Counter()
pass_counts        = collections.Counter()
image_input_files  = []
multi_pass_files   = []
single_pass_files  = []
parse_errors       = []
type_image_types   = collections.Counter()

for fname in files:
    path = os.path.join(folder, fname)
    try:
        code = open(path, encoding="utf-8", errors="replace").read()
    except Exception as e:
        parse_errors.append((fname, str(e)))
        continue

    m = HEADER_RE.search(code)
    if not m:
        parse_errors.append((fname, "no ISF header"))
        continue

    try:
        data = json.loads("{" + m.group(1) + "}")
    except Exception as e:
        parse_errors.append((fname, f"JSON error: {e}"))
        continue

    passes = data.get("PASSES", [])
    n_passes = max(len(passes), 1)
    pass_counts[n_passes] += 1
    if n_passes > 1:
        multi_pass_files.append((fname, n_passes))
    else:
        single_pass_files.append(fname)

    for inp in data.get("INPUTS", []):
        t = inp.get("TYPE", "?").lower()
        INPUT_TYPE_COUNTER[t] += 1
        if t in ("image", "video", "audiofft", "audio", "cube"):
            type_image_types[t] += 1

    if any(inp.get("TYPE","").lower() in ("image","video","audiofft","audio","cube")
           for inp in data.get("INPUTS", [])):
        image_input_files.append(fname)

    for b in ISF_BUILTINS:
        if b in code:
            BUILTIN_COUNTER[b] += 1

print(f"Total files: {len(files)}")
print(f"Parse errors: {len(parse_errors)}")
print()
print("=== Pass count distribution ===")
for k in sorted(pass_counts):
    print(f"  {k} pass(es): {pass_counts[k]} files")

print()
print("=== Input types (all files) ===")
for t, c in INPUT_TYPE_COUNTER.most_common():
    print(f"  {t:15s}: {c}")

print()
print("=== ISF built-in usage ===")
for b, c in BUILTIN_COUNTER.most_common():
    print(f"  {b:25s}: {c} files")

print()
print("=== Texture/media input types ===")
for t, c in type_image_types.most_common():
    print(f"  {t:15s}: {c} files")

print()
print(f"=== Files with image/media inputs: {len(image_input_files)} ===")

print()
print(f"=== Single-pass files ({len(single_pass_files)}) ===")
for f in single_pass_files[:20]:
    print(f"  {f}")
if len(single_pass_files) > 20:
    print(f"  ... and {len(single_pass_files)-20} more")

print()
print(f"=== Multi-pass files ({len(multi_pass_files)}) ===")
for f, n in multi_pass_files[:30]:
    print(f"  [{n} passes] {f}")
if len(multi_pass_files) > 30:
    print(f"  ... and {len(multi_pass_files)-30} more")

if parse_errors:
    print()
    print("=== Parse errors ===")
    for f, e in parse_errors:
        print(f"  {f}: {e}")
