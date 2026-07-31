import argparse
import binascii
import os.path
import time
import random
import socket
import string
import sys
import uuid
import errno
try:
	import codecs
except ImportError:
	import upy.codecs as codecs

import filetimes, rpcBind, rpcRequest
from dcerpc import MSRPCHeader, MSRPCBindNak, MSRPCRespHeader, MSRPC_BINDACK, MSRPC_BINDNAK
from kmsBase import kmsRequestStruct, UUID
from kmsRequestV4 import kmsRequestV4, generateHash
from kmsRequestV5 import kmsRequestV5
from kmsRequestV6 import kmsRequestV6
from xmltok import tokenize
from uxml2dict import parse

config = {}

kmsdb = os.path.join(os.path.dirname(__file__), 'KmsDataBase.xml')

# Application IDs whose products only need 5 clients to activate (Office).
OFFICE_APP_IDS = frozenset([
	"59a52881-a989-479d-af46-f275c6370663",  # Office 2010
	"0ff1ce15-a989-479d-af46-f275c6370663",  # Office 2013+
])

# Legacy short mode names kept for backwards compatibility. Each maps to a
# product's KmsItem @DisplayName in KmsDataBase.xml.
ALIASES = {
	'WindowsVista': "Windows Vista",
	'Windows7':     "Windows 7",
	'Windows8':     "Windows 8 (Volume)",
	'Windows81':    "Windows 8.1 (Volume)",
	'Windows10':    "Windows 10 2015 (Volume)",
	'Office2010':   "Office 2010",
	'Office2013':   "Office 2013",
	'Office2016':   "Office 2016",
}

def loadCatalog():
	"""Parse KmsDataBase.xml into a flat list of activatable products, one per
	KmsItem. Each product carries everything a KMS request needs: the parent
	application id, the KmsItem id (KMS counted id), the protocol major version
	and the list of (skuId, skuName) pairs. KmsItems without any SKU are skipped
	because there is nothing to request."""
	with open(kmsdb) as f:
		db = parse(tokenize(f), lesslist=False)['KmsData'][0]

	catalog = []
	for app in db['AppItems'][0]['AppItem']:
		appId, appName = app['@Id'], app['@DisplayName']
		kmsItems = app['KmsItem']
		if not isinstance(kmsItems, list):
			kmsItems = [kmsItems]
		for kms in kmsItems:
			skuItems = kms.get('SkuItem', [])
			if not isinstance(skuItems, list):
				skuItems = [skuItems]
			skus = [(s['@Id'], s['@DisplayName']) for s in skuItems if s]
			if not skus:
				continue
			proto = kms.get('@DefaultKmsProtocol')
			if not proto:
				continue
			catalog.append({
				'appId':   appId,
				'appName': appName,
				'kmsId':   kms['@Id'],
				'kmsName': kms['@DisplayName'],
				'major':   int(float(proto)),  # "6.0" -> 6
				'skus':    skus,
			})
	return catalog

def findProduct(catalog, mode):
	"""Resolve a -m/--mode value to a product. Accepts a legacy alias, a KmsItem
	display name (case-insensitive) or a raw KmsItem GUID."""
	mode = ALIASES.get(mode, mode)
	lowered = mode.lower()
	for product in catalog:
		if product['kmsName'].lower() == lowered:
			return product
	for product in catalog:
		if product['kmsId'].lower() == lowered:
			return product
	return None

def printCatalog(catalog):
	aliasByName = dict((v, k) for k, v in ALIASES.items())
	lastApp = None
	for product in catalog:
		if product['appName'] != lastApp:
			print("\n%s:" % product['appName'])
			lastApp = product['appName']
		alias = aliasByName.get(product['kmsName'])
		print("  V%d  %-45s  %2d SKU(s)%s" % (
			product['major'], product['kmsName'], len(product['skus']),
			"  [alias: %s]" % alias if alias else ""))

