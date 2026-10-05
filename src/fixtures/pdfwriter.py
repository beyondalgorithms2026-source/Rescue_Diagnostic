"""Write deterministic, text-only PDF 1.4 documents with the standard library."""
from __future__ import annotations


FOOTER = "SYNTHETIC TEST DOCUMENT — NOT A REAL INVOICE"
PAGE_HEIGHT = 792
TOP_Y = 744
LINE_STEP = 15
LINES_PER_PAGE = 44


def _pdf_string(text):
    """Encode a PDF literal string using WinAnsi and escape PDF delimiters."""
    value = str(text).encode("cp1252", "replace")
    return value.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def _content_stream(lines, include_footer):
    page_lines = list(lines)
    if include_footer:
        page_lines.append(FOOTER)
    parts = [b"BT\n/F1 10 Tf\n"]
    y = TOP_Y
    for line in page_lines:
        parts.extend((b"1 0 0 1 48 ", str(y).encode("ascii"), b" Tm\n(", _pdf_string(line), b") Tj\n"))
        y -= LINE_STEP
    parts.append(b"ET\n")
    return b"".join(parts)


def render_pdf(lines, path, lines_per_page=LINES_PER_PAGE):
    """Write ``lines`` to a deterministic PDF, adding the required footer last."""
    if lines_per_page < 2:
        raise ValueError("lines_per_page must be at least 2")
    all_lines = [str(line) for line in lines]
    # Reserve a line on the final page for the footer. Empty documents still get one page.
    page_chunks = []
    cursor = 0
    while len(all_lines) - cursor > lines_per_page - 1:
        page_chunks.append(all_lines[cursor:cursor + lines_per_page])
        cursor += lines_per_page
    page_chunks.append(all_lines[cursor:])

    # Object ids 1–3 are shared catalog, page tree, and font. Page and stream ids follow.
    page_ids = [4 + 2 * i for i in range(len(page_chunks))]
    stream_ids = [page_id + 1 for page_id in page_ids]
    objects = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: ("<< /Type /Pages /Kids [{}] /Count {} >>".format(
            " ".join("{} 0 R".format(page_id) for page_id in page_ids), len(page_ids))).encode("ascii"),
        3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    }
    for index, (page_id, stream_id, chunk) in enumerate(zip(page_ids, stream_ids, page_chunks)):
        has_footer = index == len(page_chunks) - 1
        stream = _content_stream(chunk, has_footer)
        objects[page_id] = ("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 {}] "
                            "/Resources << /Font << /F1 3 0 R >> >> /Contents {} 0 R >>".format(
                                PAGE_HEIGHT, stream_id)).encode("ascii")
        objects[stream_id] = b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"endstream"

    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0] * (max(objects) + 1)
    for object_id in sorted(objects):
        offsets[object_id] = len(output)
        output.extend("{} 0 obj\n".format(object_id).encode("ascii"))
        output.extend(objects[object_id])
        output.extend(b"\nendobj\n")
    xref_offset = len(output)
    output.extend("xref\n0 {}\n".format(len(offsets)).encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend("{:010d} 00000 n \n".format(offset).encode("ascii"))
    output.extend(("trailer\n<< /Size {} /Root 1 0 R >>\nstartxref\n{}\n%%EOF\n".format(
        len(offsets), xref_offset)).encode("ascii"))
    with open(path, "wb") as f:
        f.write(output)
    return path
