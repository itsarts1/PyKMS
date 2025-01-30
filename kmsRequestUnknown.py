try:
	import struct
except ImportError:
	import ustruct as struct
from kmsBase import errorCodes, kmsBase

class kmsRequestUnknown(kmsBase):
	def executeRequestLogic(self):
		finalResponse = bytearray()
		finalResponse.extend(bytearray(struct.pack('<I', 0)))
		finalResponse.extend(bytearray(struct.pack('<I', 0)))
		finalResponse.extend(bytearray(struct.pack('<I', errorCodes['SL_E_VL_KEY_MANAGEMENT_SERVICE_ID_MISMATCH'])))
		return bytes(finalResponse)