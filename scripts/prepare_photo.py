#!/usr/bin/env python3
"""Turn a locally annotated overhead cat photo into two transparent PNGs."""

from bisect import bisect_right
from io import BytesIO
import json
from math import isfinite, sqrt
from pathlib import Path

from PIL import Image, ImageChops, ImageCms, ImageDraw, ImageFilter, ImageOps

if __package__:
    from .skill_i18n import argument_parser, msg
else:
    from skill_i18n import argument_parser, msg


BODY_SIZE = (1517, 935)
HEAD = complex(200, 445)
ROOT = complex(1136.23, 423.56)
TAIL_SIZE = (684, 200)
ROOT_X, LAST_SAMPLE_X, TIP_X, CENTER_Y = 20, 646, 658, 100
RESAMPLE = Image.Resampling.BICUBIC


def read_photo(path):
    with Image.open(path) as original:
        oriented = ImageOps.exif_transpose(original)
        photo = oriented.convert("RGBA")
        if profile := oriented.info.get("icc_profile"):
            color = oriented if oriented.mode in ("L", "RGB", "CMYK", "LAB") else photo.convert("RGB")
            srgb = ImageCms.profileToProfile(
                color, BytesIO(profile), ImageCms.createProfile("sRGB"), outputMode="RGB"
            )
            photo = Image.merge("RGBA", (*srgb.split(), photo.getchannel("A")))
    photo.info.clear()
    return photo


def point(coords, size):
    x, y = map(float, coords)
    if not (0 <= x < size[0] and 0 <= y < size[1]):
        raise ValueError(msg("pointOutside", x=x, y=y, width=size[0], height=size[1]))
    return complex(x, y)


def cutout(photo, outline, directory):
    if isinstance(outline, str):
        with Image.open(directory / outline) as source:
            mask = ImageOps.exif_transpose(source).convert("L")
        if mask.size != photo.size:
            raise ValueError(msg("maskSize"))
    else:
        if len(outline) < 3:
            raise ValueError(msg("outlinePoints"))
        vertices = [point(coords, photo.size) for coords in outline]
        mask = Image.new("L", photo.size)
        ImageDraw.Draw(mask).polygon([(p.real, p.imag) for p in vertices], fill=255)
        mask = mask.filter(ImageFilter.GaussianBlur(0.6))
    result = photo.copy()
    result.putalpha(ImageChops.multiply(photo.getchannel("A"), mask))
    return result


def trim_polygon(polygon, size, label):
    if not isinstance(polygon, list) or len(polygon) < 3:
        raise ValueError(msg("trimPoints", label=label))
    vertices = []
    for coords in polygon:
        if not isinstance(coords, list) or len(coords) != 2 or any(type(v) not in (int, float) for v in coords):
            raise ValueError(msg("trimCoordinates", label=label))
        try:
            vertices.append(point(coords, size))
        except (ValueError, OverflowError) as error:
            raise ValueError(msg("withDetail", item=label, error=error)) from error
    if vertices[0] == vertices[-1]:
        vertices.pop()
    if len(set(vertices)) != len(vertices):
        raise ValueError(msg("trimDuplicates", label=label))

    def cross(a, b, c):
        return ((b - a).conjugate() * (c - a)).imag

    def overlap(a, b, c, d):
        return max(min(a, b), min(c, d)) <= min(max(a, b), max(c, d))

    origin = vertices[0]
    edges = list(zip(vertices, vertices[1:] + vertices[:1]))
    if sum(cross(origin, a, b) for a, b in edges) == 0:
        raise ValueError(msg("trimZero", label=label))
    for i, (a, b) in enumerate(edges):
        for j in range(i + 2, len(edges) - (i == 0)):
            c, d = edges[j]
            if (
                overlap(a.real, b.real, c.real, d.real)
                and overlap(a.imag, b.imag, c.imag, d.imag)
                and cross(a, b, c) * cross(a, b, d) <= 0
                and cross(c, d, a) * cross(c, d, b) <= 0
            ):
                raise ValueError(msg("trimCross", label=label))
    return vertices


