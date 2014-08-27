# -*- coding: utf-8 -*-

from construct import (Struct, Byte, String, ULInt16, UBInt16, Array, LFloat32,
                       If, Adapter, Container, ListContainer
                       )
import pystache, os, json, struct, logging
from hashlib import md5
import Queue
from tornado import ioloop

from mod.settings import HARDWARE_DRIVER_DIR, INSTALLED_HARDWARE_DIR

ERROR = 255
CONNECTION = 1
DEVICE_DESCRIPTOR = 2
ADDRESSING = 3
DATA_REQUEST = 4
UNADDRESSING = 5

QUADRA = 0

HARDWARE_TIMEOUT = 0.008
RESPONSE_TIMEOUT = 0.002

def get_time():
    return ioloop.IOLoop.time(ioloop.IOLoop.instance())

class Interrupt(Exception):
    pass

class ControlChainMessage():
    """
    ControlChainMessage is responsible for parsing and building Control Chain messages. It converts structured data into proper byteflow
    and vice-versa, according to the protocol.
    """
    def __init__(self):
        connection_parser = Struct(
            "data",
            Byte("url_size"),
            String("url", lambda ctx: ctx.url_size),
            Byte("channel"),
            ULInt16("protocol_version"),
            )
        connection_builder = connection_parser

        error_parser = Struct(
            "data",
            Byte("function"),
            Byte("code"),
            Byte("message_size"),
            String("message", lambda ctx: ctx.message_size),
            )
        error_builder = error_parser

        device_descriptor_builder = Struct("data")
        device_descriptor_parser = Struct(
            "data",
            Byte("name_size"),
            String("name", lambda ctx: ctx.name_size),
            Byte("actuator_count"),
            Array(
                lambda ctx: ctx.actuator_count,
                Struct(
                    "actuator",
                    Byte("actuator_id"),
                    Byte("name_size"),
                    String("name", lambda ctx: ctx.name_size),
                    Byte("modes_count"),
                    Array(lambda ctx: ctx.modes_count,
                          Struct("modes",
                                 UBInt16("mask"),
                                 Byte("label_size"),
                                 String("label", lambda ctx: ctx.label_size),
                                 )
                          ),
                    Byte("slots"),
                    Byte("steps_count"),
                    Array(lambda ctx: ctx.steps_count, ULInt16("steps"))
                )
            )
        )

        control_addressing_builder = Struct("data",
                                            Byte("actuator_id"),
                                            UBInt16("mode"),
                                            Byte("addressing_id"),
                                            Byte("port_properties"),
                                            Byte("label_size"),
                                            String("label", lambda ctx: ctx.label_size),
                                            LFloat32("value"),
                                            LFloat32("minimum"),
                                            LFloat32("maximum"),
                                            LFloat32("default"),
                                            ULInt16("steps"),
                                            Byte("unit_size"),
                                            String("unit", lambda ctx: ctx.unit_size),
                                            Byte("scale_points_count"),
                                            Array(lambda ctx: ctx.scale_points_count,
                                                  Struct("scale_points",
                                                         Byte("label_size"),
                                                         String("label", lambda ctx: ctx.label_size),
                                                         LFloat32("value"),
                                                           )
                                                  ),
                                           )
        control_addressing_parser = Struct("data",
                                           ULInt16("resp_status"),
                                           )
        control_unaddressing_builder = Struct("data",
                                              Byte("addressing_id"),
                                              )
        control_unaddressing_parser = Struct("data")

        data_request_builder = Struct("data",
                                      Byte("seq"))
        data_request_parser = Struct("data",
                                     Byte("events_count"),
                                     Array(lambda ctx: ctx.events_count,
                                           Struct("events",
                                                  Byte("id"),
                                                  LFloat32("value")
                                                  )
                                           ),
                                     Byte("requests_count"),
                                     Array(lambda ctx: ctx.requests_count,
                                           Struct("requests",
                                               Byte("id")
                                           ),
                                     )
                                 )

        header = Struct("header",
                        Byte("sync"),
                        Byte("destination"),
                        Byte("origin"),
                        Byte("function"),
                        ULInt16("data_size"),
                        )

        self._parser = {
            'header': header,
            ERROR: Struct("data", error_parser),
            CONNECTION: Struct("data", connection_parser),
            DEVICE_DESCRIPTOR: Struct("data", device_descriptor_parser),
            ADDRESSING: Struct("data", control_addressing_parser),
            DATA_REQUEST: Struct("data", data_request_parser),
            UNADDRESSING: Struct("data", control_unaddressing_parser),
            }

        self._builder = {
            'header': header,
            ERROR: Struct("data", error_builder),
            CONNECTION: Struct("data", connection_builder),
            DEVICE_DESCRIPTOR: Struct("data", device_descriptor_builder),
            ADDRESSING: Struct("data", control_addressing_builder),
            DATA_REQUEST: Struct("data", data_request_builder),
            UNADDRESSING: Struct("data", control_unaddressing_builder),
            }

    def _encode(self, obj):
        """
        Recursively encodes a dictionary into Container object to be serialized.
        Also, puts proper _size and _count properties.
        """
        if obj is None:
            return Container()
        if type(obj) in (dict, Container):
            for key, value in obj.items():
                obj[key] = self._encode(value)
                if type(value) in (str, unicode):
                    obj["%s_size" % key] = len(obj[key])
                elif type(value) is list:
                    obj["%s_count" % key] = len(value)
            return Container(**obj)

        if type(obj) in (list, ListContainer):
            for i, item in enumerate(obj):
                obj[i] = self._encode(item)

        return obj

    def _decode(self, obj):
        """
        Removes _size and _count properties to avoid garbage in local data.
        """
        if type(obj) in (dict, Container):
            for key, value in obj.items():
                obj[key] = self._decode(value)
                if type(value) in (list, ListContainer):
                    del obj["%s_count" % key]
                elif type(value) in (str, unicode):
                    del obj["%s_size" % key]
        elif type(obj) in (list, ListContainer):
            for i, item in enumerate(obj):
                obj[i] = self._decode(item)

        return obj

    def build(self, destination, function, obj={}):
        data = self._builder[function].build(Container(data=self._encode(obj)))
        header = self._builder['header'].build(Container(sync=0xaa,
                                                         destination=destination,
                                                         origin=0,
                                                         function=function,
                                                         data_size=len(data)))
        return header + data

    def parse(self, buffer):
        header = self._parser['header'].parse(buffer[:6])
        assert "\xaa" == chr(header.sync), "Message is not consistent, wrong SYNC byte (is not 0xAA)"
        data = buffer[6:]
        assert len(data) == header.data_size, "Message is not consistent, wrong data size"
        parser = self._parser[header.function]
        del header['data_size']
        header.data = parser.parse(data).data
        return self._decode(header)

