"""Multi-pass Shadertoy projects (Common + Buffer A-D + Image).

Two input forms:
  * Shadertoy JSON (API / exporter format with a "renderpass" list)
  * Sectioned text: tabs pasted into one file under header lines like
        // ==== Common ====
        // ==== Buffer A ====
        // ffstudio: iChannel0 = Buffer A      (directives apply to their section)
        // ffstudio: iChannel1 = rock.jpg filter=nearest wrap=clamp vflip=false
        // ==== Image ====
"""
import json
import os
import re

PASS_ORDER = ["Common", "Buffer A", "Buffer B", "Buffer C", "Buffer D", "Image"]
_SECTION_RE = re.compile(r"^[ \t]*//[ \t]*[=\-#*]{2,}[ \t]*(common|buffer[ \t]*[a-d]|image)[ \t]*[=\-#*]{2,}[ \t]*$",
                         re.I | re.M)
# Well-known Shadertoy buffer output ids.
_BUFFER_IDS = {"4dXGR8": "A", "XsXGR8": "B", "4sXGR8": "C", "XdfGR8": "D",
               "257": "A", "258": "B", "259": "C", "260": "D"}


class ProjectPass:
    def __init__(self, name, code, channels=None, line_offset=0, samplers=None):
        self.name = name              # "Common", "Buffer A".., "Image"
        self.code = code
        self.channels = channels or {}  # {0: ("buffer","A") | ("input",) | ("noise",) | ("file",path) | ("audio",) | ("none",)}
        self.line_offset = line_offset  # line in the source file where this section starts
        self.samplers = samplers or {}  # {0: {"filter": "nearest", "wrap": "repeat", "vflip": False}}


def _canon(name):
    n = re.sub(r"\s+", " ", name.strip()).lower()
    for p in PASS_ORDER:
        if p.lower() == n or p.lower().replace(" ", "") == n.replace(" ", ""):
            return p
    return None


def is_project(code):
    s = code.lstrip("﻿").lstrip()
    if s.startswith("{") or s.startswith("["):
        return '"renderpass"' in s
    return len(_SECTION_RE.findall(code)) >= 2


def parse(code, path=None):
    s = code.lstrip("﻿").lstrip()
    if s.startswith("{") or s.startswith("["):
        return _parse_json(json.loads(s), path)
    return _parse_sections(code, path)


def _channel_value(val, path):
    v = val.strip().strip("\"'")
    low = v.lower()
    m = re.match(r"(?:buffer\s*)?([a-d])$", low)
    if m and (low.startswith("buffer") or len(low) == 1):
        return ("buffer", m.group(1).upper())
    if low in ("input", "clip", "host", "video", "webcam"):
        return ("input",)
    if low == "noise":
        return ("noise",)
    if low in ("audio", "sound", "fft", "music", "mic"):
        return ("audio",)
    if low in ("none", "keyboard", "black"):
        return ("none",)
    p = v if not path or os.path.isabs(v) else os.path.join(os.path.dirname(path), v)
    return ("file", p)


def _parse_sections(code, path):
    from .convert import channel_directives, split_channel_options
    passes = []
    matches = list(_SECTION_RE.finditer(code))
    for i, m in enumerate(matches):
        name = _canon(m.group(1))
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(code)
        body = code[start:end]
        line = code.count("\n", 0, start)
        chans, samplers = {}, {}
        for k, v in channel_directives(body).items():
            value, opts = split_channel_options(v)
            chans[int(k[-1])] = _channel_value(value, path)
            samplers[int(k[-1])] = opts
        passes.append(ProjectPass(name, body, chans, line, samplers))
    return passes


def _parse_json(data, path):
    from .convert import sampler_options
    if isinstance(data, list):
        data = data[0]
    shader = data.get("Shader", data)
    info = shader.get("info", {})
    passes = []
    for rp in shader.get("renderpass", []):
        t = rp.get("type", "")
        if t == "common":
            name = "Common"
        elif t == "image":
            name = "Image"
        elif t == "buffer":
            name = _canon(rp.get("name", "")) or "Buffer " + _buffer_letter(rp.get("outputs", [{}])[0])
        else:
            continue            # sound / cubemap passes are not supported
        chans, samplers = {}, {}
        for inp in rp.get("inputs", []):
            ch = int(inp.get("channel", 0))
            ctype = inp.get("ctype", inp.get("type", ""))
            samplers[ch] = sampler_options(inp.get("sampler") or {})
            if ctype == "buffer":
                chans[ch] = ("buffer", _buffer_letter(inp))
            elif ctype in ("video", "webcam"):
                chans[ch] = ("input",)
            elif ctype in ("music", "musicstream", "mic"):
                chans[ch] = ("audio",)
            elif ctype == "texture":
                src = os.path.basename(inp.get("src", inp.get("filepath", "")))
                local = os.path.join(os.path.dirname(path), src) if path and src else ""
                chans[ch] = ("file", local) if local and os.path.isfile(local) else ("noise",)
            else:
                chans[ch] = ("none",)
        passes.append(ProjectPass(name, rp.get("code", ""), chans, samplers=samplers))
    passes.sort(key=lambda p: PASS_ORDER.index(p.name))
    passes_info = {"name": info.get("name", ""), "author": info.get("username", ""),
                   "description": info.get("description", ""), "id": info.get("id", "")}
    for p in passes:
        p.info = passes_info
    return passes


def _buffer_letter(entry):
    i = str(entry.get("id", ""))
    if i in _BUFFER_IDS:
        return _BUFFER_IDS[i]
    m = re.search(r"buffer0?([0-3])", str(entry.get("src", entry.get("filepath", ""))))
    if m:
        return "ABCD"[int(m.group(1))]
    return "A"
