import os
import hashlib
import hmac
try:
	import struct
except ImportError:
	import ustruct as struct
import pyaes
from kmsBase import kmsResponseStruct
from kmsRequestV5 import kmsRequestV5
from structure import Structure

class kmsRequestV6(kmsRequestV5):
	class DecryptedResponse(Structure):
		class Message(Structure):
			commonHdr = ()
			structure = (
				('response', ':', kmsResponseStruct),
				('keys',     '16s'),
				('hash',     '32s'),
				('hwid',     '8s'),
				('xorSalts', '16s'),
			)

		commonHdr = ()
		structure = (
			('message', ':', Message),
			('hmac',    '16s'),
		)

	key = b'\xA9\x4A\x41\x95\xE2\x01\x43\x2D\x9B\xCB\x46\x04\x05\xD8\x4A\x21'

	v6 = True

	ver = 6

	def encryptResponse(self, request, decrypted, response):
		randomSalt = bytearray(os.urandom(16))
		result = hashlib.sha256(bytes(randomSalt)).digest()

		SaltC = bytearray(request['message']['salt'])
		XorSalts = bytearray(pyaes.AES(self.key, v6=self.v6).decrypt(SaltC))
		randomStuff = bytearray(16)
		for i in range(0,16):
			randomStuff[i] = (XorSalts[i] ^ randomSalt[i]) & 0xff

		message = self.DecryptedResponse.Message()
		message['response'] = response
		message['keys'] = bytes(randomStuff)
		message['hash'] = result
		message['xorSalts'] = bytes(XorSalts)
		message['hwid'] = self.config['hwid']

		# SaltS
		SaltS = bytearray(os.urandom(16))

		d = pyaes.AESModeOfOperationCBC(self.key, SaltS, v6=True).decrypt(SaltS)

		# DSaltS
		DSaltS = bytearray(d)

		# HMacMsg
		HMacMsg = bytearray(16)
		for i in range (0, 16):
			HMacMsg[i] = (SaltS[i] ^ DSaltS[i]) & 0xff
		HMacMsg.extend(message.__bytes__())

		# HMacKey
		requestTime = decrypted['requestTime']
		HMacKey = self.getMACKey(requestTime)
		if hasattr(hashlib.sha256(), 'digest_size'):
			HMac = hmac.new(HMacKey, bytes(HMacMsg), hashlib.sha256)
		else:  # micropython defaultly use uhashlib, which has no digest_size
			HMac = hmac.new(HMacKey, bytes(HMacMsg), hashlib._sha256.sha256)
		digest = HMac.digest()

		responsedata = self.DecryptedResponse()
		responsedata['message'] = message
		responsedata['hmac'] = digest[16:]

		encrypter = pyaes.Encrypter(pyaes.AESModeOfOperationCBC(self.key, SaltS, v6=True))
		crypted = encrypter.feed(responsedata.__bytes__()) + encrypter.feed()

		return bytes(SaltS), bytes(bytearray(crypted))

	def getMACKey(self, t):
		c1 = 0x00000022816889BD
		c2 = 0x000000208CBAB5ED
		c3 = 0x3156CD5AC628477A

		i1 = (t // c1) & 0xFFFFFFFFFFFFFFFF
		i2 = (i1 * c2) & 0xFFFFFFFFFFFFFFFF
		seed = (i2 + c3) & 0xFFFFFFFFFFFFFFFF

		sha256 = hashlib.sha256()
		sha256.update(struct.pack("<Q", seed))
		digest = sha256.digest()

		return digest[16:]

