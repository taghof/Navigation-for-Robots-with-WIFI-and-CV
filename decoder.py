#!/usr/bin/env python2.7
#    
#    Copyright (c) 2012 Morten Daugaard
#
#    Permission is hereby granted, free of charge, to any person obtaining a copy
#    of this software and associated documentation files (the "Software"), to deal
#    in the Software without restriction, including without limitation the rights
#    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#    copies of the Software, and to permit persons to whom the Software is
#    furnished to do so, subject to the following conditions:
#
#    The above copyright notice and this permission notice shall be included in
#    all copies or substantial portions of the Software.
#
#    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
#    THE SOFTWARE.
#
#    This file incorporates code covered by the following terms:
#     
#       Copyright (c) 2011 Bastian Venthur
#
#       Permission is hereby granted, free of charge, to any person obtaining a copy
#       of this software and associated documentation files (the "Software"), to deal
#       in the Software without restriction, including without limitation the rights
#       to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#       copies of the Software, and to permit persons to whom the Software is
#       furnished to do so, subject to the following conditions:
#
#       The above copyright notice and this permission notice shall be included in
#       all copies or substantial portions of the Software.
#
#       THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#       IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#       FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#       AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#       LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#       OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
#       THE SOFTWARE.

"""
Video decoding for the AR.Drone.

This library uses psyco to speed-up the decoding process. It is however written
in a way that it works also without psyco installed. On the author's
development machine the speed up is from 2FPS w/o psyco to > 20 FPS w/ psyco.
"""
import array
#import cProfile
import datetime
import struct
import sys
import numpy as np
import cv2.cv as cv

try:
    import psyco
except ImportError:
    print "Please install psyco for better video decoding performance."

class BitReader(object):
    """Bitreader. Given a stream of data, it allows to read it bitwise.
    """

    def __init__(self, packet):
        self.packet = packet
        self.offset = 0
        self.bits_left = 0
        self.chunk = 0
        self.read_bits = 0

    # def derp(self, nbits, consume=True):
    #     """derp nbits and return the integervalue of the read bits.

    #     If consume is False, it behaves like a 'peek' method (ie it reads the
    #     bits but does not consume them.
    #     """
    #     # Read enough bits into chunk so we have at least nbits available
    #     while nbits > self.bits_left:
    #         try:
    #             self.chunk = (self.chunk << 32) | struct.unpack_from('<I', self.packet, self.offset)[0]
    #         except struct.error:
    #             self.chunk <<= 32
    #         self.offset += 4
    #         self.bits_left += 32
    #     # Get the first nbits bits from chunk (and remove them from chunk)
    #     shift = self.bits_left - nbits
    #     res = self.chunk >> shift
    #     if consume:
    #         self.chunk -= res << shift
    #         self.bits_left -= nbits
    #         self.read_bits += nbits
    #     return res

    def read(self, nbits, consume=True):
        """Read nbits and return the integervalue of the read bits.

        If consume is False, it behaves like a 'peek' method (ie it reads the
        bits but does not consume them.
        """
        # Read enough bits into chunk so we have at least nbits available
        while nbits > self.bits_left:
            try:
                self.chunk = (self.chunk << 32) | struct.unpack_from('<I', self.packet, self.offset)[0]
            except struct.error:
                self.chunk <<= 32
            self.offset += 4
            self.bits_left += 32
        # Get the first nbits bits from chunk (and remove them from chunk)
        shift = self.bits_left - nbits
        res = self.chunk >> shift
        if consume:
            self.chunk -= res << shift
            self.bits_left -= nbits
            self.read_bits += nbits
        return res

    def align(self):
        """Byte align the data stream."""
        shift = (8 - self.read_bits) % 8
        self.read(shift)


