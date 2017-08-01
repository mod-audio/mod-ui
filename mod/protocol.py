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

class ProtocolError(Exception):
    ERRORS = {
        "-1"  : "ERR_INSTANCE_INVALID",
        "-2"  : "ERR_INSTANCE_ALREADY_EXISTS",
        "-3"  : "ERR_INSTANCE_NON_EXISTS",
        "-101": "ERR_LV2_INVALID_URI",
        "-102": "ERR_LILV_INSTANTIATION",
        "-103": "ERR_LV2_INVALID_PARAM_SYMBOL",
        "-201": "ERR_JACK_CLIENT_CREATION",
        "-202": "ERR_JACK_CLIENT_ACTIVATION",
        "-203": "ERR_JACK_CLIENT_DEACTIVATION",
        "-204": "ERR_JACK_PORT_REGISTER",
        "-205": "ERR_JACK_PORT_CONNECTION",
        "-206": "ERR_JACK_PORT_DISCONNECTION",
        "-301": "ERR_MEMORY_ALLOCATION",
        "not found": "ERR_CMD_NOT_FOUND",
        "wrong arg type": "ERR_INVALID_ARGUMENTS",
        "few arguments": "ERR_FEW_ARGUMENTS",
        "many arguments": "ERR_MANY_ARGUMENTS",
        "finish": "ERR_FINISH",
    }
    def __init__(self, err=""):
        self.err = err
        super(ProtocolError, self).__init__(self.ERRORS.get(err.replace("\0", ""), "ERR_UNKNOWN"))

    def error_code(self):
        try:
            return "resp %d" % int(self.err)
        except ValueError:
            return self.err

def process_resp(resp, datatype):
    if resp is None:
        if datatype == 'boolean':
            return False
        if datatype == 'int':
            return 0
        if datatype == 'float_structure':
            return { 'ok': False }
        if datatype == 'string':
            return ""
        return None

    if datatype == 'float_structure':
        # resp is first an int representing status
        # then the float
        resps = resp.split()
        resp  = { 'ok': int(resps[0]) >= 0 }
        try:
            resp['value'] = float(resps[1])
        except IndexError:
            resp['ok'] = False

    elif datatype == 'string':
        # resp is a simple string, just pass it direcly
        pass

    else:
        try:
            resp = int(resp)
        except ValueError:
            resp = None

        if datatype == 'boolean' and resp is not None:
            resp = resp >= 0

    return resp

class Protocol(object):
    COMMANDS = {
        "banks": [],
        "pedalboards": [int],
        "pedalboard": [int, str],
        "hw_con": [int, int],
        "hw_dis": [int, int],
        "control_set": [int, str, float],
        "control_get": [int, str],
        "control_next": [int, int, int, int],
        "tuner": [str],
        "tuner_input": [int],
        "pedalboard_save": [],
        "pedalboard_reset": [],
        "jack_cpu_load": [],
    }

    COMMANDS_FUNC = {}

    RESPONSES = [
        "resp", "few aguments", "many arguments", "not found"
    ]

    @classmethod
    def register_cmd_callback(cls, cmd, func):
        if cmd not in cls.COMMANDS.keys():
            raise ValueError("Command %s is not registered" % cmd)

        cls.COMMANDS_FUNC[cmd] = func

    def __init__(self, msg):
        self.msg = msg.replace("\0", "").strip()
        self.cmd = ""
        self.args = []
        self.parse()

    def is_resp(self):
        return any(self.msg.startswith(resp) for resp in self.RESPONSES)

    def run_cmd(self, callback):
        if not self.cmd:
            callback("-1003") # TODO: proper error handling
            return

        cmd = self.COMMANDS_FUNC.get(self.cmd, None)
        if cmd is None:
            callback("-1003") # TODO: proper error handling
            return

        if len(self.args) != len(self.COMMANDS[self.cmd]):
            callback("-1003") # TODO: proper error handling
            return

        args = self.args + [callback]
        cmd(*args)

    def process_resp(self, datatype):
        if "resp" in self.msg:
            resp = self.msg.replace("resp ", "")
            return process_resp(resp, datatype)
        return self.msg

    def parse(self):
        if self.is_resp():
            return

        cmd = self.msg.split()
        if not cmd or cmd[0] not in self.COMMANDS.keys():
            raise ProtocolError("not found") # Command not found

        try:
            self.cmd = cmd[0]
            self.args = [ typ(arg) for typ, arg in zip(self.COMMANDS[self.cmd], cmd[1:]) ]
            if not all(str(a) for a in self.args):
                raise ValueError
        except ValueError:
            raise ProtocolError("wrong arg type for: %s %s" % (self.cmd, self.args))
