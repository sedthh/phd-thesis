#!/usr/bin/env python
# -*- coding: utf-8 -*-

import codecs
import json
import asyncio
import websockets
import atexit
from socket import gethostbyname, gethostname
from datetime import datetime
from os import path

from game import Game

class Server:

		HTML_TYPE = "html"
		LOG_TYPE = "csv"
		LOG_HEADSET = 10  # save every 10th update
		LOG_HEADSET_PREFIX = "headset_"


		def __init__(self, ip="", port=42069, fps=1,
					log_level=3, log_prefix="", log_folder="", frontend="../frontend"):
			"""Init Server class. Will run on local IP:42069 by default.

			Headset information will be broadcasted depending on the value of "fps",
			sending it more frequently from the client side will have no effect.
			fps = 10  # resend headset transformation 10 times in a second

			"""

			self.ip = ip if ip else gethostbyname(gethostname())
			self.port = port
			self.frequency = 1.0 / fps
			self.log_level = log_level
			self.log_prefix = log_prefix
			if path.isdir(log_folder):
				self.log_folder = log_folder
			else:
				raise IOError(f'"{log_folder}" is not a valid directory.')
			if path.isdir(frontend):
				self.frontend = frontend
			else:
				raise IOError(f'"{frontend}" is not a valid directory.')

			self.connections = {}
			self.environment = {}

			self.loop = asyncio.get_event_loop()
			asyncio.set_event_loop(self.loop)
			self.service = None
			self.tasks = []
			self.ai = None

		@staticmethod
		def now(f=""):
			"""Return current timestamp with microseconds, format it as string if "f" is set."""
			if not f:
				return datetime.timestamp(datetime.now())
			else:
				return datetime.now().strftime(f)

		# start server
		def run(self):
			"""Run server based on class information."""
			self.service = websockets.serve(self.thread, self.ip, self.port)
			self.tasks = [asyncio.ensure_future(self.service), asyncio.ensure_future(self.tic())]
			self.log(f'Server starting at {self.ip}:{self.port}')
			try:
				self.loop.run_until_complete(asyncio.gather(*self.tasks))
				self.loop.run_forever()
			except KeyboardInterrupt:
				self.stop()

		@atexit.register
		def stop(self):
			"""Stop server (hopefully called when closing application)."""
			self.log('Closing server.')
			self.service.ws_server.close()
			self.service.ws_server.wait_closed()
			asyncio.gather(*asyncio.Task.all_tasks()).cancel()
			self.loop.close()
			self.loop = None
			self.service = None
			self.tasks = []
			self.connections = {}
			self.environment = {}

		def log(self, msg, level=0):
			"""Print server messages based on log level."""
			if level <= self.log_level:
				print(f'{self.now("%H:%M:%S")} > {msg}')

		def dump(self, message):
			# TODO
			return message
			'''
			"""Save relevant user events to CSV file."""
			if not self.environment or "seed" not in self.environment:
				self.log("Experiment environment is not yet set up. Can not save state.")
				return
			if "from" not in message or "key" not in message or "value" not in message:
				self.log("Malformed message. Can not save state.")
				return

			file = path.join(self.log_folder, f'{self.log_prefix}{self.environment["seed"]}.{self.LOG_TYPE}')
			try:
				f = codecs.open(file, "a+", encoding="utf-8")
			except Exception as e:
				self.log(e)
				return
			timestamp = self.now('%Y-%m-%d %H:%M:%S.%f')  # microseconds

			from_ = str(message["from"]).replace(';', ',')
			key = str(message["key"]).replace(';', ',')
			if type(message["value"]) not in (str, int, float, bool):
				value = json.dumps(message["value"])
			else:
				value = str(message["value"]).replace(';', ',')
			try:
				f.write(f'{timestamp};{from_};{key};{value};\r\n')
			except Exception as e:
				self.log(e)
			finally:
				f.close()
			'''

		def id(self, client):
			"""Return printable info on connection."""
			if client not in self.connections:
				return 'UNKNOWN CONNECTION'
			if self.connections[client]["type"]:
				return f'{self.connections[client]["type"]} ({self.connections[client]["ip"]})'
			return f'{self.connections[client]["ip"]}'

		async def thread(self, client, _):
			"""Handle all incoming connections and messages from clients."""
			self.connect(client)  # connect user
			self.log(f'Incoming connection from {self.id(client)}', 1)
			try:
				# wait for data from client once the connection is established
				while True:
					try:
						message = json.loads(await client.recv())

						if "seed" in message:
							self.environment = {
								"seed": int(message["seed"]),
								"status": 0,
								"session": "idle",
								"subject": {
									"name": "",
									"gender": None,
									"avatar": "",
									"score": 0,
									"score_all": 0,
									"moves": []
								},
								"opponent": {
									"name": "",
									"gender": None,
									"avatar": "",
									"score": 0,
									"score_all": 0,
									"moves": []
								},
								"game": Game(int(message["seed"]))
							}
							self.log(f'Starting experiment with seed {int(message["seed"])}')
						if self.environment:
							if "status" in message:
								self.environment["status"] = int(message["status"])
							if "name" in message:
								self.environment["subject"]["name"] = str(message["name"])
							if "gender" in message:
								self.environment["subject"]["gender"] = bool(message["gender"])
							if "avatar" in message:
								self.environment["subject"]["avatar"] = str(message["avatar"])
							if "form" in message:
								for key, value in message["form"].items():
									# TODO: save key-value for forms
									pass
							if "session" in message:
								if message["session"] == "start":
									if self.environment["subject"]["avatar"] and self.environment["subject"]["gender"] is not None:
										self.environment["session"] = "start"
										self.environment["game"].generate(self.environment["subject"]["avatar"], self.environment["subject"]["gender"])
										self.log(f'Game session generated.', 3)
									else:
										# avatar and gender not set
										self.send(client, {"error": True})
								elif message["session"] == "pause":
									pass
								elif message["session"] == "resume":
									pass
						else:
							self.log(f'Environment is not yet set, message was discarded.', 3)
					except json.decoder.JSONDecodeError:
						self.log(f'ERROR! {self.id(client)} has sent malformed JSON data', 2)
						continue
					except KeyError as k_e:
						self.log(f'ERROR! {self.id(client)} has caused error with key {k_e}', 2)
						continue

			# disconnecting
			except websockets.ConnectionClosed:
				self.log(f'{self.id(client)} has disconnected', 1)
			except websockets.WebSocketProtocolError:
				self.log(f'ERROR! {self.id(client)} broke protocol', 2)
			except websockets.PayloadTooBig:
				self.log(f'ERROR! {self.id(client)} has sent a payload that is too large to process', 2)
			except Exception as e:
				self.log(f'ERROR! {self.id(client)} has caused an unknown exception: {e}', 1)
			finally:
				try:
					#await self.disconnect(client)
					pass
				except Exception as e:
					self.log(f'{self.id(client)} failed to disconnect safely: {e}', 2)

		def connect(self, client, data={}):
			"""Create user data when connection is established."""
			if client in self.connections:
				return
			default = {
				"type": "",
				"connected": self.now(),
				"updated": self.now(),
				"ip": (client.remote_address[0] if client.remote_address else "0.0.0.0"),
			}
			self.connections[client] = {**default, **data}

		async def disconnect(self, client):
			"""Remove user data when connection is closed."""
			if client in self.connections:
				del self.connections[client]

		async def tic(self):
			"""Generate tics in background to send headset information async."""
			# TODO
			'''
			current = self.now()
			i = 0
			while True:
				if current + self.frequency < self.now():
					current = self.now()
					await self.headsets((i % self.LOG_HEADSET == 0))
					i += 1
				await asyncio.sleep(self.frequency / 10.0)
			'''
			return

		@staticmethod
		def _validate_transform(transform={}):
			"""Ensure that payload is valid for sending headset transformation data."""
			result = {}
			for key in ("pos", "rot"):
				result[key] = {}
				for cord in ("x", "y", "z"):
					try:
						result[key][cord] = float(transform[key][cord])
					except Exception as _:
						result[key][cord] = 0.
			return result

		async def send(self, client, payload):
			"""Force send any message to a single client through websocket connection."""
			try:
				if client in self.connections:
					await client.send(json.dumps(payload))
			except Exception as e:
				self.log(f"Unable to send payload to {self.id(client)}: {e}", 1)

		def html(self, file):
			"""A horrible hack to get around AJAX cross origin requests"""
			file = path.join(self.frontend, f'{file}.{self.HTML_TYPE}')
			try:
				with codecs.open(file, 'r', encoding='utf-8') as f:
					return f.read()
			except Exception as e:
				self.log(e)
				return "Internal Server Error."


if __name__ == "__main__":
	server = Server(log_folder="../experiments", log_prefix=f"{Server.now('%Y-%m-%d')}_")
	server.run()
