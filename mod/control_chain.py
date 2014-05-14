# -*- coding: utf-8 -*-

from construct import *
import Queue
from tornado import ioloop

"""
{'range': [[0, 0, 2, 0, False, u'Knob 1'],
           [0, 0, 2, 1, False, u'Knob 2'],
           [0, 0, 2, 2, False, u'Knob 3'],
           [0, 0, 2, 3, False, u'Knob 4'],
           [1, 0, 3, 0, True, 'Exp. 1']],
 'select': [[0, 0, 2, 0, False, u'Knob 1'],
            [0, 0, 2, 1, False, u'Knob 2'],
            [0, 0, 2, 2, False, u'Knob 3'],
            [0, 0, 2, 3, False, u'Knob 4']],
 'switch': [[0, 0, 1, 0, True, u'Foot 1'],
            [0, 0, 1, 1, True, u'Foot 2'],
            [0, 0, 1, 2, True, u'Foot 3'],
            [0, 0, 1, 3, True, u'Foot 4'],
            [1, 0, 1, 0, True, 'Foot - Exp. 1']],
 'tap_tempo': [[0, 0, 1, 0, True, u'Foot 1 (Tap Tempo)'],
               [0, 0, 1, 1, True, u'Foot 2 (Tap Tempo)'],
               [0, 0, 1, 2, True, u'Foot 3 (Tap Tempo)'],
               [0, 0, 1, 3, True, u'Foot 4 (Tap Tempo)'],
               [1, 0, 1, 0, True, 'Foot - Exp. 1']]}
"""

ERROR = 255
CONNECTION = 1
DEVICE_DESCRIPTOR = 2
ADDRESSING = 3
DATA_REQUEST = 4
UNADDRESSING = 5