class Gateway():
    """
    Gateway is responsible for routing control chain messages to the proper way. It expects a byteflow message and
    handles checksums, byte replacings and connection issues.
    It uses ControlChainMessage to build and parse the messages.
    """
    def __init__(self, hmi, handler):
        # Used to handle message above this level
        self.handle = handler
        self.message = ControlChainMessage()

        # Currently control_chain is routed through HMI
        self.hmi = hmi
        from mod.protocol import Protocol
        Protocol.register_cmd_callback("chain", self.receive)

    def __checksum(self, buffer, size):
        check = 0
        for i in range(size):
            check += ord(buffer[i])
            check &= 0xFF
        return check

    def send(self, hwid, function, message=None):
        stream = self.message.build(hwid, function, message)
        msg = "%s%s" % (stream, chr(self.__checksum(stream, len(stream))))
        replaced = "\xaa"
        for c in msg[1:]:
            if c == "\x1b":
                replaced += "\x1b\x1b"
            elif c == "\xaa":
                replaced += "\x1b\x55"
            else:
                replaced += c
        self.hmi.chain(replaced)

    def receive(self, message, callback):
        # control_chain protocol is being implemented over the hmi protocol, this will soon be changed.
        # ignoring callback by now
        replaced = ""
        skip = False
        for i,c in enumerate(message):
            if skip:
                skip = False
                continue
            if i == len(message)-1:
                replaced += c
                break
            if "%s%s" % (message[i], message[i+1]) == "\x1b\x55":
                replaced += "\xaa"
                skip = True
            elif "%s%s" % (message[i], message[i+1]) == "\x1b\x1b":
                replaced += "\x1b"
                skip = True
            else:
                replaced += c
        message = replaced
        checksum = message[-1]
        message = message[:-1]
        assert checksum == chr(self.__checksum(message, len(message))), "Message is not consistent, checksum does not match"
        self.handle(self.message.parse(message))

