# Copyright (c) 2021 CensoredUsername
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.



# This file contains documented strategies used against known obfuscation techniques and some machinery
# to test them against.

# Architecture is pretty simple. There's at least two steps in unpacking the rpyc format.
# RPYC2 is an archive format that can contain multiple streams (referred to as slots)
# The first step is extracting the slot from it, which is done by one of the extractors.
# These all give a blob that's either still zlib-compressed or just the raw slot
# (some methods rely on the zlib compression to figure out the slot length)
# Then, there's 0 or more steps of decrypting the data in that slot. This ends up often
# being layers of base64, string-escape, hex-encoding, zlib-compression, etc.
# We handle this by just trying these by checking if they fit.

import os
import zlib
import struct
import base64
from collections import Counter
from decompiler import magic
import unrpyc


# Extractors are simple functions of (fobj, slotno) -> bytes
# They raise ValueError if they fail
EXTRACTORS = []
def extractor(f):
    EXTRACTORS.append(f)
    return f

# Decryptors are simple functions of (bytes, Counter) ->bytes
# They return None if they fail. If they return their input they're also considered to have failed.
DECRYPTORS = []
def decryptor(f):
    DECRYPTORS.append(f)
    return f


# Add game-specific custom extraction / decryption logic here

# End of custom extraction/decryption logic


@extractor
def extract_slot_rpyc(f, slot):
    """
    Slot extractor for a file that's in the actual rpyc format
    """
    f.seek(0)
    data = f.read()
    if data[:10] != b'RENPY RPC2':
        raise ValueError("Incorrect Header")

    position = 10
    slots = {}

    while position + 12 <= len(data):
        slotid, start, length = struct.unpack("<III", data[position : position + 12])
        if (slotid, start, length) == (0, 0, 0):
            break

        if start + length >= len(data):
            raise ValueError("Broken slot entry")

        slots[slotid] = (start, length)
        position += 12
    else:
        raise ValueError("Broken slot header structure")

    if slot not in slots:
        raise ValueError("Unknown slot id")

    start, length = slots[slot]
    return data[start : start + length]

@extractor
def extract_slot_legacy(f, slot):
    """
    Slot extractor for the legacy format
    """
    if slot != 1:
        raise ValueError("Legacy format only supports 1 slot")

    f.seek(0)
    data = f.read()

    try:
        data = zlib.decompress(data)
    except zlib.error:
        raise ValueError("Legacy format did not contain a zlib blob")

    return data

@extractor
def extract_slot_headerscan(f, slot):
    """
    Slot extractor for things that changed the magic and so moved the header around.
    """
    f.seek(0)
    data = f.read()

    position = 0
    while position + 36 < len(data):
        a,b,c,d,e,f,g,h,i = struct.unpack("<IIIIIIIII", data[position : position + 36])
        if a == 1 and d == 2 and g == 0 and b + c == e:
            break;
        position += 1

    else:
        raise ValueError("Couldn't find a header")

    slots = {}
    while position + 12 <= len(data):
        slotid, start, length = struct.unpack("<III", data[position : position + 12])
        if (slotid, start, length) == (0, 0, 0):
            break

        if start + length >= len(data):
            raise ValueError("Broken slot entry")

        slots[slotid] = (start, length)
        position += 12
    else:
        raise ValueError("Broken slot header structure")

    if slot not in slots:
        raise ValueError("Unknown slot id")

    start, length = slots[slot]
    return data[start : start + length]

@extractor
def extract_slot_zlibscan(f, slot):
    """
    Slot extractor for things that fucked with the header structure to the point where it's easier
    to just not bother with it and instead we just look for valid zlib chunks directly.
    """
    f.seek(0)
    data = f.read()

    start_positions = []

    for i in range(len(data) - 1):
        if data[i] != "\x78":
            continue

        if (ord(data[i]) * 256 + ord(data[i + 1])) % 31 != 0:
            continue

        start_positions.append(i)

    chunks = []
    for position in start_positions:
        try:
            chunk = zlib.decompress(data[position:])
        except zlib.error:
            continue
        chunks.append(chunk)

    if slot > len(chunks):
        raise ValueError("Zlibscan did not find enough chunks")

    return chunks[slot - 1]


