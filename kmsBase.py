import binascii
import filetimes
from kmsPidGenFromDB import epidGenerator, kmsdb
import os
import os.path
import sys
import time
try:
	import uuid
except ImportError:
	import upy.uuid as uuid
try:
	import codecs
except ImportError:
	import upy.codecs as codecs

from structure import Structure

# sqlite3 is optional
try:
	import sqlite3
except ImportError:
	pass

from xmltok import tokenize
from uxml2dict import parse

licenseStates = {
	0 : "Unlicensed",
	1 : "Activated",
	2 : "Grace Period",
	3 : "Out-of-Tolerance Grace Period",
	4 : "Non-Genuine Grace Period",
	5 : "Notifications Mode",
	6 : "Extended Grace Period",
}

licenseStatesEnum = {
	'unlicensed': 0,
	'licensed': 1,
	'oobGrace': 2,
	'ootGrace': 3,
	'nonGenuineGrace': 4,
	'notification': 5,
	'extendedGrace': 6
}

errorCodes = {
	'SL_E_VL_NOT_WINDOWS_SLP' : 0xC004F035,
	'SL_E_VL_NOT_ENOUGH_COUNT' : 0xC004F038,
	'SL_E_VL_BINDING_SERVICE_NOT_ENABLED' : 0xC004F039,
	'SL_E_VL_INFO_PRODUCT_USER_RIGHT' : 0x4004F040,
	'SL_I_VL_OOB_NO_BINDING_SERVER_REGISTRATION' : 0x4004F041,
	'SL_E_VL_KEY_MANAGEMENT_SERVICE_ID_MISMATCH' : 0xC004F042,
	'SL_E_VL_MACHINE_NOT_BOUND' : 0xC004F056
}

class UUID(Structure):
	commonHdr = ()
	structure = (
		('raw', '16s'),
	)

	def get(self):
		return uuid.UUID(bytes_le=self.__bytes__())

class kmsRequestStruct(Structure):
	commonHdr = ()
	structure = (
		('versionMinor',            '<H'),
		('versionMajor',            '<H'),
		('isClientVm',              '<I'),
		('licenseStatus',           '<I'),
		('graceTime',               '<I'),
		('applicationId',           ':', UUID),
		('skuId',                   ':', UUID),
		('kmsCountedId' ,           ':', UUID),
		('clientMachineId',         ':', UUID),
		('requiredClientCount',     '<I'),
		('requestTime',             '<Q'),
		('previousClientMachineId', ':', UUID),
		('machineName',             'u'),
		('_mnPad',                  '_-mnPad', '126-len(machineName)'),
		('mnPad',                   ':'),
	)

	def getMachineName(self):
		return self['machineName'].decode('utf-16le')

	def getLicenseStatus(self):
		return licenseStates[self['licenseStatus']] or "Unknown"

class kmsResponseStruct(Structure):
	commonHdr = ()
	structure = (
		('versionMinor',         '<H'),
		('versionMajor',         '<H'),
		('epidLen',              '<I=len(kmsEpid)+2'),
		('kmsEpid',              'u'),
		('clientMachineId',      ':', UUID),
		('responseTime',         '<Q'),
		('currentClientCount',   '<I'),
		('vLActivationInterval', '<I'),
		('vLRenewalInterval',    '<I'),
	)

class GenericRequestHeader(Structure):
	commonHdr = ()
	structure = (
		('bodyLength1',  '<I'),
		('bodyLength2',  '<I'),
		('versionMinor', '<H'),
		('versionMajor', '<H'),
		('remainder',    '_'),
	)

