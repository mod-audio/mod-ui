#!/usr/bin/env python3

import os, numpy, sys
from PIL import Image

source = "knob.png"

source_full_width = 8320
source_size = 128
source_png = Image.open(source)
source_steps = int(source_full_width / source_size)

steps_list = range(3, 18)

for steps in steps_list:
    target_full_width = source_size * steps
    target_step_advance = ((source_steps-1) / (steps-1))
    target_png = Image.new("RGBA", (target_full_width, source_size), (0, 0, 0, 0))

    for step in range(steps):
        x = int(step * target_step_advance) * source_size
        target_png.paste(source_png.copy().crop((x, 0, x+source_size, source_size)), (step * source_size, 0))

    target_png.save("knob_steps_{}.png".format(steps))
