"""A voice note recorded in the browser, made into one WhatsApp accepts (2026-11-04).

Chrome and Edge record audio as WebM with Opus inside; WhatsApp takes Opus only in an Ogg file. The sound itself is
already Opus, so nothing is re-encoded: the Opus packets are lifted out of the WebM blocks and written as Ogg pages
(RFC 7845) -- the same as `ffmpeg -c:a copy`, without installing ffmpeg on the server. Firefox records Ogg already and
Safari records MP4/AAC, which WhatsApp also takes, so those pass through untouched.
"""

import struct

# Matroska element IDs, with their length-marker bits, as they appear in the file.
EBML = 0x1A45DFA3
SEGMENT, CLUSTER, TRACKS, TRACK_ENTRY, BLOCK_GROUP = 0x18538067, 0x1F43B675, 0x1654AE6B, 0xAE, 0xA0
CODEC_ID, CODEC_PRIVATE, CHANNELS, AUDIO, SIMPLE_BLOCK, BLOCK = 0x86, 0x63A2, 0x9F, 0xE1, 0xA3, 0xA1
MASTERS = {SEGMENT, CLUSTER, TRACKS, TRACK_ENTRY, BLOCK_GROUP, AUDIO}
SAMPLE_RATE = 48000  # Ogg Opus granule positions always count 48 kHz samples


class VoiceError(ValueError):
    pass


def _vint(data: bytes, pos: int, *, keep_marker: bool) -> tuple[int, int, bool]:
    """(value, next position, all-ones) of the EBML variable-length integer at `pos`."""
    if pos >= len(data):
        raise VoiceError("The recording ends part-way through.")
    first = data[pos]
    length = next((n for n in range(1, 9) if first & (0x80 >> (n - 1))), 0)
    if not length or pos + length > len(data):
        raise VoiceError("The recording is not a WebM file this can read.")
    value = first if keep_marker else first & (0xFF >> length)
    for byte in data[pos + 1: pos + length]:
        value = (value << 8) | byte
    unknown = not keep_marker and value == (1 << (7 * length)) - 1
    return value, pos + length, unknown


def _opus_samples(packet: bytes) -> int:
    """How many 48 kHz samples one Opus packet holds, from its TOC byte (RFC 6716 section 3.1)."""
    if not packet:
        return 0
    toc = packet[0]
    config = toc >> 3
    if config < 12:
        frame = (480, 960, 1920, 2880)[config % 4]
    elif config < 16:
        frame = (480, 960)[config % 2]
    else:
        frame = (120, 240, 480, 960)[config % 4]
    code = toc & 0x03
    frames = 1 if code == 0 else 2 if code in (1, 2) else (packet[1] & 0x3F if len(packet) > 1 else 0)
    return frame * frames


def read_webm_opus(data: bytes) -> tuple[bytes, int, list[bytes]]:
    """(OpusHead from CodecPrivate or b"", channels, Opus packets in order) from a single-track WebM recording."""
    if len(data) < 4 or struct.unpack(">I", data[:4])[0] != EBML:
        raise VoiceError("The recording is not a WebM file.")
    head, channels, codec, packets = b"", 1, "", []
    pos = 0
    while pos < len(data):
        element, pos, _ = _vint(data, pos, keep_marker=True)
        size, pos, unknown = _vint(data, pos, keep_marker=False)
        if element in MASTERS:
            continue  # step inside; a cluster of unknown size simply runs until the next cluster begins
        end = len(data) if unknown else min(pos + size, len(data))
        body = data[pos:end]
        if element == CODEC_ID:
            codec = body.decode("ascii", "replace").strip("\x00")
        elif element == CODEC_PRIVATE:
            head = body
        elif element == CHANNELS and body:
            channels = int.from_bytes(body, "big")
        elif element in (SIMPLE_BLOCK, BLOCK) and len(body) > 4:
            _, at, _ = _vint(body, 0, keep_marker=False)  # track number
            flags = body[at + 2]
            if flags & 0x06:
                raise VoiceError("The recording uses laced blocks, which this cannot read.")
            packets.append(body[at + 3:])
        pos = end
    if codec and codec != "A_OPUS":
        raise VoiceError(f"The recording is {codec}, not Opus.")
    if not packets:
        raise VoiceError("The recording has no sound in it.")
    return head, channels, packets


def _crc_table() -> list[int]:
    table = []
    for n in range(256):
        crc = n << 24
        for _ in range(8):
            crc = ((crc << 1) ^ 0x04C11DB7) if crc & 0x80000000 else crc << 1
        table.append(crc & 0xFFFFFFFF)
    return table


CRC_TABLE = _crc_table()


def _crc32_ogg(data: bytes) -> int:
    """Ogg's CRC-32 (polynomial 0x04C11DB7, not reflected -- not zlib's)."""
    crc = 0
    for byte in data:
        crc = ((crc << 8) & 0xFFFFFFFF) ^ CRC_TABLE[(crc >> 24) ^ byte]
    return crc


def _page(packet: bytes, *, serial: int, sequence: int, granule: int, flags: int) -> bytes:
    lacing = [255] * (len(packet) // 255) + [len(packet) % 255]
    if len(lacing) > 255:
        raise VoiceError("One piece of the recording is too large for an Ogg page.")
    header = struct.pack("<4sBBqIIIB", b"OggS", 0, flags, granule, serial, sequence, 0, len(lacing)) + bytes(lacing)
    page = bytearray(header + packet)
    page[22:26] = struct.pack("<I", _crc32_ogg(bytes(page)))
    return bytes(page)


def opus_head(channels: int) -> bytes:
    return b"OpusHead" + struct.pack("<BBHIhB", 1, channels, 312, SAMPLE_RATE, 0, 0)


def webm_to_ogg(data: bytes, *, serial: int = 0x0ABF2026) -> bytes:
    """The same Opus sound, in an Ogg file: OpusHead page, OpusTags page, then one page per packet."""
    head, channels, packets = read_webm_opus(data)
    if not head.startswith(b"OpusHead"):
        head = opus_head(channels)
    vendor = b"ABF-FST portal"
    tags = b"OpusTags" + struct.pack("<I", len(vendor)) + vendor + struct.pack("<I", 0)
    out = [_page(head, serial=serial, sequence=0, granule=0, flags=0x02),
           _page(tags, serial=serial, sequence=1, granule=0, flags=0x00)]
    granule = 0
    for n, packet in enumerate(packets):
        granule += _opus_samples(packet)
        last = n == len(packets) - 1
        out.append(_page(packet, serial=serial, sequence=n + 2, granule=granule, flags=0x04 if last else 0x00))
    return b"".join(out)
