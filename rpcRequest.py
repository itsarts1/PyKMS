import binascii
import kmsBase
import rpcBase

from dcerpc import MSRPCRequestHeader, MSRPCRespHeader, MSRPC_REQUEST, MSRPC_RESPONSE

class handler(rpcBase.rpcBase):
	def parseRequest(self):
		request = MSRPCRequestHeader(self.data)

		if self.config['debug']:
			print("RPC Message Request Bytes:", binascii.b2a_hex(self.data))
			print("RPC Message Request:", request.dump())

		return request

	def generateResponse(self, request):
		responseData = kmsBase.generateKmsResponseData(request['pduData'], self.config)
		envelopeLength = len(responseData)

		response = MSRPCRespHeader()
		response['ver_major'] = request['ver_major']
		response['ver_minor'] = request['ver_minor']
		response['type'] = MSRPC_RESPONSE
		response['flags'] = self.packetFlags['firstFrag'] | self.packetFlags['lastFrag']
		response['representation'] = request['representation']
		response['call_id'] = request['call_id']

		response['alloc_hint'] = envelopeLength
		response['ctx_id'] = request['ctx_id']
		response['cancel_count'] = 0

		response['pduData'] = responseData

		if self.config['debug']:
			print("RPC Message Response:", response.dump())
			print("RPC Message Response Bytes:", binascii.b2a_hex(response.__bytes__()))

		return response

	def generateRequest(self):
		request = MSRPCRequestHeader()

		request['ver_major'] = 5
		request['ver_minor'] = 0
		request['type'] = MSRPC_REQUEST
		request['flags'] = self.packetFlags['firstFrag'] | self.packetFlags['lastFrag']
		request['representation'] = 0x10
		request['call_id'] = self.config['call_id']
		request['alloc_hint'] = len(self.data)
		request['pduData'] = bytes(self.data)

		if self.config['debug']:
			print("RPC Message Request:", request.dump())
			print("RPC Message Request Bytes:", binascii.b2a_hex(bytes(request)))

		return request

	def parseResponse(self):
		return response
