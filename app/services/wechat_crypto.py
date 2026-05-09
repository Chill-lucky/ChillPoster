# app/services/wechat_crypto.py
"""
企业微信消息加解密工具
"""
import base64
import hashlib
import random
import socket
import struct
import time
from Crypto.Cipher import AES


class PKCS7Encoder:
    """PKCS7 编码器"""
    block_size = 32

    @classmethod
    def encode(cls, text):
        text_length = len(text)
        amount_to_pad = cls.block_size - (text_length % cls.block_size)
        if amount_to_pad == 0:
            amount_to_pad = cls.block_size
        pad = chr(amount_to_pad)
        return text + pad * amount_to_pad

    @classmethod
    def decode(cls, decrypted):
        pad = ord(decrypted[-1])
        if pad < 1 or pad > 32:
            pad = 0
        return decrypted[:-pad]


class WeChatCrypto:
    """企业微信消息加解密"""

    def __init__(self, token, encoding_aes_key, corp_id):
        self.token = token
        self.corp_id = corp_id
        self.key = base64.b64decode(encoding_aes_key + "=")
        assert len(self.key) == 32

    def get_signature(self, timestamp, nonce, encrypt):
        """计算签名"""
        sort_list = [self.token, timestamp, nonce, encrypt]
        sort_list.sort()
        sha = hashlib.sha1()
        sha.update("".join(sort_list).encode())
        return sha.hexdigest()

    def verify_signature(self, signature, timestamp, nonce, encrypt):
        """验证签名"""
        return signature == self.get_signature(timestamp, nonce, encrypt)

    def encrypt(self, text):
        """加密消息"""
        # 16位随机字符串
        random_str = ''.join(random.choice('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789') for _ in range(16))
        text = text.encode('utf-8')
        # 拼接: 随机字符串 + 消息长度(4字节网络序) + 消息 + corp_id
        text_length = struct.pack("I", socket.htonl(len(text)))
        text = random_str.encode() + text_length + text + self.corp_id.encode()
        # PKCS7 填充
        text = PKCS7Encoder.encode(text.decode('latin-1')).encode('latin-1')
        # AES 加密
        cipher = AES.new(self.key, AES.MODE_CBC, self.key[:16])
        encrypted = cipher.encrypt(text)
        return base64.b64encode(encrypted).decode()

    def decrypt(self, encrypt, msg_signature=None, timestamp=None, nonce=None):
        """解密消息"""
        if msg_signature and timestamp and nonce:
            if not self.verify_signature(msg_signature, timestamp, nonce, encrypt):
                raise Exception("签名验证失败")

        # Base64 解码
        encrypted = base64.b64decode(encrypt)
        # AES 解密
        cipher = AES.new(self.key, AES.MODE_CBC, self.key[:16])
        decrypted = cipher.decrypt(encrypted)
        # 去除 PKCS7 填充
        decrypted = PKCS7Encoder.decode(decrypted.decode('latin-1'))
        # 去除16位随机字符串
        content = decrypted[16:]
        # 获取消息长度
        xml_len = socket.ntohl(struct.unpack("I", content[:4].encode('latin-1'))[0])
        # 获取消息内容
        xml_content = content[4:4 + xml_len].encode('latin-1').decode('utf-8')
        # 获取 corp_id
        from_corp_id = content[4 + xml_len:].encode('latin-1').decode('utf-8')

        if from_corp_id != self.corp_id:
            raise Exception("Corp ID 不匹配")

        return xml_content