# History
This Version allows for activation of Windows Server 2022-2025 <br>
py-kms is a port of node-kms by [markedsword](http://forums.mydigitallife.info/members/183074-markedsword), which is a port of either the C#, C++, or .NET implementations of KMSEmulator, of which the original version was written by [CODYQX4](http://forums.mydigitallife.info/members/89933-CODYQX4) and is derived from the reverse-engineered code of Microsoft's official KMS.

# Features
- Responds to V4, V5, and V6 KMS requests.
- Supports activating all versions after Windows Vista / 2008 and Office 2010.
- It's written in Python.

# Dependencies
- Python 2.6 or higher, micropython v1.9 or higher.
- Python 2.6 needs the "argparse" module installed.
- Micropython needs libffi, and modules in micropythonlib, check section below.

# Usage
- To start the server, execute `python server.py [listen_address] [port]`. The default listening address is `0.0.0.0` (all interfaces) and the default port is `1688`.
- To run the client, use `python client.py server_address [port]`. The default port is `1688`.
- To run on ipv6, please use a valid ipv6 address, for example `::` for broadcast.

# Client product selection
The client can request activation for any product defined in `KmsDataBase.xml`, from Windows Vista / Office 2010 through Windows Server 2025 / Office 2019.
- List every available product: `python client.py server_address --list`.
- Pick a product with `-m/--mode`, using either a short alias or the full product name:
  - `python client.py server_address -m Windows10` (legacy aliases still work)
  - `python client.py server_address -m "Windows Server 2025"`
- Optionally target a specific edition with `--sku` (matched by name substring or GUID), e.g. `--sku Datacenter`.
- Run `python test_client_all.py` to exercise the client against a locally-started server for every product across the V4, V5 and V6 protocols.

# Micropython support (unix port only)
- Micropython v1.9 is necessary since large int support starts here.
- You need libffi.
- You need some standard library of module. Use `micropython -m upip install -r requirements-micropython.txt` to install.
- Only unix port is supported. Other platforms don't have some stdlib and performance may be a problem.

# Disclaimer
This program is meant for education use only and not meant to be used in production environment. We do not condone hosting this software for public use and we only suggest this for educational environments. We are not liable for any claims from Microsoft Corp.
<br> DO NOT PUBLICLY HOST THIS.