def trimmed_body_alpha(body, polygons):
    if not isinstance(polygons, list):
        raise ValueError(msg("trimList"))
    if not polygons:
        return None

    aa, tile_size = 4, 512
    step = tile_size * aa
    tiles = {}
    for i, polygon in enumerate(polygons, 1):
        vertices = trim_polygon(polygon, body.size, msg("trimLabel", i=i))
        scaled = [(int(p.real * aa), int(p.imag * aa)) for p in vertices]
        columns, rows = zip(*scaled)
        for row in range(min(rows) // step, max(rows) // step + 1):
            for column in range(min(columns) // step, max(columns) // step + 1):
                tiles.setdefault((column * tile_size, row * tile_size), []).append(scaled)

    alpha = body.getchannel("A")
    for (left, top), outlines in tiles.items():
        width = min(tile_size, body.width - left)
        height = min(tile_size, body.height - top)
        box = (left, top, left + width, top + height)
        keep = Image.new("L", (width * aa, height * aa), 255)
        draw = ImageDraw.Draw(keep)
        # Draw the union and average only the subpixels in each image pixel.
        for outline in outlines:
            draw.polygon([(x - left * aa, y - top * aa) for x, y in outline], fill=0)
        keep = keep.resize((width, height), Image.Resampling.BOX)
        alpha.paste(ImageChops.multiply(alpha.crop(box), keep), box)
    return alpha


def inspect_edge(photo, body, alpha, box):
    left, top, right, bottom = box
    width, height = right - left, bottom - top
    scale = min(4, 640 / max(width, height))
    size = (max(1, round(width * scale)), max(1, round(height * scale)))

    # Resize directly from the box to bound memory and keep enlarged pixels crisp.
    source = photo.resize(size, Image.Resampling.NEAREST, box=box)
    before = body.resize(size, Image.Resampling.NEAREST, box=box)
    after = before
    if alpha is not None:
        after = before.copy()
        after.putalpha(alpha.resize(size, Image.Resampling.NEAREST, box=box))

    light, cool = (246, 245, 240), (25, 37, 55)
    panels = [(source, light), (after, light), (after, cool)]
    if alpha is not None:
        panels.extend(((before, light), (before, cool)))
    width, height = size
    gap = 2
    preview = Image.new("RGB", (len(panels) * (width + gap) - gap, height), (128, 128, 128))
    for i, (layer, background) in enumerate(panels):
        x = i * (width + gap)
        preview.paste(background, (x, 0, x + width, height))
        preview.paste(layer, (x, 0), layer)
    return preview


def frame_body(body, head, root, alpha=None):
    if head == root:
        raise ValueError(msg("sameAnchors"))
    inverse = (root - head) / (ROOT - HEAD)
    offset = head - HEAD * inverse
    a, b = inverse.real, inverse.imag
    transform = (a, -b, offset.real, b, a, offset.imag)
    if alpha is not None:
        original_alpha = body.getchannel("A")
        body = body.copy()
        # Remove the background before the RGBA resample so its color cannot bleed into fur.
        body.putalpha(alpha)
    framed = body.transform(BODY_SIZE, Image.Transform.AFFINE, transform, RESAMPLE)
    if alpha is not None:
        # Bicubic interpolation can ring near sharp edges. A trim may only reduce opacity.
        before = original_alpha.transform(BODY_SIZE, Image.Transform.AFFINE, transform, RESAMPLE)
        after = ImageChops.darker(before, framed.getchannel("A"))
        framed.putalpha(after)
        visible = [0] + [255] * 255
        removed = ImageChops.subtract(before.point(visible), after.point(visible))
        framed.paste((0, 0, 0, 0), mask=removed)
    for label, anchor in (("head", HEAD), ("root", ROOT)):
        if framed.getpixel((round(anchor.real), round(anchor.imag)))[3] <= 85:
            raise ValueError(msg("uncovered", anchor=label))
    return framed, 1 / abs(inverse)


def straighten_tail(photo, centers, widths, scale):
    if len(centers) < 3 or widths[-1] != 0 or any(not isfinite(w) or w <= 0 for w in widths[:-1]):
        raise ValueError(msg("tailWidths"))
    segments = [b - a for a, b in zip(centers, centers[1:])]
    if any(segment == 0 for segment in segments):
        raise ValueError(msg("tailDuplicates"))
    directions = [segment / abs(segment) for segment in segments]
    tangents = [directions[0], *(a + b for a, b in zip(directions, directions[1:])), directions[-1]]
    if any(abs(tangent) < 0.01 for tangent in tangents):
        raise ValueError(msg("tailBend"))
    normals = [1j * tangent / abs(tangent) for tangent in tangents]
    arc = [0.0]
    for segment in segments:
        arc.append(arc[-1] + abs(segment))

    # Use the body scale across the tail so the rump seam retains its size.
    width_scale = min(scale, 188 / max(widths))
    half_strip = CENTER_Y / width_scale

    def section(x):
        if x < ROOT_X:
            center = centers[0] + directions[0] * ((x - ROOT_X) / scale)
            normal, width = normals[0], widths[0]
        else:
            if x <= LAST_SAMPLE_X:
                distance = arc[-2] * (x - ROOT_X) / (LAST_SAMPLE_X - ROOT_X)
            else:
                distance = arc[-2] + (arc[-1] - arc[-2]) * (x - LAST_SAMPLE_X) / (TIP_X - LAST_SAMPLE_X)
            i = min(bisect_right(arc, distance) - 1, len(segments) - 1)
            fraction = (distance - arc[i]) / (arc[i + 1] - arc[i])
            center = centers[i] + segments[i] * fraction
            normal = normals[i] * (1 - fraction) + normals[i + 1] * fraction
            normal /= abs(normal)
            if x > LAST_SAMPLE_X:
                width = widths[-2] * sqrt(max(0, 1 - fraction**2))
            else:
                width = widths[i] * (1 - fraction) + widths[i + 1] * fraction
        offset = normal * half_strip
        return center - offset, center + offset, width * width_scale / 2

    sections = [section(x) for x in range(TIP_X + 1)]
    mesh = []
    for x, ((top, bottom, _), (next_top, next_bottom, _)) in enumerate(zip(sections, sections[1:])):
        corners = tuple(coord for p in (top, bottom, next_bottom, next_top) for coord in (p.real, p.imag))
        mesh.append(((x, 0, x + 1, TAIL_SIZE[1]), corners))
    strip = photo.transform(TAIL_SIZE, Image.Transform.MESH, mesh, RESAMPLE)

    # Widths isolate the intended tail section from adjacent fur in tight bends.
    aa = 3
    matte = Image.new("L", tuple(size * aa for size in TAIL_SIZE))
    top = [(x * aa, (CENTER_Y - section[2]) * aa) for x, section in enumerate(sections)]
    bottom = [(x * aa, (CENTER_Y + section[2]) * aa) for x, section in reversed(list(enumerate(sections)))]
    ImageDraw.Draw(matte).polygon(top + bottom, fill=255)
    alpha = ImageChops.multiply(strip.getchannel("A"), matte.resize(TAIL_SIZE, Image.Resampling.LANCZOS))
    for x in range(ROOT_X, LAST_SAMPLE_X + 1):
        if alpha.getpixel((x, CENTER_Y)) <= 85:
            raise ValueError(msg("tailCenter", x=x))
    strip.putalpha(alpha)
    # Drop hidden RGB so fully transparent pixels carry no background from the photo.
    strip.paste((0, 0, 0, 0), (0, 0, *TAIL_SIZE), alpha.point([255] + [0] * 255))
    return strip, width_scale < scale


def main():
    parser = argument_parser("photoDescription")
    parser.add_argument("photo", type=Path, help=msg("photoHelp"))
    parser.add_argument("layout", type=Path, help=msg("layoutHelp"))
    parser.add_argument("output_dir", type=Path, help=msg("dirHelp"))
    parser.add_argument(
        "--inspect-box", action="append", type=int, nargs=4, default=[],
        metavar=("LEFT", "TOP", "RIGHT", "BOTTOM"),
        help=msg("inspectHelp"),
    )
    args = parser.parse_args()
    try:
        # json detects the BOM used by Windows PowerShell as well as plain UTF-8.
        layout = json.loads(args.layout.read_bytes())
        photo = read_photo(args.photo)
        for left, top, right, bottom in args.inspect_box:
            if not (0 <= left < right <= photo.width and 0 <= top < bottom <= photo.height):
                raise ValueError(msg("invalidBox", left=left, top=top, right=right, bottom=bottom,
                                     width=photo.width, height=photo.height))
        head = point(layout["head"], photo.size)
        tail = layout.get("tail", [])
        centers = [point((x, y), photo.size) for x, y, _ in tail]
        body = cutout(photo, layout["body"], args.layout.parent)
        alpha = trimmed_body_alpha(body, layout.get("body_trims", []))
        root = centers[0] if centers else point(layout["rump"], photo.size)
        framed, scale = frame_body(body, head, root, alpha)
        if not args.inspect_box:
            del body, alpha
        if centers:
            tail_photo = cutout(photo, layout["tail_outline"], args.layout.parent) if "tail_outline" in layout else photo
            strip, narrowed = straighten_tail(tail_photo, centers, [float(w) for _, _, w in tail], scale)
            if narrowed:
                print(msg("tailNarrowed"))
        else:
            strip = Image.new("RGBA", TAIL_SIZE)
        args.output_dir.mkdir()
        outputs = [args.output_dir / name for name in ("body.png", "tail.png")]
        try:
            framed.save(outputs[0], "PNG")
            strip.save(outputs[1], "PNG")
            for i, box in enumerate(args.inspect_box, 1):
                path = args.output_dir / f"edge-{i:02d}.png"
                outputs.append(path)
                inspect_edge(photo, body, alpha, box).save(path, "PNG")
        except Exception:
            for path in outputs:
                path.unlink(missing_ok=True)
            args.output_dir.rmdir()
            raise
    except (OSError, ValueError, TypeError, KeyError, AttributeError, ImageCms.PyCMSError) as error:
        parser.error(str(error))
    print(msg("layersReady" if centers else "staticLayersReady"))


if __name__ == "__main__":
    main()