# from zig-zag back to normal
ZIG_ZAG_POSITIONS = array.array('B',
                                ( 0,  1,  8, 16,  9,  2, 3, 10,
                                  17, 24, 32, 25, 18, 11, 4,  5,
                                  12, 19, 26, 33, 40, 48, 41, 34,
                                  27, 20, 13,  6,  7, 14, 21, 28,
                                  35, 42, 49, 56, 57, 50, 43, 36,
                                  29, 22, 15, 23, 30, 37, 44, 51,
                                  58, 59, 52, 45, 38, 31, 39, 46,
                                  53, 60, 61, 54, 47, 55, 62, 63))

# Inverse quantization
IQUANT_TAB = array.array('B',
                         ( 3,  5,  7,  9, 11, 13, 15, 17,
                           5,  7,  9, 11, 13, 15, 17, 19,
                           7,  9, 11, 13, 15, 17, 19, 21,
                           9, 11, 13, 15, 17, 19, 21, 23,
                           11, 13, 15, 17, 19, 21, 23, 25,
                           13, 15, 17, 19, 21, 23, 25, 27,
                           15, 17, 19, 21, 23, 25, 27, 29,
                           17, 19, 21, 23, 25, 27, 29, 31))

# Used for upscaling the 8x8 b- and r-blocks to 16x16
SCALE_TAB = array.array('B', 
                        ( 0,  0,  1,  1,  2,  2,  3,  3,
                          0,  0,  1,  1,  2,  2,  3,  3,
                          8,  8,  9,  9, 10, 10, 11, 11,
                          8,  8,  9,  9, 10, 10, 11, 11,
                          16, 16, 17, 17, 18, 18, 19, 19,
                          16, 16, 17, 17, 18, 18, 19, 19,
                          24, 24, 25, 25, 26, 26, 27, 27,
                          24, 24, 25, 25, 26, 26, 27, 27,

                          4,  4,  5,  5,  6,  6,  7,  7,
                          4,  4,  5,  5,  6,  6,  7,  7,
                          12, 12, 13, 13, 14, 14, 15, 15,
                          12, 12, 13, 13, 14, 14, 15, 15,
                          20, 20, 21, 21, 22, 22, 23, 23,
                          20, 20, 21, 21, 22, 22, 23, 23,
                          28, 28, 29, 29, 30, 30, 31, 31,
                          28, 28, 29, 29, 30, 30, 31, 31,

                          32, 32, 33, 33, 34, 34, 35, 35,
                          32, 32, 33, 33, 34, 34, 35, 35,
                          40, 40, 41, 41, 42, 42, 43, 43,
                          40, 40, 41, 41, 42, 42, 43, 43,
                          48, 48, 49, 49, 50, 50, 51, 51,
                          48, 48, 49, 49, 50, 50, 51, 51,
                          56, 56, 57, 57, 58, 58, 59, 59,
                          56, 56, 57, 57, 58, 58, 59, 59,

                          36, 36, 37, 37, 38, 38, 39, 39,
                          36, 36, 37, 37, 38, 38, 39, 39,
                          44, 44, 45, 45, 46, 46, 47, 47,
                          44, 44, 45, 45, 46, 46, 47, 47,
                          52, 52, 53, 53, 54, 54, 55, 55,
                          52, 52, 53, 53, 54, 54, 55, 55,
                          60, 60, 61, 61, 62, 62, 63, 63,
                          60, 60, 61, 61, 62, 62, 63, 63))

# Count leading zeros look up table
CLZLUT = array.array('B',
                     (8, 7, 6, 6, 5, 5, 5, 5, 4, 4, 4, 4, 4, 4, 4, 4,
                      3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
                      2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
                      2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
                      1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
                      1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
                      1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
                      1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
                      0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                      0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                      0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                      0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                      0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                      0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                      0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                      0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0))

