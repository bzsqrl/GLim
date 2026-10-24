"""Scope-aware GLSL tokenizer and light structural analysis.

All source rewriting in FFStudio goes through this module instead of ad-hoc
regexes. Edits replace token text in place and always preserve newlines, so
line numbers in compiler errors still match the user's original file.
"""
import re
from dataclasses import dataclass, field

_TOKEN_RE = re.compile(r"""
 (?P<comment>//[^\n]*|/\*.*?(?:\*/|\Z))
|(?P<preproc>^[ \t]*\#(?:[^\n\\]|\\.|\\\n)*)
|(?P<nl>\n)
|(?P<ws>[ \t\r\f\v]+)
|(?P<number>0[xX][0-9a-fA-F]+[uU]?|(?:\d+\.\d*|\.\d+|\d+)(?:[eE][+-]?\d+)?(?:lf|LF|[fFuU])?)
|(?P<ident>[A-Za-z_]\w*)
|(?P<punct><<=|>>=|\+\+|--|<<|>>|<=|>=|==|!=|&&|\|\||\^\^|\+=|-=|\*=|/=|%=|&=|\|=|\^=|.)
""", re.S | re.M | re.X)

TRIVIA = ("ws", "nl", "comment")


class Tok:
    __slots__ = ("kind", "text")

    def __init__(self, kind, text):
        self.kind = kind
        self.text = text

    def __repr__(self):
        return f"Tok({self.kind},{self.text!r})"


def tokenize(src: str) -> list:
    toks = []
    pos = 0
    n = len(src)
    while pos < n:
        m = _TOKEN_RE.match(src, pos)
        toks.append(Tok(m.lastgroup, m.group()))
        pos = m.end()
    return toks


def untokenize(toks) -> str:
    return "".join(t.text for t in toks)


def blank(toks, i, j):
    """Remove tokens i..j inclusive, keeping their newlines."""
    for k in range(i, j + 1):
        toks[k].text = "\n" * toks[k].text.count("\n")
        toks[k].kind = "ws" if toks[k].text == "" else "nl"


# ── GLSL vocabulary ──────────────────────────────────────────────────────────

TYPES = {
    "void", "bool", "int", "uint", "float", "double",
    "vec2", "vec3", "vec4", "bvec2", "bvec3", "bvec4", "ivec2", "ivec3", "ivec4",
    "uvec2", "uvec3", "uvec4", "dvec2", "dvec3", "dvec4",
    "mat2", "mat3", "mat4", "mat2x2", "mat2x3", "mat2x4", "mat3x2", "mat3x3",
    "mat3x4", "mat4x2", "mat4x3", "mat4x4",
    "sampler2D", "sampler3D", "samplerCube", "sampler2DRect", "sampler2DArray",
    "isampler2D", "usampler2D", "sampler1D", "sampler2DShadow",
}

QUALIFIERS = {
    "const", "uniform", "in", "out", "inout", "varying", "attribute", "highp",
    "mediump", "lowp", "precise", "invariant", "flat", "smooth", "noperspective",
    "centroid", "layout", "buffer", "shared", "coherent", "volatile", "restrict",
    "readonly", "writeonly", "patch", "sample",
}

# Identifiers that are reserved/keywords in desktop GLSL 4.10 core but were
# legal identifiers in GLSL ES 1.00 (WebGL1 / GLSL Sandbox) or ES 3.00 code.
RESERVED_IN_410 = {
    "input", "output", "sample", "filter", "common", "partition", "active",
    "buffer", "shared", "resource", "patch", "subroutine", "smooth", "flat",
    "noperspective", "centroid", "precise", "coherent", "volatile", "restrict",
    "readonly", "writeonly", "superp", "double", "dvec2", "dvec3", "dvec4",
    "texture1D", "image1D", "image2D", "image3D", "union", "enum", "typedef",
    "template", "this", "goto", "inline", "noinline", "public", "static",
    "extern", "external", "interface", "long", "short", "half", "fixed",
    "unsigned", "cast", "namespace", "using", "sizeof", "packed", "row_major",
    "dmat2", "dmat3", "dmat4", "hvec2", "hvec3", "hvec4", "fvec2", "fvec3", "fvec4",
}

