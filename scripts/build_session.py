#!/usr/bin/env python3
"""Build a local pet-the-cat session from a downloaded page and two PNGs."""

import base64
import codecs
import json
import os
from pathlib import Path
import struct
import tempfile
import zlib

if __package__:
    from .skill_i18n import argument_parser, catalog, language, msg
else:
    from skill_i18n import argument_parser, catalog, language, msg

PAGE_LIMIT = 4 * 1024 * 1024
PNG_LIMIT = 16 * 1024 * 1024
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
PNG_DEPTHS = {0: (1, 2, 4, 8, 16), 2: (8, 16), 3: (1, 2, 4, 8), 4: (8, 16), 6: (8, 16)}
PNG_CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}
ADAM7_PASSES = (
    (0, 0, 8, 8), (4, 0, 8, 8), (0, 4, 4, 8), (2, 0, 4, 4),
    (0, 2, 2, 4), (1, 0, 2, 2), (0, 1, 1, 2),
)

PACK_TAG = '<script type="application/octet-stream" id="pack">'
CHARSET_TAG = '<head>\n<meta charset="utf-16le">'
LOADER_ASSIGNMENT = "e.textContent=s;"
LOADER_HOOK = LOADER_ASSIGNMENT + "document.body.append(e);e.remove()"
RENDERER_HOOK = "D.photos=L;D.directory=ae;D.textContent=ay;"
SESSION_HEAD = (
    '<head>\n<meta charset="utf-8">\n'
    '<meta name="pet-the-cat-local" content="v1">\n'
    '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; '
    "script-src 'unsafe-inline'; script-src-attr 'none'; style-src 'unsafe-inline'; "
    'img-src data: blob:; base-uri \'none\'; form-action \'none\'">'
)

INSTALL_TEXTURES = r"""
{
  const {name, body, tail} = %s;
  const id = "petlocal";
  const tailId = id + "-tail";
  const menu = document.querySelector(".choices");
  if (!menu?.querySelector("button[data-cat]") ||
      document.querySelector('[data-cat="' + id + '"]') ||
      Object.hasOwn(ae, id) || Object.hasOwn(ae, tailId)) return;

  const hooks = [
    ["{type:'image/avif'}",
      "{type:name==='petlocal'||name==='petlocal-tail'?'image/png':'image/avif'}"],
    ["selected=Object.hasOwn(names,requestedCat)?requestedCat:'kuro';",
      "selected=Object.hasOwn(names,requestedCat)?requestedCat:'petlocal';"],
  ];
  let renderer = ay;
  for (const [before, after] of hooks) {
    const index = renderer.indexOf(before);
    if (index < 0 || index !== renderer.lastIndexOf(before)) return;
    renderer = renderer.replace(before, after);
  }

  const decode = encoded => {
    const binary = atob(encoded);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < bytes.length; i++) bytes[i] = binary.charCodeAt(i);
    return bytes;
  };
  const bodyBytes = decode(body);
  const tailBytes = decode(tail);
  const tailOffset = L.length + bodyBytes.length;
  const photos = new Uint8Array(tailOffset + tailBytes.length);
  photos.set(L);
  photos.set(bodyBytes, L.length);
  photos.set(tailBytes, tailOffset);
  ae[id] = [L.length, bodyBytes.length, 0, 0, 1517, 935, 1517, 935];
  ae[tailId] = [tailOffset, tailBytes.length, 0, 0, 684, 200, 684, 200];

  const button = document.createElement("button");
  button.type = "button";
  button.dataset.cat = id;
  button.title = name;
  button.setAttribute("aria-label", name);
  button.setAttribute("aria-pressed", "false");
  const coat = document.createElement("span");
  coat.className = "coat";
  coat.setAttribute("aria-hidden", "true");
  const preview = URL.createObjectURL(new Blob([bodyBytes], {type: "image/png"}));
  coat.style.background = "#e3d9ca url(" + preview + ") center/contain no-repeat";
  button.append(coat);
  menu.append(button);

  D.photos = photos;
  D.directory = ae;
  D.textContent = renderer;
  petLocalInstalled = true;
}
"""


