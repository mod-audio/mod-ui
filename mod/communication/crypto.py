#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later

import io
import uuid

try:
    from Cryptodome.Cipher import PKCS1_OAEP, AES
    from Cryptodome.Hash import SHA1
    from Cryptodome.PublicKey import RSA
    from Cryptodome.Signature import pkcs1_15 as PKCS1_v1_5
    usingCryptodome = True
except ImportError:
    from Crypto.Cipher import PKCS1_OAEP, AES
    from Crypto.Hash import SHA1
    from Crypto.PublicKey import RSA
    from Crypto.Signature import PKCS1_v1_5
    usingCryptodome = False


def encrypt(recipient_key_txt: str, data: str):
    out = io.BytesIO()

    recipient_key = RSA.importKey(recipient_key_txt)
    session_key = uuid.uuid4().bytes

    # Encrypt the session key with the public RSA key
    cipher_rsa = PKCS1_OAEP.new(recipient_key)

    out.write(cipher_rsa.encrypt(session_key))

    # Encrypt the data with the AES session keynonce: str, nonce: str,
    cipher_aes = AES.new(session_key, AES.MODE_EAX, uuid.uuid4().bytes)
    if usingCryptodome:
        ciphertext, tag = cipher_aes.encrypt_and_digest(bytes(data, 'utf-8'))
    else:
        ciphertext, tag = cipher_aes.encrypt_and_digest(data)
    [out.write(x) for x in (cipher_aes.nonce, tag, ciphertext)]
    out.seek(0)
    return out.getvalue()


def decrypt(private_key_txt: str, encrypted: bytes):
    private_key = RSA.importKey(private_key_txt)
    if usingCryptodome:
        private_key_size = int((private_key.size_in_bits() + 1)/8)
    else:
        private_key_size = int((private_key.size() + 1)/8)

    buffer = io.BytesIO(encrypted)
    session_key, nonce, tag, ciphertext = \
       [buffer.read(x) for x in (private_key_size, 16, 16, -1)]

    # Decrypt the session key with the public RSA key
    cipher_rsa = PKCS1_OAEP.new(private_key)
    session_key = cipher_rsa.decrypt(session_key)

    # Decrypt the data with the AES session key
    cipher_aes = AES.new(session_key, AES.MODE_EAX, nonce)
    data = cipher_aes.decrypt_and_verify(ciphertext, tag)
    return data.decode()


def sign_message_sha1(key_txt: str, message: str):
    key = RSA.importKey(key_txt)
    sha1 = SHA1.new()
    sha1.update(message.encode())
    return PKCS1_v1_5.new(key).sign(sha1)


def verify_signature(sender_key_txt: str, contents: str, signature: bytes):
    sender_key = RSA.importKey(sender_key_txt)
    sha1 = SHA1.new()
    sha1.update(contents.encode())
    if usingCryptodome:
        try:
            PKCS1_v1_5.new(sender_key).verify(sha1, signature)
            return True
        except ValueError:
            return False
    else:
        return PKCS1_v1_5.new(sender_key).verify(sha1, signature)
