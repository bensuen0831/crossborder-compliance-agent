"""Genuine PDF raster/text fixtures, without sparse files or unused binary padding."""

import hashlib


def write_large_raster_pdf(path, marker, *, width=30000, height=6000):
    offsets = [0]
    with path.open("wb") as out:
        out.write(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")

        def obj(number, content):
            offsets.append(out.tell())
            out.write(str(number).encode() + b" 0 obj\n" + content + b"\nendobj\n")

        obj(1, b"<< /Type /Catalog /Pages 2 0 R >>")
        obj(2, b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
        obj(
            3,
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 5 0 R >> /XObject << /Im1 6 0 R >> >> "
            b"/Contents 4 0 R >>",
        )
        safe_marker = marker.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        content = (
            "BT /F1 12 Tf 40 750 Td (Article 1. " + safe_marker + ") Tj ET\n"
            "q 500 0 0 500 40 180 cm /Im1 Do Q\n"
        ).encode("ascii")
        obj(
            4,
            b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"endstream",
        )
        obj(5, b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
        offsets.append(out.tell())
        size = width * height * 3
        out.write(
            b"6 0 obj\n<< /Type /XObject /Subtype /Image /ColorSpace /DeviceRGB "
            b"/BitsPerComponent 8 /Width "
            + str(width).encode()
            + b" /Height "
            + str(height).encode()
            + b" /Length "
            + str(size).encode()
            + b" >>\nstream\n"
        )

        # Every byte is consumed as an actual RGB sample by the PDF image XObject.
        remaining, index = size, 0
        while remaining:
            amount = min(1024**2, remaining)
            pixels = hashlib.shake_256((marker + ":" + str(index)).encode()).digest(amount)
            out.write(pixels)
            remaining -= amount
            index += 1
        out.write(b"\nendstream\nendobj\n")
        xref = out.tell()
        out.write(b"xref\n0 7\n0000000000 65535 f \n")
        for offset in offsets[1:]:
            out.write(f"{offset:010d} 00000 n \n".encode())
        out.write(
            b"trailer\n<< /Size 7 /Root 1 0 R >>\nstartxref\n" + str(xref).encode() + b"\n%%EOF\n"
        )


def write_large_multipage_pdf(path, marker, *, pages=12, width=5000, height=3000):
    """Keep each genuine image stream within the native reader's safety bound."""
    offsets = [0]
    with path.open("wb") as output:
        output.write(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")

        def begin(number):
            assert len(offsets) == number
            offsets.append(output.tell())
            output.write(f"{number} 0 obj\n".encode())

        begin(1)
        output.write(b"<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
        begin(2)
        children = " ".join(f"{4 + i * 3} 0 R" for i in range(pages))
        output.write(f"<< /Type /Pages /Kids [{children}] /Count {pages} >>\nendobj\n".encode())
        begin(3)
        output.write(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n")
        for page in range(pages):
            number = 4 + page * 3
            begin(number)
            output.write(
                (
                    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                    "/Resources << /Font << /F1 3 0 R >> /XObject << /Im1 "
                    f"{number + 2} 0 R >> >> /Contents {number + 1} 0 R >>\nendobj\n"
                ).encode()
            )
            text = f"Article {page + 1}. {marker}".replace("(", "\\(").replace(")", "\\)")
            content = (
                f"BT /F1 10 Tf 30 760 Td ({text}) Tj ET\nq 500 0 0 500 40 180 cm /Im1 Do Q\n"
            ).encode("ascii")
            begin(number + 1)
            output.write(
                f"<< /Length {len(content)} >>\nstream\n".encode()
                + content
                + b"endstream\nendobj\n"
            )
            begin(number + 2)
            remaining = width * height * 3
            output.write(
                (
                    "<< /Type /XObject /Subtype /Image /ColorSpace /DeviceRGB "
                    f"/BitsPerComponent 8 /Width {width} /Height {height} "
                    f"/Length {remaining} >>\nstream\n"
                ).encode()
            )
            block_number = 0
            while remaining:
                amount = min(1024**2, remaining)
                output.write(
                    hashlib.shake_256(f"{marker}:{page}:{block_number}".encode()).digest(amount)
                )
                remaining -= amount
                block_number += 1
            output.write(b"\nendstream\nendobj\n")
        xref = output.tell()
        output.write(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
        for offset in offsets[1:]:
            output.write(f"{offset:010d} 00000 n \n".encode())
        output.write(
            (
                f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n"
            ).encode()
        )
