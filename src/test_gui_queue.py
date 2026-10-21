import sys, os, tempfile
sys.path.insert(0, 'src')
from pathlib import Path

def detect_format(path):
    ext = Path(path).suffix.lower()
    if ext == '.fs':   return 'ISF (.fs)'
    if ext == '.txt':  return 'Shadertoy'
    try:
        header = open(path, encoding='utf-8', errors='replace').read(2000)
        if '/*{' in header or '/*\n{' in header or '/* {' in header:
            return 'ISF (.fs)'
        if 'void mainImage' in header:
            return 'Shadertoy'
    except Exception:
        pass
    return 'ISF (.fs)'

samples = [
    ('KaleidoKnot.fs',             'ISF (.fs)'),
    ('isf-VidVox/Checkerboard.fs', 'ISF (.fs)'),
    ('isf-VidVox/Noise.fs',        'ISF (.fs)'),
]

print('detect_format tests:')
for path, expected in samples:
    got = detect_format(path)
    status = 'OK' if got == expected else 'FAIL (got %s)' % got
    print('  [%s] %s' % (status, path))

# .txt -> Shadertoy
with tempfile.NamedTemporaryFile(suffix='.txt', delete=False, mode='w') as f:
    f.write('void mainImage(out vec4 fragColor, in vec2 fragCoord) {}')
    tmp = f.name
got = detect_format(tmp)
os.unlink(tmp)
print('  [%s] .txt -> Shadertoy (got %s)' % ('OK' if got == 'Shadertoy' else 'FAIL', got))

print()
print('Import check (no GUI launch):')
# Just check the module parses without error
import ast
src = open('src/main_gui.py', encoding='utf-8').read()
try:
    ast.parse(src)
    print('  [OK] main_gui.py parses cleanly')
except SyntaxError as e:
    print('  [FAIL] SyntaxError:', e)