BUILTIN_FUNCS = {
    "radians", "degrees", "sin", "cos", "tan", "asin", "acos", "atan", "sinh",
    "cosh", "tanh", "asinh", "acosh", "atanh", "pow", "exp", "log", "exp2",
    "log2", "sqrt", "inversesqrt", "abs", "sign", "floor", "trunc", "round",
    "roundEven", "ceil", "fract", "mod", "modf", "min", "max", "clamp", "mix",
    "step", "smoothstep", "isnan", "isinf", "floatBitsToInt", "floatBitsToUint",
    "intBitsToFloat", "uintBitsToFloat", "fma", "frexp", "ldexp",
    "packUnorm2x16", "packSnorm2x16", "packUnorm4x8", "packSnorm4x8",
    "unpackUnorm2x16", "unpackSnorm2x16", "unpackUnorm4x8", "unpackSnorm4x8",
    "packHalf2x16", "unpackHalf2x16", "length", "distance", "dot", "cross",
    "normalize", "faceforward", "reflect", "refract", "matrixCompMult",
    "outerProduct", "transpose", "determinant", "inverse", "lessThan",
    "lessThanEqual", "greaterThan", "greaterThanEqual", "equal", "notEqual",
    "any", "all", "not", "uaddCarry", "usubBorrow", "umulExtended",
    "imulExtended", "bitfieldExtract", "bitfieldInsert", "bitfieldReverse",
    "bitCount", "findLSB", "findMSB", "textureSize", "textureQueryLod",
    "texture", "textureProj", "textureLod", "textureOffset", "texelFetch",
    "texelFetchOffset", "textureProjOffset", "textureLodOffset",
    "textureProjLod", "textureProjLodOffset", "textureGrad", "textureGradOffset",
    "textureProjGrad", "textureProjGradOffset", "textureGather",
    "textureGatherOffset", "dFdx", "dFdy", "fwidth", "interpolateAtCentroid",
    "interpolateAtSample", "interpolateAtOffset", "noise1", "noise2", "noise3",
    "noise4",
}

ES1_MISSING_BUILTINS = {
    "round", "roundEven", "trunc", "sinh", "cosh", "tanh", "asinh", "acosh",
    "atanh", "inverse", "transpose", "determinant", "outerProduct", "isnan",
    "isinf", "modf", "fma", "floatBitsToInt", "floatBitsToUint", "intBitsToFloat",
    "uintBitsToFloat", "packUnorm2x16", "unpackUnorm2x16", "packHalf2x16",
    "unpackHalf2x16", "bitCount", "findLSB", "findMSB",
}

# Old GLSL ES 1.00 / GLSL 1.20 texture functions that don't exist in 4.10 core.
LEGACY_RENAMES = {
    "texture2D": "texture", "texture2DLod": "textureLod",
    "texture2DLodEXT": "textureLod", "texture2DProj": "textureProj",
    "texture2DProjLod": "textureProjLod", "textureCube": "texture",
    "textureCubeLod": "textureLod", "textureCubeLodEXT": "textureLod",
    "texture2DGradEXT": "textureGrad", "texture2DRect": "texture",
    "texture3D": "texture", "shadow2D": "texture",
}


# ── Structural analysis ──────────────────────────────────────────────────────

@dataclass
class Declarator:
    name: str
    name_idx: int                 # token index of the name
    array_span: tuple = None      # (start, end) token indices of [..] incl. brackets
    init_span: tuple = None       # (start, end) of initializer tokens (after '=')
    span: tuple = None            # whole declarator incl. leading comma


@dataclass
class GlobalItem:
    kind: str                     # decl | func | proto | struct | precision | preproc | other
    start: int
    end: int                      # inclusive token index
    qualifiers: list = field(default_factory=list)
    qual_idx: dict = field(default_factory=dict)
    type: str = ""
    type_idx: int = -1
    decls: list = field(default_factory=list)
    name: str = ""                # function name
    name_idx: int = -1
    body: tuple = None            # (open brace idx, close brace idx) for functions
    params: tuple = None          # (open paren idx, close paren idx)


