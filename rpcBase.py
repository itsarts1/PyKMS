
class rpcBase:

	packetFlags = {
		'firstFrag' : 1, # 0x01
		'lastFrag' : 2, # 0x02
		'cancelPending' : 4, # 0x04
		'reserved' : 8, # 0x08
		'multiplex' : 16, # 0x10
		'didNotExecute' : 32, # 0x20
		'maybe' : 64, # 0x40
		'objectUuid' : 128 # 0x80
	}

	def __init__(self, data, config):
		self.data = data
		self.config = config

	def populate(self):
		return self.generateResponse(self.parseRequest())

	def parseRequest(self):
		return {}
