#!/usr/bin/env python3
import json
import os
import re
import sys
from argparse import ArgumentParser, FileType
from collections import OrderedDict
from xml.etree import ElementTree

SVG_TEMPLATE = """<?xml version="1.0" standalone="no"?>
<svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="{viewbox}"
    width="{width}"
    height="{height}"
    >
    <g transform="matrix(1 0 0 -1 0 0)">
        <path style="fill: #000000" d="{path}" />
    </g>
</svg>
"""


HTML_TEMPLATE = """
<!doctype html>
<html>
    <head>
        <style>
            .images {
                display: flex;
                flex-wrap: wrap;
            }
            
            .images img, .images .item {
                width: 5vw;
                height: auto;
            }

            .images img {
                border: 1px solid gray;
            }

            .break {
                width: 100%;
                height: 0;
            }
        </style>
    </head>
    <body>
        $IMAGES_HTML
    </body>
</html>
"""


IMG_TEMPLATE = """
<div class="item">
    <img src="{src}"><br>
    <div>{label}</div>
</div>
"""


GLYPH_NAME_RE = re.compile(r"uni([A-F0-9]+)")


GLYPH_NAMES = {}
GLYPH_DESCRIPTIONS = {}
with open("metadata/glyphnames.json") as f:
    glyph_name_data = json.load(f)
    for k, v in glyph_name_data.items():
        codepoint = int(v["codepoint"][2:], 16)
        GLYPH_NAMES[codepoint] = k
        GLYPH_DESCRIPTIONS[codepoint] = v["description"]


CLASSES = {}
ORDERED_CLASSES = []
with open("metadata/classes.json") as f:
    classes_data = json.load(f)
    for k, items in classes_data.items():
        ORDERED_CLASSES.append(k)
        for item in items:
            CLASSES[item] = k
ORDERED_CLASSES = sorted(ORDERED_CLASSES)


def main(args):
    p = ArgumentParser()
    p.add_argument("input", type=FileType("rb"))
    p.add_argument("output_dir")

    args = p.parse_args()
    os.makedirs(args.output_dir, exist_ok=True)

    root = (
        ElementTree.parse(args.input)
        .getroot()
        .find("{http://www.w3.org/2000/svg}defs")
        .find("{http://www.w3.org/2000/svg}font")
    )
    width = None
    height = None
    viewbox = None

    items = OrderedDict()

    for child in root:
        if child.tag == "{http://www.w3.org/2000/svg}font-face":
            viewbox = child.attrib["bbox"]
            values = [int(x) for x in viewbox.split()]
            width = values[2] - values[0]
            height = values[3] - values[1]
        if child.tag != "{http://www.w3.org/2000/svg}glyph":
            continue
        if "unicode" not in child.attrib or "d" not in child.attrib:
            continue
        character_u = child.attrib["unicode"]
        code_point = ord(list(character_u)[0])
        if code_point in GLYPH_DESCRIPTIONS:
            glyph_name = (
                GLYPH_DESCRIPTIONS[code_point].replace("/", "-").replace(":", "-")
            )
        else:
            # continue
            glyph_name = child.attrib["glyph-name"]

        path = os.path.join(args.output_dir, glyph_name) + ".svg"

        try:
            cls = CLASSES[GLYPH_NAMES[code_point]]
        except KeyError:
            cls = "Uncategorized"

        if cls not in items:
            items[cls] = []
        items[cls].append(
            {
                "path": path,
                "html": IMG_TEMPLATE.format(src=path, label=glyph_name),
                "d": child.attrib["d"],
            }
        )

    images_html_items = []
    for cls_k, items in items.items():
        images_html_items.append("<h1>" + cls_k + "</h1>")
        images_html_items.append('<div class="images">')
        for (i, item) in enumerate(items):
            with open(item["path"], "w") as f:
                f.write(
                    SVG_TEMPLATE.format(
                        width=width, height=height, viewbox=viewbox, path=item["d"]
                    )
                )
            images_html_items.append(item["html"])
            # if i > 0 and i % 10 == 0:
            # images_html_items.append('<div class="break"></div>')
        images_html_items.append("</div>")

    with open("index.html", "w") as f:
        f.write(HTML_TEMPLATE.replace("$IMAGES_HTML", "".join(images_html_items)))


if __name__ == "__main__":
    main(sys.argv)
