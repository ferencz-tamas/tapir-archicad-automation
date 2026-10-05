"""
gen_raw_dump_fields.py - generates archicad-addon/Sources/RawElementFields.inc for the developer-only
DumpRawElementFields command.

For every element type listed in TYPES it parses the struct declaration out of the Archicad API DevKit header
(APIdefs_Elements.h) and emits one RAW_FIELD (...) line per real member (filler_* are skipped). Naming:
  head.<member>                 the element header (head.type is split into head.type.typeID / .variationID)
  <member>                      a member of the element struct itself, e.g. height
  openingBase.<m>, shellBase.<m> shared base structs are flattened with their member name as prefix
  u.<union member>.<m>          anonymous-union members (roof / shell), emitted only for the active class

Usage: python tools/gen_raw_dump_fields.py <DevKit Support dir>
       e.g. python tools/gen_raw_dump_fields.py archicad-addon/Build/DevKits/AC28/Support
"""

import json
import re
import sys
from pathlib import Path

# (API_ElemTypeID, struct name, member of the API_Element union)
TYPES = [
    ("API_WallID", "API_WallType", "wall"),
    ("API_ColumnID", "API_ColumnType", "column"),
    ("API_BeamID", "API_BeamType", "beam"),
    ("API_WindowID", "API_WindowType", "window"),
    ("API_DoorID", "API_WindowType", "door"),
    ("API_ObjectID", "API_ObjectType", "object"),
    ("API_LampID", "API_ObjectType", "lamp"),
    ("API_SlabID", "API_SlabType", "slab"),
    ("API_RoofID", "API_RoofType", "roof"),
    ("API_MeshID", "API_MeshType", "mesh"),
    ("API_ZoneID", "API_ZoneType", "zone"),
    ("API_CurtainWallID", "API_CurtainWallType", "curtainWall"),
    ("API_ShellID", "API_ShellType", "shell"),
    ("API_MorphID", "API_MorphType", "morph"),
    ("API_SkylightID", "API_SkylightType", "skylight"),
    ("API_StairID", "API_StairType", "stair"),
    ("API_RailingID", "API_RailingType", "railing"),
    ("API_OpeningID", "API_OpeningType", "opening"),
    # document tools
    ("API_DimensionID", "API_DimensionType", "dimension"),
    ("API_LevelDimensionID", "API_LevelDimensionType", "levelDimension"),
    ("API_RadialDimensionID", "API_RadialDimensionType", "radialDimension"),
    ("API_AngleDimensionID", "API_AngleDimensionType", "angleDimension"),
    ("API_TextID", "API_TextType", "text"),
    ("API_LabelID", "API_LabelType", "label"),
    ("API_LineID", "API_LineType", "line"),
    ("API_ArcID", "API_ArcType", "arc"),
    ("API_CircleID", "API_ArcType", "circle"),
    ("API_PolyLineID", "API_PolyLineType", "polyLine"),
    ("API_SplineID", "API_SplineType", "spline"),
    ("API_PictureID", "API_PictureType", "picture"),
    ("API_DrawingID", "API_DrawingType", "drawing"),
    ("API_HatchID", "API_HatchType", "hatch"),
    ("API_HotspotID", "API_HotspotType", "hotspot"),
    # viewpoint tools
    ("API_CutPlaneID", "API_CutPlaneType", "cutPlane"),
    ("API_ElevationID", "API_CutPlaneType", "elevation"),
    ("API_InteriorElevationID", "API_InteriorElevationType", "interiorElevation"),
    ("API_DetailID", "API_DetailType", "detail"),
    ("API_WorksheetID", "API_DetailType", "worksheet"),
    ("API_CameraID", "API_CameraType", "camera"),
]
# Nested member paths to flatten per element type (derived from the Notion rows by sandbox/api_field_checklist/make_nested_hints.py)
HINTS_FILE = Path(__file__).resolve().parent / "raw_dump_nested_members.json"
HINTS = json.loads(HINTS_FILE.read_text(encoding="utf8")) if HINTS_FILE.exists() else {}
HEAD_STRUCT = "API_Elem_Head"
FLATTEN = {"openingBase": "API_OpeningBaseType", "shellBase": "API_ShellBaseType"}   # member -> struct
FLATTEN_DEEP = {"verticalLink": "API_VerticalLink"}   # members of flattened structs that are flattened once more
# struct types (by name) that are flattened with their member name as prefix at any depth (the freeform opening)
RECURSE_RE = re.compile(r"^API_Opening(?:FloorPlan|Extrusion|CutSurfaces|Outlines|CoverFills|ReferenceAxis)\w*(?:Parameters|Data)$")
UNION_CONDITIONS = {   # union member struct -> condition under which it is the valid one
    "API_PlaneRoofData": "elem.roof.roofClass == API_PlaneRoofID",
    "API_PolyRoofData": "elem.roof.roofClass == API_PolyRoofID",
    "API_ExtrudedShellData": "elem.shell.shellClass == API_ExtrudedShellID",
    "API_RevolvedShellData": "elem.shell.shellClass == API_RevolvedShellID",
    "API_RuledShellData": "elem.shell.shellClass == API_RuledShellID",
    "API_TextType": "elem.label.labelClass == APILblClass_Text",       # members of API_LabelType's union
    "API_ObjectType": "elem.label.labelClass == APILblClass_Symbol",
}

MEMBER_RE = re.compile(r"^\s*([\w:<>]+(?:\s+[\w:<>]+)*?)[\s\*&]+(\w+)\s*(?:\[[^\]]*\]\s*)*;")


def strip_comments(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"//[^\n]*", "", text)