# Map pixels from four 8x8 blocks to one 16x16
MB_TO_GOB_MAP = array.array('B',
                            [  0,   1,   2,   3,   4,   5,   6,   7,
                               16,  17,  18,  19,  20,  21,  22,  23,
                               32,  33,  34,  35,  36,  37,  38,  39,
                               48,  49,  50,  51,  52,  53,  54,  55,
                               64,  65,  66,  67,  68,  69,  70,  71,
                               80,  81,  82,  83,  84,  85,  86,  87,
                               96,  97,  98,  99, 100, 101, 102, 103,
                               112, 113, 114, 115, 116, 117, 118, 119,
                               8,   9,  10,  11,  12,  13,  14,  15,
                               24,  25,  26,  27,  28,  29,  30,  31,
                               40,  41,  42,  43,  44,  45,  46,  47,
                               56,  57,  58,  59,  60,  61,  62,  63,
                               72,  73,  74,  75,  76,  77,  78,  79,
                               88,  89,  90,  91,  92,  93,  94,  95,
                               104, 105, 106, 107, 108, 109, 110, 111,
                               120, 121, 122, 123, 124, 125, 126, 127,
                               128, 129, 130, 131, 132, 133, 134, 135,
                               144, 145, 146, 147, 148, 149, 150, 151,
                               160, 161, 162, 163, 164, 165, 166, 167,
                               176, 177, 178, 179, 180, 181, 182, 183,
                               192, 193, 194, 195, 196, 197, 198, 199,
                               208, 209, 210, 211, 212, 213, 214, 215,
                               224, 225, 226, 227, 228, 229, 230, 231,
                               240, 241, 242, 243, 244, 245, 246, 247,
                               136, 137, 138, 139, 140, 141, 142, 143,
                               152, 153, 154, 155, 156, 157, 158, 159,
                               168, 169, 170, 171, 172, 173, 174, 175,
                               184, 185, 186, 187, 188, 189, 190, 191,
                               200, 201, 202, 203, 204, 205, 206, 207,
                               216, 217, 218, 219, 220, 221, 222, 223,
                               232, 233, 234, 235, 236, 237, 238, 239,
                               248, 249, 250, 251, 252, 253, 254, 255])

MB_ROW_MAP = array.array('B', [i / 16 for i in MB_TO_GOB_MAP])
MB_COL_MAP = array.array('B', [i % 16 for i in MB_TO_GOB_MAP])

# An array of zeros. It is much faster to take the zeros from here than to
# generate a new list when needed.
ZEROS = array.array('i', [0 for i in xrange(256)])

# Constants needed for the inverse discrete cosine transform.
FIX_0_298631336 = 2446
FIX_0_390180644 = 3196
FIX_0_541196100 = 4433
FIX_0_765366865 = 6270
FIX_0_899976223 = 7373
FIX_1_175875602 = 9633
FIX_1_501321110 = 12299
FIX_1_847759065 = 15137
FIX_1_961570560 = 16069
FIX_2_053119869 = 16819
FIX_2_562915447 = 20995
FIX_3_072711026 = 25172
CONST_BITS = 13
PASS1_BITS = 1
F1 = CONST_BITS - PASS1_BITS - 1
F2 = CONST_BITS - PASS1_BITS
F3 = CONST_BITS + PASS1_BITS + 3

# tuning parameter for get_block
TRIES = 16
MASK = 2**(TRIES*32)-1
SHIFT = 32*(TRIES-1)

def _first_half(data):
    """Helper function used to precompute the zero values in a 12 bit datum.
    """
    # data has to be 12 bits wide
    streamlen = 0
    # count the zeros
    zerocount = CLZLUT[data >> 4];
    data = (data << (zerocount + 1)) & 0b111111111111
    streamlen += zerocount + 1
    # get number of remaining bits to read
    toread = 0 if zerocount <= 1 else zerocount - 1
    additional = data >> (12 - toread)
    data = (data << toread) & 0b111111111111
    streamlen += toread
    # add as many zeros to out_list as indicated by additional bits
    # if zerocount is 0, tmp = 0 else the 1 merged with additional bits
    tmp = 0 if zerocount == 0 else (1 << toread) | additional
    return [streamlen, tmp]


