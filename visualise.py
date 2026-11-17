#!/usr/bin/env python3
"""Visualises ontologies in the graph spec format (model.json, and model.yaml if present) as SVG diagrams.

Usage: python3 visualise.py [FOLDER | MODEL.json ...]

For each folder or model file given, or every folder below this script that holds a model.json, reads the model,
checks that the model.yaml beside it, if there is one, describes the same model, and writes an SVG of the same name
beside it, e.g. model.svg: one card per node and one arrow per relationship, laid out in layers from the roots of the
graph, with dotted arrows for the labels a subtype also carries. Arrows are named by their relationship type wherever
the name fits without overlapping a card or another name, the main relationships first; hovering a card or arrow
shows its description, and a card links to its reference.

How cards are coloured and arrows drawn comes from the diagram.json beside the model, if there is one:

    {
      "source": "the IDO 4.2 FDIS Turtle file",           what the model was generated from
      "link": "the term in PCA RDS",                       what a card links to
      "areas": {                                           up to four areas, which colour the cards
        "field": "root",                                   the extensions.custom field of a node that places it,
        "groups": [                                        matching a value equal to, or starting with, one of
          {"name": "Objects", "values": ["Object"]}, ...   a group's values followed by a dot
        ]
      },
      "sub": ["root", "#properties"],                      what a card prints under its name: extensions.custom
                                                           fields, a true flag printing its name, and #properties
                                                           the number of properties
      "lines": {                                           how arrows are drawn: by the counts at the "from" or
        "by": "from",                                      "to" end (main with count or min_count, dashed with
        "legend": {"main": "...", "dashed": "...", ...}    max_count, thin otherwise), or by "field:NAME", main
      }                                                    when extensions.custom.NAME is true and dashed otherwise
    }

Every key is optional; without the file, cards share one colour and arrows are drawn by the counts at their "from"
end. Uses only the Python standard library.
"""

import json
import re
import sys
from math import atan2, cos, degrees, hypot, radians, sin
from pathlib import Path
from xml.sax.saxutils import escape

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
SECONDARY = "#52514e"
MUTED = "#898781"
IMPLIED = "#b3b0a9"  # the supertype label a subtype also carries

# The ways a relationship arrow is drawn: its stroke, the marker on its end and the colour of its name, darkened to
# stay readable at label size. Each standard decides which relationships are main, dashed or thin.
STYLES = {
    "main": ('stroke="#736f68" stroke-width="1.5" marker-end="url(#m-main)"', "#5c5953"),
    "dashed": ('stroke="#a19e96" stroke-width="1.4" stroke-dasharray="6 4" marker-end="url(#m-minor)"', "#817e78"),
    "thin": ('stroke="#a19e96" stroke-width="1.2" marker-end="url(#m-minor)"', "#817e78"),
}
MARKERS = (("m-main", "#736f68"), ("m-minor", "#a19e96"), ("m-imp", IMPLIED))
IMPLIED_ATTRS = f'stroke="{IMPLIED}" stroke-width="1.4" stroke-dasharray="1.5 4" stroke-linecap="round" marker-start="url(#m-imp)"'

# The first four slots of a categorical palette whose every pair clears both the colour-blind and the normal-vision
# separation floors; each card also prints its area, so identity never rides on the hue alone.
HUES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]


def custom(item):
    return item.get("extensions", {}).get("custom", {})


def count_of(node):
    count = len(node.get("properties", {}))
    return f"{count} propert{'y' if count == 1 else 'ies'}"


# What the line legend says when diagram.json doesn't, by how the lines are drawn.
LEGENDS = {
    "end": {
        "main": "required: every {end} node has one or more",
        "dashed": "every {end} node has at most one",
        "thin": "otherwise unconstrained",
    },
    "field": {"main": "{field}", "dashed": "not {field}"},
}


