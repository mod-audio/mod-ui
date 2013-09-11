# -*- coding: utf-8 -*-

# Copyright 2012-2013 AGR Audio, Industria e Comercio LTDA. <contato@portalmod.com>
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
        -1  : "ERR_INSTANCE_INVALID",
        -2  : "ERR_INSTANCE_ALREADY_EXISTS",
        -3  : "ERR_INSTANCE_NON_EXISTS",
        -101: "ERR_LV2_INVALID_URI",
        -102: "ERR_LILV_INSTANTIATION",
        -103: "ERR_LV2_INVALID_PARAM_SYMBOL",
        -201: "ERR_JACK_CLIENT_CREATION",
        -202: "ERR_JACK_CLIENT_ACTIVATION",
        -203: "ERR_JACK_CLIENT_DEACTIVATION",
        -204: "ERR_JACK_PORT_REGISTER",
        -205: "ERR_JACK_PORT_CONNECTION",
        -206: "ERR_JACK_PORT_DISCONNECTION",
        -301: "ERR_MEMORY_ALLOCATION",
    }
    def __init__(self, err=""):
        super(ProtocolError, self).__init__(ProtocolError.ERRORS.get(int(err.replace("\0", "")), "ERR_UNKNOWN"))

def process_resp(resp, datatype):
    if datatype == 'float_structure':
        # resp is first an int representing status
        # then the float
        resps = resp.split()
        resp = { 'ok': int(resps[0]) >= 0 }
        try:
            resp['value'] = float(resps[1])
        except IndexError:
            resp['ok'] = False
    else:
        try:
            resp = int(resp)
        except:
            resp = -1003

        if datatype == 'boolean':
            resp = resp >= 0
    return resp