def read_limited(path, limit):
    if not path.is_file():
        raise ValueError(msg("notFile", path=path))
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError(msg("tooLarge", path=path, limit=limit // (1024 * 1024)))
    return data


def png_chunks(data):
    if not data.startswith(PNG_SIGNATURE):
        raise ValueError(msg("pngSignature"))
    view = memoryview(data)
    offset = len(PNG_SIGNATURE)
    while offset + 12 <= len(data):
        size, kind = struct.unpack_from(">I4s", data, offset)
        end = offset + 8 + size
        if end + 4 > len(data):
            raise ValueError(msg("pngTruncated"))
        checksum = struct.unpack_from(">I", data, end)[0]
        if not kind.isalpha() or not kind[2:3].isupper():
            raise ValueError(msg("pngChunkType"))
        if zlib.crc32(view[offset + 4:end]) != checksum:
            raise ValueError(msg("pngCrc", kind=kind.decode("ascii")))
        if kind == b"IEND":
            if size or end + 4 != len(data):
                raise ValueError(msg("pngEndInvalid"))
            return
        yield kind, view[offset + 8:end]
        offset = end + 4
    raise ValueError(msg("pngEndMissing"))


def validate_scanlines(compressed, width, height, bits_per_pixel, interlace):
    passes = ADAM7_PASSES if interlace else ((0, 0, 1, 1),)
    layouts = []
    for x, y, dx, dy in passes:
        if x < width and y < height:
            columns = (width - x + dx - 1) // dx
            rows = (height - y + dy - 1) // dy
            stride = 1 + (columns * bits_per_pixel + 7) // 8
            layouts.append((stride, rows))
    expected = sum(stride * rows for stride, rows in layouts)
    decoder = zlib.decompressobj()
    pixels = decoder.decompress(compressed, expected + 1)
    if len(pixels) != expected or not decoder.eof or decoder.unused_data:
        raise ValueError(msg("pngPixels"))
    offset = 0
    for stride, rows in layouts:
        end = offset + stride * rows
        if any(value > 4 for value in pixels[offset:end:stride]):
            raise ValueError(msg("pngFilter"))
        offset = end


def validate_png(data, dimensions):
    chunks = png_chunks(data)
    kind, header = next(chunks, (None, b""))
    if kind != b"IHDR" or len(header) != 13:
        raise ValueError(msg("pngHeader"))
    width, height, depth, color, compression, filter_method, interlace = struct.unpack(
        ">IIBBBBB", header
    )
    if (width, height) != dimensions:
        raise ValueError(msg("pngDimensions", expectedWidth=dimensions[0], expectedHeight=dimensions[1],
                             width=width, height=height))
    if depth not in PNG_DEPTHS.get(color, ()) or compression or filter_method or interlace > 1:
        raise ValueError(msg("pngFormat"))

    palette = 0
    transparency = color in (4, 6)
    compressed = bytearray()
    seen_idat = False
    ended_idat = False
    for kind, chunk in chunks:
        if kind == b"IDAT":
            if ended_idat or (color == 3 and not palette):
                raise ValueError(msg("pngDataOrder"))
            compressed.extend(chunk)
            seen_idat = True
            continue
        ended_idat = seen_idat
        if kind == b"PLTE":
            if seen_idat or palette or (color == 2 and transparency) or color in (0, 4) or (
                not len(chunk) or len(chunk) % 3 or len(chunk) > 768
            ):
                raise ValueError(msg("pngPalette"))
            palette = len(chunk) // 3
            if color == 3 and palette > 2 ** depth:
                raise ValueError(msg("pngPaletteDepth"))
        elif kind == b"tRNS":
            if seen_idat or transparency or color not in (0, 2, 3):
                raise ValueError(msg("pngTransparencyChunk"))
            if color == 3:
                if not 0 < len(chunk) <= palette or all(alpha == 255 for alpha in chunk):
                    raise ValueError(msg("pngPaletteAlpha"))
            else:
                channels = PNG_CHANNELS[color]
                if len(chunk) != 2 * channels or any(
                    value >= 2 ** depth for (value,) in struct.iter_unpack(">H", chunk)
                ):
                    raise ValueError(msg("pngAlphaColor"))
            transparency = True
        elif kind == b"acTL":
            raise ValueError(msg("pngStatic"))
        elif kind[:1].isupper():
            raise ValueError(msg("pngCritical", kind=kind.decode("ascii")))
    if not transparency:
        raise ValueError(msg("pngAlpha"))
    validate_scanlines(compressed, width, height, depth * PNG_CHANNELS[color], interlace)


def read_texture(path, dimensions):
    data = read_limited(path, PNG_LIMIT)
    try:
        validate_png(data, dimensions)
    except (ValueError, zlib.error) as error:
        raise ValueError(msg("withDetail", item=path, error=error)) from error
    return base64.b64encode(data).decode("ascii")


def js_value(value):
    # Also prevent HTML's script tokenizer from seeing user data as markup.
    return json.dumps(value, ensure_ascii=True, separators=(",", ":")).replace("<", r"\u003c")


def read_bootstrap(pack, lang=None):
    # The public page prefixes its pack with the small bootstrap in 14-bit pairs.
    # The bootstrap itself still handles the site-specific decompression.
    base = 0x3000
    length = ord(pack[0]) - base if pack else 0
    if not 0 < length < len(pack) - 1:
        raise ValueError(msg("packLength", lang=lang))
    pairs = [ord(char) - base for char in pack[1:1 + length]]
    if any(not 0 <= pair < 0x4000 for pair in pairs):
        raise ValueError(msg("packEncoding", lang=lang))
    return "".join(chr(pair >> 7) + chr(pair & 127) for pair in pairs)


def build_session(raw, name, body, tail, lang=None):
    lang = lang or language()
    words = catalog(lang)["session"]
    try:
        if not raw.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
            raise ValueError(msg("pageEncoding", lang=lang))
        page = raw.decode("utf-16")
        head, pack_tag, rest = page.partition(PACK_TAG)
        pack, close_tag, loader = rest.partition("</script>")
        if (
            not pack_tag or not close_tag or page.count(PACK_TAG) != 1
            or not head.startswith('<!doctype html>\n<html lang="ja">\n' + CHARSET_TAG)
            or loader.count(LOADER_HOOK) != 1 or loader.count(LOADER_ASSIGNMENT) != 1
        ):
            raise ValueError(msg("pageStructure", lang=lang))
        bootstrap = read_bootstrap(pack, lang)
        if bootstrap.count(RENDERER_HOOK) != 1:
            raise ValueError(msg("rendererEntry", lang=lang))
    except ValueError as error:
        raise ValueError(f'{error} {words["incompatible"]}') from error

    textures = {"name": name, "body": body, "tail": tail}
    patched = bootstrap.replace(RENDERER_HOOK, INSTALL_TEXTURES % js_value(textures))
    script = (
        "(() => {\nlet petLocalInstalled = false;\n" + patched
        + "\nif (!petLocalInstalled) {\n"
        '  const notice = document.createElement("p");\n'
        '  notice.setAttribute("role", "alert");\n'
        "  notice.lang = " + js_value(lang) + ";\n"
        "  notice.textContent = " + js_value(words["incompatible"]) + ";\n"
        "  document.body.prepend(notice);\n}\n})();"
    )
    loader = loader.replace(LOADER_ASSIGNMENT, "e.textContent=" + js_value(script) + ";")
    session_head = SESSION_HEAD + f'\n<meta name="pet-my-cat-language" content="{lang}">'
    return head.replace(CHARSET_TAG, session_head, 1) + pack_tag + pack + close_tag + loader


def write_new(path, document):
    # Publish only a finished file, and never replace an existing directory entry.
    out = tempfile.NamedTemporaryFile(dir=path.parent, prefix=".pet-session-", delete=False)
    temporary = Path(out.name)
    try:
        with out:
            out.write(document.encode("utf-8"))
        os.link(temporary, path)
    except FileExistsError as error:
        raise ValueError(msg("outputExists", path=path)) from error
    finally:
        temporary.unlink()


def main():
    parser = argument_parser("buildDescription")
    parser.add_argument("--page", type=Path, required=True, help=msg("pageHelp"))
    parser.add_argument("--body", type=Path, required=True, help=msg("bodyHelp"))
    parser.add_argument("--tail", type=Path, required=True, help=msg("tailHelp"))
    parser.add_argument("--name", help=msg("nameHelp"))
    parser.add_argument("--out", type=Path, required=True, help=msg("outHelp"))
    args = parser.parse_args()
    name = args.name if args.name is not None else catalog(args.lang)["session"]["defaultName"]
    if not name.strip():
        parser.error(msg("blankName"))
    try:
        page = read_limited(args.page, PAGE_LIMIT)
        body = read_texture(args.body, (1517, 935))
        tail = read_texture(args.tail, (684, 200))
        write_new(args.out, build_session(page, name, body, tail, args.lang))
    except (OSError, ValueError) as error:
        parser.exit(1, f"{parser.prog}: {error}\n")


if __name__ == "__main__":
    main()