def significant(toks, start=0, end=None):
    end = len(toks) if end is None else end
    return [i for i in range(start, end) if toks[i].kind not in TRIVIA]


def match_close(toks, i):
    """toks[i] is an opening bracket; return index of its partner."""
    pairs = {"(": ")", "[": "]", "{": "}"}
    open_c = toks[i].text
    close_c = pairs[open_c]
    depth = 0
    for k in range(i, len(toks)):
        t = toks[k]
        if t.kind != "punct":
            continue
        if t.text == open_c:
            depth += 1
        elif t.text == close_c:
            depth -= 1
            if depth == 0:
                return k
    return len(toks) - 1


def analyze(toks) -> list:
    """Split a token list into top-level items."""
    items = []
    i = 0
    n = len(toks)
    while i < n:
        t = toks[i]
        if t.kind in TRIVIA:
            i += 1
            continue
        if t.kind == "preproc":
            items.append(GlobalItem("preproc", i, i))
            i += 1
            continue
        start = i
        prev_sig = None
        end = None
        while i < n:
            t = toks[i]
            if t.kind == "punct":
                if t.text in ("(", "["):
                    i = match_close(toks, i)
                elif t.text == "{":
                    close = match_close(toks, i)
                    if prev_sig is not None and toks[prev_sig].text == ")":
                        end = close
                        break
                    i = close           # struct / interface block, continue to ';'
                elif t.text == ";":
                    end = i
                    break
            if t.kind not in TRIVIA and t.kind != "preproc":
                prev_sig = i
            i += 1
        if end is None:
            end = n - 1
        items.append(_classify(toks, start, end))
        i = end + 1
    return items


def _classify(toks, start, end):
    sig = significant(toks, start, end + 1)
    item = GlobalItem("other", start, end)
    if not sig:
        return item
    words = [toks[k].text for k in sig]
    if words[0] == "precision":
        item.kind = "precision"
        return item
    if words[0] == "struct" or ("struct" in words[:3] and "{" in words):
        item.kind = "struct"
        return item
    p = 0
    while p < len(sig) and toks[sig[p]].kind == "ident" and toks[sig[p]].text in QUALIFIERS:
        q = toks[sig[p]].text
        item.qualifiers.append(q)
        item.qual_idx[q] = sig[p]
        if q == "layout" and p + 1 < len(sig) and toks[sig[p + 1]].text == "(":
            close = match_close(toks, sig[p + 1])
            while p < len(sig) and sig[p] < close:
                p += 1
        p += 1
    if p >= len(sig) or toks[sig[p]].kind != "ident":
        return item
    item.type = toks[sig[p]].text
    item.type_idx = sig[p]
    p += 1
    # array type: float[3] a = ...
    if p < len(sig) and toks[sig[p]].text == "[":
        close = match_close(toks, sig[p])
        while p < len(sig) and sig[p] <= close:
            p += 1
    if p >= len(sig) or toks[sig[p]].kind != "ident":
        return item           # e.g. interface block / anonymous
    name_idx = sig[p]
    if p + 1 < len(sig) and toks[sig[p + 1]].text == "(":
        item.name = toks[name_idx].text
        item.name_idx = name_idx
        item.params = (sig[p + 1], match_close(toks, sig[p + 1]))
        if toks[end].text == "}":
            item.kind = "func"
            open_b = next(k for k in sig if k > item.params[1] and toks[k].text == "{")
            item.body = (open_b, end)
        else:
            item.kind = "proto"
        return item
    item.kind = "decl"
    # declarators
    k = p
    decl_start = sig[p]
    while k < len(sig):
        nm = sig[k]
        if toks[nm].kind != "ident":
            break
        d = Declarator(toks[nm].text, nm)
        k += 1
        if k < len(sig) and toks[sig[k]].text == "[":
            close = match_close(toks, sig[k])
            d.array_span = (sig[k], close)
            while k < len(sig) and sig[k] <= close:
                k += 1
        if k < len(sig) and toks[sig[k]].text == "=":
            init_start = sig[k + 1] if k + 1 < len(sig) else sig[k]
            depth = 0
            while k < len(sig):
                tt = toks[sig[k]].text
                if tt in ("(", "[", "{"):
                    depth += 1
                elif tt in (")", "]", "}"):
                    depth -= 1
                elif depth == 0 and tt in (",", ";"):
                    break
                k += 1
            d.init_span = (init_start, sig[k - 1])
        stop = sig[k] if k < len(sig) else end
        d.span = (decl_start, stop - 1)
        item.decls.append(d)
        if k < len(sig) and toks[sig[k]].text == ",":
            decl_start = sig[k]
            k += 1
            continue
        break
    return item


