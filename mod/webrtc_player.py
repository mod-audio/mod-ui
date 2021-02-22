import os
import re
import subprocess
from tornado.ioloop import IOLoop

from mod import settings

def _is_audio_file(filename):
    return re.match('^[A-Za-z0-9._-]+\.(webm|wav)$', filename)


class WebrtcPlayerManager:
    def __init__(self, host):
        self.host = host
        self.clients = set()
        self.link = False
        self.players = {
            1: self.create_player(1),
            2: self.create_player(2),
        }

    def create_player(self, inpt):

        def broadcast(msg):
            msg['input'] = inpt
            self.broadcast(msg)

        return WebrtcPlayer(inpt, self.host, broadcast)

    def add_client(self, client):
        self.clients.add(client)

        players = {

        }
        for (inpt, player) in self.players.items():
            players[inpt] = player.get_state()

        client.send({
            'cmd': 'state',
            'link': self.link,
            'players': players,
        })

    def remove_client(self, client):
        self.clients.remove(client)

    def broadcast(self, msg):
        for client in self.clients:
            client.send(msg)

    def handle(self, msg):
        cmd = msg['cmd']

        if cmd == 'set_link':
            self.link = msg['link']
        else:
            # this is an input specific cmd
            inpt = msg.get('input', None)
            if inpt:
                player = self.players[inpt]

            print("GOT COMMAND %s in input %d" % (cmd, inpt))

            if cmd == 'select_audio':
                if not _is_audio_file(msg['audio']):
                    return
                player.select_audio(msg['audio'])

            elif cmd in ('play', 'stop'):
                self.link_cmd(cmd, player)
                if cmd == 'play' and not self.host.transport_rolling:
                    self.host.set_transport_rolling(True, True, False, True, False)
                elif cmd == 'stop':
                    if not self.playing:
                        self.host.set_transport_rolling(False, True, False, True, False)

        self.broadcast(msg)

    def link_cmd(self, cmd, player):
        if not self.link:
            getattr(player, cmd)()
            return
        for pl in self.players.values():
            getattr(pl, cmd)()
            if pl is not player:
                self.broadcast({
                    'cmd': cmd,
                    'input': pl.input_number,
                })

    @property
    def playing(self):
        for player in self.players.values():
            if player.playing:
                return True
        return False


class WebrtcPlayer:

    def __init__(self, input_number, host, broadcast):
        self.host = host
        self.input_number = input_number
        self.broadcast = broadcast
        self.selected_audio = self.list_audios()[0]
        self.playing = False

    @property
    def audio_filename(self):
        return os.path.join(settings.WEBRTC_PLAYER_AUDIO_DIR, self.selected_audio)

    def get_state(self):
        return {
            'audios': self.list_audios(),
            'selected_audio': self.selected_audio,
            'playing': self.playing,
        }

    def select_audio(self, audio):
        self.selected_audio = audio
        if self.playing:
            self.host.webrtc_select_audio(self.input_number, self.audio_filename)

    def play(self):
        if not self.selected_audio:
            return False
        self.playing = True
        self.host.webrtc_play(self.input_number, self.audio_filename)

    def stop(self):
        self.playing = False
        self.host.webrtc_stop(self.input_number)

    def list_audios(self):
        audios = []
        for filename in os.listdir(settings.WEBRTC_PLAYER_AUDIO_DIR):
            if not _is_audio_file(filename):
                continue
            audios.append(filename)
        return sorted(audios)
