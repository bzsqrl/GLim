"""ShaderIR: the single internal description every front-end produces and
every emitter consumes."""
from dataclasses import dataclass, field


@dataclass
class Param:
    name: str                 # GLSL uniform name ("" for CPU-only params such as Speed)
    kind: str                 # float | int | bool | event | long | color | point2D | speed | mouse
    label: str = ""
    default: object = 0.0
    min: object = None
    max: object = None
    glsl_type: str = "float"  # float | int | bool | vec2 | vec3 | vec4
    labels: list = None       # long: option labels
    values: list = None       # long: option values
    pixel_space: bool = False # point2D: value is in pixels (ISF default when MIN/MAX absent)
    origin: str = "isf"       # isf | const | define | uniform | synthetic
    hidden: bool = False      # user chose not to expose it: compiled in as a constant
    source_default: object = None  # the shader's own default, before .ffstudio.json overrides

    def display(self):
        return self.label or humanize(self.name)


@dataclass
class Image:
    name: str                 # sampler uniform name used by the shader code
    source: str = "host"      # host | imported | audio | none | target (another name for a pass target)
    index: int = 0            # host input index
    path: str = ""            # imported image path
    repeat: bool = True       # wrap mode for imported images
    noise_size: int = 256     # size of generated noise when the file is missing
    rows: int = 1             # audio: 1 = spectrum (ISF), 2 = spectrum + wave (Shadertoy)
    isf_type: str = ""        # original ISF input type (audio / audioFFT) for re-export
    filter: str = ""          # "" (source default) | nearest | linear | mipmap (Shadertoy sampler)
    wrap: str = ""            # "" (source default) | clamp | repeat; imported images use `repeat`
    flip: bool = True         # imported: load upright (Shadertoy vflip)
    target: str = ""          # source "target": the pass target this sampler reads


@dataclass
class Pass:
    target: str = None        # None = final output
    persistent: bool = False
    float: bool = False
    width: str = None         # ISF size expressions, e.g. "$WIDTH/2.0"
    height: str = None
    program: int = 0


@dataclass
class Program:
    code: str                 # transformed user code (line-preserving)
    entry: str                # "main" (renamed to ffm_main) or "mainImage"
    aliases: dict = field(default_factory=dict)   # name -> host symbol key
    hoisted: list = field(default_factory=list)   # assignment statements for ffm_init()
    force_opaque: bool = False
    label: str = ""           # pass name for multi-program shaders ("Buffer A")
    line_offset: int = 0      # lines of shared code (Common) prepended before the pass
    channels: list = None     # Shadertoy: sampler name feeding iChannel0..3
    prelude: str = ""         # code placed before the user's (ISF .vs vertex logic)


@dataclass
class Phase:
    """time * (float params) in the shader, replaced by a running total the host
    keeps (total += product of the params' values * frame time). Moving one of
    those sliders then changes the rate instead of jumping the animation."""
    name: str                 # uniform the shader reads, e.g. ffm_phase0
    params: tuple             # param names multiplied together (repeats allowed)


@dataclass
class ShaderIR:
    name: str
    dialect: str              # isf | shadertoy | glsl
    kind: str = "source"      # source | effect | mixer
    programs: list = field(default_factory=list)
    params: list = field(default_factory=list)
    images: list = field(default_factory=list)
    passes: list = field(default_factory=list)
    meta: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)
    promoted: list = field(default_factory=list)   # names promoted from consts/defines
    phases: list = field(default_factory=list)     # Phase: time * params, accumulated by the host

    def phase(self, params):
        """Name of the Phase for these params, creating it if needed."""
        key = tuple(sorted(params))
        for ph in self.phases:
            if ph.params == key:
                return ph.name
        self.phases.append(Phase(f"ffm_phase{len(self.phases)}", key))
        return self.phases[-1].name

    def param(self, name):
        return next((p for p in self.params if p.name == name), None)


def humanize(name: str) -> str:
    import re
    s = name.strip("_")
    s = re.sub(r"_+", " ", s)
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", s)
    words = s.split()
    out = []
    for w in words:
        out.append(w.capitalize() if w.isupper() and len(w) > 1 else w[:1].upper() + w[1:])
    return " ".join(out) or name