def standard_of(config, source):
    """How a model is drawn, from its diagram.json: how to find a node's area and what its card prints under its
    name, how each relationship is drawn and what the line legend says, and where the model came from."""
    groups = config.get("areas", {}).get("groups", [])
    if len(groups) > len(HUES):
        sys.exit(f"{source}: at most {len(HUES)} areas")
    field = config.get("areas", {}).get("field")

    def area(node):
        if not groups:
            return 0
        value = str(custom(node).get(field, ""))
        for i, group in enumerate(groups):
            if any(value == v or value.startswith(v + ".") for v in group["values"]):
                return i
        sys.exit(f"{source}: no area for {field} {value!r} of {node['labels']['identifier']}")

    def sub(node):
        parts = []
        for name in config.get("sub", ["#properties"]):
            value = count_of(node) if name == "#properties" else custom(node).get(name)
            if value is True:
                parts.append(name)
            elif isinstance(value, list):
                parts.append(", ".join(map(str, value)))
            elif value not in (None, False, ""):
                parts.append(str(value))
        return parts

    by = config.get("lines", {}).get("by", "from")
    if by.startswith("field:"):
        flag = by.split(":", 1)[1]
        style = lambda rel: "main" if custom(rel).get(flag) else "dashed"
        defaults = {k: v.format(field=flag) for k, v in LEGENDS["field"].items()}
    elif by in ("from", "to"):

        def style(rel):
            """Main when every node at the end has one or more, dashed when it has at most one, thin otherwise."""
            if "count" in rel[by] or "min_count" in rel[by]:
                return "main"
            return "dashed" if "max_count" in rel[by] else "thin"

        defaults = {k: v.format(end="source" if by == "from" else "target") for k, v in LEGENDS["end"].items()}
    else:
        sys.exit(f"{source}: lines are drawn by from, to or field:NAME, not {by}")
    legend = config.get("lines", {}).get("legend", defaults)
    return {
        "areas": [group["name"] for group in groups],
        "area": area,
        "sub": sub,
        "style": style,
        "legend": [(name, legend[name]) for name in STYLES if name in legend],
        "source": config.get("source", source),
        "link": config.get("link", "the reference"),
    }

MARGIN = 60
COLUMN_GAP = 64
ROW_GAP = 26
HEADER = 150
SUB_LINE = 35  # the pitch of the small lines inside a card
MAX_EXTRA = 52  # the characters a card's key or implied label line keeps; hover shows them all
REL_CHAR = 6.4  # the pixels a character of a relationship label takes


def parse_yaml(text):
    """Reads back the YAML that generate.py writes: block style, every scalar JSON-quoted."""
    lines = [line for line in text.splitlines() if line.strip()]
    entry = re.compile(r'^("(?:[^"\\]|\\.)*"): (.*)$')

    def indent(i):
        return len(lines[i]) - len(lines[i].lstrip())

    def parse(i, column):
        """The value starting at line i, indented by exactly `column` spaces; returns (value, next line)."""
        if lines[i][column] == "-":  # a list: items are "- scalar" or "-" with the item on the lines below
            items = []
            while i < len(lines) and indent(i) == column and lines[i][column] == "-":
                if lines[i][column:] == "-":
                    value, i = parse(i + 1, column + 2)
                else:
                    value, i = json.loads(lines[i][column + 2 :]), i + 1
                items.append(value)
            return items, i
        out = {}  # a mapping: "key": scalar, or "key": with the value on the lines below
        while i < len(lines) and indent(i) == column:
            body = lines[i][column:]
            if body.endswith(":"):  # the value follows on the lines below
                out[json.loads(body[:-1])], i = parse(i + 1, column + 2)
                continue
            match = entry.match(body)
            if not match:
                break
            out[json.loads(match.group(1))], i = json.loads(match.group(2)), i + 1
        return out, i

    return parse(0, 0)[0]


def edges_of(model):
    """Every (parent, child) pair the layout follows: each relationship, and each supertype to its subtypes."""
    edges = [(rel["from"]["node"], rel["to"]["node"]) for rel in model["relationships"].values()]
    for name, node in model["nodes"].items():
        edges += [(supertype, name) for supertype in node["labels"].get("implied", [])]
    return [(a, b) for a, b in edges if a != b]


def layers_of(nodes, edges):
    """The layer of each node: one plus the layer of its deepest parent, ignoring cycles. A node without parents
    is then pulled forward to sit just before its nearest child, rather than with every other root in the first."""
    parents, children = {node: set() for node in nodes}, {node: set() for node in nodes}
    for a, b in edges:
        parents[b].add(a)
        children[a].add(b)

    layer, path = {}, set()

    def visit(node):
        if node in path:
            return -1  # a cycle: the edge back adds no layer
        if node in layer:
            return layer[node]
        path.add(node)
        # Sorted, so that which edge of a cycle is cut, and with it the layout, is the same on every run.
        layer[node] = max((visit(parent) + 1 for parent in sorted(parents[node])), default=0)
        path.discard(node)
        return layer[node]

    for node in nodes:
        visit(node)
    for node in nodes:
        if not parents[node] and children[node]:
            layer[node] = min(layer[child] for child in children[node]) - 1
    return layer


