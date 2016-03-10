import json
import base64
from mod.communication import crypt, device


def encrypt_and_encode(public_key: str, data: str):
    with open(public_key, 'r') as fh:
        server_key_text = fh.read()
    encrypted = crypt.encrypt(server_key_text, data)
    return base64.encodebytes(encrypted)


def create_token_message(nonce: str):
    data = json.dumps({
        'nonce': nonce,
        'device_tag': device.get_tag(),
        'device_uid': device.get_uid(),
    })
    return json.dumps({'message': encrypt_and_encode(device.get_server_key(), data).decode()})


def decode_and_decrypt(message: str):
    data = json.loads(message)['message']
    with open(device.get_device_key(), 'r') as fh:
        device_key_text = fh.read()
    encrypted = base64.decodebytes(data.encode())
    return crypt.decrypt(device_key_text, encrypted)