def main():
	parser = argparse.ArgumentParser()
	parser.add_argument("ip", action="store", help="The IP address or hostname of the KMS host.", type=str)
	parser.add_argument("port", nargs="?", action="store", default=1688, help="The port the KMS service is listening on. The default is \"1688\".", type=int)
	parser.add_argument("-m", "--mode", dest="mode", default="Windows7", type=str, help="The product to request activation for. Accepts a legacy alias (Windows7, Windows10, Office2016, ...) or any product name from KmsDataBase.xml (e.g. \"Windows Server 2025\"). Use --list to see all products. Default is \"Windows7\".")
	parser.add_argument("--list", dest="list", action="store_const", const=True, default=False, help="List every product available in KmsDataBase.xml and exit.")
	parser.add_argument("--sku", dest="sku", default=None, type=str, help="Optionally pick a specific SKU (by name or GUID) within the chosen product. Default is the product's first SKU.")
	parser.add_argument("-c", "--cmid", dest="cmid", default=None, help="Use this flag to manually specify a CMID to use. If no CMID is specified, a random CMID will be generated.", type=str)
	parser.add_argument("-n", "--name", dest="machineName", default=None, help="Use this flag to manually specify an ASCII machineName to use. If no machineName is specified, a random machineName will be generated.", type=str)
	parser.add_argument("-v", "--verbose", dest="verbose", action="store_const", const=True, default=False, help="Use this flag to enable verbose output.")
	parser.add_argument("-d", "--debug", dest="debug", action="store_const", const=True, default=False, help="Use this flag to enable debug output. Implies \"-v\".")
	config.update(vars(parser.parse_args()))
	checkConfig()
	config['call_id'] = 1
	if config['debug']:
		config['verbose'] = True
	updateConfig()
	print("Connecting to %s on port %d..." % (config['ip'], config['port']))
	try:
		kmsData = exchange()
	except RuntimeError as e:
		print("Error: %s Exiting..." % e)
		sys.exit(1)
	printResult(kmsData)

def exchange():
	"""Run the RPC bind followed by the activation request against the
	configured server and return the parsed KMS response data. Raises
	RuntimeError on any protocol-level failure."""
	s = socket.create_connection((config['ip'], config['port']))
	if config['verbose']:
		print("Connection successful!")
	binder = rpcBind.handler(None, config)
	RPC_Bind = bytes(binder.generateRequest())
	if config['verbose']:
		print("Sending RPC bind request...")
	s.send(RPC_Bind)
	try:
		bindResponse = s.recv(1024)
	except socket.error as e:
		if e.errno == errno.ECONNRESET:
			raise RuntimeError("Connection reset by peer during bind.")
		raise
	if not bindResponse:
		raise RuntimeError("No data received during bind.")
	packetType = MSRPCHeader(bindResponse)['type']
	if packetType == MSRPC_BINDNAK:
		MSRPCBindNak(bindResponse).dump()
		raise RuntimeError("RPC bind was rejected by the server (BINDNAK).")
	if packetType != MSRPC_BINDACK:
		raise RuntimeError("Unexpected RPC packet type during bind: %s." % packetType)
	if config['verbose']:
		print("RPC bind acknowledged.")
	kmsRequest = createKmsRequest()
	requester = rpcRequest.handler(kmsRequest, config)
	s.send(bytes(requester.generateRequest()))
	response = s.recv(1024)
	if config['debug']:
		print("Response:", binascii.b2a_hex(response))
	if not response:
		raise RuntimeError("No data received for the activation request.")
	parsed = MSRPCRespHeader(response)
	return readKmsResponse(parsed['pduData'], kmsRequest, config)

def printResult(kmsData):
	kmsResp = kmsData['response']
	try:
		hwid = kmsData['hwid']
		print("KMS Host HWID:", binascii.b2a_hex(hwid).upper().decode('ascii'))
	except KeyError:
		pass
	print("KMS Host ePID:", kmsResp['kmsEpid'].decode('utf-16le'))
	print("KMS Host Current Client Count:", kmsResp['currentClientCount'])
	print("KMS VL Activation Interval:", kmsResp['vLActivationInterval'])
	print("KMS VL Renewal Interval:", kmsResp['vLRenewalInterval'])

def checkConfig():
	if config['cmid'] is not None:
		try:
			uuid.UUID(config['cmid'])
		except ValueError:
			print("Error: Bad CMID. Exiting...")
			raise
	if config['machineName'] is not None:
		if len(config['machineName']) < 2 or len(config['machineName']) > 63:
			print("Error: machineName must be between 2 and 63 characters in length.")
			sys.exit()

