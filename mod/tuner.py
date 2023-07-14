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

from math import log2 as log2f

NOTES = ['A', 'A#', 'B', 'C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#']

def find_freqnotecents(f, rf):
    ratio = log2f(f/rf)
    nf = 12 * ratio + 49
    n = round(nf)
    idx = (n - 1) % len(NOTES)
    note = NOTES[idx]
    octave = (n + 8) // len(NOTES)
    scale = (nf - n) / 4;
    cents = (scale * 10000) / 25;
    return f, "%s%d" % (note, octave), cents * 16