class Message():
    """
    Message is responsible for parsing and building Control Chain messages. It converts structured data into proper byteflow
    and vice-versa, according to the protocol.
    """
    def __init__(self):
        connection_parser = Struct("data",
            Byte("name_size"),
            String("name", lambda ctx: ctx.name_size),
            Byte("channel"),
            ULInt16("protocol_version"),
        )
        connection_builder = connection_parser

        error_parser = Struct("data",
            ULInt16("code"),
            Byte("msg_size"),
            String("message", lambda ctx: ctx.msg_size),
        )
        error_builder = error_parser

        device_descriptor_builder = Struct("data")
        device_descriptor_parser = Struct("data",
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

        control_addressing_builder = Struct("data",
                                            Byte("addressing_id"),
                                            Byte("port_mask"),
                                            Byte("actuator_id"),
                                            Byte("chosen_mask"),
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
        control_unaddressing_builder = Struct("control_unaddressing",
            If(lambda ctx: ctx._.origin == 0, Byte("addressing_id")),
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
                                     Array(lambda ctx: ctx.requests_count, Byte("requests")),
                                     )

        self._parser = Struct("parser",
            Byte("destination"),
            Byte("origin"),
            Byte("function"),
            ULInt16("data_size"),
            If(lambda ctx: ctx["function"] == 255, error_parser),
            If(lambda ctx: ctx["function"] == 1, connection_parser),
            If(lambda ctx: ctx["function"] == 2, device_descriptor_parser),
            If(lambda ctx: ctx["function"] == 3, control_addressing_parser),
            If(lambda ctx: ctx["function"] == 4, data_request_parser),
            If(lambda ctx: ctx["function"] == 5, control_unaddressing_parser),
        )

        self._builder = {
            'header': Struct("header",
                             Byte("destination"),
                             Byte("origin"),
                             Byte("function"),
                             ULInt16("data_size")),

            255: Struct("data", error_builder),
            1: Struct("data", connection_builder),
            2: Struct("data", device_descriptor_builder),
            3: Struct("data", control_addressing_builder),
            4: Struct("data", data_request_builder),
            5: Struct("data", control_unaddressing_builder),
            }

    def _make_container(self, obj):
        if obj is None:
            return Container()
        for key, value in obj.items():
            if type(value) is dict:
                obj[key] = self._make_container(value)
        return Container(**obj)

    def build(self, destination, function, obj=None):
        data = self._builder[function].build(Container(data=self._make_container(obj)))
        header = self._builder['header'].build(Container(destination=destination,
                                                         origin=0,
                                                         function=function,
                                                         data_size=len(data)))
        return header + data

    def parse(self, buffer):
        return self._parser.parse(buffer)

class Gateway():
    """
    Gateway is responsible for routing control chain messages to the proper way. It expects a byteflow message and 
    handles checksums, byte replacings and connection issues.
    It uses Message to build and parse the messages.
    """
    def __init__(self, handler):
        # Used to handle message above this level
        self.handle = handler
        self.message = Message()

        # Currently control_chain is routed through HMI
        from mod.session import SESSION
        self.hmi = SESSION.hmi
        from mod.protocol import Protocol
        Protocol.register_cmd_callback("chain", self.receive)
        
    def __checksum(self, buffer, size):
        check = 0
        for i in range(size):
            check += ord(buffer[i])
            check &= 0xFF

        if check == 0x00 or check == 0xAA:
            return (~check & 0xFF)

        return check

    def send(self, hwid, function, message=None):
        stream = self.message.build(hwid, 0, function, message)
        self.hmi.send("chain %s%s" % (stream, self.__checksum(stream)))

    def receive(self, message, callback):
        # control_chain protocol is being implemented over the hmi protocol, this will soon be changed.
        # ignoring callback by now
        checksum = message[-1]
        message = message[:-1]
        if checksum == self.__checksum(message):
            self.handle(self.message.parse(message))

class PipeLine():
    """
    PipeLine will send any commands from the Manager to the devices, while polling for events
    every 2 milliseconds. It does that in a way to priorize commands, avoid collisions and
    preserve polling frequency.
    The only control chain message handled by PipeLine is the data_request, all others will go
    to HardwareManager
    """
    def __init__(self, handler):
        # Used to handle messages above this level
        self.handle = handler
        self.gateway = Gateway(self.receive)
        
        # List of hardware ids that will be polled
        self.poll_queue = []
        #  Pointer to the next device to be polled
        self.poll_pointer = 0
        # Time of last poll, initialized on past to schedule start asap
        self.last_poll = ioloop.IOLoop.time() - 1
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
        self.timeout = self.ioloop.add_timeout(self.last_poll + 0.002, task)

    def interrupt(self):
        """
        Cancels any timeout and schedules a process_next to be executed asap
        """
        if self.timeout is not None:
            self.ioloop.remove_timeout(self.timeout)
        self.timeout = self.ioloop.add_timeout(self.last_poll, self.process_next)        

    def process_next(self):
        """
        Checks if there's anything in output queue. If so, send first event, otherwise schedules a poll
        """
        try:
            if self.output_queue.empty():
                return self.schedule(self.poll_next)
            hwid, function, message = self.output_queue.get()
            self.gateway.send(hwid, function, message)        
            self.schedule(self.process_next)
        except:
            self.schedule(self.process_next)

    def poll_next(self):
        """
        Does one polling cycle and schedules next event.
        """
        self.last_poll = ioloop.IOLoop.time()
        try:
            if len(self.poll_queue) == 0:
                return self.schedule(self.process_next)
            self.poll_pointer = (self.poll_pointer + 1) % len(self.poll_queue)
            self.poll_device(self.poll_queue[self.poll_pointer])
            self.schedule(self.process_next)
        except:
            self.schedule(self.process_next)

    def receive(self, msg):
        self.handle(msg)
        self.process_next()

    def poll_device(self, hwid):
        """
        Sends a data_request message to a given hardware
        """
        seq = self.data_request_seqs[hwid]
        self.send(hwid, DATA_REQUEST, {'seq': seq })
        
    def send(self, hwid, function, data=None):
        """
        Puts the message in output queue and interrupts any sleeping
        """
        self.output_queue.put((hwid, function, data))
        self.interrupt()

class HardwareManager():
    """
    HardwareManager is responsible for managing the connections to devices, know which ones are online, the hardware ids and addressing ids.
    It translates the Control Chain protocol to proper calls to Session methods.
    """
    class __init__(self, session):
        self.session = session
        self.pipeline = PipeLine(self.receive)

        # Store hardware data, indexed by hwid
        self.hardwares = {}
        # hwids, indexed by url, channel
        self.hardware_index = {}
        # Pointer used to choose a free hardware id
        self.hardware_id_pointer = 0
        # Last time each hardware have been seen, for timeouts
        self.hardware_tstamp = {}

        # Store addressings data, indexed by hwid, addressing_id
        self.addressings = {}
        # hwid, addressing_id, indexed by instanceId, symbol
        self.addressing_index = {}
        # Pointers used to choose free addressing ids, per hardware
        self.current_addressing_id = {}

        # Maps Control Chain function ids to internal methods
        self.dispatch_table = {
            CONNECTION: self.device_connect,
            DEVICE_DESCRIPTOR: self.save_device_driver,
            DATA_REQUEST: self.receive_device_data,
            ADDRESSING: self.confirm_addressing,
            UNADDRESSING: self.confirm_unaddressing,
            }
    
    def start(self):
        self.pipeline.start()
    def send(self, hwid, function, data=None):
        self.pipeline.send(hwid, function, data)

    def receive(self, msg):
        """
        Called by pipeline, will route message internally
        """
        self.hardware_tstamp[msg.origin] = ioloop.IOLoop.time()
        self.dispatch_table[msg.function](msg.origin, msg.data)
    
    def _generate_hardware_id(self):
        start = self.hardware_id_pointer
        while self.hardwares.get(self.current_id) is not None:
            self.hardware_id_pointer = (self.hardware_id_pointer + 1) % 256
            if self.hardware_id_pointer == start:
                return None # full!
        return self.hardware_id_pointer

    def device_connect(self, origin, data):
        url = data['url']
        channel = data['channel']
        logging.info("connection %s on %d" % (url, channel))
        hwid = self._generate_hardware_id()
        self.hardwares[hwid] = data
        self.hwid_index[(url, channel)] = hwid
        self.hardware_tstamp[hwid] = ioloop.IOLoop.time()
        self.send(hwid, CONNECTION, data)
        if not os.path.exists(self.get_driver_path(url)):
            self.send(hwid, DEVICE_DESCRIPTOR)
            return

        if not self.hardware_is_installed(url, channel):
            return

        self.load_hardware(url, channel)

    def device_disconnect(self, hwid):
        data = self.hardwares.pop(hwid)
        del self.hw_index[(data['url'], data['channel'])]
        del self.hardware_tstamp[hwid]
        self.unload_hardware(hwid)

    def get_driver_path(self, url):
        device_id = md5(url).hexdigest()
        return os.path.join(HARDWARE_DRIVER_DIR, device_id)

    def hardware_is_installed(self, url, channel):
        device_id = md5(url).hexdigest()
        installation_path = os.path.join(KNOWN_HARDWARE_DIR, "%s_%d" % (device_id, channel))
        return os.path.exists(installation_path) and os.path.exists(self.get_driver_path())

    def load_hardware(self, url, channel):
        hwid = self.hwid_index.get((url, channel))
        if hwid is None:
            return
        self.pipeline.add_hardware(hwid)

        """
        hardware_data = json.loads(open(self.get_driver_path(url)).read())
        self.hardwares[hwid].update(hardware_data)
        """

    def unload_hardware(self, hwid):
        self.pipeline.remove_hardware(hwid)

    def save_device_driver(self, hwid, data):
        path = self.get_driver_path(data['url'])
        open(path, 'w').write(json.dumps(data))
        

    def receive_device_data(self, hwid, data):
        self.data_request_seqs[hwid] = (self.data_request_seqs[hwid]+1) % 256
        # TODO handle updates
        for addressing_id in data.requests:
            self.send_addressing_data(addressing_id)            




        
        
    