def updateConfig():
	catalog = loadCatalog()

	if config.get('list'):
		printCatalog(catalog)
		sys.exit()

	product = findProduct(catalog, config['mode'])
	if product is None:
		print("Error: unknown mode/product \"%s\". Use --list to see the available products." % config['mode'])
		sys.exit(1)

	skuId = product['skus'][0][0]
	if config.get('sku'):
		wanted = config['sku'].lower()
		skuId = next((sid for sid, sname in product['skus'] if wanted == sid.lower() or wanted in sname.lower()), None)
		if skuId is None:
			print("Error: SKU \"%s\" not found for product \"%s\". Available SKUs:" % (config['sku'], product['kmsName']))
			for sid, sname in product['skus']:
				print("  %s  %s" % (sid, sname))
			sys.exit(1)

	config['RequiredClientCount'] = 5 if product['appId'].lower() in OFFICE_APP_IDS else 25
	config['KMSProtocolMajorVersion'] = product['major']
	config['KMSProtocolMinorVersion'] = 0
	config['KMSClientLicenseStatus'] = 2
	config['KMSClientAppID'] = product['appId']
	config['KMSClientSkuID'] = skuId
	config['KMSClientKMSCountedID'] = product['kmsId']

	if config['verbose']:
		print("Requesting activation for: %s (V%d)" % (product['kmsName'], product['major']))

def createKmsRequestBase():
	requestDict = kmsRequestStruct()
	requestDict['versionMinor'] = config['KMSProtocolMinorVersion']
	requestDict['versionMajor'] = config['KMSProtocolMajorVersion']
	requestDict['isClientVm'] = 0
	requestDict['licenseStatus'] = config['KMSClientLicenseStatus']
	requestDict['graceTime'] = 43200
	requestDict['applicationId'] = UUID(uuid.UUID(config['KMSClientAppID']).bytes_le)
	requestDict['skuId'] = UUID(uuid.UUID(config['KMSClientSkuID']).bytes_le)
	requestDict['kmsCountedId'] = UUID(uuid.UUID(config['KMSClientKMSCountedID']).bytes_le)
	requestDict['clientMachineId'] = UUID(uuid.UUID(config['cmid']).bytes_le if (config['cmid'] is not None) else uuid.uuid4().bytes_le)
	requestDict['previousClientMachineId'] = b'\0' * 16 #requestDict['clientMachineId'] # I'm pretty sure this is supposed to be a null UUID.
	requestDict['requiredClientCount'] = config['RequiredClientCount']
	requestDict['requestTime'] = filetimes.timestamp2filetime(time.time())
	requestDict['machineName'] = codecs.encode(config['machineName'] or ''.join(random.choice(string.ascii_letters + string.digits) for i in range(random.randint(2,63))), 'utf_16_le')
	requestDict['mnPad'] = codecs.encode('\0', 'utf_16_le') * (63 - len(codecs.decode(requestDict['machineName'], 'utf_16_le')))

	# Debug Stuff
	if config['debug']:
		print("Request Base Dictionary:", requestDict.dump())

	return requestDict

def createKmsRequest():
	# Update the call ID
	config['call_id'] += 1

	# KMS Protocol Major Version
	if config['KMSProtocolMajorVersion'] == 4:
		handler = kmsRequestV4(None, config)
	elif config['KMSProtocolMajorVersion'] == 5:
		handler = kmsRequestV5(None, config)
	elif config['KMSProtocolMajorVersion'] == 6:
		handler = kmsRequestV6(None, config)
	else:
		return None

	requestBase = createKmsRequestBase()
	return handler.generateRequest(requestBase)

def readKmsResponse(data, request, config):
	if config['KMSProtocolMajorVersion'] == 4:
		print("Received V4 response")
		response = readKmsResponseV4(data)
	elif config['KMSProtocolMajorVersion'] == 5:
		print("Received V5 response")
		response = readKmsResponseV5(data)
	elif config['KMSProtocolMajorVersion'] == 6:
		print("Received V6 response")
		response = readKmsResponseV6(data)
	else:
		print("Unhandled response version: %d.%d" % (config['KMSProtocolMajorVersion'], config['KMSProtocolMinorVersion']))
		print("I'm not even sure how this happened...")
	return response

def readKmsResponseV4(data):
	response = kmsRequestV4.ResponseV4(data)
	hashed = generateHash(bytearray(bytes(response['response'])))
	print("Response Hash has expected value:", hashed == response['hash'])
	return response

def readKmsResponseV5(data):
	response = kmsRequestV5.ResponseV5(data)
	decrypted = kmsRequestV5(data, config).decryptResponse(response)
	return decrypted

def readKmsResponseV6(data):
	response = kmsRequestV6.ResponseV5(data)
	decrypted = kmsRequestV6(data, config).decryptResponse(response)
	message = decrypted['message']
	return message

if __name__ == "__main__":
	main()
