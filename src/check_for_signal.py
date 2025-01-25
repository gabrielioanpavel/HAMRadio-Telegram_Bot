import os
import time

while True:
	ok = False

	for _ in range(0, 5):
		if os.path.getsize('signal.txt') != 0:
			ok = True
			with open('signal.txt', 'w'):
				pass

			break
		
		time.sleep(30)

	if not ok:
		break

print('Bot crashed, rebooting system...\n')
os.system('sudo reboot')