def order(layers, edges):
    """Sorts each layer by the mean relative position of its neighbours, sweeping back and forth to cut crossings."""
    neighbours = {node: [] for nodes in layers for node in nodes}
    for a, b in edges:
        neighbours[a].append(b)
        neighbours[b].append(a)

    position = {node: i / len(nodes) for nodes in layers for i, node in enumerate(nodes)}
    for sweep in range(12):
        for nodes in layers if sweep % 2 == 0 else reversed(layers):
            mean = {n: sum(position[m] for m in neighbours[n]) / len(neighbours[n]) if neighbours[n] else position[n] for n in nodes}
            nodes.sort(key=lambda n: (mean[n], position[n]))
            for i, node in enumerate(nodes):
                position[node] = i / len(nodes)


def card(name, node, standard):
    """The lines a node card shows, and the width and height they need."""
    keys = next((c["properties"] for c in node.get("constraints", {}).values() if c["type"] == "KEY"), [])
    sub = " · ".join(part for part in standard["sub"](node) if part)
    extras = []
    if node["labels"].get("implied"):
        extras.append("also " + ", ".join(node["labels"]["implied"]))
    if keys:
        extras.append("key: " + " + ".join(keys))
    extras = [extra if len(extra) <= MAX_EXTRA else extra[: MAX_EXTRA - 1] + "…" for extra in extras]
    widths = [len(name) * 7.9, len(sub) * 5.9, *(len(extra) * 5.7 for extra in extras)]
    return {"sub": sub, "extras": extras, "width": max(120, 26 + max(widths)), "height": 40 + SUB_LINE - 25 + 14 * len(extras)}


def tint(hex_color, towards_white):
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (1, 3, 5))
    mix = lambda c: round(c + (255 - c) * towards_white)
    return f"#{mix(r):02x}{mix(g):02x}{mix(b):02x}"


