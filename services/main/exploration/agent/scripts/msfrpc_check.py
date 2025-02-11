import time
import os
from pymetasploit3.msfrpc import MsfRpcClient

msfrpc_port = os.getenv('MSFRPCD_PORT')

counter = 0
while True:
	if counter > 100:
		print("Gave up trying to connect, lets continue")
		break

	try:
		client = MsfRpcClient('Amdspon200ss11a', port=msfrpc_port)
		print("msfrpc is up, will continue!")
		break
	except:
		print("Error trying to connect to msfrpc service, will try again in 5 seconds..")
		time.sleep(5)
		counter += 1