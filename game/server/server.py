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

	def __init__(self, ip="", port=42069,
				log_level=3, log_folder="", log_info="", log_game=""):
		"""Init Server class. Will run on local IP:42069 by default."""

		self.ip = ip if ip else gethostbyname(gethostname())
		self.port = port
		self.frequency = 1.0 / 10.  # fps=10
		self.log_level = log_level
		self.log_info = log_info
		self.log_game = log_game
		if path.isdir(log_folder):
			self.log_folder = log_folder
		else:
			raise IOError(f'ERROR! "{log_folder}" is not a valid directory.')

		self.connections = {}
		self.environment = {}

		self.loop = asyncio.get_event_loop()
		asyncio.set_event_loop(self.loop)
		self.service = None
		self.tasks = []
		self.ai = None

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
		self.log('Closing server')
		self.terminate()
		for client in self.connections:
			self.disconnect(client)
		self.connections = {}

		self.service.ws_server.close()
		self.service.ws_server.wait_closed()
		asyncio.gather(*asyncio.Task.all_tasks()).cancel()

		self.loop.close()
		self.loop = None
		self.service = None
		self.tasks = []

	def log(self, msg, level=0):
		"""Print server messages based on log level."""
		if level <= self.log_level:
			if "sid" in self.environment:
				print(f'{self.now("%H:%M:%S")} [{self.environment["sid"]}] > {msg}')
			else:
				print(f'{self.now("%H:%M:%S")} > {msg}')

	def _save_data(self, file, key, value):
		if not self.environment or "sid" not in self.environment:
			self.log("ERROR! Experiment environment is not yet set up, can not save to CSV.", 1)
			return
		key, value = self._for_csv(key), self._for_csv(value)
		timestamp = self.now('%Y-%m-%d %H:%M:%S.%f')  # microseconds
		file = path.join(self.log_folder, file)
		try:
			f = codecs.open(file, "a+", encoding="utf-8")
			f.write(f'{timestamp};{self.environment["sid"]};{key};{value};\r\n')
		except Exception as ef:
			self.log(ef)
		finally:
			f.close()

	def save_info(self, key, value=""):
		"""Save user info to CSV file."""
		if not self.log_info:
			return
		self._save_data(self.log_info, key, value)

	def save_game(self, key, value=""):
		"""Save user info to CSV file."""
		if not self.log_game:
			return
		self._save_data(self.log_game, key, value)

	def id(self, client):
		"""Return printable info on connection."""
		if client not in self.connections:
			return 'UNIDENTIFIED CONNECTION'
		if self.connections[client]["type"]:
			return f'{self.connections[client]["ip"]} ({self.connections[client]["type"]})'
		return f'{self.connections[client]["ip"]}'

	async def thread(self, client, _):
		"""Handle all incoming connections and messages from clients."""
		self.connect(client)  # connect user
		self.log(f'Incoming connection from {self.id(client)}', 1)
		try:
			# wait for data from client once the connection is established
			while True:
				try:
					message = await client.recv()
					self.update(client)  # now message was received at timestamp
					message = json.loads(message)  # convert to dict

					# see if message object has all required fields
					if "type" not in message or "data" not in message:
						self.log(f'ERROR! Message should consist of: {"type":"str", "data":{...}}.', 2)
						continue
					elif message["type"] not in ("info", "game"):
						self.log(f'ERROR! Message type can be either "info" or "game".', 2)
						continue

					# receiving user info / form values
					elif message["type"] == "info":

						# can not continue without subject id
						if "sid" in message["data"]:
							try:
								sid = int(self._for_csv(message["data"]["sid"]))
							except Exception as ei:
								self.log(f'ERROR! Subject ID can only be numeric, stopping experiment.', 1)
								return
							if sid:
								self.environment["sid"] = sid
								self.environment["game_over"] = False
								self.log(f'Subject ID was set, starting experiment', 1)
							else:
								self.log(f'ERROR! Subject id is invalid.', 2)
								continue
						if "sid" not in self.environment:
							self.log(f'ERROR! All messages will be ignored until "sid" is set.', 2)
							continue

						# check data
						for key, value in message["data"].items():
							if key == "terminate":
								self.save_info(key, bool(value))
								if value:
									self.log(f'Experiment was a success. Now resetting environment\n', 1)
								else:
									self.log(f'Experiment failed. Now resetting environment\n', 1)
								self.terminate()
								break
							elif key == "type":
								self.connections[client]["type"] = value
								self.log(f'Client {self.id(client)} was identified', 2)
							elif key in ("nick", "avatar", "gender"):
								self.save_info(key, value)
								self.environment[key] = value
								self.log(f'Subject\'s {key} was set to {value}', 1)
							elif key.startswith("form_"):
								self.save_info(key, value)
							elif key != "sid":
								self.log(f'ERROR! Unknown "info" key "{key}"', 2)

					# receiving game data
					elif message["type"] == "game":

						if "sid" not in self.environment:
							self.log(f'ERROR! All messages will be ignored until "sid" is set.', 2)
							await self.send(client, "error", {"message": "Subject ID and information is not yet given."})
							continue

						# can not continue if subject's profile is not set and game is not connected
						if "connect" in message["data"]:
							ready = True
							for test in ("nick", "avatar", "gender"):
								if test not in self.environment:
									self.log(f'The game can not start until the subject has set their {test}', 2)
									ready = False
							if ready:
								if "ready" not in self.environment or not self.environment["ready"]:
									# tried to replay
									if "game_over" in self.environment and self.environment["game_over"]:
										await self.send(client, "error", {"message": "Subject has already played a game."})
										continue
									# create game environment for new player
									self.environment["ready"] = True
									self.environment["game_over"] = False
									self.environment["game"] = Game(self.environment["sid"])  # use SID as random seed
									self.environment["game"].generate(self.environment["avatar"], bool(self.environment["gender"]))

									self.save_game("connected", "")
									await self.send(client, "game", {"connected": True})
									self.log(f'Subject {self.id(client)} has started playing', 1)
								else:
									# reconecting
									self.save_game("reconnected", "")
									env = self.environment["game"].get_environment()
									await self.send(client, "game", env)
									self.log(f'Subject {self.id(client)} has reconnected', 1)
							else:
								await self.send(client, "error", {"message": "Subject is not ready setting up their profile."})
						if "ready" not in self.environment or not self.environment["ready"]:
							self.log('ERROR! Subject needs to set up their profile before the experiment can start.', 2)
							continue

						# check data
						for key, value in message["data"].items():
							if key == "type":
								self.connections[client]["type"] = value
								self.log(f'Client {self.id(client)} was identified', 2)
							elif key == "search":
								search = self.environment["game"].search()
								if search >= 0:
									env = self.environment["game"].get_environment()
									self.save_game(key, search)
									for env_key in env:
										self.save_game(env_key, env[env_key])
									await self.hook(lambda: self.send(client, "game", env), env["loading"])
									await self.hook(lambda: self.play_bot(client), env["loading"] + env["wait"])
								else:
									# no more games to play, subject can exit VR
									await self.game_over()
									self.log(f'Subject {self.id(client)} has finished playing', 1)
							elif key == "play":
								# in case of reconnecting before searching
								if self.environment["game"].is_playing():
									# saving is handled by function
									await self.play_subject(client, bool(value))
								else:
									# ignore move, fore new match
									await self.send(client, "game", {"end": True})
							elif key == "disconnect":
								self.environment["ready"] = False
								self.environment["game_over"] = True
								self.save_game(key, value)
								#await self.send(client, "game", {"exit": True})
								self.log(f'Subject {self.id(client)} has disconnected', 1)
							elif key != "connect":
								self.log(f'ERROR! Unknown "game" key "{key}"', 2)

				except json.decoder.JSONDecodeError:
					self.log(f'ERROR! {self.id(client)} has sent malformed JSON data.', 2)
					continue

		# disconnecting
		except websockets.ConnectionClosed:
			self.log(f'{self.id(client)} has disconnected', 1)
		except websockets.WebSocketProtocolError:
			self.log(f'ERROR! {self.id(client)} broke protocol.', 2)
		except websockets.PayloadTooBig:
			self.log(f'ERROR! {self.id(client)} has sent a payload that is too large to process.', 2)
		except Exception as e:
			# requires attention even from the researcher, therefor this error has log_level=1
			self.log(f'ERROR! {self.id(client)} has caused an unknown exception: {e}.', 1)
		finally:
			try:
				self.disconnect(client)
			except Exception as e:
				self.log(f'{self.id(client)} failed to disconnect safely: {e}.', 2)

	def connect(self, client, data={}):
		"""Create user data when connection is established."""
		if client in self.connections:
			return
		default = {
			"type": "unknown",
			"connected": self.now(),
			"updated": self.now(),
			"ip": (client.remote_address[0] if client.remote_address else "0.0.0.0"),
		}
		self.connections[client] = {**default, **data}

	def disconnect(self, client):
		"""Remove user data when connection is closed."""
		if client in self.connections:
			del self.connections[client]

	def update(self, client):
		"""Update timestamp of last received message from client"""
		if client in self.connections:
			self.connections[client]["updated"] = self.now()

	def terminate(self):
		"""Terminate experiment and allow a new one"""
		self.environment = {}

	# async
	async def hook(self, function, delay):
		if "trigger" not in self.environment:
			self.environment["trigger"] = {}
		stamp = self.now() + delay
		while stamp in self.environment["trigger"]:
			stamp += 1
		self.environment["trigger"][stamp] = function

	async def play_bot(self, client):
		if "game" not in self.environment:
			self.log("ERROR! Game environment is not set, can not make move.")
			return
		if await self.environment["game"].play_bot():
			await self.score_game(client, "play_subject")
		else:
			self.save_game("play_bot", self.environment["game"].move_bot)
			await self.send(client, "game", {"move": True})

	async def play_subject(self, client, move):
		if "game" not in self.environment:
			self.log("ERROR! Game environment is not set, can not make move.")
			return
		if self.environment["game"].play_subject(move):
			await self.score_game(client, "play_bot")
		else:
			self.save_game("play_subject", move)

	async def score_game(self, client, ignore_save=""):
		results = self.environment["game"].score_game()
		for key in results:
			if key != ignore_save:
				self.save_game(key, results[key])
		await self.send(client, "game", results)
		# new move
		if results["rounds_left"] > 0:
			await self.play_bot(client)
		else:
			await self.hook(lambda: self.send(client, "game", {"end": True}), 2.)

	async def game_over(self):
		self.environment["game_over"] = True
		total = self.environment["game"].score_subject_all
		self.save_game("score_subject_all", total)
		await self.broadcast({"search": -1, "exit": True})

	async def tic(self):
		"""Generate tics in background to send information async."""
		current = self.now()
		while True:
			if current + self.frequency < self.now():
				current = self.now()
				try:
					if "trigger" in self.environment and self.environment["trigger"]:
						for stamp in self.environment["trigger"]:
							if stamp <= current:
								if self.environment["trigger"][stamp] is not None:
									await self.environment["trigger"][stamp]()
									self.environment["trigger"][stamp] = None
						# delete None
						self.environment["trigger"] = {k: v for k, v in self.environment["trigger"].items() if v is not None}
				except Exception as et:
					self.log(f'ERROR! Tic generated exception: {et}.')
			await asyncio.sleep(self.frequency / 10.0)

	# send payload
	async def send(self, client, type_, data):
		"""Create payload and send it to client"""
		if type_ not in ("info", "game", "error"):
			self.log(f'ERROR! Unknown payload type "{type_}".', 2)
			return
		if not isinstance(data, dict):
			self.log(f'ERROR! Payload data must be dict.', 2)
			return
		payload = {"type": type_, "data": data}
		await self.post(client, payload)

	async def broadcast(self, data):
		"""Send data to all clients with their "type" set"""
		if not isinstance(data, dict):
			self.log(f'ERROR! Payload data must be dict.', 2)
			return
		for client in self.connections:
			if self.connections[client]["type"] in ("info", "game"):
				payload = {"type": self.connections[client]["type"], "data": data}
				await self.post(client, payload)

	async def post(self, client, payload):
		"""Force send any message to a single client through websocket connection."""
		try:
			if client in self.connections:
				payload = json.dumps(payload)
				await client.send(payload)
		except TypeError as ej:
			self.log(f'ERROR! Unable to dump payload: {ej}.', 2)
			print(payload)
			raise ej
		except Exception as ep:
			self.log(f"ERROR! Unable to send payload to {self.id(client)}: {ep}.", 2)

	@staticmethod
	def _for_csv(value):
		return str(value).strip().replace(';', ',')

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

	@staticmethod
	def now(f=""):
		"""Return current timestamp with microseconds, format it as string if "f" is set."""
		if not f:
			return datetime.timestamp(datetime.now())
		else:
			return datetime.now().strftime(f)


if __name__ == "__main__":
	import argparse

	parser = argparse.ArgumentParser("Run server from command line")
	parser.add_argument("--ip", help="IP of server, defaults to current IP", type=str, default="", required=False)
	parser.add_argument("--port", help="Port of server, defaults to 42069", type=int, default=42069, required=False)
	parser.add_argument("--log_level", help="Log level for debugging", type=int, default=3, required=False)
	parser.add_argument("--log_folder", help="Folder for logs", type=str, default="../experiments", required=False)
	parser.add_argument("--log_info", help="File name of Info logs in 'log_folder'", type=str, default=f"{Server.now('%Y-%m-%d')}_info.csv", required=False)
	parser.add_argument("--log_game", help="File name of Info logs in 'log_folder'", type=str, default=f"{Server.now('%Y-%m-%d')}_game.csv", required=False)
	args = parser.parse_args()
	server = Server(ip=args.ip, port=args.port, log_level=args.log_level, log_folder=args.log_folder, log_info=args.log_info, log_game=args.log_game)
	server.run()