def render(model, standard):
    """Lays the model out and renders it as SVG."""
    nodes, relationships = model["nodes"], model["relationships"]
    edges = edges_of(model)
    layer = layers_of(nodes, edges)
    layers = [[] for _ in range(max(layer.values()) + 1)]
    for name in nodes:
        layers[layer[name]].append(name)
    order(layers, edges)

    cards = {name: card(name, node, standard) for name, node in nodes.items()}
    x, y, column_x = {}, {}, MARGIN
    for names in layers:
        next_y = HEADER
        for name in names:
            x[name], y[name] = column_x, next_y
            next_y += cards[name]["height"] + ROW_GAP
        column_x += max(cards[name]["width"] for name in names) + COLUMN_GAP
    bottom = max(y[name] + cards[name]["height"] for name in nodes)
    width = column_x - COLUMN_GAP + MARGIN

    # Relationships between the same pair of nodes share a lane, nudged apart; ones that point backwards or
    # sideways dip below the diagram instead, each on its own level.
    parallel, backwards = {}, []
    for rid, rel in relationships.items():
        parallel.setdefault((rel["from"]["node"], rel["to"]["node"]), []).append((rid, rel))
    dip = bottom + 60

    def path_between(a, b, index=0, count=1):
        """The arrow a→b, and where to centre its label: a point, the tangent angle there, and the room, in
        pixels, the label has before it overruns the cards at either end."""
        aw, ah, bw, bh = cards[a]["width"], cards[a]["height"], cards[b]["width"], cards[b]["height"]
        if a == b:  # a self loop, out into the gap beside the card, with its label turned to stand beside it
            x1, y1, x2, y2 = x[a] + aw - 20, y[a] + ah * 0.3, x[a] + aw - 6, y[a] + ah * 0.62
            label = {"x": x1 + 31, "y": (y1 + y2) / 2 + 3, "angle": -90, "room": ah - 14}
            return f"M {x1:.0f} {y1:.0f} C {x1 + 30:.0f} {y1 - 8:.0f}, {x1 + 30:.0f} {y2 + 8:.0f}, {x2:.0f} {y2:.0f}", label
        if layer[b] > layer[a]:
            k = (x[b] - x[a] - aw) * 0.45 if layer[b] - layer[a] == 1 else COLUMN_GAP * 2
            # Lanes 14 pixels apart, squeezed when there are many, so the bundle stays clear of the header.
            off = (index - (count - 1) / 2) * min(14, 126 / max(1, count - 1))
            sx, sy = x[a] + aw, y[a] + ah / 2
            tx, ty = x[b], y[b] + bh / 2
            label = {
                "x": (sx + tx) / 2,
                "y": (sy + ty) / 2 + 0.75 * off + 3,
                "angle": degrees(atan2(ty - sy, tx - sx - k)),
                "room": hypot(tx - sx, ty - sy) - 10,
            }
            if label["angle"] > 90 or label["angle"] <= -90:
                label["angle"] += 180 if label["angle"] < 0 else -180  # keep the label reading left to right
            return f"M {sx:.0f} {sy:.0f} C {sx + k:.0f} {sy + off:.0f}, {tx - k:.0f} {ty + off:.0f}, {tx:.0f} {ty:.0f}", label
        sx, sy = x[a] + aw / 2, y[a] + ah  # backwards or sideways: dip below the diagram
        tx, ty = x[b] + bw / 2, y[b] + bh
        level = dip + len(backwards) * 12
        backwards.append(level)
        return (
            f"M {sx:.0f} {sy:.0f} C {sx:.0f} {level:.0f}, {tx:.0f} {level:.0f}, {tx:.0f} {ty:.0f}",
            # The label sits on the curve's lowest point, its t = 0.5 midpoint, not at the control points' level.
            {"x": (sx + tx) / 2, "y": (sy + 6 * level + ty) / 8 - 5, "angle": 0, "room": abs(tx - sx) - 10},
        )

    def footprint(label, name):
        """Points along the label's baseline, every few pixels, to test it against cards and other labels."""
        half, a = len(name) * REL_CHAR / 2, radians(label["angle"])
        steps = max(1, int(half * 2 / 6))
        return [
            (label["x"] + (t * 2 * half / steps - half) * cos(a), label["y"] - 3 + (t * 2 * half / steps - half) * sin(a))
            for t in range(steps + 1)
        ]

    def on_card(px, py):
        return any(x[n] - 3 <= px <= x[n] + cards[n]["width"] + 3 and y[n] - 3 <= py <= y[n] + cards[n]["height"] + 3 for n in nodes)

    def arrow_label(label, name, color):
        return (
            f'<text class="rel" style="fill:{color}" x="{label["x"]:.0f}" y="{label["y"]:.0f}" text-anchor="middle" '
            f'transform="rotate({label["angle"]:.0f} {label["x"]:.0f} {label["y"]:.0f})">{escape(name)}</text>'
        )

    arrows, candidates = [], []
    for (a, b), rels in parallel.items():
        for index, (rid, rel) in enumerate(rels):
            style = standard["style"](rel)
            path, label = path_between(a, b, index, len(rels))
            arrows.append(
                f'<path d="{path}" fill="none" {STYLES[style][0]}>'
                f'<title>{escape(f"{rel["type"]}: {rel.get("description", "")}")}</title></path>'
            )
            candidates.append((style != "main", -label["room"], label, rel["type"], style))

    # Arrows are named where the whole name fits and clears every card and label already placed: the main
    # relationships first, then those with the most room. The rest are named on hover.
    labels, placed = [], []
    for _, _, label, name, style in sorted(candidates, key=lambda c: c[:2]):
        if len(name) * REL_CHAR > label["room"]:
            continue
        points = footprint(label, name)
        if any(on_card(px, py) for px, py in points):
            continue
        if any(abs(px - qx) < 7 and abs(py - qy) < 10 for px, py in points for qx, qy in placed):
            continue
        placed += points
        labels.append(arrow_label(label, name, STYLES[style][1]))
    implied = []
    for name, node in nodes.items():
        for supertype in node["labels"].get("implied", []):
            # Drawn from the supertype, which the layout puts first, with the arrowhead pointing back at it.
            implied.append(
                f'<path d="{path_between(supertype, name)[0]}" fill="none" {IMPLIED_ATTRS}>'
                f"<title>{escape(f'Every {name} is also a {supertype}')}</title></path>"
            )
    height = max(bottom, dip + len(backwards) * 12) + 70

    cards_svg = []
    for name, node in nodes.items():
        c, hue = cards[name], HUES[standard["area"](node)]
        lines = [
            f'<text class="label" x="{x[name] + 13:.0f}" y="{y[name] + 20:.0f}">{escape(name)}</text>',
            f'<text class="sub" x="{x[name] + 13:.0f}" y="{y[name] + SUB_LINE:.0f}">{escape(c["sub"])}</text>',
            *(
                f'<text class="extra" x="{x[name] + 13:.0f}" y="{y[name] + SUB_LINE + 14 * (i + 1):.0f}">'
                f"{escape(extra)}</text>"
                for i, extra in enumerate(c["extras"])
            ),
        ]
        properties = ", ".join(node.get("properties", {}))
        title = escape(f"{name} — {node.get('description', '')}\nProperties: {properties}")
        body = (
            f'<g><title>{title}</title>'
            f'<rect x="{x[name]:.0f}" y="{y[name]:.0f}" width="{c["width"]:.0f}" height="{c["height"]:.0f}" '
            f'rx="7" fill="{tint(hue, 0.9)}" stroke="{hue}" stroke-width="1.4"/>{"".join(lines)}</g>'
        )
        cards_svg.append(f'<a href="{escape(node["reference"])}">{body}</a>' if node.get("reference") else body)

    markers = "".join(
        f'<marker id="{mid}" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6.5" markerHeight="6.5" '
        f'orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" fill="{color}"/></marker>'
        for mid, color in MARKERS
    )

    # The header: title, counts, then the colour and line legends on one row.
    implied_count = sum(len(node["labels"].get("implied", [])) for node in nodes.values())
    legend, lx = [], MARGIN
    for hue, name in zip(HUES, standard["areas"]):
        legend.append(f'<rect x="{lx}" y="96" width="14" height="14" rx="3" fill="{hue}"/>')
        legend.append(f'<text class="sub" x="{lx + 20}" y="108">{escape(name)}</text>')
        lx += 20 + len(name) * 5.9 + 40
    for attrs, name in (
        *((STYLES[style][0], name) for style, name in standard["legend"]),
        (IMPLIED_ATTRS, "subtype: also carries the supertype's label"),
    ):
        legend.append(f'<path d="M {lx} 103 h 40" fill="none" {attrs}/>')
        legend.append(f'<text class="sub" x="{lx + 52}" y="108">{escape(name)}</text>')
        lx += 52 + len(name) * 5.9 + 40
    width = max(width, lx + MARGIN)  # the legends must fit inside the canvas too

    subtitle = (
        f"{len(nodes)} nodes · {len(relationships)} relationships · {implied_count} implied labels, generated "
        f"from {standard['source']}. The main arrows are named by their relationship type; hover any arrow for "
        f"its name and description, and cards link to {standard['link']}."
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" '
        f'viewBox="0 0 {width:.0f} {height:.0f}" font-family="system-ui, -apple-system, Segoe UI, sans-serif">\n'
        f"<style>.label{{font-size:13px;font-weight:700;fill:{INK}}}.sub{{font-size:10.5px;fill:{SECONDARY}}}"
        f".extra{{font-size:10px;font-style:italic;fill:{MUTED}}}"
        f".rel{{font-size:9px;font-weight:600;letter-spacing:.3px;paint-order:stroke;stroke:{SURFACE};"
        f"stroke-width:3px;stroke-linejoin:round}}</style>\n"
        f"<defs>{markers}</defs>\n"
        f'<rect width="100%" height="100%" fill="{SURFACE}"/>\n'
        f'<text x="{MARGIN}" y="48" font-size="26" font-weight="700" fill="{INK}">{escape(model["name"])} ontology</text>\n'
        f'<text x="{MARGIN}" y="72" class="sub" font-size="13">{escape(subtitle)}</text>\n'
        + "".join(legend) + "\n"
        + "".join(arrows) + "".join(implied) + "".join(labels) + "\n"
        + "".join(cards_svg) + "\n</svg>\n"
    )


