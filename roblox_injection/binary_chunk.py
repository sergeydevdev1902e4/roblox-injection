import struct
from dataclasses import dataclass
from typing import List, Tuple, Optional

ROBLOX_BINARY_MAGIC = b"<roblox!\x89\xff\x0d\x0a\x1a\x0a"


class BinaryFormatError(Exception):
    pass


@dataclass
class ChunkHeader:
    name: str
    compressed_len: int
    uncompressed_len: int
    payload_offset: int


def verify_header(data: bytes) -> Tuple[int, int, int]:
    """Validate rbxl binary header and return (version, class_count, instance_count)."""
    if len(data) < 32:
        raise BinaryFormatError("File too short to be a valid Roblox binary place")

    if not data.startswith(ROBLOX_BINARY_MAGIC):
        raise BinaryFormatError("Invalid binary header magic bytes")

    # header layout: 14 bytes magic, 2 bytes version, 4 bytes class count, 4 bytes inst count, 8 bytes reserved
    version, class_count, instance_count = struct.unpack_from("<HII", data, 14)
    if version != 0:
        raise BinaryFormatError(f"Unsupported binary format version: {version}")

    return version, class_count, instance_count


def scan_chunks(data: bytes) -> List[ChunkHeader]:
    verify_header(data)
    offset = 32
    total_len = len(data)
    chunks: List[ChunkHeader] = []

    while offset < total_len:
        if offset + 16 > total_len:
            # Some exporters leave trailing null bytes after END chunk
            tail = data[offset:]
            if set(tail) == {0}:
                break
            raise BinaryFormatError(f"Truncated chunk header at offset {offset}")

        raw_name, comp_len, uncomp_len, reserved = struct.unpack_from("<4sIII", data, offset)
        offset += 16

        chunk_name = raw_name.decode("latin1", errors="replace").rstrip("\x00")

        # comp_len == 0 means uncompressed payload
        payload_size = comp_len if comp_len > 0 else uncomp_len
        # print(f"chunk={chunk_name} c_len={comp_len} u_len={uncomp_len} offset={offset}")

        if offset + payload_size > total_len:
            raise BinaryFormatError(f"Chunk {chunk_name} specifies size beyond file boundary")

        chunks.append(ChunkHeader(
            name=chunk_name,
            compressed_len=comp_len,
            uncompressed_len=uncomp_len,
            payload_offset=offset,
        ))

        offset += payload_size
        if chunk_name == "END":
            # FIXME: verify if END chunk payload content matters (usually contains '<roblox!')
            break

    return chunks


def get_raw_chunk_payload(data: bytes, chunk: ChunkHeader) -> bytes:
    size = chunk.compressed_len if chunk.compressed_len > 0 else chunk.uncompressed_len
    start = chunk.payload_offset
    return data[start : start + size]
