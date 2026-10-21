import os
import sys

# Test script to compile a solid color shader
from builder import build_plugin

payload = {
    "code": """
void mainImage( out vec4 fragColor, in vec2 fragCoord )
{
    // Generate an obvious color so we know it rendered
    vec2 uv = fragCoord/iResolution.xy;
    fragColor = vec4(uv.x, uv.y, 0.5, 1.0);
}
""",
    "inputs": []
}

out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "boilerplates")
res = build_plugin(payload, out_dir)
print(res)