class PipeLine():
    """
    PipeLine will send any commands from the Manager to the devices, while polling for events
    every 2 milliseconds. It does that in a way to priorize commands, avoid collisions and
    preserve polling frequency.
    The only control chain message handled by PipeLine is the data_request, all others will go
    to HardwareManager
    """
    def __init__(self, hmi, handler):
        # Used to handle messages above this level
        self.handle = handler
        self.gateway = Gateway(hmi, self.receive)
        self.segunda = False

        # List of hardware ids that will be polled
        self.poll_queue = []
        #  Pointer to the next device to be polled
        self.poll_pointer = 0
        # Time of last poll, initialized on past to schedule start asap
        self.last_poll = get_time() - 1
        # There must always be one scheduled event, this will store the tornado's timeout for it.
        self.timeout = None
        # The sequencial data request number for each device.
        self.data_request_seqs = {}
        # A queue of output commands, that will interrupt polling until it's empty
        self.output_queue = Queue.Queue()

        self.ioloop = ioloop.IOLoop.instance()

    def add_hardware(self, hwid):
        self.data_request_seqs[hwid] = 0
        self.poll_queue.append(hwid)

    def remove_hardware(self, hwid):
        self.data_request_seqs.pop(hwid)
        self.poll_queue.remove(hwid)

    def start(self):
        self.schedule(self.process_next)

    def schedule(self, task):
        """
        Schedules a task for 2 milliseconds from last polling.
        """
        if self.timeout is not None:
            self.ioloop.remove_timeout(self.timeout)
        self.timeout = self.ioloop.add_timeout(self.last_poll + 0.02, task)

    def interrupt(self):
        """
        Cancels any timeout and schedules a process_next to be executed asap
        """
        if self.timeout is not None:
            self.ioloop.remove_timeout(self.timeout)
        self.ioloop.add_timeout(self.last_poll, self.process_next)
        raise Interrupt

    def process_next(self):
        """
        Checks if there's anything in output queue. If so, send first event, otherwise schedules a poll
        """
        # TODO: check why this try/finally block wasnt working
        #try:
        if self.output_queue.empty():
            return self.schedule(self.poll_next)
        hwid, function, message = self.output_queue.get()
        self.gateway.send(hwid, function, message)
        #finally:
        self.schedule(self.process_next)

    def poll_next(self):
        """
        Does one polling cycle and schedules next event.
        """
        self.last_poll = get_time()
        try:
            if len(self.poll_queue) == 0:
                return self.schedule(self.process_next)
            self.poll_pointer = (self.poll_pointer + 1) % len(self.poll_queue)
            self.poll_device(self.poll_queue[self.poll_pointer])
            self.schedule(self.process_next)
        except Interrupt:
            pass
        except Exception, e:
            logging.info(str(e))
            self.schedule(self.process_next)

    def receive(self, msg):
        """
        Called by gateway. Handles a message and process next thing in queue
        """
        self.handle(msg)
        self.process_next()

    def poll_device(self, hwid):
        """
        Sends a data_request message to a given hardware
        """
        seq = self.data_request_seqs[hwid]
        print "SEQ: %d" % seq
        self.send(hwid, DATA_REQUEST, {'seq': seq })

    def send(self, hwid, function, data=None):
        """
        Puts the message in output queue and interrupts any sleeping
        """
        self.output_queue.put((hwid, function, data))
        self.interrupt()

