#!/usr/bin/env python3
"""End-to-end test: drive the KMS client against a locally-run server for every
product in KmsDataBase.xml, across all three protocol versions (V4, V5, V6).

For each product it performs a real RPC bind + activation exchange over a socket
and verifies the response:
  * V4      -> the response CMAC-AES hash matches (integrity check)
  * V5 / V6 -> the AES-CBC response decrypts and yields a well-formed ePID

Run:  python3 test_client_all.py
Exits non-zero if any product fails.
"""
import socket
import subprocess
import sys
import time

import client
from kmsRequestV4 import generateHash

HOST = "127.0.0.1"


def wait_for_server(port, timeout=15):
	deadline = time.time() + timeout
	while time.time() < deadline:
		try:
			socket.create_connection((HOST, port), timeout=1).close()
			return True
		except OSError:
			time.sleep(0.2)
	return False


def epid_of(kmsData):
	return kmsData['response']['kmsEpid'].decode('utf-16le')


def check(product, port):
	"""Run one full client exchange for a product and validate the response.
	Returns (ok, detail)."""
	# Build a fresh config the same way the CLI would, then reuse the client's
	# own exchange() against the running server.
	client.config.clear()
	client.config.update({
		'ip': HOST,
		'port': port,
		'mode': product['kmsName'],
		'sku': None,
		'list': False,
		'cmid': None,
		'machineName': None,
		'verbose': False,
		'debug': False,
		'call_id': 1,
	})
	client.updateConfig()
	kmsData = client.exchange()

	epid = epid_of(kmsData)
	if not epid or epid.count('-') < 6:
		return False, "malformed ePID %r" % epid

	major = product['major']
	if major == 4:
		# kmsData is a ResponseV4 structure carrying the raw hash.
		ok = generateHash(bytearray(bytes(kmsData['response']))) == kmsData['hash']
		return (ok, "hash ok" if ok else "V4 hash mismatch")
	if major == 6:
		# Only V6 carries an HWID in the decrypted message.
		if 'hwid' not in kmsData.fields:
			return False, "V6 response missing HWID"
	return True, "decrypted, ePID %s" % epid


def main():
	catalog = client.loadCatalog()
	port = 21688  # non-privileged test port

	server = subprocess.Popen(
		[sys.executable, "server.py", HOST, str(port)],
		stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
	)
	try:
		if not wait_for_server(port):
			print("FATAL: server did not come up on port %d" % port)
			return 1

		results = []
		for product in catalog:
			try:
				ok, detail = check(product, port)
			except Exception as e:
				ok, detail = False, "exception: %r" % e
			results.append((ok, product, detail))
			print("[%s] V%d  %-45s  %s" % (
				"PASS" if ok else "FAIL", product['major'], product['kmsName'], detail))
	finally:
		server.terminate()
		try:
			server.wait(timeout=5)
		except Exception:
			server.kill()

	total = len(results)
	passed = sum(1 for ok, _, _ in results if ok)
	by_ver = {}
	for ok, product, _ in results:
		v = by_ver.setdefault(product['major'], [0, 0])
		v[0] += 1
		if ok:
			v[1] += 1
	print("\nSummary: %d/%d products passed" % (passed, total))
	for v in sorted(by_ver):
		print("  V%d: %d/%d" % (v, by_ver[v][1], by_ver[v][0]))

	return 0 if passed == total else 1


if __name__ == "__main__":
	sys.exit(main())