def idents_in(toks, i, j):
    """Identifier texts in token range i..j inclusive (skips member access: a.xy)."""
    out = []
    prev = None
    for k in range(i, j + 1):
        t = toks[k]
        if t.kind == "ident" and not (prev is not None and prev.text == "."):
            out.append(t.text)
        if t.kind not in TRIVIA:
            prev = t
    return out


def rename_idents(toks, mapping, start=0, end=None, skip_member=True):
    """Rename identifier tokens per mapping (not after '.')."""
    end = len(toks) if end is None else end
    prev = None
    for k in range(start, end):
        t = toks[k]
        if t.kind == "ident" and t.text in mapping:
            if not (skip_member and prev is not None and prev.text == "."):
                t.text = mapping[t.text]
        if t.kind not in TRIVIA:
            prev = t


def next_sig(toks, i):
    for k in range(i + 1, len(toks)):
        if toks[k].kind not in TRIVIA:
            return k
    return None


def prev_sig(toks, i):
    for k in range(i - 1, -1, -1):
        if toks[k].kind not in TRIVIA:
            return k
    return None


def declared_names(toks) -> set:
    """Every identifier that appears in a declaring position anywhere
    (globals, locals, function params, function names, struct members)."""
    names = set()
    sig = significant(toks)
    for a, b in zip(sig, sig[1:]):
        ta, tb = toks[a], toks[b]
        if tb.kind == "ident" and ta.kind == "ident" and ta.text in TYPES:
            names.add(tb.text)
    for it in analyze(toks):
        if it.kind in ("func", "proto"):
            names.add(it.name)
        for d in it.decls:
            names.add(d.name)
        if it.kind == "preproc":
            m = re.match(r"\s*#\s*define\s+(\w+)", toks[it.start].text)
            if m:
                names.add(m.group(1))
    return names


_NUM_RE = re.compile(r"^[+-]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][+-]?\d+)?[fF]?$")


def parse_number(text):
    text = text.strip()
    if not _NUM_RE.match(text):
        return None
    return float(text.rstrip("fF"))


def parse_literal_vector(text):
    """'vec3(1., .5, 0)' -> [1.0, 0.5, 0.0]; also scalar numbers. None if not literal."""
    text = re.sub(r"\s+", "", text)
    v = parse_number(text)
    if v is not None:
        return [v]
    m = re.match(r"^(-?)(vec[234]|ivec[234])\((.*)\)$", text)
    if not m:
        return None
    parts = m.group(3).split(",") if m.group(3) else []
    vals = [parse_number(p) for p in parts]
    if not vals or any(v is None for v in vals):
        return None
    if m.group(1):
        vals = [-v for v in vals]
    size = int(m.group(2)[-1])
    if len(vals) == 1:
        vals = vals * size
    if len(vals) != size:
        return None
    return vals


def used_names(toks):
    """Identifiers used anywhere, including inside #define bodies."""
    used = {t.text for t in toks if t.kind == "ident"}
    for t in toks:
        if t.kind == "preproc":
            used.update(re.findall(r"[A-Za-z_]\w*", t.text))
    return used


def rename_everywhere(toks, mapping):
    """rename_idents, plus whole-word renames inside preprocessor lines."""
    rename_idents(toks, mapping)
    if not mapping:
        return
    rx = re.compile(r"\b(" + "|".join(re.escape(k) for k in mapping) + r")\b")
    for t in toks:
        if t.kind == "preproc":
            t.text = rx.sub(lambda m: mapping[m.group(1)], t.text)