def _second_half(data):
    """Helper function to precompute the nonzeror values in a 15 bit datum.
    """
    # data has to be 15 bits wide
    streamlen = 0
    zerocount = CLZLUT[data >> 7]
    data = (data << (zerocount + 1)) & 0b111111111111111
    streamlen += zerocount + 1
    # 01 == EOB
    eob = False
    if zerocount == 1:
        eob = True
        return [streamlen, None, eob]
    # get number of remaining bits to read
    toread = 0 if zerocount == 0 else zerocount - 1
    additional = data >> (15 - toread)
    data = (data << toread) & 0b111111111111111
    streamlen += toread
    tmp = (1 << toread) | additional
    # get one more bit for the sign
    tmp = -tmp if data >> (15 - 1) else tmp
    tmp = int(tmp)
    streamlen += 1
    return [streamlen, tmp, eob]


# Precompute all 12 and 15 bit values for the entropy decoding process
FH = [_first_half(i) for i in xrange(2**12)]
SH = [_second_half(i) for i in xrange(2**15)]


def inverse_dct(block):
    """Inverse discrete cosine transform.
    """
    workspace = ZEROS[0:64]
    data = ZEROS[0:64]
    for pointer in xrange(8):
        if (block[pointer + 8] == 0 and block[pointer + 16] == 0 and
            block[pointer + 24] == 0 and block[pointer + 32] == 0 and
            block[pointer + 40] == 0 and block[pointer + 48] == 0 and
            block[pointer + 56] == 0):
            dcval = block[pointer] << PASS1_BITS
            for i in xrange(8):
                workspace[pointer + i*8] = dcval
            continue

        z2 = block[pointer + 16]
        z3 = block[pointer + 48]
        z1 = (z2 + z3) * FIX_0_541196100
        tmp2 = z1 + z3 * -FIX_1_847759065
        tmp3 = z1 + z2 * FIX_0_765366865
        z2 = block[pointer]
        z3 = block[pointer + 32]
        tmp0 = (z2 + z3) << CONST_BITS
        tmp1 = (z2 - z3) << CONST_BITS
        tmp10 = tmp0 + tmp3
        tmp13 = tmp0 - tmp3
        tmp11 = tmp1 + tmp2
        tmp12 = tmp1 - tmp2
        tmp0 = block[pointer + 56]
        tmp1 = block[pointer + 40]
        tmp2 = block[pointer + 24]
        tmp3 = block[pointer + 8]
        z1 = tmp0 + tmp3
        z2 = tmp1 + tmp2
        z3 = tmp0 + tmp2
        z4 = tmp1 + tmp3
        z5 = (z3 + z4) * FIX_1_175875602
        tmp0 *= FIX_0_298631336
        tmp1 *= FIX_2_053119869
        tmp2 *= FIX_3_072711026
        tmp3 *= FIX_1_501321110
        z1 *= -FIX_0_899976223
        z2 *= -FIX_2_562915447
        z3 *= -FIX_1_961570560
        z4 *= -FIX_0_390180644
        z3 += z5
        z4 += z5
        tmp0 += z1 + z3
        tmp1 += z2 + z4
        tmp2 += z2 + z3
        tmp3 += z1 + z4
        workspace[pointer + 0] = ((tmp10 + tmp3 + (1 << F1)) >> F2)
        workspace[pointer + 56] = ((tmp10 - tmp3 + (1 << F1)) >> F2)
        workspace[pointer + 8] = ((tmp11 + tmp2 + (1 << F1)) >> F2)
        workspace[pointer + 48] = ((tmp11 - tmp2 + (1 << F1)) >> F2)
        workspace[pointer + 16] = ((tmp12 + tmp1 + (1 << F1)) >> F2)
        workspace[pointer + 40] = ((tmp12 - tmp1 + (1 << F1)) >> F2)
        workspace[pointer + 24] = ((tmp13 + tmp0 + (1 << F1)) >> F2)
        workspace[pointer + 32] = ((tmp13 - tmp0 + (1 << F1)) >> F2)

    for pointer in xrange(0, 64, 8):
        z2 = workspace[pointer + 2]
        z3 = workspace[pointer + 6]
        z1 = (z2 + z3) * FIX_0_541196100
        tmp2 = z1 + z3 * -FIX_1_847759065
        tmp3 = z1 + z2 * FIX_0_765366865
        tmp0 = (workspace[pointer] + workspace[pointer + 4]) << CONST_BITS
        tmp1 = (workspace[pointer] - workspace[pointer + 4]) << CONST_BITS
        tmp10 = tmp0 + tmp3
        tmp13 = tmp0 - tmp3
        tmp11 = tmp1 + tmp2
        tmp12 = tmp1 - tmp2
        tmp0 = workspace[pointer + 7]
        tmp1 = workspace[pointer + 5]
        tmp2 = workspace[pointer + 3]
        tmp3 = workspace[pointer + 1]
        z1 = tmp0 + tmp3
        z2 = tmp1 + tmp2
        z3 = tmp0 + tmp2
        z4 = tmp1 + tmp3
        z5 = (z3 + z4) * FIX_1_175875602
        tmp0 *= FIX_0_298631336
        tmp1 *= FIX_2_053119869
        tmp2 *= FIX_3_072711026
        tmp3 *= FIX_1_501321110
        z1 *= -FIX_0_899976223
        z2 *= -FIX_2_562915447
        z3 *= -FIX_1_961570560
        z4 *= -FIX_0_390180644
        z3 += z5
        z4 += z5
        tmp0 += z1 + z3
        tmp1 += z2 + z4
        tmp2 += z2 + z3
        tmp3 += z1 + z4
        data[pointer + 0] = (tmp10 + tmp3) >> F3
        data[pointer + 7] = (tmp10 - tmp3) >> F3
        data[pointer + 1] = (tmp11 + tmp2) >> F3
        data[pointer + 6] = (tmp11 - tmp2) >> F3
        data[pointer + 2] = (tmp12 + tmp1) >> F3
        data[pointer + 5] = (tmp12 - tmp1) >> F3
        data[pointer + 3] = (tmp13 + tmp0) >> F3
        data[pointer + 4] = (tmp13 - tmp0) >> F3

    return data