def _balanced(header_text, start):
    depth, i = 1, start
    while depth:
        c = header_text[i]
        depth += (c == "{") - (c == "}")
        i += 1
    return header_text[start:i - 1], i


def find_struct(header_text, struct_name, _depth=0):
    """Body of 'struct NAME {...}', 'typedef struct [tag] {...} NAME;' or of the struct NAME is an alias of; None if unknown."""
    m = re.search(r"\bstruct\s+" + struct_name + r"\s*(?:final\s*)?\{", header_text)
    if m:
        return _balanced(header_text, m.end())[0]
    for mm in re.finditer(r"\btypedef\s+struct\s*\w*\s*\{", header_text):
        body, end = _balanced(header_text, mm.end())
        tail = re.match(r"\s*(\w+)\s*;", header_text[end:])
        if tail and tail.group(1) == struct_name:
            return body
    alias = re.search(r"\busing\s+" + struct_name + r"\s*=\s*(\w+)\s*;", header_text)
    if alias is None:
        alias = re.search(r"\btypedef\s+(\w+)\s+" + struct_name + r"\s*;", header_text)
    if alias and alias.group(1) not in ("struct", "enum", "union") and _depth < 4:
        return find_struct(header_text, alias.group(1), _depth + 1)
    return None


def struct_body(header_text, struct_name):
    body = find_struct(header_text, struct_name)
    if body is None:
        raise SystemExit(f"struct {struct_name} not found")
    return body


def struct_members(header_text, struct_name):
    """-> list of ('field', name, type) and ('union', varname, [(name, type)...]); filler_* and bit-fields skipped."""
    items, in_union, union_members = [], False, []
    for line in struct_body(header_text, struct_name).splitlines():
        if re.search(r"\bunion\s*\{", line):
            in_union, union_members = True, []
            continue
        um = re.match(r"\s*\}\s*(\w+)\s*;", line)
        if in_union and um:
            items.append(("union", um.group(1), union_members))
            in_union = False
            continue
        if "{" in line or "}" in line or re.search(r"\w\s*:\s*\d+\s*;", line):   # nested types / bit-fields
            continue
        mm = MEMBER_RE.match(line)
        if not mm or mm.group(2).startswith("filler"):
            continue
        (union_members if in_union else items).append(("field", mm.group(2), mm.group(1)) if not in_union else (mm.group(2), mm.group(1)))
    return items


def field_lines(header, struct_name, member, name_prefix="", expr_prefix=None, depth=0, hints=frozenset()):
    """RAW_FIELD lines for the members of struct_name reached as elem.<member>[...]"""
    lines = []
    expr_prefix = expr_prefix or f"elem.{member}"
    for item in struct_members(header, struct_name):
        if item[0] == "field":
            _, name, _type = item
            if name == "head":
                continue
            if name in FLATTEN and depth == 0:
                lines += field_lines(header, FLATTEN[name], member, f"{name_prefix}{name}.", f"{expr_prefix}.{name}", 1, hints)
            elif name in FLATTEN_DEEP and depth == 1:
                lines += field_lines(header, FLATTEN_DEEP[name], member, f"{name_prefix}{name}.", f"{expr_prefix}.{name}", 2, hints)
            elif RECURSE_RE.match(_type) or (f"{name_prefix}{name}" in hints and find_struct(header, _type) is not None):
                lines += field_lines(header, _type, member, f"{name_prefix}{name}.", f"{expr_prefix}.{name}", depth + 1, hints)
            else:
                lines.append(f'RAW_FIELD ("{name_prefix}{name}", {expr_prefix}.{name})')
        else:
            _, var, members = item
            for mname, mtype in members:
                cond = UNION_CONDITIONS.get(mtype)
                inner = field_lines(header, mtype, member, f"{name_prefix}{var}.{mname}.", f"{expr_prefix}.{var}.{mname}", 3, hints)
                if cond:
                    lines.append(f"if ({cond}) {{ " + " ".join(inner) + " }")
    return lines


def main():
    support = Path(sys.argv[1])
    header = strip_comments((support / "Inc" / "APIdefs_Elements.h").read_text(encoding="utf8", errors="replace"))
    out = ["// Generated by tools/gen_raw_dump_fields.py from the Archicad API DevKit - do not edit by hand.", ""]
    head = [i[1] for i in struct_members(header, HEAD_STRUCT) if i[0] == "field"]
    head_lines = []
    for f in head:
        if f == "type":
            head_lines += ['RAW_FIELD ("head.type.typeID", elem.header.type.typeID)',
                           'RAW_FIELD ("head.type.variationID", elem.header.type.variationID)']
        else:
            head_lines.append(f'RAW_FIELD ("head.{f}", elem.header.{f})')
    out.append("#define RAW_HEAD_FIELDS \\")
    out += [f"    {l} \\" for l in head_lines]
    out[-1] = out[-1].rstrip(" \\")
    out.append("")
    for type_id, struct, member in TYPES:
        lines = field_lines(header, struct, member, hints=frozenset(HINTS.get(type_id, [])))
        out.append(f"#define RAW_FIELDS_{type_id} \\")
        out += [f"    {l} \\" for l in lines]
        out[-1] = out[-1].rstrip(" \\")
        out.append("")
        print(f"{type_id:20} {struct:22} {len(lines)} field statements")
    dst = Path(__file__).resolve().parent.parent / "archicad-addon" / "Sources" / "RawElementFields.inc"
    dst.write_text("\n".join(out) + "\n", encoding="utf8")
    print(f"wrote {dst}")


if __name__ == "__main__":
    main()
