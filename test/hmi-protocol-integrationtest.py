#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
import argparse
import sys
import serial

class TestHMIProtocol(unittest.TestCase):
    serial_path = ''
 
    def setUp(self):
        # TODO: Jack, mod-host, socat and mod-ui must be
        # running...probably easier to run by hand
        self.ser = serial.Serial(self.serial_path, 31250, timeout=0.1)

    def test_get_tempo_bpm(self):
        # \x00 terminated!
        msg = ("get_tempo_bpm\00").encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()
        
        # Read until terminating \x00 byte
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0 120.0\x00')        
            
            #raise Exception('Manually raised exception') # raise ERROR
            #self.fail("conditions not met") # raise FAIL
        else:
            self.fail("No response")

    # ##    Check end-to-end
    # def test_set_tempo_bpm(self):
    #     # Depends on get_tempo_bpm!
    #     current_tempo = None
        
    #     # Get the current tempo
    #     msg = ("get_tempo_bpm\00").encode("utf-8")
    #     self.ser.write(msg)
    #     self.ser.flush()
    #     resp = self.ser.read_until('\x00', 100)
    #     if (resp):
    #         tmpstr = resp.decode("utf-8").split(' ')
    #         current_tempo = float(tmpstr[2].strip('\x00'))            
    #     else:
    #         self.fail("No response")

    #     # Increase the current tempo by 5 BPM
    #     msg = ("set_tempo_bpm {0}\00").format(current_tempo+5).encode("utf-8")
    #     self.ser.write(msg)
    #     self.ser.flush();
        
    #     resp = self.ser.read_until('\x00', 100)
    #     if (resp):
    #         self.assertEqual(resp, b'resp 0\x00')
    #     else:
    #         self.fail("No response")

    #     # Check the new tempo
    #     msg = ("get_tempo_bpm\00").encode("utf-8")
    #     self.ser.write(msg)
    #     self.ser.flush()
    #     resp = self.ser.read_until('\x00', 100)
    #     if (resp):
    #         tmpstr = resp.decode("utf-8").split(' ')
    #         current_tempo = float(tmpstr[2].strip('\x00'))
    #         self.assertEqual(current_tempo, 125.0) ## still 120?
    #     else:
    #         self.fail("No response")

    #     ## TODO: This fails here, because Jack is not updated on the tempo, yet.

        
    # def test_get_tempo_bpb(self):
    #     msg = ("get_tempo_bpb\00").encode("utf-8")
    #     self.ser.write(msg)
    #     self.ser.flush()
        
    #     resp = self.ser.read_until('\x00', 100)
    #     if (resp):
    #         self.assertEqual(resp, b'resp 0 4.0\x00')
    #     else:
    #         self.fail("No response")

    # def test_get_snapshot_prgch(self):
    #     msg = ("get_snapshot_prgch\00").encode("utf-8")
    #     self.ser.write(msg)
    #     self.ser.flush()
        
    #     resp = self.ser.read_until('\x00', 100)
    #     if (resp):
    #         self.assertEqual(resp, b'resp 0 14\x00')
    #     else:
    #         self.fail("No response")

    # def test_get_bank_prgch(self):
    #     msg = ("get_bank_prgch\00").encode("utf-8")
    #     self.ser.write(msg)
    #     self.ser.flush()
        
    #     resp = self.ser.read_until('\x00', 100)
    #     if (resp):
    #         self.assertEqual(resp, b'resp 0 15\x00')
    #     else:
    #         self.fail("No response")

    # def test_get_clk_src(self):
    #     msg = ("get_clk_src\00").encode("utf-8")
    #     self.ser.write(msg)
    #     self.ser.flush()
        
    #     resp = self.ser.read_until('\x00', 100)
    #     if (resp):
    #         self.assertEqual(resp, b'resp 0 0\x00')
    #     else:
    #         self.fail("No response")

    # def test_retrieve_profile(self):
    #     msg = ("retrieve_profile 0\00").encode("utf-8")
    #     self.ser.write(msg)
    #     self.ser.flush()
        
    #     resp = self.ser.read_until('\x00', 100)
    #     if (resp):
    #         self.assertEqual(resp, b'resp -1\x00') # Profile not existing?
    #     else:
    #         self.fail("No response")

    # def test_get_exp_cv(self):
    #     msg = ("get_exp_cv\00").encode("utf-8")
    #     self.ser.write(msg)
    #     self.ser.flush()
        
    #     resp = self.ser.read_until('\x00', 100)
    #     if (resp):
    #         self.assertEqual(resp, b'resp 0 0\x00')
    #     else:
    #         self.fail("No response")

    # def test_get_hp_cv(self):
    #     msg = ("get_hp_cv\00").encode("utf-8")
    #     self.ser.write(msg)
    #     self.ser.flush()
        
    #     resp = self.ser.read_until('\x00', 100)
    #     if (resp):
    #         self.assertEqual(resp, b'resp 0 0\x00')
    #     else:
    #         self.fail("No response")

    # def test_get_in_chan_link(self): #TODO check resp
    #     """get_in_chan_link: [int]"""
    #     msg = ("get_in_chan_link 0\00").encode("utf-8")
    #     self.ser.write(msg)
    #     self.ser.flush()
        
    #     resp = self.ser.read_until('\x00', 100)
    #     if (resp):
    #         self.assertEqual(resp, b'resp -1\x00')
    #     else:
    #         self.fail("No response")

    # def test_get_out_chan_link(self): #TODO check resp
    #     """get_out_chan_link: [int]"""
    #     msg = ("get_out_chan_link 0\00").encode("utf-8")
    #     self.ser.write(msg)
    #     self.ser.flush()
        
    #     resp = self.ser.read_until('\x00', 100)
    #     if (resp):
    #         self.assertEqual(resp, b'resp -1\x00')
    #     else:
    #         self.fail("No response")

    # def test_get_display_brightness(self):
    #     msg = ("get_display_brightness\00").encode("utf-8")
    #     self.ser.write(msg)
    #     self.ser.flush()
        
    #     resp = self.ser.read_until('\x00', 100)
    #     if (resp):
    #         self.assertEqual(resp, b'resp 0 50\x00')
    #     else:
    #         self.fail("No response")

    # def test_get_master_volume_channel_mode(self):
    #     msg = ("get_master_volume_channel_mode\00").encode("utf-8")
    #     self.ser.write(msg)
    #     self.ser.flush()
        
    #     resp = self.ser.read_until('\x00', 100)
    #     if (resp):
    #         self.assertEqual(resp, b'resp 0 0\x00')
    #     else:
    #         self.fail("No response")

    # def test_get_play_status(self):
    #     msg = ("get_play_status\00").encode("utf-8")
    #     self.ser.write(msg)
    #     self.ser.flush()
        
    #     resp = self.ser.read_until('\x00', 100)
    #     if (resp):
    #         self.assertEqual(resp, b'resp 0 0\x00')
    #     else:
    #         self.fail("No response")

    # def test_get_master_volume_channel(self):
    #     msg = ("get_master_volume_channel\00").encode("utf-8")
    #     self.ser.write(msg)
    #     self.ser.flush()
        
    #     resp = self.ser.read_until('\x00', 100)
    #     if (resp):
    #         self.assertEqual(resp, b'resp 0 0\x00')
    #     else:
    #         self.fail("No response")

    def test_get_tuner_mute(self):
        msg = ("get_tuner_mute\00").encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()
        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0 0\x00') # 0 means what?
        else:
            self.fail("No response")

    def test_get_pb_name(self):
        msg = ("get_pb_name\00").encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()
        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0 Foobar\x00')
        else:
            self.fail("No response")

    # def test_banks(self):
    #     msg = ("banks\00").encode("utf-8")
    #     self.ser.write(msg)
    #     self.ser.flush()
        
    #     resp = self.ser.read_until('\x00', 100)
    #     if (resp):
    #         self.assertEqual(resp, b'resp 0 All 0 "Test" 1\x00')
    #     else:
    #         self.fail("No response")


            
    # # Note: plural
    # def test_pedalboards(self):
    #     """pedalboards: [int]"""
    #     msg = ("pedalboards\00").encode("utf-8")
    #     self.ser.write(msg)
    #     self.ser.flush()
        
    #     resp = self.ser.read_until('\x00', 100)
    #     if (resp):
    #         self.assertEqual(resp, b'resp 0\x00') # check correctness
    #     else:
    #         self.fail("No response")

    # # Note: singular            
    # def test_pedalboard(self):
    #     """pedalboard: [int, str]"""
    #     msg = ("pedalboard\00").encode("utf-8")
    #     self.ser.write(msg)
    #     self.ser.flush()
        
    #     resp = self.ser.read_until('\x00', 100)
    #     if (resp):
    #         self.assertEqual(resp, b'resp 0\x00') # check correctness, is this default?
    #     else:
    #         self.fail("No response")

    # def test_hw_con(self):
    #     """hw_con: [int, int]"""
    #     msg = ("hw_con\00").encode("utf-8")
    #     self.ser.write(msg)
    #     self.ser.flush()
        
    #     resp = self.ser.read_until('\x00', 100)
    #     if (resp):
    #         self.assertEqual(resp, b'resp 0\x00') # check correctness! [int, int]
    #     else:
    #         self.fail("No response")

    # def test_hw_dis(self):
    #     """hw_dis: [int, int]"""
    #     msg = ("hw_dis\00").encode("utf-8")
    #     self.ser.write(msg)
    #     self.ser.flush()
        
    #     resp = self.ser.read_until('\x00', 100)
    #     if (resp):
    #         self.assertEqual(resp, b'resp 0\x00') # check correctness! [int, int]
    #     else:
    #         self.fail("No response")

    # def test_control_set(self):
    #     """control_set: [int, str, float]"""
    #     msg = ("control_set\00").encode("utf-8")
    #     self.ser.write(msg)
    #     self.ser.flush()
        
    #     resp = self.ser.read_until('\x00', 100)
    #     if (resp):
    #         self.assertEqual(resp, b'resp 0\x00') # check correctness
    #     else:
    #         self.fail("No response")

    # def test_control_set(self):
    #     """control_get: [int, str]"""
    #     msg = ("control_get\00").encode("utf-8")
    #     self.ser.write(msg)
    #     self.ser.flush()
        
    #     resp = self.ser.read_until('\x00', 100)
    #     if (resp):
    #         self.assertEqual(resp, b'resp 0\x00') # check correctness
    #     else:
    #         self.fail("No response")

    # def test_control_next(self):
    #     """control_next: [int, int, int, int]"""
    #     msg = ("control_next\00").encode("utf-8")
    #     self.ser.write(msg)
    #     self.ser.flush()
        
    #     resp = self.ser.read_until('\x00', 100)
    #     if (resp):
    #         self.assertEqual(resp, b'resp 0\x00') # check correctness
    #     else:
    #         self.fail("No response")
            
    def test_tuner(self):
        """tuner: [str]"""
        msg = ("tuner\00").encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()
        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0\x00') # returns -1003. Not testable?
        else:
            self.fail("No response")

    def test_tuner_input(self):
        """tuner_input: [int]"""
        msg = ("tuner_input 0\00").encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()
        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0\x00') # check correctness
        else:
            self.fail("No response")
            
    # def test_pedalboard_save(self):
    #     """pedalboard_save: []"""
    #     msg = ("pedalboard_save\00").encode("utf-8")
    #     self.ser.write(msg)
    #     self.ser.flush()
        
    #     resp = self.ser.read_until('\x00', 100)
    #     if (resp):
    #         self.assertEqual(resp, b'resp 0\x00') # check correctness
    #     else:
    #         self.fail("No response")

    # def test_pedalboard_reset(self):
    #     """pedalboard_reset: []"""
    #     msg = ("pedalboard_reset\00").encode("utf-8")
    #     self.ser.write(msg)
    #     self.ser.flush()
        
    #     resp = self.ser.read_until('\x00', 100)
    #     if (resp):
    #         self.assertEqual(resp, b'resp 0\x00') # check correctness
    #     else:
    #         self.fail("No response")

    ## TODO: If the response code is -1003 it does not get here somehow!
    def test_jack_cpu_load(self):
        msg = ("jack_cpu_load\00").encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()
        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0\x00') # Wrong!
        else:
            self.fail("No response")

    
    ## TODO: Wrong protocol usage results in no error but OK!
    def test_get_truebypass_value01(self):
        """get_truebypass_value: [int]"""
        msg = ("get_truebypass_value 0\00").encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()
        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0 0\x00') # left
        else:
            self.fail("No response")

    def test_get_truebypass_value02(self):
        """get_truebypass_value: [int]"""            
        msg = ("get_truebypass_value 1\00").encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()
        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0 0\x00') # right
        else:
            self.fail("No response")

            
    # def test_set_truebypass_value(self):
    #     """set_truebypass_value: [int, int]"""
    #     msg = ("set_truebypass_value 0 0\00").encode("utf-8") ## Not existing?
    #     self.ser.write(msg)
    #     self.ser.flush()
        
    #     resp = self.ser.read_until('\x00', 100)
    #     if (resp):
    #         self.assertEqual(resp, b'resp 0\x00') # check correctness
    #     else:
    #         self.fail("No response")