def get_pheader(bitreader):
    """Read the picture header.

    Returns the width and height of the image.
    """
    bitreader.align()
    psc = bitreader.read(22)
    assert(psc == 0b0000000000000000100000)
    pformat = bitreader.read(2)
    assert(pformat != 0b00)
    if pformat == 1:
        # CIF
        width, height = 88, 72
    else:
        # VGA
        width, height = 160, 120
    presolution = bitreader.read(3)
    assert(presolution != 0b000)
    # double resolution presolution-1 times
    width = width << presolution - 1
    height = height << presolution - 1
    #print "width/height:", width, height
    ptype = bitreader.read(3)
    pquant = bitreader.read(5)
    pframe = bitreader.read(32)
    return width, height


def get_block(bitreader, has_coeff):
    """Read a 8x8 block from the data stream.

    This method takes care of the huffman-, RLE, zig-zag and idct and returns a
    list of 64 ints.
    """

    # read the first 10 bits in a 16 bit datum
    out_list = ZEROS[0:64]
    out_list[0] = int(bitreader.read(10)) * IQUANT_TAB[0]
    if not has_coeff:
        return inverse_dct(out_list)
    i = 1
    while 1:
        _ = bitreader.read(32*TRIES, False)
        streamlen = 0
        #######################################################################
        for j in xrange(TRIES):
            data = (_ << streamlen) & MASK
            data >>= SHIFT

            l, tmp = FH[data >> 20]
            streamlen += l
            data = (data << l) & 0xffffffff
            i += tmp

            l, tmp, eob = SH[data >> 17]
            streamlen += l
            if eob:
                bitreader.read(streamlen)
                return inverse_dct(out_list)
            j = ZIG_ZAG_POSITIONS[i]
            out_list[j] = tmp*IQUANT_TAB[j]
            i += 1
        #######################################################################
        bitreader.read(streamlen)
    return inverse_dct(out_list)


