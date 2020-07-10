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
    # Make sure this is free of duplicates!
    COMMANDS = {
        "banks": [int, int],
        "pedalboards": [int, int, int],
        "pb": [int, str],

        "hw_con": [int, int],
        "hw_dis": [int, int],

        "s": [int, float], # control_set
        "g": [int], # control_get
        "n": [int], # control_next
        "ncp": [int, int], # next_control_page

        "pbs": [], # pedalboard_save
        "pbr": [], # pedalboard_reset

        "g_bp": [int],      # get_truebypass_value
        "s_bp": [int, int], # set_truebypass_value

        # Quick Bypass Mode
        "g_qbp": [],    # get_q_bypass
        "s_qbp": [int], # set_q_bypass

        # Beats per minute
        "g_bpm": [],    # get_tempo_bpm
        "s_bpm": [int], # set_tempo_bpm

        # Beats per bar
        "g_bpb": [],    # get_tempo_bpb
        "s_bpb": [int], # set_tempo_bpb

        "tu": [str],    # tuner
        "tu_i": [int],  # tuner_input
        "g_tum": [],    # get_tuner_mute
        "s_tum": [int], # set_tuner_mute

        "fn": [int], # footswitch_navigation

        # User Profile handling
        "g_p": [],    # get_current_profile
        "r_p": [int], # retrieve_profile
        "s_p": [int], # store_profile

        # Master volume channel mode
        "g_mv_c": [],    # get_mv_channel
        "s_mv_c": [int], # set_mv_channel

        # Stereo Link for inputs and outputs
        "g_il": [],    # get_in_chan_link
        "s_il": [int], # set_in_chan_link
        "g_ol": [],    # get_out_chan_link
        "s_ol": [int], # set_out_chan_link

        # Configurable in- and output
        "g_ex": [],      # get_exp_cv
        "s_ex": [int],   # set_exp_cv
        "g_hp": [],      # get_hp_cv
        "s_hp": [int],   # set_hp_cv
        "g_exp_m": [],    # get_exp_mode
        "s_exp_m": [int], # set_exp_mode

        # Transport and tempo sync mode
        "g_cls": [],    # get_clk_src
        "s_cls": [int], # set_clk_src

        # MIDI program change channel for switching snapshots
        "g_ssc": [],    # get_snapshot_prgch
        "s_ssc": [int], # set_snapshot_prgch

        # MIDI Beat Clock sending
        "g_mclk": [],    # get_send_midi_clk
        "s_mclk": [int], # set_send_midi_clk

        # MIDI program change channel for switching pedalboards in a bank
        "g_pbc": [],    # get_pb_prgch
        "s_pbc": [int], # set_pb_prgch

        # Transport play status
        "g_ps": [],    # get_play_status
        "s_ps": [int], # set_play_status

        # Display brightness
        "g_br": [],    # get_display_brightness
        "s_br": [int], # set_display_brightness

        "sl": [int], # snapshot_load
        "ss": [int], # snapshot_save

        "lp": [int], # page_load

        "am": [str, str, str, str], # alsamixer

        # unused
        "get_pb_name": [],
        "encoder_clicked": [int],
    }

    COMMANDS_FUNC = {}

    RESPONSES = [
        "resp", "few arguments", "many arguments", "not found"
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
