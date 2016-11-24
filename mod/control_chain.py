#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from ctypes import *

class String(Structure):
    _fields_ = [
        ("size", c_uint8),
        ("text", c_char_p),
    ]

class Data(Structure):
    _fields_ = [
        ("assigment_id", c_uint8),
        ("value", c_float),
    ]

class DataUpdate(Structure):
    _fields_ = [
        ("count", c_uint8),
        ("updates_list", POINTER(Data)),
    ]

class Actuator(Structure):
    _fields_ = [
        ("idx", c_uint8),
    ]

class DevDescriptor(Structure):
    _fields_ = [
        ("idx", c_uint8),
        ("label", POINTER(String)),
        ("actuators_count", c_uint8),
        ("actuators", POINTER(POINTER(Actuator))),
    ]

class Assignment(Structure):
    _fields_ = [
        ("device_id", c_int),
        ("actuator_id", c_int),
        ("value", c_float),
        ("min", c_float),
        ("max", c_float),
        ("def", c_float),
        ("mode", c_uint32),
    ]

DATA_CB = CFUNCTYPE(None, POINTER(DataUpdate))
DEVDESC_CB = CFUNCTYPE(None, POINTER(DevDescriptor))

class ControlChain(object):
    def __init__(self, serial_port, baudrate):
        self.obj = None
        self.lib = cdll.LoadLibrary("libcontrol_chain.so")

        # cc_handle_t* cc_init(const char *port_name, int baudrate);
        self.lib.cc_init.argtypes = [c_char_p, c_int]
        self.lib.cc_init.restype = c_void_p

        # void cc_finish(cc_handle_t *handle);
        self.lib.cc_finish.argtypes = [c_void_p]
        self.lib.cc_finish.restype = None

        #int cc_assignment(cc_handle_t *handle, cc_assignment_t *assignment);
        self.lib.cc_assignment.argtypes = [c_void_p, POINTER(Assignment)]
        self.lib.cc_assignment.restype = int

        #void cc_unassignment(cc_handle_t *handle, int assignment_id);
        self.lib.cc_unassignment.argtypes = [c_void_p, c_int]
        self.lib.cc_unassignment.restype = None

        #void cc_data_update_cb(cc_handle_t *handle, void (*callback)(void *arg));
        self.lib.cc_data_update_cb.argtypes = [c_void_p, DATA_CB]
        self.lib.cc_data_update_cb.restype = None

        #void cc_dev_descriptor_cb(cc_handle_t *handle, void (*callback)(void *arg));
        self.lib.cc_dev_descriptor_cb.argtypes = [c_void_p, DEVDESC_CB]
        self.lib.cc_dev_descriptor_cb.restype = None

        self.obj = self.lib.cc_init(serial_port.encode('utf-8'), baudrate)

        print("obj =>", self.obj, type(self.obj))

        if self.obj is None:
            raise NameError('Cannot create ControlChain object, check serial port')

        # define data update callback
        self._data_update_cb = DATA_CB(self._data_update)

        # define device descriptor callback
        self._dev_descriptor_cb = DEVDESC_CB(self._dev_descriptor)

    def __del__(self):
        if self.obj is None:
            return
        try:
            self.lib.cc_finish(self.obj)
        except NameError:
            pass

    def assignment(self, assignment):
        if isinstance(assignment, (list, tuple)):
            assignment = Assignment(*assignment)
        return self.lib.cc_assignment(self.obj, pointer(assignment))

    def unassignment(self, assignment_id):
        self.lib.cc_unassignment(self.obj, assignment_id)

    def dev_descriptor_cb(self, callback):
        self.user_dev_descriptor_cb = callback
        self.lib.cc_dev_descriptor_cb(self.obj, self._dev_descriptor_cb)

    def data_update_cb(self, callback):
        self.user_data_update_cb = callback
        self.lib.cc_data_update_cb(self.obj, self._data_update_cb)

    # internal, parses data for data_update_cb
    def _data_update(self, arg):
        data = arg.contents

        updates = []
        for i in range(data.count):
            update = {}
            updates.append({
                'assigment_id': int(data.updates_list[i].assigment_id),
                'value'       : float(data.updates_list[i].value)
            })

        self.user_data_update_cb(updates)

    # internal, parses data for dev_descriptor_cb
    def _dev_descriptor(self, arg):
        desc = arg.contents

        actuators = []
        for i in range(desc.actuators_count):
            actuators.append({
                'id': int(desc.actuators[i].contents.idx)
            })

        dev_descriptor = {
            'id'       : int(desc.idx),
            'label'    : desc.label.contents.text.decode('utf-8', errors='ignore'),
            'actuators': actuators,
        }

        self.user_dev_descriptor_cb(dev_descriptor)

### test
if __name__ == "__main__":
    def data_update(updates):
        print("data_update", updates)

    def dev_descriptor(dev_desc):
        print("dev_descriptor", dev_desc)

    cc1 = ControlChain('/dev/ttyS3', 115200)
    cc1.data_update_cb(data_update)
    cc1.dev_descriptor_cb(dev_descriptor)

    cc2 = ControlChain('/dev/ttyS3', 115200)
    cc2.data_update_cb(data_update)
    cc2.dev_descriptor_cb(dev_descriptor)

    import time
    time.sleep(1)

    assignment_id1 = cc1.assignment((1, 0, 1.0, 0.0, 1.0, 0.0, 1))
    print('assignment_id1', assignment_id1)

    assignment_id2 = cc2.assignment((1, 0, 1.0, 0.0, 1.0, 0.0, 1))
    print('assignment_id2', assignment_id2)

    time.sleep(1)

    if assignment_id1 >= 0: cc1.unassignment(assignment_id1)
    if assignment_id2 >= 0: cc2.unassignment(assignment_id2)
