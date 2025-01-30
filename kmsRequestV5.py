import os
import binascii
import hashlib
import pyaes
from kmsBase import kmsRequestStruct, kmsResponseStruct, kmsBase
from structure import Structure

class kmsRequestV5(kmsBase):
	class RequestV5(Structure):
		class Message(Structure):
			commonHdr = ()
			structure = (
				('salt',      '16s'),
				('encrypted', '240s'), #kmsRequestStruct
			)

		commonHdr = ()
		structure = (
			('bodyLength1',  '<I=2 + 2 + len(message)'),
			('bodyLength2',  '<I=2 + 2 + len(message)'),
			('versionMinor', '<H'),
			('versionMajor', '<H'),
			('message',      ':', Message),
		)

	class ResponseV5(Structure):
		commonHdr = ()
		structure = (
			('bodyLength1',  '<I=2 + 2 + len(salt) + len(encrypted)'),
			('unknown',      '!I=0x00000200'),
			('bodyLength2',  '<I=2 + 2 + len(salt) + len(encrypted)'),
			('versionMinor', '<H'),
			('versionMajor', '<H'),
			('salt',         '16s'),
			('encrypted',    ':'), #DecryptedResponse
			('padding',      ':=bytearray(4 + (((~bodyLength1 & 3) + 1) & 3))'),  # https://forums.mydigitallife.info/threads/71213-Source-C-KMS-Server-from-Microsoft-Toolkit?p=1277542&viewfull=1#post1277542
		)

	class DecryptedResponse(Structure):
		commonHdr = ()
		structure = (
			('response', ':', kmsResponseStruct),
			('keys',     '16s'),
			('hash',     '32s'),
		)

	key = b'\xCD\x7E\x79\x6F\x2A\xB2\x5D\xCB\x55\xFF\xC8\xEF\x83\x64\xC4\x70'

	v6 = False

	ver = 5

	def executeRequestLogic(self):
		requestData = self.RequestV5(self.data)
	
		decrypted = self.decryptRequest(requestData)

		responseBuffer = self.serverLogic(decrypted)
	
		iv, encrypted = self.encryptResponse(requestData, decrypted, responseBuffer)

		return self.generateResponse(iv, encrypted, requestData)
	
	def decryptRequest(self, request):
		encrypted = request['message']['encrypted']
		iv = request['message']['salt']

		decrypter = pyaes.Decrypter(pyaes.AESModeOfOperationCBC(self.key, iv, v6=self.v6))
		decrypted = decrypter.feed(encrypted) + decrypter.feed()

		return kmsRequestStruct(decrypted)

	def encryptResponse(self, request, decrypted, response):
		randomSalt = bytearray(os.urandom(16))
		result = hashlib.sha256(bytes(randomSalt)).digest()

		iv = bytearray(request['message']['salt'])

		XorSalts = pyaes.AES(self.key, v6=self.v6).decrypt(iv)
		randomStuff = bytearray(16)
		for i in range(0,16):
			randomStuff[i] = (bytearray(XorSalts)[i] ^ randomSalt[i]) & 0xff

		responsedata = self.DecryptedResponse()
		responsedata['response'] = response
		responsedata['keys'] = bytes(randomStuff)
		responsedata['hash'] = result

		encrypter = pyaes.Encrypter(pyaes.AESModeOfOperationCBC(self.key, iv, v6=self.v6))
		crypted = encrypter.feed(responsedata.__bytes__()) + encrypter.feed()

		return bytes(iv), crypted

	def decryptResponse(self, response):
		paddingLength = len(response.packField('padding'))
		iv = response['salt']
		encrypted = response['encrypted'][:-paddingLength]

		decrypter = pyaes.Decrypter(pyaes.AESModeOfOperationCBC(self.key, iv, v6=self.v6))
		decrypted = decrypter.feed(encrypted) + decrypter.feed()

		return self.DecryptedResponse(decrypted)
	
	def generateResponse(self, iv, encryptedResponse, requestData):
		response = self.ResponseV5()
		response['versionMinor'] = requestData['versionMinor']
		response['versionMajor'] = requestData['versionMajor']
		response['salt'] = iv
		response['encrypted'] = encryptedResponse

		if self.config['debug']:
			print("KMS V%d Response: %s" % (self.ver, response.dump()))
			print("KMS V%d Structue Bytes: %s" % (self.ver, binascii.b2a_hex(response.__bytes__())))

		return response

	def generateRequest(self, requestBase):
		salt = os.urandom(16)
		message = self.RequestV5.Message()
		message['salt'] = salt
		encrypter = pyaes.Encrypter(pyaes.AESModeOfOperationCBC(self.key, salt, v6=self.v6))
		message['encrypted'] = encrypter.feed(requestBase) + encrypter.feed()

		request = self.RequestV5()
		request['versionMinor'] = requestBase['versionMinor']
		request['versionMajor'] = requestBase['versionMajor']
		request['message'] = message

		if self.config['debug']:
			print("Request V%d Data: %s" % (self.ver, request.dump()))
			print("Request V%d: %s" % (self.ver, binascii.b2a_hex(bytes(request))))

		return request
