import json
import base64
from mod.communication import crypt, device


def create_token_message(nonce: str):
    data = json.dumps({
        'nonce': nonce,
        'device_tag': device.get_tag(),
        'device_uid': device.get_uid(),
        'image_version': device.get_image_version(),
    })
    encrypted = crypt.encrypt(device.get_server_key(), data)
    encoded = base64.encodebytes(encrypted)
    return {'message': encoded.decode()}


def decode_and_decrypt(message: str):
    data = json.loads(message)['message']
    encrypted = base64.decodebytes(data.encode())
    return crypt.decrypt(device.get_device_key(), encrypted)
