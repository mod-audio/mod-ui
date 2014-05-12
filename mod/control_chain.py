# -*- coding: utf-8 -*-

from construct import *

class ControlChain():
    def __init__(self):
        connection = Struct("connection",
            Byte("name_size"),
            String("name", lambda ctx: ctx.name_size),
            Byte("channel"),
            ULInt16("protocol_version"),
        )

        error = Struct("error",
            ULInt16("code"),
            Byte("msg_size"),
            String("message", lambda ctx: ctx.msg_size),
        )

        device_descriptor = Struct("dev_desc",
            Byte("actuators_count"),
            Array(lambda ctx: ctx.actuators_count,
                Struct("actuator",
                    Byte("name_size"),
                    String("name", lambda ctx: ctx.name_size),
                    Byte("masks_count"),
                    Array(lambda ctx: ctx.masks_count,
                          Struct("mask",
                                 Byte("prop"),
                                 Byte("label_size"),
                                 String("label", lambda ctx: ctx.label_size),
                                 )
                          ),
                    Byte("slots"),
                    Byte("type"),
                    Byte("steps_count"),
                    Array(lambda ctx: ctx.steps_count, ULInt16("steps"))
                )
            )
        )

        control_addressing = Struct("control_addressing",
            If(lambda ctx: ctx._.origin > 0, ULInt16("resp_status")),
            If(lambda ctx: ctx._.origin == 0, Byte("addressing_id")),
            If(lambda ctx: ctx._.origin == 0, Byte("port_mask")),
            If(lambda ctx: ctx._.origin == 0, Byte("actuator_id")),
            If(lambda ctx: ctx._.origin == 0, Byte("chosen_mask")),
            If(lambda ctx: ctx._.origin == 0, Byte("label_size")),
            If(lambda ctx: ctx._.origin == 0, String("label", lambda ctx: ctx.label_size)),
            If(lambda ctx: ctx._.origin == 0, LFloat32("value")),
            If(lambda ctx: ctx._.origin == 0, LFloat32("minimum")),
            If(lambda ctx: ctx._.origin == 0, LFloat32("maximum")),
            If(lambda ctx: ctx._.origin == 0, LFloat32("default")),
            If(lambda ctx: ctx._.origin == 0, ULInt16("steps")),
            If(lambda ctx: ctx._.origin == 0, Byte("unit_size")),
            If(lambda ctx: ctx._.origin == 0, String("unit", lambda ctx: ctx.unit_size)),
            If(lambda ctx: ctx._.origin == 0, Byte("scale_points_count")),
            If(lambda ctx: ctx._.origin == 0, Array(lambda ctx: ctx.scale_points_count,
                                                    Struct("scale_points",
                                                           Byte("label_size"),
                                                           String("label", lambda ctx: ctx.label_size),
                                                           LFloat32("value"),
                                                           )
                                                    ))
        )

        control_unaddressing = Struct("control_unaddressing",
            If(lambda ctx: ctx._.origin == 0, Byte("addressing_id")),
        )

        data_request = Struct("data_request",
            If(lambda ctx: ctx._.origin == 0, Byte("seq")),
            If(lambda ctx: ctx._.origin > 0, Byte("events_count")),
            If(lambda ctx: ctx._.origin > 0, 
               Array(lambda ctx: ctx.events_count,
                     Struct("events",
                            Byte("id"),
                            LFloat32("value")
                            )
                     ),
               ),
            If(lambda ctx: ctx._.origin > 0, Byte("requests_count")),
            If(lambda ctx: ctx._.origin > 0, 
               Array(lambda ctx: ctx.requests_count, Byte("requests"))),
        )

        self._parser = Struct("parser",
            Byte("sync"),
            Byte("destination"),
            Byte("origin"),
            Byte("function"),
            ULInt16("data_size"),
            If(lambda ctx: ctx["data_size"] > 0 and ctx["function"] == 255, error),
            If(lambda ctx: ctx["data_size"] > 0 and ctx["function"] == 1, connection),
            If(lambda ctx: ctx["data_size"] > 0 and ctx["function"] == 2, device_descriptor),
            If(lambda ctx: ctx["data_size"] > 0 and ctx["function"] == 3, control_addressing),
            If(lambda ctx: ctx["data_size"] > 0 and ctx["function"] == 4, data_request),
            If(lambda ctx: ctx["data_size"] > 0 and ctx["function"] == 5, control_unaddressing),
            Byte("checksum"),
            Byte("end")
        )

    def __checksum(self, buffer, size):
        check = 0
        for i in range(size):
            check += ord(buffer[i])
            check &= 0xFF

        if check == 0x00 or check == 0xAA:
            return (~check & 0xFF)

        return check

    def build(self, obj):
        return self._parser.build(obj)

    def connection(self, destination, origin, name, channel):
        pass

    def device_descriptor(self):
        def encoder(obj, ctx):
            return Container()

        def decoder(obj, ctx):
            pass

    def parse(self, buffer):
        buffer+="\x00"
        buffer = buffer.replace("\x1b\xff", "\x00")
        buffer = buffer.replace("\x1b\x55", "\xaa")
        buffer = buffer.replace("\x1b\x1b", "\x1b")

        return self._parser.parse(buffer)