def get_mb(bitreader, array, width, offset):
    """Get macro block.

    This method does not return data but modifies the picture parameter in
    place.
    """

    mbc = bitreader.read(1)
    if mbc == 0:
        mbdesc = bitreader.read(8)
        assert(mbdesc >> 7 & 1)
        
        if mbdesc >> 6 & 1:
            mbdiff = bitreader.read(2)
        y = get_block(bitreader, mbdesc & 1)
        y.extend(get_block(bitreader, mbdesc >> 1 & 1))
        y.extend(get_block(bitreader, mbdesc >> 2 & 1))
        y.extend(get_block(bitreader, mbdesc >> 3 & 1))
        cb = get_block(bitreader, mbdesc >> 4 & 1)
        cr = get_block(bitreader, mbdesc >> 5 & 1)
        
        # ycbcr to rgb
        for i in xrange(256):
            j = SCALE_TAB[i]
            Y = y[i] - 16
            B = cb[j] - 128
            R = cr[j] - 128
            r = (298 * Y           + 409 * R + 128) >> 8
            g = (298 * Y - 100 * B - 208 * R + 128) >> 8
            b = (298 * Y + 516 * B           + 128) >> 8
            r = 0 if r < 0 else r
            r = 255 if r > 255 else r
            g = 0 if g < 0 else g
            g = 255 if g > 255 else g
            b = 0 if b < 0 else b
            b = 255 if b > 255 else b
            # re-order the pixels
            row = MB_ROW_MAP[i]
            col = MB_COL_MAP[i]
            rowoff = offset[0]
            coloff = offset[1]
            
            #index =  offset + row*(width*3) + (col*3)
            #picture[ rowoff+row, coloff+col] =  (r, g, b)
            #print str(rowoff+row) + ", " + str(coloff+col) + " - " + str(array.shape) + "\r"
            
            array[rowoff+row, coloff+col] = (r, g, b)            
    else:
        print "mbc was not zero"



def get_gob(bitreader, array,  slicenr, width):
    """Read a group of blocks.
    
    The method does not return data, the picture parameter is modified in place
    instead.
    """
    # the first gob has a special header

    if slicenr > 0:
        bitreader.align()
        gobsc = bitreader.read(22)
        if gobsc == 0b0000000000000000111111:
            print "weeeee"
            return False
        elif (not (gobsc & 0b0000000000000000100000) or
             (gobsc & 0b1111111111111111000000)):
            print "Got wrong GOBSC, aborting.", bin(gobsc)
            return False
        _ = bitreader.read(5)
    offset = slicenr*16*width
    for i in xrange(width / 16):
        get_mb(bitreader, array, width, (slicenr*16, i*16))#(offset+16*i))

# def cv2array(im): 
#   depth2dtype = { 
#         cv.IPL_DEPTH_8U: 'uint8', 
#         cv.IPL_DEPTH_8S: 'int8', 
#         cv.IPL_DEPTH_16U: 'uint16', 
#         cv.IPL_DEPTH_16S: 'int16', 
#         cv.IPL_DEPTH_32S: 'int32', 
#         cv.IPL_DEPTH_32F: 'float32', 
#         cv.IPL_DEPTH_64F: 'float64', 
#     } 

#   arrdtype=im.depth 
#   a = numpy.fromstring( 
#          im.tostring(), 
#          dtype=depth2dtype[im.depth], 
#          count=im.width*im.height*im.nChannels) 
#   a.shape = (im.height,im.width,im.nChannels) 
#   return a 

