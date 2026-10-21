import sys, json, re
sys.path.insert(0, 'src')
from parser import parse_isf

code = open('KaleidoKnot.fs', 'r', encoding='utf-8').read()
result = parse_isf(code)

print('Error:', result.get('error', 'None'))
inputs = result.get('inputs', [])
print(f'Inputs: {len(inputs)}')

# Re-parse header to check for PASSES
m = re.search(r'/\*\{(.*?)\}\*/', code, re.DOTALL)
if m:
    data = json.loads('{' + m.group(1) + '}')
    passes = data.get('PASSES', [])
    print(f'PASSES: {len(passes)}')
    for p in passes:
        print(f'  {p}')

# Check for ISF built-ins in body
builtins = ['isf_FragNormCoord', 'RENDERSIZE', 'PASSINDEX', 'FRAMEINDEX',
            'TIMEDELTA', 'IMG_NORM_PIXEL', 'IMG_PIXEL', 'gl_FragColor']
for b in builtins:
    if b in code:
        print(f'Uses ISF builtin: {b}')
