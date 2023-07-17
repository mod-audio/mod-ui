#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later

import unittest
import argparse
import sys
import serial

class TestHMIProtocol(unittest.TestCase):
    serial_path = ''

    def setUp(self):
        # NOTE: Jack, mod-host, socat and mod-ui must be
        # running...probably easier to run by hand
        self.ser = serial.Serial(self.serial_path, 31250, timeout=0.1)


    ## Note: Try to keep the same order as in Protocol.COMMANDS!

    def test_store_default_profile(self):
        #      "store_profile": [str]
        msg = ("store_profile Default\00").encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()
        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0\x00')
        else:
            self.fail("No response")

    def test_banks(self):
        msg = ("banks\00").encode("utf-8")

        self.ser.write(msg)
        self.ser.flush()

        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0 All 0 "Test" 1\x00')
        else:
            self.fail("No response")
            
    # Note: plural
    def test_pedalboards(self):
        """pedalboards: [int]"""
        msg = ("pedalboards\00").encode("utf-8")

        self.ser.write(msg)
        self.ser.flush()

        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0\x00') # TODO check correctness
        else:
            self.fail("No response")

    # Note: singular            
    def test_pedalboard(self):
        """pedalboard: [int, str]"""
        msg = ("pedalboard\00").encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()

        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0\x00') # TODO check correctness, is this default?
        else:
            self.fail("No response")


    def test_pedalboard_save(self):
        """pedalboard_save: []"""
        msg = ("pedalboard_save\00").encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()

        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0\x00') # TODO check correctness
        else:
            self.fail("No response")


    def test_pedalboard_reset(self):
        """pedalboard_reset: []"""
        msg = ("pedalboard_reset\00").encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()

        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0\x00')
        else:
            self.fail("No response")


    ## TODO: Wrong protocol usage results in NO error!
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


    def test_set_truebypass_value01(self):
        """set_truebypass_value: [int, int]"""
        msg = ("set_truebypass_value 0 0\00").encode("utf-8") ## Not existing?
        self.ser.write(msg)
        self.ser.flush()

        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0\x00') # check correctness
        else:
            self.fail("No response")

    def test_set_truebypass_value02(self):
        """set_truebypass_value: [int, int]"""
        msg = ("set_truebypass_value 0 1\00").encode("utf-8") ## Not existing?
        self.ser.write(msg)
        self.ser.flush()

        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0\x00') # check correctness
        else:
            self.fail("No response")

    def test_set_truebypass_value03(self):
        """set_truebypass_value: [int, int]"""
        msg = ("set_truebypass_value 1 0\00").encode("utf-8") ## Not existing?
        self.ser.write(msg)
        self.ser.flush()

        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0\x00') # check correctness
        else:
            self.fail("No response")

    def test_set_truebypass_value04(self):
        """set_truebypass_value: [int, int]"""
        msg = ("set_truebypass_value 1 1\00").encode("utf-8") ## Not existing?
        self.ser.write(msg)
        self.ser.flush()

        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0\x00') # check correctness
        else:
            self.fail("No response")

    # TODO: Test if this changes something
    def test_set_q_bypass(self):        
        # First set this to the default value!
        default = 0
        #      "set_q_bypass": [int],
        msg = ("set_q_bypass {0}\00").format(default).encode("utf-8")
        self.ser.write(msg)
        self.ser.flush();
        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0\x00')
        else:
            self.fail("No response")            

            
    def test_get_q_bypass(self):
        #      "get_q_bypass": [],
        msg = ("get_q_bypass\00").encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()
        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0 0\x00')
        else:
            self.fail("No response")


    def test_get_tempo_bpm(self):
        # \x00 terminated!
        #      "get_tempo_bpm": [],
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

    ##    Check end-to-end
    def test_set_tempo_bpm(self):
        # Note: This test depends on get_tempo_bpm!
        current_tempo = None
        
        # Get the current tempo
        msg = ("get_tempo_bpm\00").encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            tmpstr = resp.decode("utf-8").split(' ')
            current_tempo = float(tmpstr[2].strip('\x00'))            
        else:
            self.fail("No response")

        # Increase the current tempo by 5 BPM
        #      "set_tempo_bpm": [float],
        msg = ("set_tempo_bpm {0}\00").format(current_tempo+5).encode("utf-8")
        self.ser.write(msg)
        self.ser.flush();
        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0\x00')
        else:
            self.fail("No response")

        # Check the new tempo
        msg = ("get_tempo_bpm\00").encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            tmpstr = resp.decode("utf-8").split(' ')
            current_tempo = float(tmpstr[2].strip('\x00'))
            self.assertEqual(current_tempo, 125.0)
        else:
            self.fail("No response")

        # Set it back to 120 BPM. So running this test-suite again
        # will not fail on `get_tempo_bpm`.
        msg = ("set_tempo_bpm {0}\00").format(120.0).encode("utf-8")
        self.ser.write(msg)
        self.ser.flush();
        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0\x00')
        else:
            self.fail("No response")

        # Check the tempo again
        msg = ("get_tempo_bpm\00").encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            tmpstr = resp.decode("utf-8").split(' ')
            current_tempo = float(tmpstr[2].strip('\x00'))
            self.assertEqual(current_tempo, 120.0)
        else:
            self.fail("No response")
            

    # TODO: Does this have an effect?
    def test_set_tempo_bpb(self):
        # Set it back to 4.0 BPB as a baseline.
        msg = ("set_tempo_bpb {0}\00").format(4.0).encode("utf-8")
        self.ser.write(msg)
        self.ser.flush();
        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0\x00')
        else:
            self.fail("No response")            
        
    def test_get_tempo_bpb(self):
        #      "get_tempo_bpb": [],
        msg = ("get_tempo_bpb\00").encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()
        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0 4.0\x00')
        else:
            self.fail("No response")


    def test_set_tempo_bpb_02(self):
        # Note: This test depends on get_tempo_bpb!
        
        msg = ("get_tempo_bpb\00").encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            tmpstr = resp.decode("utf-8").split(' ')
            current_beats = float(tmpstr[2].strip('\x00'))
            self.assertEqual(current_beats, 4.0)
        else:
            self.fail("No response")

        #      "set_tempo_bpb": [float]
        new_beat_count = 7
        msg = ("set_tempo_bpb {0}\00").format(new_beat_count).encode("utf-8")
        self.ser.write(msg)
        self.ser.flush();
        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0\x00')
        else:
            self.fail("No response")

        # Check the new beats
        msg = ("get_tempo_bpb\00").encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            tmpstr = resp.decode("utf-8").split(' ')
            current_beats = float(tmpstr[2].strip('\x00'))
            self.assertEqual(current_beats, new_beat_count)
        else:
            self.fail("No response")

        # Set it back to 4 BPB. So running this test-suite again
        # will not fail on `get_tempo_bpb`.
        beats = 4
        msg = ("set_tempo_bpb {0}\00").format(beats).encode("utf-8")
        self.ser.write(msg)
        self.ser.flush();
        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0\x00')
        else:
            self.fail("No response")

        # Check the beats again
        msg = ("get_tempo_bpb\00").encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            tmpstr = resp.decode("utf-8").split(' ')
            current_beats = float(tmpstr[2].strip('\x00'))
            self.assertEqual(current_beats, beats)
        else:
            self.fail("No response")


    # # TODO "tuner": [str], test more possible strings!
    # def test_tuner(self):
    #     """tuner: [str]"""
    #     msg = ("tuner\00").encode("utf-8")
    #     self.ser.write(msg)
    #     self.ser.flush()
        
    #     resp = self.ser.read_until('\x00', 100)
    #     if (resp):
    #         self.assertEqual(resp, b'resp 0\x00') # TODO returns -1003. Not testable?
    #     else:
    #         self.fail("No response")

    def test_tuner_input(self):
        """tuner_input: [int]"""
        msg = ("tuner_input 0\00").encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()
        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0\x00') # TODO check correctness
        else:
            self.fail("No response")
                
    def test_get_tuner_mute(self):
        """get_tuner_mute: []"""
        msg = ("get_tuner_mute\00").encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()
        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0 0\x00')
        else:
            self.fail("No response")

    def test_set_tuner_mute(self):
        #      "set_tuner_mute": [int]
        msg = ("set_tuner_mute 0\00").encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()
        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0\x00')
        else:
            self.fail("No response")
            

    def test_current_profile(self):
        # The profile has state. Reset the state by storing it.
        msg = ("store_profile CurrentProfileTest\00").encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0\x00')
        else:
            self.fail("No response")
        
        #      "get_current_profile"
        msg = ("get_current_profile\00").encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()
        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0 0 1\x00') # TOOD: Why does that fail on first run?
        else:
            self.fail("No response")

    
    def test_retrieve_non_existing_profile(self):
        #       "retrieve_profile": [str],        
        msg = ("retrieve_profile Non-Existent\00").encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()
        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp -1\x00')
        else:
            self.fail("No response")

    def test_store_profile(self):
        #      "store_profile": [str]
        msg = ("store_profile Foobar\00").encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()
        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0\x00')
        else:
            self.fail("No response")
            
    def test_retrieve_profile(self):
        #      "retrieve_profile": [str]
        msg = ("retrieve_profile {0}\00".format("Foobar")).encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()
        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0\x00')
        else:
            self.fail("No response")            


    def test_set_mv_channel_mode(self):
        """set_mv_channel: [int]"""
        default = 0
        msg = ("set_mv_channel {0}\00".format(default)).encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()
        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp -1\x00')
        else:
            self.fail("No response")
            

    def test_get_mv_channel_mode(self):
        #      "get_mv_channel": []
        msg = ("get_mv_channel\00").encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()
        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0 0\x00')
        else:
            self.fail("No response")

    def test_set_in_chan_link(self):
        """set_in_chan_link: [int]"""
        default = 0
        msg = ("set_in_chan_link {0}\00".format(default)).encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()
        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp -1\x00')
        else:
            self.fail("No response")

    def test_get_in_chan_link(self):
        """get_in_chan_link: []"""
        msg = ("get_in_chan_link\00").encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()
        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0 0\x00')
        else:
            self.fail("No response")

    def test_set_out_chan_link(self):
        """set_out_chan_link: [int]"""
        default = 0
        msg = ("set_out_chan_link {0}\00".format(default)).encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()
        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp -1\x00')
        else:
            self.fail("No response")
            
            
    def test_get_out_chan_link(self):
        """get_out_chan_link: []"""
        msg = ("get_out_chan_link\00").encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()
        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0 0\x00')
        else:
            self.fail("No response")


    def test_get_exp_cv(self):
        """set_exp_cv: [int]"""
        default = 0
        msg = ("set_exp_cv {0}\00".format(default)).encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()
        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0\x00')
        else:
            self.fail("No response")

    
    def test_get_exp_cv(self):
        #      "get_exp_cv": []
        msg = ("get_exp_cv\00").encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()
        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0 0\x00')
        else:
            self.fail("No response")


    def test_set_hp_cv(self):
        """set_hp_cv: []"""
        default = 0
        msg = ("set_hp_cv {0}\00".format(default)).encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()
        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0\x00')
        else:
            self.fail("No response")

    
    def test_get_hp_cv(self):
        """get_hp_cv: []"""
        msg = ("get_hp_cv\00").encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()
        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0 0\x00')
        else:
            self.fail("No response")

            
    def test_set_exp_mode(self):
        """set_exp_mode: [int]"""
        default = 0
        msg = ("set_exp_mode {0}\00".format(default)).encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()
        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0\x00')
        else:
            self.fail("No response")            

            
    def test_get_exp_mode(self):
        """get_exp_mode: []"""
        msg = ("get_exp_mode\00").encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()
        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0 0\x00')
        else:
            self.fail("No response")


    def test_set_cv_bias(self):
        """set_cv_bias: [int]"""
        # The profile has state. Reset the state by calling `retrieve`.
        msg = ("retrieve_profile Default\00").encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0\x00')
        else:
            self.fail("No response")

        default = 0
        msg = ("set_cv_bias {0}\00".format(default)).encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()
        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp -1\x00')
        else:
            self.fail("No response")            

        default = 1
        msg = ("set_cv_bias {0}\00".format(default)).encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()
        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0\x00')
        else:
            self.fail("No response")            

        default = 0
        msg = ("set_cv_bias {0}\00".format(default)).encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()
        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0\x00')
        else:
            self.fail("No response")

    def test_get_cv_bias(self):
        """get_cv_bias: []"""
        msg = ("get_cv_bias\00").encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()
        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0 0\x00')
        else:
            self.fail("No response")

        
    def test_get_clk_src(self):
        #      "get_clk_src": [],        
        msg = ("get_clk_src\00").encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()
        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0 0\x00')
        else:
            self.fail("No response")


    # TODO: Test if this changes something
    def test_set_clk_src_01(self):
        # The profile has state. Reset the state by calling `retrieve`.
        msg = ("retrieve_profile Default\00").encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0\x00')
        else:
            self.fail("No response")

        # First set this to the default value!
        default = 0
        #      "set_clk_src": [int],        
        msg = ("set_clk_src {0}\00").format(default).encode("utf-8")
        self.ser.write(msg)
        self.ser.flush();
        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp -1\x00')
        else:
            self.fail("No response")

        # Change it
        default = 1
        #      "set_clk_src": [int],        
        msg = ("set_clk_src {0}\00").format(default).encode("utf-8")
        self.ser.write(msg)
        self.ser.flush();
        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0\x00')
        else:
            self.fail("No response")

        # Change it back
        default = 0
        #      "set_clk_src": [int],        
        msg = ("set_clk_src {0}\00").format(default).encode("utf-8")
        self.ser.write(msg)
        self.ser.flush();
        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0\x00')
        else:
            self.fail("No response")
            

    def test_get_snapshot_prgch(self):
        #      "get_snapshot_prgch": [],
        msg = ("get_snapshot_prgch\00").encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()
        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0 14\x00')
        else:
            self.fail("No response")


    # TODO: Test if this changes something
    def test_set_snapshot_prgch_01(self):
        # The profile has state. Reset the state by calling `store`.
        msg = ("retrieve_profile Default\00").encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0\x00')
        else:
            self.fail("No response")
        
        # First set this to the default value!
        default_channel = 14
        #      "set_snapshot_prgch": [int],        
        msg = ("set_snapshot_prgch {0}\00").format(default_channel).encode("utf-8")
        self.ser.write(msg)
        self.ser.flush();
        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp -1\x00') # Because it was not changed!
        else:
            self.fail("No response")

        # Now change it
        default_channel = 2
        #      "set_snapshot_prgch": [int],        
        msg = ("set_snapshot_prgch {0}\00").format(default_channel).encode("utf-8")
        self.ser.write(msg)
        self.ser.flush();
        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0\x00')
        else:
            self.fail("No response")

        # Change it back
        default_channel = 14
        #      "set_snapshot_prgch": [int],        
        msg = ("set_snapshot_prgch {0}\00").format(default_channel).encode("utf-8")
        self.ser.write(msg)
        self.ser.flush();
        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0\x00')
        else:
            self.fail("No response")
            

    ## TODO missing the plug-in on PC...
    # def test_set_midi_clk_off_01(self):
    #     off = 0
    #     ##     "set_send_midi_clk": [int],
    #     msg = ("set_send_midi_clk {0}\00").format(off).encode("utf-8")
    #     self.ser.write(msg)
    #     self.ser.flush();
        
    #     resp = self.ser.read_until('\x00', 100)
    #     if (resp):
    #         self.assertEqual(resp, b'resp 0\x00')
    #     else:
    #         self.fail("No response")

    def test_get_send_midi_clk_01(self):
        ## First set it to off!
        #self.test_set_midi_clk_off_01()
       
        ##     "get_send_midi_clk": []
        msg = ("get_send_midi_clk\00").encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()
        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0 0\x00')
        else:
            self.fail("No response")

    # # TODO: Missing the plug-in on PC.
    # def test_set_midi_clk_on_01(self):
    #     on = 1
    #     ##     "set_send_midi_clk": [int],
    #     msg = ("set_send_midi_clk {0}\00").format(on).encode("utf-8")
    #     self.ser.write(msg)
    #     self.ser.flush();
        
    #     resp = self.ser.read_until('\x00', 100)
    #     if (resp):
    #         self.assertEqual(resp, b'resp 0\x00')
    #     else:
    #         self.fail("No response")

    #     ## Check the value!
    #     ##     "get_send_midi_clk": []
    #     msg = ("get_send_midi_clk\00").encode("utf-8")
    #     self.ser.write(msg)
    #     self.ser.flush()
        
    #     resp = self.ser.read_until('\x00', 100)
    #     if (resp):
    #         self.assertEqual(resp, b'resp 0 1\x00')
    #     else:
    #         self.fail("No response")
            
    #     ## Set the value back to default
    #     off = 0
    #     ##     "set_send_midi_clk": [int],
    #     msg = ("set_send_midi_clk {0}\00").format(off).encode("utf-8")
    #     self.ser.write(msg)
    #     self.ser.flush();
        
    #     resp = self.ser.read_until('\x00', 100)
    #     if (resp):
    #         self.assertEqual(resp, b'resp 0\x00')
    #     else:
    #         self.fail("No response")

            
    def test_get_pb_prgch(self):
        # The profile has state. Reset the state by calling `store`.
        msg = ("retrieve_profile Foobar\00").encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0\x00')
        else:
            self.fail("No response")
        
        #      "get_pedalboard_prgch": [],
        msg = ("get_pb_prgch\00").encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()
        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0 15\x00')
        else:
            self.fail("No response")


    def test_set_pb_prgch_01(self):
        # The profile has state. Reset the state by calling `store`.
        msg = ("retrieve_profile Foobar\00").encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0\x00')
        else:
            self.fail("No response")

        # First set this to the default value!
        default_channel = 15
        #      "set_pb_prgch": [int],
        msg = ("set_pb_prgch {0}\00").format(default_channel).encode("utf-8")
        self.ser.write(msg)
        self.ser.flush();
        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp -1\x00')
        else:
            self.fail("No response")    

        # Change it.
        default_channel = 12
        #      "set_pb_prgch": [int],
        msg = ("set_pb_prgch {0}\00").format(default_channel).encode("utf-8")
        self.ser.write(msg)
        self.ser.flush();
        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0\x00')
        else:
            self.fail("No response")    

        # Change it back.
        default_channel = 15
        #      "set_pb_prgch": [int],
        msg = ("set_pb_prgch {0}\00").format(default_channel).encode("utf-8")
        self.ser.write(msg)
        self.ser.flush();
        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0\x00')
        else:
            self.fail("No response")    
            
            
    def test_get_play_status(self):
        #      "get_play_status": []        
        msg = ("get_play_status\00").encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()
        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0 0\x00') # Assume ist stopped?
        else:
            self.fail("No response")

    def test_set_play_status_stop(self):
        """set_play_status: [int]"""
        stop = 0
        msg = ("set_play_status {0}\00".format(stop)).encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()
        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0\x00')
        else:
            self.fail("No response")    

    def test_set_play_status_run(self):
        """set_play_status: [int]"""
        run = 1
        msg = ("set_play_status {0}\00".format(run)).encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()

        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0\x00')
        else:
            self.fail("No response")

        # Stop again
        stop = 0
        msg = ("set_play_status {0}\00".format(stop)).encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()

        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0\x00')
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
            
    def test_hw_con(self):
        """hw_con: [int, int]"""
        msg = ("hw_con\00").encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()
        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0\x00') # TODO check correctness! [int, int]
        else:
            self.fail("No response")

    def test_hw_dis(self):
        """hw_dis: [int, int]"""
        msg = ("hw_dis\00").encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()
        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0\x00') # TODO check correctness! [int, int]
        else:
            self.fail("No response")

    def test_control_set(self):
        """control_set: [int, str, float]"""
        msg = ("control_set\00").encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()
        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0\x00') # TODO check correctness
        else:
            self.fail("No response")

    def test_control_set(self):
        """control_get: [int, str]"""
        msg = ("control_get\00").encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()
        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0\x00') # TODO check correctness
        else:
            self.fail("No response")

    def test_control_next(self):
        """control_next: [int, int, int, int]"""
        msg = ("control_next\00").encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()
        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0\x00') # TODO check correctness
        else:
            self.fail("No response")
                        
    def test_pedalboard_save(self):
        """pedalboard_save: []"""
        msg = ("pedalboard_save\00").encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()
        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0\x00') # TODO check correctness
        else:
            self.fail("No response")

    def test_pedalboard_reset(self):
        """pedalboard_reset: []"""
        msg = ("pedalboard_reset\00").encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()
        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0\x00') # TODO check correctness
        else:
            self.fail("No response")

    # ## TODO: If the response code is -1003 it does not get here somehow!
    # def test_jack_cpu_load(self):
    #     msg = ("jack_cpu_load\00").encode("utf-8")
    #     self.ser.write(msg)
    #     self.ser.flush()
        
    #     resp = self.ser.read_until('\x00', 100)
    #     if (resp):
    #         self.assertEqual(resp, b'resp 0\x00') # Wrong!
    #     else:
    #         self.fail("No response")

    def test_pedalboard_reset(self):
        """pedalboard_reset: []"""
        msg = ("pedalboard_reset\00").encode("utf-8")
        self.ser.write(msg)
        self.ser.flush()
        
        resp = self.ser.read_until('\x00', 100)
        if (resp):
            self.assertEqual(resp, b'resp 0\x00') # TODO check correctness
        else:
            self.fail("No response")
            
            

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