def read_picture(data):
    """Convert an AR.Drone image packet to an opencv image.
    Returns: w'idth, height, image and time to decode the image
    """
    if data is None:
        print "no image data"
        return None
    
    bitreader = BitReader(data)
    t = datetime.datetime.now()
    width, height = get_pheader(bitreader)
    slices = height / 16
    blocks = width / 16
    
    #retarray = np.zeros((height, width, 3), np.uint8)
    #retarray = cv.CreateImage((width, height), 8, 3)
    #retarray = np.empty((height, width, 3), np.uint8, 'C')
    retarray = cv.CreateMat(height, width, cv.CV_8UC3)

    for i in xrange(0, slices):
        get_gob(bitreader, retarray, i, width)

    # total_red = 0
    # total_green = 0
    # total_blue = 0

    # pixels = width*height

    # for w in range(width):
    #     for h in range(height):
    #         (r, g, b) = retimg[ h, w]
    #         total_red += r
    #         total_green += g
    #         total_blue += b

    # avg_red = total_red / pixels
    # avg_green = total_green / pixels    
    # avg_blue = total_blue / pixels

    # #print avg_red, avg_green, avg_blue

    # var_red = 0
    # var_green = 0
    # var_blue = 0

    # for w in range(width):
    #     for h in range(height):
    #         (r, g, b) = retimg[ h, w]
    #         var_red += (r-avg_red)**2
    #         var_green += (g-avg_green)**2
    #         var_blue += (b-avg_blue)**2

    # var_red = var_red/pixels
    # var_green = var_green/pixels
    # var_blue = var_blue/pixels
    
    # #print var_red, var_green, var_blue 

    # dev_red = var_red**0.5
    # dev_green = var_green**0.5
    # dev_blue = var_blue**0.5

    # print dev_red, dev_green, dev_blue 

    bitreader.align()
    eos = bitreader.read(22)
    assert(eos == 0b0000000000000000111111)

    t2 = datetime.datetime.now()

    return width, height, np.asarray(retarray), (t2 - t).microseconds / 1000000.0

