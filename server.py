import os
import sys
import argparse
import binascii
try:
	import re
except ImportError:
	import ure as re
import socket
try:
	import socketserver
except ImportError:
	try:
		import SocketServer as socketserver
	except ImportError:
		import upy.socketserver as socketserver
import errno

import rpcBind, rpcRequest
from dcerpc import MSRPCHeader, MSRPC_BIND, MSRPC_REQUEST, MSRPC_ALTERCTX

try:
	IOError
except NameError:
	class IOError(OSError):
		pass

if hasattr(os, 'fork'):
	class TCPServer(socketserver.ForkingTCPServer):
		pass
else:  # os.fork not implemented on Windows
	class TCPServer(socketserver.ThreadingTCPServer):
		pass

config = {}

def main():
	parser = argparse.ArgumentParser()
	parser.add_argument("ip", nargs="?", action="store", default="0.0.0.0", help="The IP address to listen on. The default is \"0.0.0.0\" (all interfaces).", type=str)
	parser.add_argument("port", nargs="?", action="store", default=1688, help="The network port to listen on. The default is \"1688\".", type=int)
	parser.add_argument("-e", "--epid", dest="epid", default=None, help="Use this flag to manually specify an ePID to use. If no ePID is specified, a random ePID will be generated.", type=str)
	parser.add_argument("-l", "--lcid", dest="lcid", default=None, help="Use this flag to manually specify an LCID for use with randomly generated ePIDs. Default is user default language.", type=int)
	parser.add_argument("-c", "--client-count", dest="CurrentClientCount", default=None, help="Use this flag to specify the current client count. Default is 26. A number >25 is required to enable activation.", type=int)
	parser.add_argument("-a", "--activation-interval", dest="VLActivationInterval", default=120, help="Use this flag to specify the activation interval (in minutes). Default is 120 minutes (2 hours).", type=int)
	parser.add_argument("-r", "--renewal-interval", dest="VLRenewalInterval", default=1440 * 7, help="Use this flag to specify the renewal interval (in minutes). Default is 10080 minutes (7 days).", type=int)
	parser.add_argument("-v", "--verbose", dest="verbose", action="store_const", const=True, default=False, help="Use this flag to enable verbose output.")
	parser.add_argument("-d", "--debug", dest="debug", action="store_const", const=True, default=False, help="Use this flag to enable debug output. Implies \"-v\".")
	parser.add_argument("-s", "--sqlite", dest="sqlite", action="store_const", const=True, default=False, help="Use this flag to store request information from unique clients in an SQLite database.")
	parser.add_argument("-o", "--log", dest="log", action="store_const", const=True, default=False, help="Use this flag to enable logging to a file.")
	parser.add_argument("-w", "--hwid", dest="hwid", action="store", default='364F463A8863D35F', help="Use this flag to specify a HWID. The HWID must be an 16-character string of hex characters. The default is \"364F463A8863D35F\".")	
	parsed = parser.parse_args()
	try:
		config.update(vars(parsed))
	except NameError:  # vars not supported on micropython
		config.update(dict((o.dest, getattr(parsed, o.dest)) for o in parser.pos))
		config.update(dict((o.dest, getattr(parsed, o.dest)) for o in parser.opt))
	# Sanitize HWID
	try:
		config['hwid'] = binascii.a2b_hex(''.join([e for e in config['hwid'].strip('0x') if re.match(r'[0-9a-fA-F]', e)]))
		if len(binascii.b2a_hex(config['hwid'])) < 16:
			print("Error: HWID \"%s\" is invalid. Hex string is too short." % binascii.b2a_hex(config['hwid']))
			return
		elif len(binascii.b2a_hex(config['hwid'])) > 16:
			print("Error: HWID \"%s\" is invalid. Hex string is too long." % binascii.b2a_hex(config['hwid']))
			return
	except TypeError:
		print("Error: HWID \"%s\" is invalid. Odd-length hex string." % binascii.b2a_hex(config['hwid']))
		return
	if not config['lcid']:
		# http://stackoverflow.com/questions/3425294/how-to-detect-the-os-default-language-in-python
		if hasattr(sys, 'implementation') and sys.implementation.name == 'micropython':
			config['lcid'] = 1033
		elif os.name == 'nt':
			import ctypes

			config['lcid'] = ctypes.windll.kernel32.GetUserDefaultUILanguage()  # TODO: or GetSystemDefaultUILanguage?
		else:
			import locale

			try:
				config['lcid'] = next(k for k, v in locale.windows_locale.items() if v == locale.getdefaultlocale()[0])
			except StopIteration:
				config['lcid'] = 1033
	if config['debug']:
		config['verbose'] = True
	try:
		import sqlite3
	except ImportError:
		print("Warning: Module \"sqlite3\" is not installed--database support disabled.")
		config['dbSupport'] = False
	else:
		config['dbSupport'] = True
	TCPServer.address_family = socket.getaddrinfo(config['ip'], config['port'], 0, socket.SOCK_DGRAM)[0][0]
	try:
		server = TCPServer((config['ip'], config['port']), kmsServer)
	except OSError:  # micropython can't recognize 2-tuple server_address
		server = TCPServer((config['ip'], config['port'], socket.AF_INET6), kmsServer)
	server.timeout = 5
	print("TCP server listening at %s on port %d." % (config['ip'],config['port']))
	server.serve_forever()

class kmsServer(socketserver.BaseRequestHandler):
	def setup(self):
		print("Connection accepted: %s:%d" % (self.client_address[0],self.client_address[1]))

	def handle(self):
		while True:
			# self.request is the TCP socket connected to the client
			try:
				data = self.request.recv(1024)
			except socket.error as e:
				if e.errno == errno.ECONNRESET:
					print("Error: Connection reset by peer.")
					break
				else:
					raise
			if not data:
				print("No data received!")
				break
			# data = bytearray(data.strip())
			# print binascii.b2a_hex(str(data))
			packetType = MSRPCHeader(data)['type']
			if packetType in (MSRPC_BIND, MSRPC_ALTERCTX):
				if config['verbose']:
					print("RPC bind request received.")
				handler = rpcBind.handler(data, config)
			elif packetType == MSRPC_REQUEST:
				if config['verbose']:
					print("Received activation request.")
				handler = rpcRequest.handler(data, config)
			else:
				print("Error: Invalid RPC request type", packetType)
				break

			res = handler.populate().__bytes__()
			self.request.send(res)

			if packetType == MSRPC_BIND:
				if config['verbose']:
					print("RPC bind acknowledged.")
			elif packetType == MSRPC_REQUEST:
				if config['verbose']:
					print("Responded to activation request.")
				break

	def finish(self):
		self.request.close()
		print("Connection closed: %s:%d" % (self.client_address[0],self.client_address[1]))

if __name__ == "__main__":
	main()
