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
        <p><a href="https://github.com/browserboard/smufl2svg">Source code</a></p>
        $IMAGES_HTML
    </body>
</html>
"""


IMG_TEMPLATE = """
<div class="item">
    <img src="{src}" title="{glyph_name}"><br>
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
ORDERED_CLASSES = [
    'tf_metronomeMarks',
    'rests',
    'octaves',
    'forTextBasedApplications',
    'combiningStaffPositions',
    'tf_ornaments',
    'dynamics',
    'Uncategorized',
    'pauses',
    'pausesAbove',
    'pausesBelow',
    'tf_hairpins',
    'tf_pictograms',
    
    # clefs
    'clefsF',
    'clefsG',
    'clefsC',
    'clefs',
    
    # staves
    'tf_zeroWidth',
]
with open("metadata/classes.json") as f:
    classes_data = json.load(f)
    for k, items in classes_data.items():
        if k not in ORDERED_CLASSES:
            ORDERED_CLASSES.append(k)
        for item in items:
            CLASSES[item] = k
            
# ignore symbols that either need to be combined or extend outside a reasonable bounding box
STOPWORDS = ['number below', 'number above', 'combining', 'notehead', '512th', '1024th', 'systemDivider', 'organGerman']


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
            minx, miny, maxx, maxy = [int(x) for x in viewbox.split()]
            
            # the original bounding box is bigger than we need
            miny += 600
            maxx -= 400
            maxy += 800

            width = maxx - minx
            height = maxy - miny
            viewbox = "{minx} {miny} {maxx} {maxy}".format(minx=minx, miny=miny, maxx=maxx, maxy=maxy)
        if child.tag != "{http://www.w3.org/2000/svg}glyph":
            continue
        if "unicode" not in child.attrib or "d" not in child.attrib:
            continue
        character_u = child.attrib["unicode"]
        code_point = ord(list(character_u)[0])
        try:
            glyph_name = GLYPH_NAMES[code_point]
        except KeyError:
            continue
        if code_point in GLYPH_DESCRIPTIONS:
            label = (
                GLYPH_DESCRIPTIONS[code_point].replace("/", "-").replace(":", "-")
            )
        else:
            # continue
            label = child.attrib["glyph-name"]
            
        has_stop_word = False
        for word in STOPWORDS:
            if word in label.lower() or word in glyph_name:
                print("Skip", glyph_name, repr(label))
                has_stop_word = True
                break
        if has_stop_word:
            continue

        path = os.path.join(args.output_dir, glyph_name) + ".svg"

        try:
            cls = CLASSES[glyph_name]
        except KeyError:
            cls = "Uncategorized"
            
        if cls == "noteheads" or cls not in ORDERED_CLASSES:
            continue # skip all note heads

        if cls not in items:
            items[cls] = []

        item = {
            "path": path,
            "html": IMG_TEMPLATE.format(src=path, label=label, glyph_name=glyph_name),
            "d": child.attrib["d"],
        }
        with open(item["path"], "w") as f:
            f.write(
                SVG_TEMPLATE.format(
                    width=width, height=height, viewbox=viewbox, path=item["d"]
                )
        )

        items[cls].append(
            item
        )

    images_html_items = []
    for cls_k in ORDERED_CLASSES:
        if cls_k not in items:
            print("Nothing in", cls_k)
            continue
        inner_items = items[cls_k]
        images_html_items.append("<h1>" + cls_k + "</h1>")
        images_html_items.append('<div class="images">')
        for (i, item) in enumerate(inner_items):
            images_html_items.append(item["html"])
            # if i > 0 and i % 10 == 0:
            # images_html_items.append('<div class="break"></div>')
        images_html_items.append("</div>")

    with open("index.html", "w") as f:
        f.write(HTML_TEMPLATE.replace("$IMAGES_HTML", "".join(images_html_items)))


if __name__ == "__main__":
    main(sys.argv)
