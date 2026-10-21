import sys
try:
    from PyQt5 import QtWidgets, QtGui, QtOpenGL
except ImportError:
    pass
import OpenGL.GL as gl

app = QtWidgets.QApplication(sys.argv)
widget = QtOpenGL.QGLWidget()
widget.makeCurrent()

vertex_source = """#version 410 core
uniform vec2 MaxUV;
layout( location = 0 ) in vec4 vPosition;
layout( location = 1 ) in vec2 vUV;
out vec2 uv;
void main()
{
	gl_Position = vPosition;
	uv = vUV;
}
"""

fragment_source = """#version 410 core
uniform vec3 iResolution;
uniform float iTime;
uniform float iTimeDelta;
uniform int iFrame;

in vec2 uv;
out vec4 fragColor;

void mainImage( out vec4 fragColor, in vec2 fragCoord )
{
    vec2 uvc = fragCoord/iResolution.xy;
    fragColor = vec4(uvc.x, uvc.y, 0.5, 1.0);
}

void main() {
    vec2 fragCoord = uv * iResolution.xy;
    vec4 finalColor = vec4(0.0);
    mainImage(finalColor, fragCoord);
    fragColor = finalColor;
}
"""

vs = gl.glCreateShader(gl.GL_VERTEX_SHADER)
gl.glShaderSource(vs, vertex_source)
gl.glCompileShader(vs)

fs = gl.glCreateShader(gl.GL_FRAGMENT_SHADER)
gl.glShaderSource(fs, fragment_source)
gl.glCompileShader(fs)

program = gl.glCreateProgram()
gl.glAttachShader(program, vs)
gl.glAttachShader(program, fs)
gl.glLinkProgram(program)

status = gl.glGetProgramiv(program, gl.GL_LINK_STATUS)
if status != gl.GL_TRUE:
    log = gl.glGetProgramInfoLog(program)
    print("Shader link error:")
    print(log.decode('utf-8'))
else:
    print("Shader linked successfully.")
