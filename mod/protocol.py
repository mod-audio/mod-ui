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

from mod.mod_protocol import CMD_ARGS

PLUGIN_LOG_TRACE   = 0
PLUGIN_LOG_NOTE    = 1
PLUGIN_LOG_WARNING = 2
PLUGIN_LOG_ERROR   = 3

class ProtocolError(Exception):
    ERRORS = {
        "-1"  : "ERR_INSTANCE_INVALID",
        "-2"  : "ERR_INSTANCE_ALREADY_EXISTS",
        "-3"  : "ERR_INSTANCE_NON_EXISTS",
        "-4"  : "ERR_INSTANCE_UNLICENSED",
        "-101": "ERR_LV2_INVALID_URI",
        "-102": "ERR_LV2_INSTANTIATION",
        "-103": "ERR_LV2_INVALID_PARAM_SYMBOL",
        "-104": "ERR_LV2_INVALID_PRESET_URI",
        "-105": "ERR_LV2_CANT_LOAD_STATE",
        "-201": "ERR_JACK_CLIENT_CREATION",
        "-202": "ERR_JACK_CLIENT_ACTIVATION",
        "-203": "ERR_JACK_CLIENT_DEACTIVATION",
        "-204": "ERR_JACK_PORT_REGISTER",
        "-205": "ERR_JACK_PORT_CONNECTION",
        "-206": "ERR_JACK_PORT_DISCONNECTION",
        "-207": "ERR_JACK_VALUE_OUT_OF_RANGE",
        "-301": "ERR_ASSIGNMENT_ALREADY_EXISTS",
        "-302": "ERR_ASSIGNMENT_INVALID_OP",
        "-303": "ERR_ASSIGNMENT_LIST_FULL",
        "-304": "ERR_ASSIGNMENT_FAILED",
        "-401": "ERR_CONTROL_CHAIN_UNAVAILABLE",
        "-402": "ERR_LINK_UNAVAILABLE",
        "-901": "ERR_MEMORY_ALLOCATION",
        "-902": "ERR_INVALID_OPERATION",
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
    COMMANDS_ARGS = {}
    COMMANDS_FUNC = {}
    COMMANDS_USED = []

    RESPONSES = (
        "r", "resp", "few arguments", "many arguments", "not found",
    )

    @classmethod
    def register_cmd_callback(cls, model, cmd, func):
        if model not in CMD_ARGS.keys():
            raise ValueError("Model %s is not available" % model)
        if cmd not in CMD_ARGS[model].keys():
            raise ValueError("Command %s is not available" % cmd)
        if cmd in cls.COMMANDS_USED:
            raise ValueError("Command %s is already registered" % cmd)

        cls.COMMANDS_ARGS[cmd] = CMD_ARGS[model][cmd]
        cls.COMMANDS_FUNC[cmd] = func
        cls.COMMANDS_USED.append(cmd)

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

        if len(self.args) != len(self.COMMANDS_ARGS[self.cmd]):
            callback("-1003") # TODO: proper error handling
            return

        args = self.args + [callback]
        cmd(*args)

    def process_resp(self, datatype):
        if self.msg.startswith("r "):
            resp = self.msg.replace("r ", "")
            return process_resp(resp, datatype)
        elif self.msg.startswith("resp "):
            resp = self.msg.replace("resp ", "")
            return process_resp(resp, datatype)
        return self.msg

    def parse(self):
        if not self.msg:
            raise ProtocolError("wrong arg type for: '%s'" % (self.cmd,))
        if self.is_resp():
            return

        s = self.msg.find(' ')
        if s > 0:
            self.cmd = self.msg[:s]
            if self.cmd not in self.COMMANDS_USED:
                raise ProtocolError("not found")
            args = self.msg.split(None, len(self.COMMANDS_ARGS[self.cmd]))

        else:
            self.cmd = self.msg
            if self.cmd not in self.COMMANDS_USED:
                raise ProtocolError("not found")
            args = []

        try:
            self.args = [ typ(arg) for typ, arg in zip(self.COMMANDS_ARGS[self.cmd], args[1:]) ]
            if not all(str(a) for a in self.args):
                raise ValueError
        except ValueError:
            raise ProtocolError("wrong arg type for: %s %s" % (self.cmd, self.args))
