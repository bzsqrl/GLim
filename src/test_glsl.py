import sys
try:
    from PyQt5 import QtWidgets, QtGui, QtOpenGL
except ImportError:
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "PyQt5"])
    from PyQt5 import QtWidgets, QtGui, QtOpenGL

import OpenGL.GL as gl

app = QtWidgets.QApplication(sys.argv)
widget = QtOpenGL.QGLWidget()
widget.makeCurrent()

fragment_source = """#version 410 core
uniform vec3 iResolution;
uniform float iTime;
uniform float iTimeDelta;
uniform int iFrame;

in vec2 uv;
out vec4 fragColor;

void mainImage( out vec4 fragColor, in vec2 fragCoord )
{
    // Generate an obvious color so we know it rendered
    vec2 uvc = fragCoord/iResolution.xy;
    fragColor = vec4(uvc.x, uvc.y, 0.5, 1.0);
}

void main() {
    vec2 fragCoord = uv * iResolution.xy;
    vec4 finalColor = vec4(0.0);
    
    // FFMaker Wrapper to execute the shader code.
    mainImage(finalColor, fragCoord);
    
    fragColor = finalColor;
}
"""

shader = gl.glCreateShader(gl.GL_FRAGMENT_SHADER)
gl.glShaderSource(shader, fragment_source)
gl.glCompileShader(shader)
status = gl.glGetShaderiv(shader, gl.GL_COMPILE_STATUS)

if status != gl.GL_TRUE:
    log = gl.glGetShaderInfoLog(shader)
    print("Shader compile error:")
    print(log.decode('utf-8'))
else:
    print("Shader compiled successfully in PyOpenGL.")
