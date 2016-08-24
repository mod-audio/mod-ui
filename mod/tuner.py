# -*- coding: utf-8 -*-

# Copyright 2012-2013 AGR Audio, Industria e Comercio LTDA. <contato@moddevices.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from functools import reduce

NOTES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

_freqs4 = [261.63, 277.18, 293.66, 311.13, 329.63, 349.23, 369.99, 392.0, 415.3, 440.0, 466.16, 493.88]
FREQS = reduce(lambda l1, l2: l1+l2, ([ freq/2**i for freq in _freqs4 ] for i in range(4, -4, -1)))

def find_freqnotecents(f):
    freq = min(FREQS, key=lambda i: abs(i-f))
    idx = FREQS.index(freq)
    octave = int(idx / 12)
    note = NOTES[FREQS.index(freq/2**octave)]
    d = 1 if f >= freq else -1
    next_f = FREQS[idx+d]
    cents =  int(100 * (f - freq) / (next_f - freq)) * d
    return freq, "%s%d" % (note, octave), cents
