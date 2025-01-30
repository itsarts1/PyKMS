import binascii
import rpcBase
try:
	import uuid
except ImportError:
	import upy.uuid as uuid

from dcerpc import MSRPCHeader, MSRPCBindAck, MSRPC_BINDACK, MSRPC_BIND, MSRPC_ALTERCTX, MSRPC_ALTERCTX_R
from structure import Structure

uuidNDR32 = uuid.UUID('8a885d04-1ceb-11c9-9fe8-08002b104860')
uuidNDR64 = uuid.UUID('71710533-beba-4937-8319-b5dbef9ccc36')
uuidTime = uuid.UUID('6cb71c2c-9812-4540-0300-000000000000')
uuidEmpty = uuid.UUID('00000000-0000-0000-0000-000000000000')

class CtxItem(Structure):
	structure = (
		('ContextID',          '<H=0'),
		('TransItems',         'B=0'),
		('Pad',                'B=0'),
		('AbstractSyntaxUUID', '16s=b""'),
		('AbstractSyntaxVer',  '<I=0'),
		('TransferSyntaxUUID', '16s=b""'),
		('TransferSyntaxVer',  '<I=0'),
	)

	def ts(self):
		return uuid.UUID(bytes_le=self['TransferSyntaxUUID'])

class CtxItemResult(Structure):
	structure = (
		('Result',             '<H=0'),
		('Reason',             '<H=0'),
		('TransferSyntaxUUID', '16s=b""'),
		('TransferSyntaxVer',  '<I=0'),
	)

	def __init__(self, result, reason, tsUUID, tsVer):
		Structure.__init__(self)
		self['Result'] = result
		self['Reason'] = reason
		self['TransferSyntaxUUID'] = tsUUID.bytes_le
		self['TransferSyntaxVer'] = tsVer

class CtxItemArray:
	def __init__(self, data):
		self.data = data

	def __len__(self):
		return len(self.data)

	def __bytes__(self):
		return self.data

	def __str__(self):
		"""
		In python 2, func `bytes` is alias of `str` and redirect to `__str__`,
		workaround here is to redirect back to `__bytes__`
		"""
		if str is bytes:
			return self.__bytes__()
		else:
			return super(CtxItemArray, self).__str__()

	def dump(self, msg=None, indent=0):
		if msg is None: msg = self.__class__.__name__
		ind = ' '*indent
		print("\n%s" % (msg,))
		item_cnt = int( (len(self) + len(CtxItem()) - 1) / len(CtxItem()) )  # ceiling
		for i in range(item_cnt):
			if hasattr(self[i], 'dump'):
				self[i].dump('%s%s:{' % (ind,i), indent = indent + 4)
				print("%s}" % ind)
			else:
				print("%s%s: {%r}" % (ind,i,self[i]))

	def __getitem__(self, i):
		return CtxItem(self.data[(len(CtxItem()) * i):])

class MSRPCBind(Structure):
	_CTX_ITEM_LEN = len(CtxItem())

	structure = (
			('max_tfrag',   '<H=4280'),
			('max_rfrag',   '<H=4280'),
			('assoc_group', '<L=0'),
			('ctx_num',     'B=0'),
			('Reserved',    'B=0'),
			('Reserved2',   '<H=0'),
			('_ctx_items',  '_-ctx_items', 'self["ctx_num"]*self._CTX_ITEM_LEN'),
			('ctx_items',   ':', CtxItemArray),
	)

