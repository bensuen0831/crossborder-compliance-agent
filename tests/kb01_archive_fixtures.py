"""Genuine stored RAR4/RAR5 fixture encoding; actual file bytes, CRCs and headers."""

import struct
import zlib


def crc_file(path):
    crc = 0
    with path.open("rb") as source:
        while block := source.read(1024**2):
            crc = zlib.crc32(block, crc)
    return crc & 0xFFFFFFFF


def copy_file(path, output):
    with path.open("rb") as source:
        while block := source.read(1024**2):
            output.write(block)


def vint(number):
    result = bytearray()
    while number >= 128:
        result.append((number & 127) | 128)
        number >>= 7
    result.append(number)
    return bytes(result)


def rar4_header(kind, flags, body):
    data = struct.pack("<BHH", kind, flags, 7 + len(body)) + body
    return struct.pack("<H", zlib.crc32(data) & 0xFFFF) + data


def write_rar4(path, members):
    with path.open("wb") as output:
        output.write(b"Rar!\x1a\x07\x00")
        output.write(rar4_header(0x73, 0, struct.pack("<HI", 0, 0)))
        for name, source in members:
            name = name.encode("ascii")
            size = source.stat().st_size
            if size > 0xFFFFFFFF:
                raise ValueError("RAR4 fixture large-file extension is not implemented")
            body = (
                struct.pack(
                    "<IIBIIBBHI", size, size, 3, crc_file(source), 0, 20, 0x30, len(name), 0o100644
                )
                + name
            )
            output.write(rar4_header(0x74, 0x8000, body))
            copy_file(source, output)
        output.write(rar4_header(0x7B, 0, b""))


def rar5_header(kind, body, data_size=None):
    flags = 2 if data_size is not None else 0
    data = vint(kind) + vint(flags)
    if data_size is not None:
        data += vint(data_size)
    data += body
    data = vint(len(data)) + data
    return struct.pack("<I", zlib.crc32(data) & 0xFFFFFFFF) + data


def write_rar5(path, members):
    with path.open("wb") as output:
        output.write(b"Rar!\x1a\x07\x01\x00")
        output.write(rar5_header(1, vint(0)))
        for name, source in members:
            name = name.encode("utf-8")
            size = source.stat().st_size
            body = (
                vint(4)
                + vint(size)
                + vint(0o100644)
                + struct.pack("<I", crc_file(source))
                + vint(0)
                + vint(1)
                + vint(len(name))
                + name
            )
            output.write(rar5_header(2, body, size))
            copy_file(source, output)
        output.write(rar5_header(5, vint(0)))
