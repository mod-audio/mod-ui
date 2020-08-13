import json
import base64
from mod.communication import crypto, device


def create_token_message(labs: bool, nonce: str):
    signature = crypto.sign_message_sha1(device.get_device_key(), nonce)
    data = json.dumps({
        'nonce': nonce,
        'device_tag': device.get_tag(),
        'device_uid': device.get_uid(),
        'image_version': device.get_image_version(),
        'signature': base64.encodebytes(signature).decode(),
    })
    encrypted = crypto.encrypt(device.get_labs_key() if labs else device.get_server_key(), data)
    encoded = base64.encodebytes(encrypted)
    return {'message': encoded.decode()}


def decode_and_decrypt(labs: bool, message: str, signature: str):
    encrypted = base64.decodebytes(message.encode())
    token = crypto.decrypt(device.get_device_key(), encrypted)

    # verify signature on newer versions
    jwt_payload = json.loads(base64.decodebytes((token.split('.')[1] + '===').encode()).decode())
    version = [int(i) for i in jwt_payload.get('version', '2.2.2').split('.')]
    if version >= [2, 3, 2]:
        signature = signature.strip()
        if not signature or not crypto.verify_signature(device.get_labs_key() if labs else device.get_server_key(),
                                                        message,
                                                        base64.decodebytes(signature.encode())):
            raise Exception('Server signature verification failed')

    return token