class handler(rpcBase.rpcBase):
	def parseRequest(self):
		request = MSRPCHeader(self.data)

		if self.config['debug']:
			print("RPC Bind Request Bytes:", binascii.b2a_hex(self.data))
			print("RPC Bind Request:", request.dump(), MSRPCBind(request['pduData']).dump())

		return request

	def generateResponse(self, request):
		response = MSRPCBindAck()
		bind = MSRPCBind(request['pduData'])

		response['ver_major'] = request['ver_major']
		response['ver_minor'] = request['ver_minor']
		response['flags'] = self.packetFlags['firstFrag'] | self.packetFlags['lastFrag']
		if request['type'] == MSRPC_BIND:
			response['type'] = MSRPC_BINDACK
			response['flags'] |= request['flags'] & self.packetFlags['multiplex']
		elif request['type'] == MSRPC_ALTERCTX:
			response['type'] = MSRPC_ALTERCTX_R
		else:
			raise TypeError('Unknown RPC request type for bind like handler: %s' % response['type'])
		response['representation'] = request['representation']
		response['auth_len'] = request['auth_len']
		response['call_id'] = request['call_id']

		response['max_tfrag'] = bind['max_tfrag']
		response['max_rfrag'] = bind['max_rfrag']
		response['assoc_group'] = 0x1063bf3f

		port = str(self.config['port']).encode()
		if request['type'] == MSRPC_BIND:
			response['SecondaryAddrLen'] = len(port) + 1
			response['SecondaryAddr'] = port
			response['frag_len'] = 36 + bind['ctx_num'] * 24
		elif request['type'] == MSRPC_ALTERCTX:
			response['SecondaryAddrLen'] = 0
			response['frag_len'] = 32 + bind['ctx_num'] * 24
		else:
			raise TypeError('Unknown RPC request type for bind like handler: %s' % response['type'])
		response['ctx_num'] = bind['ctx_num']

		preparedResponses = {}
		if request['type'] == MSRPC_BIND:
			if uuidNDR64 in [bind['ctx_items'][i].ts() for i in range(bind['ctx_num'])]:
				preparedResponses[uuidNDR32] = CtxItemResult(2, 2, uuidEmpty, 0)
				preparedResponses[uuidNDR64] = CtxItemResult(0, 0, uuidNDR64, 1)
				preparedResponses[uuidTime] = CtxItemResult(3, 3, uuidEmpty, 0)
			else:
				preparedResponses[uuidNDR32] = CtxItemResult(0, 0, uuidNDR32, 2)
				preparedResponses[uuidNDR64] = CtxItemResult(2, 2, uuidEmpty, 0)
				preparedResponses[uuidTime] = CtxItemResult(3, 3, uuidEmpty, 0)
		elif request['type'] == MSRPC_ALTERCTX:
			preparedResponses[uuidNDR32] = CtxItemResult(0, 0, uuidNDR32, 2)
		else:
			raise TypeError('Unknown RPC request type for bind like handler: %s' % response['type'])

		response['ctx_items'] = b''
		for i in range (0, bind['ctx_num']):
			ts_uuid = bind['ctx_items'][i].ts()
			resp = preparedResponses[ts_uuid]
			response['ctx_items'] += resp.__bytes__()

		if self.config['debug']:
			print("RPC Bind Response:", response.dump())
			print("RPC Bind Response Bytes:", binascii.b2a_hex(response.__bytes__()))

		return response

	def generateRequest(self):
		firstCtxItem = CtxItem()
		firstCtxItem['ContextID'] = 0
		firstCtxItem['TransItems'] = 1
		firstCtxItem['Pad'] = 0
		firstCtxItem['AbstractSyntaxUUID'] = uuid.UUID('51c82175-844e-4750-b0d8-ec255555bc06').bytes_le
		firstCtxItem['AbstractSyntaxVer'] = 1
		firstCtxItem['TransferSyntaxUUID'] = uuidNDR32.bytes_le
		firstCtxItem['TransferSyntaxVer'] = 2

		secondCtxItem = CtxItem()
		secondCtxItem['ContextID'] = 1
		secondCtxItem['TransItems'] = 1
		secondCtxItem['Pad'] = 0
		secondCtxItem['AbstractSyntaxUUID'] = uuid.UUID('51c82175-844e-4750-b0d8-ec255555bc06').bytes_le
		secondCtxItem['AbstractSyntaxVer'] = 1
		secondCtxItem['TransferSyntaxUUID'] = uuidTime.bytes_le
		secondCtxItem['TransferSyntaxVer'] = 1

		bind = MSRPCBind()
		bind['max_tfrag'] = 5840
		bind['max_rfrag'] = 5840
		bind['assoc_group'] = 0
		bind['ctx_num'] = 2
		bind['ctx_items'] = CtxItemArray(bytes(firstCtxItem)+bytes(secondCtxItem))

		request = MSRPCHeader()
		request['ver_major'] = 5
		request['ver_minor'] = 0
		request['type'] = MSRPC_BIND
		request['flags'] = self.packetFlags['firstFrag'] | self.packetFlags['lastFrag'] | self.packetFlags['multiplex']
		request['call_id'] = self.config['call_id']
		request['pduData'] = bytes(bind)

		if self.config['debug']:
			print("RPC Bind Request:", request.dump(), MSRPCBind(request['pduData']).dump())
			print("RPC Bind Request Bytes:", binascii.b2a_hex(bytes(request)))

		return request

	def parseResponse(self):
		return response

