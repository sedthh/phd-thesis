#!/usr/bin/env python
# -*- coding: utf-8 -*-

import codecs
import json
import asyncio
import websockets
import atexit
import numpy as np
from socket import gethostbyname, gethostname
from datetime import datetime
from os import path


class Server:

		LOG_TYPE = "csv"
		LOG_HEADSET = 10  # save every 10th update

		def __init__(self, ip="", port=42069, fps=1,
					log_level=3, log_folder="", log_prefix=""):
			"""Init Server class. Will run on local IP:42069 by default.

			Headset information will be broadcasted depending on the value of "fps",
			sending it more frequently from the client side will have no effect.
			fps = 10  # resend headset transformation 10 times in a second

			"""

			self.ip = ip if ip else gethostbyname(gethostname())
			self.port = port
			self.frequency = 1.0 / fps
			self.log_level = log_level
			if path.isdir(log_folder):
				self.log_folder = log_folder
			else:
				raise IOError(f'"{log_folder}" is not a valid directory.')
			self.log_prefix = log_prefix

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
		def run(self, ai=None):
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
			"""Save relevant user events to CSV file."""
			if not self.environment or "seed" not in self.environment:
				self.log("Experiment environment is not yet set up. Can not save state.")
				return
			if "from" not in message or "key" not in message or "value" not in message:
				self.log("Malformed message. Can not save state.")
				return

			file = path.join(self.log_folder, f'{self.log_prefix}{self.environment["seed"]}.{self.LOG_TYPE}')
			try:
				f = codecs.open(file, 'a+', encoding='utf-8')
			except Exception as e:
				self.log(e)
				return
			timestamp = self.now('%Y-%m-%d %H:%M:%S.%f')  # microseconds

			from_ = str(message["from"]).replace(";", ",")
			key = str(message["key"]).replace(";", ",")
			if message["value"] and type(message["value"]) not in (str, int, float, bool):
				value = json.dumps(message["value"])
			else:
				value = str(message["value"]).replace(";", ",")
			try:
				f.write(f'{timestamp};{from_};{key};{value};\r\n')
			except Exception as e:
				self.log(e)
			finally:
				f.close()

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
					except json.decoder.JSONDecodeError:
						self.log(f'ERROR! {self.id(client)} has sent malformed JSON data', 2)
						await self.system(client, 406)
						continue
					if "from" not in message or "key" not in message or "value" not in message:
						self.log(f'ERROR! {self.id(client)} has sent JSON without all of these keys present: from, key, value', 2)
						await self.system(client, 406)
						continue

					# allow ping if JSON is valid
					self.connections[client]["updated"] = self.now()
					if message["from"] in ("server", "subject", "ai"):
						self.connections[client]["type"] = message["from"]
					else:
						self.log(f'ERROR! {self.id(client)} requested invalid client type', 2)
						await self.system(client, 400)
						continue
					if message["key"] == "ping":
						await self.system(client, 220)
						continue

					# setup environment before accepting messages
					if message["from"] == "server":
						if message["key"] == "start":
							if self.environment:
								self.log(f'ERROR! Request from {self.id(client)} tried to re-initiate environment.', 2)
								await self.system(client, 403)
								continue
							else:
								self.setup(int(message["value"]))
								await self.system(client, 200, "Environment ready.")
						elif message["key"] == "stop":
							self.environment = {}
							await self.system(client, 200, "Environment deleted.")
						self.dump(message)
						continue
					if not self.environment:
						self.log(f'ERROR! Request from {self.id(client)} was rejected, because the environment is not yet ready', 2)
						await self.system(client, 403)
						continue

					# decode valid JSON from client
					try:
						if message["from"] in ("subject", "ai"):
							if message["key"] in ("name", "avatar", "choice"):
								self.environment[message["from"]][message["key"]] = message["value"]
								self.dump(message)
								# update info for everyone else
								self.broadcast(message, client)
							elif message["key"] == "meta":
								for key, value in message["value"].items():
									self.environment[message["from"]]["meta"][key] = value
								self.dump(message)
							elif message["key"] == "transform":
								self.environment[message["from"]][message["key"]] = self._validate_transform(message["value"])
							elif message["key"] == "headset":
								self.connections[client]["headset"] = bool(message["value"])
							else:
								self.log(f'ERROR! {self.id(client)} sent message with unknown "key":"{message["key"]}"', 2)
								await self.system(client, 400)
						else:
							self.log(f'ERROR! {self.id(client)} sent message with unknown "from":"{message["from"]}"', 2)
							await self.system(client, 400)

					except Exception as e:
						self.log(f'ERROR! {self.id(client)} has sent data that can not be parsed: {e}', 2)
						await self.system(client, 500)

			# disconnecting
			except websockets.ConnectionClosed:
				self.log(f'{self.id(client)} has disconnected', 1)
			except websockets.WebSocketProtocolError:
				self.log(f'ERROR! {self.id(client)} broke protocol', 1)
			except websockets.PayloadTooBig:
				self.log(f'ERROR! {self.id(client)} has sent a payload that is too large to process', 1)
			except Exception as e:
				self.log(f'ERROR! {self.id(client)} has caused an unknown exception: {e}', 1)
			finally:
				try:
					await self.disconnect(client)
				except Exception as e:
					self.log(f'{self.id(client)} failed to disconnect safely: {e}', 2)
					del self.connections[client]

		def connect(self, client, data={}):
			"""Create user data when connection is established."""
			if client in self.connections:
				return
			default = {
				"type": "",
				"headset": False,
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
			current = self.now()
			i = 0
			while True:
				if current + self.frequency < self.now():
					current = self.now()
					await self.headsets((i % self.LOG_HEADSET == 0))
					i += 1
				await asyncio.sleep(self.frequency / 10.0)

		def setup(self, seed):
			# TODO: generate decoy data and games using ai
			self.environment = {
				"seed": seed,
				"stage": "",
				"games": 0,
				"subject": self._setup_player(),
				"ai": self._setup_player(),
			}
			self.log(f'Setting up new environment with seed {seed}', 1)

		def _setup_player(self):
			return {
				"name": "",
				"avatar": "",
				"transform": self._validate_transform(),
				"choice": "",
				"points": 0,
				"sum": 0,
				"meta": {}
			}

		@staticmethod
		def _validate_transform(transform={}):
			"""Ensure that payload is valid for sending headset transformation data."""
			result = {}
			for key in ("pos", "rot"):
				result[key] = {}
				for cord in ("x", "y", "z"):
					try:
						result[key][cord] = float(transform[key][cord])
					except:
						result[key][cord] = 0.
			return result

		def _payload(self, payload={}):
			default = {
				"time": self.now(),
				"from": "server",
				"key": "foo",
				"value": "bar"
			}
			return {key:(payload[key] if key in payload else default[key]) for key in ("time", "from", "key", "value")}

		async def send(self, client, payload):
			"""Force send any message to a single client through websocket connection."""
			try:
				if client in self.connections:
					await client.send(json.dumps(payload))
			except Exception as e:
				self.log(f"Unable to send payload to {self.id(client)}: {e}", 1)

		async def system(self, client, code=200, msg=""):
			"""Send system and error messages to client."""
			if client in self.connections:
				payload = self._payload({
					"key": ("system" if (code >= 100 and code < 400) else "error"),
					"value": {
						"code": code,
						"msg": (msg if msg else self._get_system_message(code))
					}
				})
				await self.send(client, payload)

		async def broadcast(self, payload, ignore=None):
			"""Make sure payload is valid, then send it to all clients
			(except to optional ignore=user)."""
			payload = self._payload(payload)
			for recipient in self.connections:
				if ignore and recipient != ignore:
					await self.send(recipient, payload)

		async def headsets(self, save=False):
			"""Send all headset data to all users in all rooms (called on tics)."""
			if not self.environment:
				return
			for type_ in ("subject", "ai"):
				payload = self._payload({
					"from": type_,
					"key": "transform",
					"value": self.environment[type_]["transform"]
				})
				for recipient in self.connections:
					if self.connections[recipient]["headset"]:
						if self.connections[recipient]["type"] != type_:
							await self.send(recipient, payload)
				if save:
					self.dump(payload)

		@staticmethod
		def _get_system_message(code):
			"""Return system codes similar to HTTP / FTP status (200-300 ok, 400-500 error)."""
			# ok
			if code == 200:
				return "Ok."  # may be overwritten
			elif code == 202:
				return "Access granted."
			elif code == 220:
				return "Pong."
			# error
			elif code == 400:
				return "Bad request."
			elif code == 403:
				return "Access denied."
			elif code == 406:
				return "Data object has invalid structure."
			elif code == 500:
				return "Internal server error."
			return "Unknown."


if __name__ == "__main__":
	server = Server(log_folder="../experiments", log_prefix=f"{Server.now('%Y-%m-%d_%H-%M-%S')}_")
	server.run()
