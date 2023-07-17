#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later

from math import log2 as log2f

NOTES = ['A', 'A#', 'B', 'C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#']

def find_freqnotecents(f, rf, res):
    ratio = log2f(f/rf)
    nf = 12 * ratio + 49
    n = round(nf)
    idx = (n - 1) % len(NOTES)
    note = NOTES[idx]
    octave = (n + 8) // len(NOTES)
    scale = (nf - n) / 4;
    cents = (scale * 10000) / 25;
    return f, "%s%d" % (note, octave), cents * res