class AddressingManager():
    """
    HardwareManager is responsible for managing the connections to devices, know which ones are online, the hardware ids and addressing ids.
    It translates the Control Chain protocol to proper calls to Session methods.
    """
    def __init__(self, hmi, handler):
        # Handler is the function that will receive (instance_id, symbol, value) updates
        self.handle = handler

        self.pipeline = PipeLine(hmi, self.receive)

        # Store hardware data, indexed by hwid
        self.hardwares = {}
        # hwids, indexed by url, channel
        self.hardware_index = {}
        # Pointer used to choose a free hardware id
        self.hardware_id_pointer = 1
        # Last time each hardware have been seen, for timeouts
        self.hardware_tstamp = {}

        # Store addressings data, indexed by hwid, addressing_id
        self.addressings = {}
        # Addressings indexed by instanceId, symbol. The data stored is a tupple containing:
        #  - a boolean indicating if the hardware is present
        #  - hwid, addressing_id if so
        #  - url, channel otherwise
        self.addressing_index = {}
        # Pointers used to choose free addressing ids, per hardware
        self.addressing_id_pointers = {}
        # Addressings to devices that are not connected
        # indexed by (url, channel) then (instance_id, port_id)
        self.pending_addressings = {}

        # Callbacks to be called when answers to commands sent are received,
        # indexed by (hwid, function)
        self.callbacks = {}

        self.ioloop = ioloop.IOLoop.instance()

        # Maps Control Chain function ids to internal methods
        self.dispatch_table = {
            CONNECTION: self.device_connect,
            DEVICE_DESCRIPTOR: self.save_device_driver,
            DATA_REQUEST: self.receive_device_data,
            ADDRESSING: self.confirm_addressing,
            UNADDRESSING: self.confirm_unaddressing,
            }

    def start(self):
        """
        Starts the engine
        """
        self.pipeline.start()
        self.ioloop.add_callback(self._timeouts)

    def send(self, hwid, function, data=None, callback=None):
        """
        Sends a message through the pipeline.
        Stores the callback to handle responses later.
        """
        current_callback, tstamp = self.callbacks.get((hwid, function), (None, 0))
        if current_callback is not None:
            # There's already a callback for this hardware/function. This means that
            # the previous message was not returned, let's consider this an error
            # in previous communication
            current_callback(False)
        if callback is not None:
            self.callbacks[(hwid, function)] = (callback, get_time())
        try:
            self.pipeline.send(hwid, function, data)
        except Interrupt:
            pass

    def _timeouts(self):
        """
        Checks for hardwares that are not communicating and messages that have not been answered.
        Disconnects the devices and call the response callbacks with False result.
        """
        # TODO it would be more efficient to separate them, as the hardware_timeout is much greater than
        # response timeout
        now = get_time()
        try:
            # Devices
            hwids = self.hardwares_tstamp.keys()
            for hwid, tstamp in self.hardware_tstamp.keys():
                if now - tstamp > HARDWARE_TIMEOUT:
                    self.device_disconnect(hwid)

            # Callbacks
            keys = self.callbacks.keys()
            for key in keys:
                callback, tstamp = self.callbacks[key]
                if now - tsamp > RESPONSE_TIMEOUT:
                    callback(False)
                    del self.callbacks[key]
        finally:
            self.ioloop.add_timeout(now + RESPONSE_TIMEOUT, self._timeouts)

    def receive(self, msg):
        """
        Called by pipeline.
        Routes message internally, including the callback, if any
        """
        if msg.origin > 0 and not self.hardwares.get(msg.origin):
            # device is sending message after being disconnected
            return

        self.hardware_tstamp[msg.origin] = get_time()
        try:
            callback, tstamp = self.callbacks.pop((msg.origin, msg.function))
            self.dispatch_table[msg.function](msg.origin, msg.data, callback)
        except KeyError:
            """
            Either this is not a response from AddressingManager (device_connect and data_request,
            for example) or the message has timed out.
            In case of timeout, this call will probably raise an error, the receiving function may
            either expect no callback to handle an error or this call will result in error.
            """
            self.dispatch_table[msg.function](msg.origin, msg.data)

    def _generate_hardware_id(self):
        """
        Gets a free hardware id
        """
        start = self.hardware_id_pointer
        pointer = start
        while self.hardwares.get(pointer) is not None:
            pointer = (pointer + 1) % 256
            if pointer == start:
                return None # full!
        self.hardware_id_pointer = pointer
        return pointer + 0x7f

    def _generate_addressing_id(self, hwid):
        """
        Gets a free addressing id for this hardware
        """
        start = self.addressing_id_pointers[hwid]
        pointer = start
        while self.addressings[hwid].get(pointer) is not None:
            pointer = (pointer + 1) % 256
            if pointer == start:
                return None # full!
        self.addressing_id_pointers[hwid] = pointer
        return pointer

    def device_connect(self, origin, data):
        """
        Receives a device_connect message.
        Creates the proper hardware id and initializes the structures for it,
        send the hardware id to device and asks for its description.
        If this device is enabled, loads it in pipeline.
        """
        url = data['url']
        channel = data['channel']
        logging.info("connection %s on %d" % (url, channel))
        hwid = self._generate_hardware_id()
        self.hardwares[hwid] = data
        self.hardware_index[(url, channel)] = hwid
        self.hardware_tstamp[hwid] = get_time()
        self.addressings[hwid] = {}
        self.addressing_id_pointers[hwid] = 0

        self.send(hwid, CONNECTION, data)
        self.send(hwid, DEVICE_DESCRIPTOR)

        self.install_hardware(url, channel)

        if not self.hardware_is_installed(url, channel):
            return

        self.load_hardware(url, channel)

    def install_hardware(self, url, channel):
        device_id = md5(url).hexdigest()
        installation_path = os.path.join(INSTALLED_HARDWARE_DIR, "%s_%d" % (device_id, channel))
        open(installation_path, 'w').close()

    def device_disconnect(self, hwid):
        """
        Cleans all data from a given hardware id. This will be used in timeouts.
        """
        self.unload_hardware(hwid)
        data = self.hardwares.pop(hwid)
        del self.hw_index[(data['url'], data['channel'])]
        del self.hardware_tstamp[hwid]

    def get_driver_path(self, url):
        """
        Gets path to store the device description, as send by it.
        """
        device_id = md5(url).hexdigest()
        return os.path.join(HARDWARE_DRIVER_DIR, device_id)

    def hardware_is_installed(self, url, channel):
        """
        Checks if a device is installed by user in this channel.
        Otherwise, it's not considered in pipeline.
        """
        device_id = md5(url).hexdigest()
        installation_path = os.path.join(INSTALLED_HARDWARE_DIR, "%s_%d" % (device_id, channel))
        return os.path.exists(installation_path) and os.path.exists(self.get_driver_path(url))

    def load_hardware(self, url, channel):
        """
        Load a hardware in Pipeline and sends all pending addresses to it
        """
        hwid = self.hardware_index.get((url, channel))
        if hwid is None:
            return

        pending = self.pending_addressings.get((url, channel), {}).keys()
        def next_addressing():
            if len(pending) == 0:
                return
            instance_id, port_id = pending.pop(-1)
            addressing = self.pending_addressings[(url, channel)].pop((instance_id, port_id))
            self.commit_addressing(hwid, instance_id, port_id, next_addressing)

        self.ioloop.add_callback(next_addressing)

    def unload_hardware(self, hwid):
        """
        Saves all of device's addressings and removes it from Pipeline
        """
        url = self.hardwares[hwid]['url']
        channel = self.hardwares[hwid]['channel']
        self.pending_addressings[(url, channel)] = {}
        addrids = self.addressings[hwid].keys()
        for addrid in addrids:
            instance_id, port_id, addressing = self.addressing[hwid].pop(addrid)
            self.addressing_index[(instance_id, port)] = (False, url, channel)
            self.pending_addressings[(url, channel)][(instance_id, port_id)] = addressing

        self.pipeline.remove_hardware(hwid)

    def save_device_driver(self, hwid, data):
        """
        Save the device description send by the device.
        """
        data.update(self.hardwares[hwid])
        for actuator in data['actuator']:
            actuator['name'] = pystache.render(actuator['name'], data)
        path = self.get_driver_path(data['url'])
        open(path, 'w').write(json.dumps(data))

    def receive_device_data(self, hwid, data):
        """
        Handles updates sent by hardware. This is the result of a polling by Pipeline.
        """
        self.pipeline.data_request_seqs[hwid] = (self.pipeline.data_request_seqs[hwid]+1) % 256
        # Report events to Session
        for event in data.events:
            try:
                instance_id, port_id, addressing = self.addressings[hwid][event['id']]
            except KeyError:
                logging.info("not addressed event: %s on %s" % (hwid, event['id']))
                continue
            self.handle(instance_id, port_id, event['value'])
        # Resend any addressings requested
        for addrid in data.requests:
            self.send(hwid, ADDRESSING, self.addressings[hwid][addrid][2])

    def address(self, instance_id, port_id, url, channel, actuator_id, mode, port_properties, label, value,
                minimum, maximum, default, steps, unit, scale_points, callback=None):
        """
        Addresses a control port to an actuator.
        First check if the port is not already addressed somewhere else and unaddress
        if that's the case.
        """
        data = {
            # url and channel are important in addressing structure, but
            # won't be encoded in control_chain message
            'url': url,
            'channel': channel,
            'actuator_id': actuator_id,
            'mode': mode,
            'port_properties': port_properties,
            'label': label,
            'value': value,
            'minimum': minimum,
            'maximum': maximum,
            'default': default,
            'steps': steps,
            'unit': unit,
            'scale_points': scale_points
            }

        def do_address(result=True, msg=None):
            # This will either be called immediately or after unaddressing
            # this port from other actuator. So, do_address maybe a callback.
            if not result:
                return callback(None, msg)

            hwid = self.hardware_index.get((url, channel))
            if hwid is not None:
                self.commit_addressing(hwid, instance_id, port_id, data, callback)
            else:
                self.store_pending_addressing(url, channel, instance_id, port_id, data)
                self.ioloop.add_callback(lambda: callback(data))

        if self.addressing_index.get((instance_id, port_id)) is None:
            do_address()
        else:
            self.unaddress(instance_id, port_id, do_address)

    def commit_addressing(self, hwid, instance_id, port_id, addressing, callback):
        """
        Sends this addressing to a connected hardware
        """
        addrid = self._generate_addressing_id(hwid)
        addressing['addressing_id'] = addrid
        self.addressings[hwid][addrid] = (instance_id, port_id, addressing)
        self.addressing_index[(instance_id, port_id)] = (True, hwid, addrid)
        def _callback(ok=True):
            if ok and hwid != QUADRA:
                self.pipeline.add_hardware(hwid)
                # TODO: Check if this is really necessary
                # self.send(hwid, DATA_REQUEST, {'seq': 1})
                callback(addressing)
            elif ok and hwid == QUADRA:
                callback(addressing)
            else:
                callback(None)
        data = self.addressings[hwid][addrid][2]
        if hwid != QUADRA:
            self.send(hwid, ADDRESSING, data, _callback)
        else:
            # TODO: this is hard coded for QUADRA
            self.send_hmi_addressing(hwid, addrid, data, callback=_callback)

    def send_next(self, hwid, actuator_type, actuator_id):
        if actuator_type == 2:
            actuator_id += 4
        actuator_id += 1
        index = self.addressings_by_actuator[(hwid, actuator_id)][0]
        index = (index + 1) % len(self.addressings_by_actuator[(hwid, actuator_id)][1])
        addrid = self.addressings_by_actuator[(hwid, actuator_id)][1][index]
        self.addressings_by_actuator[(hwid, actuator_id)] = (index, self.addressings_by_actuator[(hwid, actuator_id)][1])
        self.send_hmi_addressing(hwid, addrid, self.addressings[hwid][addrid][2])

    def _get_hmi_acttype_and_actid(self, addressing):
        data = addressing
        acttype = 1 if data['actuator_id'] <= 4 else 2 # TODO: hard coded for QUADRA
        actid = (data['actuator_id'] if data['actuator_id'] <= 4 else data['actuator_id'] - 4) - 1
        return (acttype, actid)

    def send_hmi_addressing(self, hwid, addrid, data, index=None, size=None, callback=lambda x: None):
        if index is None:
            current_idx = self.addressings_by_actuator[(hwid, data['actuator_id'])][0]
            index = current_idx
        if size is None:
            size = len(self.addressings_by_actuator[(hwid, data['actuator_id'])][1])
        acttype, actid = self._get_hmi_acttype_and_actid(data)
        import re
        r = re.compile("%[^a-zA-Z ]*[dfs]")
        self.hmi.control_add(
                    self.addressings[hwid][addrid][0],
                    self.addressings[hwid][addrid][1],
                    data['label'],
                    data['port_properties'], # var type
                    r.sub("", data['unit']).strip(),
                    data['value'],
                    data['maximum'],
                    data['minimum'],
                    data['steps'],
                    0, # hwtype hard coded for QUADRA
                    hwid,
                    acttype,
                    actid,
                    size,
                    index+1,
                    [ (e['label'], e['value']) for e in data['scale_points'] ],
                    callback=callback)

    def store_pending_addressing(self, url, channel, instance_id, port_id, addressing):
        """
        Stores an addressing to a disconnected hardware to send it when it's connected
        """
        hwkey = (url, channel)
        if not self.pending_addressings.get(hwkey):
            self.pending_addressings[hwkey] = {}
        self.pending_addressings[hwkey][(instance_id, port_id)] = addressing
        self.addressing_index[(instance_id, port_id)] = (False, url, channel)

    def confirm_addressing(self, origin, data, callback=None):
        """
        Receives a confirmation that the addressing occurred.
        """
        if callback:
            callback(True)

    def unaddress(self, instance_id, port_id, callback):
        """
        Removes an addressing for the given control port.
        """
        current = self.addressing_index.get((instance_id, port_id))
        if current is None:
            # Non-existing addressing, error
            self.ioloop.add_callback(lambda: callback(False))
            return

        def clean_addressing_structures(ok=True, msg=None):
            if not ok:
                return callback(False, msg)
            addr = self.addressing_index.pop((instance_id, port_id))
            if addr[0]:
                # device is present
                del self.addressings[addr[1]][addr[2]]
            else:
                # device is not present
                del self.pending_addressings[(addr[1], addr[2])][(instance_id, port_id)]
            callback(True, msg)

        if not current[0]:
            # Addressed to a disconnected device, we just need to clean structures
            self.ioloop.add_callback(clean_addressing_structures)
            return

        connected, hwid, addrid = current
        self.send(hwid, UNADDRESSING, { 'addressing_id': addrid }, clean_addressing_structures)

    def confirm_unaddressing(self, origin, data, callback=None):
        """
        Receives an unaddressing confirmation
        """
        if callback:
            callback(True)

    def unaddress_many(self, addressings, callback):
        """
        Gets a list of (instance_id, port_id) and unadresses all of them
        """
        def unaddress_next(ok=True, msg=None):
            if not ok:
                return callback(False)
            if len(addressings) == 0:
                return callback(True)
            instance_id, port_id = addressings.pop(-1)
            self.unaddress(instance_id, port_id, unaddress_next)
        unaddress_next()

    def unaddress_instance(self, instance_id, callback):
        """
        Removes all addressings from an instance
        """
        if instance_id < 0:
            return self.unaddress_all(callback)
        addressings = [ x for x in self.addressing_index.keys() if x[0] == instance_id ]
        self.unaddress_many(addressings, callback)

    def unaddress_all(self, callback):
        """
        Removes all addressings
        """
        addressings = self.addressing_index.keys()
        self.unaddress_many(addressings, callback)


def get_actuator_list():
    actuators = []
    for device_id in os.listdir(HARDWARE_DRIVER_DIR):
        path = os.path.join(HARDWARE_DRIVER_DIR, device_id)
        data = json.loads(open(path).read())
        if not md5(data.get('url')).hexdigest() == device_id:
            # Just to avoid automatic backup files here
            continue
        for actuator in data['actuator']:
            actuator['url'] = data['url']
            actuator['channel'] = data['channel']
            actuator['key'] = md5('%s:%s:%s' % (actuator['url'],
                                                actuator['channel'],
                                                actuator['actuator_id'])).hexdigest()
            for mode in actuator['modes']:
                mode['key'] = '%04X' % mode['mask']
                mode['relevant'], mode['expected'] = struct.unpack('2B', struct.pack('>H', mode['mask']))
            actuators.append(actuator)
    return actuators

def get_actuator_index():
    actuators = {}
    for actuator in get_actuator_list():
        actuators[actuator['key']] = actuator
    return actuators