class kmsBase:
	def __init__(self, data, config):
		self.data = data
		self.config = config
		self.dbName = os.path.join(os.path.dirname(__file__), 'clients.db')
		if self.config.get('sqlite', False) and self.config.get('dbSupport', False):
			if not os.path.isfile(self.dbName):
				# Initialize the database.
				con = None
				try:
					con = sqlite3.connect(self.dbName)
					cur = con.cursor()
					cur.execute("CREATE TABLE clients(clientMachineId TEXT, machineName TEXT, applicationId TEXT, skuId TEXT, licenseStatus TEXT, lastRequestTime INTEGER, kmsEpid TEXT, requestCount INTEGER)")

				except sqlite3.Error as e:
					print("Error %s:" % e.args[0])
					sys.exit(1)

				finally:
					if con:
						con.commit()
						con.close()

	def serverLogic(self, kmsRequest):

		if self.config['debug']:
			print("KMS Request Bytes:", binascii.b2a_hex(kmsRequest.__bytes__()))
			print("KMS Request:", kmsRequest.dump())

		clientMachineId = str(kmsRequest['clientMachineId'].get())
		applicationId = str(kmsRequest['applicationId'].get())
		skuId = str(kmsRequest['skuId'].get())
		requestDatetime = filetimes.filetime2timestamp(kmsRequest['requestTime'])

		if not hasattr(time, 'libc'):
			local_dt = time.strftime('%Y-%m-%d %H:%M:%S (UTC%z)', time.localtime(requestDatetime))
		else:  # micropython-time doesn't support time zone
			local_dt = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(requestDatetime))

		# activation threshold:
		# https://docs.microsoft.com/en-us/windows/deployment/volume-activation/activate-windows-10-clients-vamt
		kmsdata = parse(tokenize(open(kmsdb)), lesslist=False)['KmsData'][0]
		appName, skuName, currentClientCount = applicationId, skuId, 25
		for app in kmsdata['AppItems'][0]['AppItem']:
			max_activ_thld = 0
			for kms in app['KmsItem']:
				max_activ_thld = max(max_activ_thld, int(kms.get('@NCountPolicy', 25)))
				for sku in kms.get('SkuItem', []):
					if sku['@Id'] == skuId:
						skuName = sku['@DisplayName']
			if app['@Id'] == applicationId:
				appName = app['@DisplayName']
				currentClientCount = max_activ_thld * 2

		infoDict = {
			"machineName" : kmsRequest.getMachineName(),
			"clientMachineId" : clientMachineId,
			"appId" : appName,
			"skuId" : skuName,
			"licenseStatus" : kmsRequest.getLicenseStatus(),
			"requestTime" : int(time.time()),
			"kmsEpid" : None
		}

		#print infoDict

		if self.config['verbose']:
			print("     Machine Name: %s" % infoDict["machineName"])
			print("Client Machine ID: %s" % infoDict["clientMachineId"])
			print("   Application ID: %s" % infoDict["appId"])
			print("           SKU ID: %s" % infoDict["skuId"])
			print("   Licence Status: %s" % infoDict["licenseStatus"])
			print("     Request Time: %s" % local_dt)

		if self.config['sqlite'] and self.config['dbSupport']:
			con = None
			try:
				con = sqlite3.connect(self.dbName)
				cur = con.cursor()
				cur.execute("SELECT * FROM clients WHERE clientMachineId=:clientMachineId;", infoDict)
				try:
					data = cur.fetchone()
					if not data:
						#print "Inserting row..."
						cur.execute("INSERT INTO clients (clientMachineId, machineName, applicationId, skuId, licenseStatus, lastRequestTime, requestCount) VALUES (:clientMachineId, :machineName, :appId, :skuId, :licenseStatus, :requestTime, 1);", infoDict)
					else:
						#print "Data:", data
						if data[1] != infoDict["machineName"]:
							cur.execute("UPDATE clients SET machineName=:machineName WHERE clientMachineId=:clientMachineId;", infoDict)
						if data[2] != infoDict["appId"]:
							cur.execute("UPDATE clients SET applicationId=:appId WHERE clientMachineId=:clientMachineId;", infoDict)
						if data[3] != infoDict["skuId"]:
							cur.execute("UPDATE clients SET skuId=:skuId WHERE clientMachineId=:clientMachineId;", infoDict)
						if data[4] != infoDict["licenseStatus"]:
							cur.execute("UPDATE clients SET licenseStatus=:licenseStatus WHERE clientMachineId=:clientMachineId;", infoDict)
						if data[5] != infoDict["requestTime"]:
							cur.execute("UPDATE clients SET lastRequestTime=:requestTime WHERE clientMachineId=:clientMachineId;", infoDict)
						# Increment requestCount
						cur.execute("UPDATE clients SET requestCount=requestCount+1 WHERE clientMachineId=:clientMachineId;", infoDict)

				except sqlite3.Error as e:
					print("Error %s:" % e.args[0])

			except sqlite3.Error as e:
				print("Error %s:" % e.args[0])
				sys.exit(1)

			finally:
				if con:
					con.commit()
					con.close()

		return self.createKmsResponse(kmsRequest, currentClientCount)

	def createKmsResponse(self, kmsRequest, currentClientCount):
		response = kmsResponseStruct()
		response['versionMinor'] = kmsRequest['versionMinor']
		response['versionMajor'] = kmsRequest['versionMajor']

		if not self.config["epid"]:
			response["kmsEpid"] = codecs.encode(epidGenerator(kmsRequest['kmsCountedId'].get(), kmsRequest['versionMajor'], self.config["lcid"]), 'utf_16_le')
		else:
			response["kmsEpid"] = codecs.encode(self.config["epid"], 'utf_16_le')
		response['clientMachineId'] = kmsRequest['clientMachineId']
		response['responseTime'] = kmsRequest['requestTime']
		if self.config["CurrentClientCount"]:
			response['currentClientCount'] = self.config["CurrentClientCount"]
		else:
			response['currentClientCount'] = currentClientCount
		response['vLActivationInterval'] = self.config["VLActivationInterval"]
		response['vLRenewalInterval'] = self.config["VLRenewalInterval"]

		if self.config['sqlite'] and self.config['dbSupport']:
			con = None
			try:
				con = sqlite3.connect(self.dbName)
				cur = con.cursor()
				cur.execute("SELECT * FROM clients WHERE clientMachineId=?;", [str(kmsRequest['clientMachineId'].get())])
				try:
					data = cur.fetchone()
					#print "Data:", data
					if data[6]:
						response["kmsEpid"] = codecs.encode(data[6], 'utf_16_le')
					else:
						cur.execute("UPDATE clients SET kmsEpid=? WHERE clientMachineId=?;", (str(response["kmsEpid"].decode('utf-16le')), str(kmsRequest['clientMachineId'].get())))

				except sqlite3.Error as e:
					print("Error %s:" % e.args[0])

			except sqlite3.Error as e:
				print("Error %s:" % e.args[0])
				sys.exit(1)

			finally:
				if con:
					con.commit()
					con.close()

		if self.config['verbose']:
			print("      Server ePID: %s" % response["kmsEpid"].decode('utf-16le'))
		return response

import kmsRequestV4, kmsRequestV5, kmsRequestV6, kmsRequestUnknown

def generateKmsResponseData(data, config):
	version = GenericRequestHeader(data)['versionMajor']
	currentDate = time.strftime("%a %b %d %H:%M:%S %Y")

	if version == 4:
		print("Received V%d request on %s." % (version, currentDate))
		messagehandler = kmsRequestV4.kmsRequestV4(data, config)
	elif version == 5:
		print("Received V%d request on %s." % (version, currentDate))
		messagehandler = kmsRequestV5.kmsRequestV5(data, config)
	elif version == 6:
		print("Received V%d request on %s." % (version, currentDate))
		messagehandler = kmsRequestV6.kmsRequestV6(data, config)
	else:
		print("Unhandled KMS version.", version)
		messagehandler = kmsRequestUnknown.kmsRequestUnknown(data, config)
	return messagehandler.executeRequestLogic()