def read_yaml(path):
    """The model a model.yaml describes: as generate.py writes it, else through PyYAML if it is installed, else None."""
    text = path.read_text()
    if text.lstrip().startswith('"'):  # every key JSON-quoted: the form generate.py writes
        return parse_yaml(text)
    try:
        import yaml
    except ImportError:
        return None
    return yaml.safe_load(text)


def visualise(path):
    """Checks a model.json against the model.yaml beside it, if there is one, and writes the SVG beside it."""
    source = path / "model.json" if path.is_dir() else path
    name = f"{source.parent.name}/{source.name}" if source.name != "model.json" else source.parent.name
    model = json.loads(source.read_text())
    yaml_path = source.with_suffix(".yaml")
    if yaml_path.exists():
        described = read_yaml(yaml_path)
        if described is None:
            print(f"{name}: {yaml_path.name} isn't in the form generate.py writes and PyYAML isn't installed, so it wasn't checked")
        elif described != model:
            sys.exit(f"{name}: {yaml_path.name} and {source.name} describe different models")
    config_path = source.parent / "diagram.json"
    config = json.loads(config_path.read_text()) if config_path.exists() else {}
    svg = source.with_suffix(".svg")
    svg.write_text(render(model, standard_of(config, source.name)))
    implied = sum(len(node["labels"].get("implied", [])) for node in model["nodes"].values())
    print(f"{name}: {len(model['nodes'])} nodes, {len(model['relationships'])} relationships, {implied} implied labels → {svg.name}")


def main():
    here = Path(__file__).resolve().parent
    paths = [Path(arg).resolve() for arg in sys.argv[1:]] or sorted(p.parent for p in here.rglob("model.json"))
    for path in paths:
        visualise(path)


if __name__ == "__main__":
    main()
