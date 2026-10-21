import os, re, json

folder = r'C:\Users\beatf\Documents\Antigravity\FFMaker\isf-VidVox'
HEADER_RE = re.compile(r'/\*\{(.*?)\}\*/', re.DOTALL)

samples = ['Noise.fs', 'Color Invert.fs', 'Bright.fs', 'Bad TV.fs', 'Checkerboard.fs', 'Noise Displace.fs']
for fname in samples:
    path = os.path.join(folder, fname)
    if not os.path.exists(path):
        print(fname, '-- not found'); continue
    code = open(path, encoding='utf-8', errors='replace').read()
    m = HEADER_RE.search(code)
    if not m:
        print(fname, '-- no header'); continue
    data = json.loads('{' + m.group(1) + '}')
    inputs = data.get('INPUTS', [])
    passes = data.get('PASSES', [])
    print(f'=== {fname} ({len(passes)} passes, {len(inputs)} inputs) ===')
    for inp in inputs:
        t = inp.get('TYPE', '?')
        n = inp.get('NAME', '?')
        print(f'  {t:10s}  {n}')
    body_start = code.find('}*/') + 3
    body = code[body_start:].strip()
    for line in body.splitlines()[:20]:
        print(' ', line)
    print()