def decode_navdata(packet):
    """Decode a navdata packet."""

    if packet is None:
        return None

    offset = 0
    _ =  struct.unpack_from("IIII", packet, offset)
    drone_state = dict()
    drone_state['fly_mask']             = _[1]       & 1 # FLY MASK : (0) ardrone is landed, (1) ardrone is flying
    drone_state['video_mask']           = _[1] >>  1 & 1 # VIDEO MASK : (0) video disable, (1) video enable
    drone_state['vision_mask']          = _[1] >>  2 & 1 # VISION MASK : (0) vision disable, (1) vision enable */
    drone_state['control_mask']         = _[1] >>  3 & 1 # CONTROL ALGO (0) euler angles control, (1) angular speed control */
    drone_state['altitude_mask']        = _[1] >>  4 & 1 # ALTITUDE CONTROL ALGO : (0) altitude control inactive (1) altitude control active */
    drone_state['user_feedback_start']  = _[1] >>  5 & 1 # USER feedback : Start button state */
    drone_state['command_mask']         = _[1] >>  6 & 1 # Control command ACK : (0) None, (1) one received */
    drone_state['fw_file_mask']         = _[1] >>  7 & 1 # Firmware file is good (1) */
    drone_state['fw_ver_mask']          = _[1] >>  8 & 1 # Firmware update is newer (1) */
    drone_state['fw_upd_mask']          = _[1] >>  9 & 1 # Firmware update is ongoing (1) */
    drone_state['navdata_demo_mask']    = _[1] >> 10 & 1 # Navdata demo : (0) All navdata, (1) only navdata demo */
    drone_state['navdata_bootstrap']    = _[1] >> 11 & 1 # Navdata bootstrap : (0) options sent in all or demo mode, (1) no navdata options sent */
    drone_state['motors_mask']          = _[1] >> 12 & 1 # Motor status : (0) Ok, (1) Motors problem */
    drone_state['com_lost_mask']        = _[1] >> 13 & 1 # Communication lost : (1) com problem, (0) Com is ok */
    drone_state['vbat_low']             = _[1] >> 15 & 1 # VBat low : (1) too low, (0) Ok */
    drone_state['user_el']              = _[1] >> 16 & 1 # User Emergency Landing : (1) User EL is ON, (0) User EL is OFF*/
    drone_state['timer_elapsed']        = _[1] >> 17 & 1 # Timer elapsed : (1) elapsed, (0) not elapsed */
    drone_state['angles_out_of_range']  = _[1] >> 19 & 1 # Angles : (0) Ok, (1) out of range */
    drone_state['ultrasound_mask']      = _[1] >> 21 & 1 # Ultrasonic sensor : (0) Ok, (1) deaf */
    drone_state['cutout_mask']          = _[1] >> 22 & 1 # Cutout system detection : (0) Not detected, (1) detected */
    drone_state['pic_version_mask']     = _[1] >> 23 & 1 # PIC Version number OK : (0) a bad version number, (1) version number is OK */
    drone_state['atcodec_thread_on']    = _[1] >> 24 & 1 # ATCodec thread ON : (0) thread OFF (1) thread ON */
    drone_state['navdata_thread_on']    = _[1] >> 25 & 1 # Navdata thread ON : (0) thread OFF (1) thread ON */
    drone_state['video_thread_on']      = _[1] >> 26 & 1 # Video thread ON : (0) thread OFF (1) thread ON */
    drone_state['acq_thread_on']        = _[1] >> 27 & 1 # Acquisition thread ON : (0) thread OFF (1) thread ON */
    drone_state['ctrl_watchdog_mask']   = _[1] >> 28 & 1 # CTRL watchdog : (1) delay in control execution (> 5ms), (0) control is well scheduled */
    drone_state['adc_watchdog_mask']    = _[1] >> 29 & 1 # ADC Watchdog : (1) delay in uart2 dsr (> 5ms), (0) uart2 is good */
    drone_state['com_watchdog_mask']    = _[1] >> 30 & 1 # Communication Watchdog : (1) com problem, (0) Com is ok */
    drone_state['emergency_mask']       = _[1] >> 31 & 1 # Emergency landing : (0) no emergency, (1) emergency */
    data = dict()
    data['drone_state'] = drone_state
    data['header'] = _[0]
    data['seq_nr'] = _[2]
    data['vision_flag'] = _[3]
    offset += struct.calcsize("IIII")
    while 1:
        try:
            id_nr, size =  struct.unpack_from("HH", packet, offset)
            offset += struct.calcsize("HH")
        except struct.error:
            break
        values = []
        for i in range(size-struct.calcsize("HH")):
            values.append(struct.unpack_from("c", packet, offset)[0])
            offset += struct.calcsize("c")
        # navdata_tag_t in navdata-common.h
        if id_nr == 0:
            values = struct.unpack_from("IIfffIfffI", "".join(values))
            values = dict(zip(['ctrl_state', 'battery', 'theta', 'phi', 'psi', 'altitude', 'vx', 'vy', 'vz', 'num_frames'], values))
            # convert the millidegrees into degrees and round to int, as they
            # are not so precise anyways
            for i in 'theta', 'phi', 'psi':
                values[i] = values[i] / 1000
                #values[i] /= 1000
            psi = values['psi']
            values['psi'] = psi if psi > 0 else 360+psi 

        data[id_nr] = values
    return data

try:
    psyco.bind(BitReader)
    psyco.bind(get_block)
    psyco.bind(get_gob)
    psyco.bind(get_mb)
    psyco.bind(inverse_dct)
    psyco.bind(read_picture)
except NameError:
    print "Unable to bind video decoding methods with psyco. Proceeding anyways, but video decoding will be slow!"
 
# def main():
#     data = open('testdata/100.dat').read()
#     #cProfile.runctx('read_picture(data)', globals(), locals())
    
# if __name__ == '__main__':
#     # if 'profile' in sys.argv:
#     #     cProfile.run('main()')
#     # else:
#     main()
        
    