# # Beats per minute                                                
#         "get_tempo_bpm": [],
#         "set_tempo_bpm": [float],
# 	# Beats per bar                                                   
#         "get_tempo_bpb": [],
#         "set_tempo_bpb": [float],

#         # MIDI program change channel for switching snapshots             
# 	"get_snapshot_prgch": [],
# 	"set_snapshot_prgch": [int],
#         # MIDI program change channel for switching pedalboard banks      
#         "get_bank_prgch": [],
# 	"set_bank_prgch": [int],

# 	# Transport and tempo sync mode                                   
# 	"get_clk_src": [],
# 	"set_clk_src": [int],

#         # MIDI Beat Clock sending                                         
# 	"get_send_midi_clk": [],
#         "set_send_midi_clk": [int],

#         # User Profile handling                                           
# 	"retrieve_profile": [int],
# 	"store_profile": [int],

#         # Configurable in- and output                                     
#         "get_exp_cv": [],
# 	"set_exp_cv": [int],
# 	"get_hp_cv": [],
#         "set_hp_cv": [int],

# 	# Stereo Link for inputs and outputs                              
# 	"get_in_chan_link": [int],
# 	"set_in_chan_link": [int, int],
# 	"get_out_chan_link": [int],
# 	"set_out_chan_link": [int, int],

#         # Display brightness                                              
# 	"get_display_brightness": [],
#         "set_display_brightness": [int],

#         # Master volume channel mode                                      
# 	"get_master_volume_channel_mode": [],
# 	"set_master_volume_channel_mode": [int],

#         "get_play_status": [],
#         "set_play_status": [int],

#         "get_master_volume_channel": [],
#         "set_master_volume_channel": [int],

#         "get_tuner_mute": [],
#         "set_tuner_mute": [int],

        
            
            
        
if __name__ == '__main__':
    # Handle command line arguments
    parser = argparse.ArgumentParser(description='Test the HMI protocol implemented in mod-ui.')
    parser.add_argument('-d', '--device', nargs=1, required=True,
                        help='serial device, e.g. /dev/pts/5')
    parser.add_argument('unittest_args', nargs='*')    
    args = parser.parse_args()

    # Configure the serial device path
    TestHMIProtocol.serial_path = args.device[0]

    # Overwrite the `--device argument`, so unittest is not bothered
    sys.argv[1:] = args.unittest_args
    unittest.main()