@decryptor
def decrypt_zlib(data, count):
    try:
        return zlib.decompress(data)
    except zlib.error:
        return None

@decryptor
def decrypt_hex(data, count):
    if not all(i in "abcdefABCDEF0123456789" for i in count.keys()):
        return None
    try:
        return data.decode("hex")
    except Exception:
        return None

@decryptor
def decrypt_base64(data, count):
    if not all(i in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789+/=\n" for i in count.keys()):
        return None
    try:
        return base64.b64decode(data)
    except Exception:
        return None

@decryptor
def decrypt_string_escape(data, count):
    if not all(ord(i) >= 0x20 and ord(i) < 0x80 for i in count.keys()):
        return None
    try:
        newdata = data.decode("string-escape")
    except Exception:
        return None
    if newdata == data:
        return None
    return newdata


def assert_is_normal_rpyc(f):
    """
    Analyze the structure of a single rpyc file object for correctness.
    Does not actually say anything about the _contents_ of that section, just that we were able
    to slice it out of there.

    If succesful, returns the uncompressed contents of the first storage slot.
    """

    f.seek(0)
    header = f.read(1024)
    f.seek(0)

    if header[:10] != b'RENPY RPC2':
        # either legacy, or someone messed with the header

        # assuming legacy, see if this thing is a valid zlib blob
        raw_data = f.read()
        f.seek(0)

        try:
            uncompressed = zlib.decompress(raw_data)
        except zlib.error:
            raise ValueError("Did not find RENPY RPC2 header, but interpretation as legacy file failed")

        return uncompressed


    else:
        if len(header) < 46:
            # 10 bytes header + 4 * 9 bytes content table
            return ValueError("File too short")

        a,b,c,d,e,f,g,h,i = struct.unpack("<IIIIIIIII", header[10: 46])

        # does the header format match default ren'py generated files?
        if not (a == 1 and b == 46 and d == 2 and (g, h, i) == (0, 0, 0) and b + c == e):
            return ValueError("Header data is abnormal, did the format gain extra fields?")

        f.seek(b)
        raw_data = f.read(c)
        f.seek(0)
        if len(raw_data) != c:
            return ValueError("Header data is incompatible with file length")

        try:
            uncompressed = zlib.decompress(raw_data)
        except zlib.error:
            return ValueError("Slot 1 did not contain a zlib blob")

        if not uncompressed.endswith("."):
            return ValueError("Slot 1 did not contain a simple pickle")

        return uncompressed


def read_ast(f):
    diagnosis = ["Attempting to deobfuscate file:"]

    raw_datas = set()

    for extractor in EXTRACTORS:
        try:
            data = extractor(f, 1)
        except ValueError as e:
            diagnosis.append("strategy %s failed: %s" % (extractor.__name__, e.message))
        else:
            diagnosis.append("strategy %s success" % extractor.__name__)
            raw_datas.add(data)

    if not raw_datas:
        diagnosis.append("All strategies failed. Unable to extract data")
        raise ValueError("\n".join(diagnosis))

    if len(raw_datas) != 1:
        diagnosis.append("Strategies produced different results. Trying all options")

    data = None
    for raw_data in raw_datas:
        try:
            data, stmts, d = try_decrypt_section(raw_data)
        except ValueError as e:
            diagnosis.append(e.message)
        else:
            diagnosis.extend(d)
            with unrpyc.printlock:
                print("\n".join(diagnosis))
            return stmts

    diagnosis.append("All strategies failed. Unable to deobfuscate data")
    raise ValueError("\n".join(diagnosis))


def try_decrypt_section(raw_data):
    diagnosis = []

    layers = 0
    while layers < 10:
        # can we load it yet?
        try:
            data, stmts = magic.safe_loads(raw_data, unrpyc.class_factory, {"_ast", "collections"})
        except Exception:
            pass
        else:
            return data, stmts, diagnosis

        layers += 1
        count = Counter(raw_data)

        for decryptor in DECRYPTORS:
            newdata = decryptor(raw_data, count)
            if newdata is None:
                continue
            else:
                raw_data = newdata
                diagnosis.append("performed a round of %s" % decryptor.__name__)
                break
        else:
            break

    diagnosis.append("Did not know how to decrypt data.")
    raise ValueError("\n".join(diagnosis))
