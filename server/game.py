#!/usr/bin/env python
# -*- coding: utf-8 -*-

import numpy as np


class Game:

	F_NAMES = -1 * np.arange(20) - 1
	M_NAMES = np.arange(20) + 1
	STRATEGIES = ["tft", "grim", "pavlov", "susp_tft", "hard_majo", "per_dc", "all_c", "all_d", "random"]
	STAGES = ["temple", "jail", "lab", "home", "forest", "station", "beach", "junkyard", "tron"]
	OPPONENTS = ["mirror", "unknown", "doctor", "pirate", "robot", "king", "old", "young", "foreigner"]
	DUPLICATE_FROM = 2
	DUPLICATE_TO = 4
	NUMBER_OF_GAMES = 5

	def __init__(self, seed):
		self.seed = seed
		self.current = 0
		self.moves_subject = []
		self.moves_opponent = []

		self.strategies = []
		self.stages = []
		self.opponents = []
		self.genders = []
		self.names = []

	def generate(self, avatar, gender):
		"""Generate environment and opponents based on seed"""
		np.random.seed(self.seed)

		self.opponents = np.random.permutation(self.OPPONENTS)
		self.genders = np.random.choice([False, True], size=9)
		# in case the same avatar with same gender is among the opponents,
		# (besides the mirror opponent), flip its gender
		if avatar in self.opponents:
			self.genders[np.where(self.opponents == avatar)[0]] = not gender
		# change mirror opponent to the same as player's avatar & gender
		mirror = np.where(self.opponents == "mirror")
		self.opponents[mirror] = avatar
		self.genders[mirror] = gender

		# generate names based on opponents' gender
		f_names = np.random.permutation(self.F_NAMES)
		m_names = np.random.permutation(self.M_NAMES)
		self.names = []
		for i, g in enumerate(self.genders):
			if g:
				self.names.append(f_names[i])
			else:
				self.names.append(m_names[i])

		# rematch with a certain opponent again
		self.strategies = self._replay(np.random.permutation(self.STRATEGIES))
		self.stages = self._replay(np.random.permutation(self.STAGES))
		self.opponents = self._replay(self.opponents)
		self.genders = self._replay(self.genders)
		self.names = self._replay(self.names)

		return self

	def _replay(self, data):
		"""Include the same opponent and environment twice"""
		return np.concatenate((data[:self.DUPLICATE_TO],
							   [data[self.DUPLICATE_FROM]],
							   data[self.DUPLICATE_TO:]))

	@staticmethod
	def ai(strategy="random", moves_user=[], moves_opponent=[]):
		if strategy == "tft":
			if not moves_user:
				return True
			else:
				return moves_user[-1]
		elif strategy == "grim":
			if not moves_user:
				return True
			elif False in moves_user:
				return False
			else:
				return True
		elif strategy == "pavlov":
			if not moves_user:
				return True
			if moves_user[-1] != moves_opponent[-1]:
				return not moves_opponent[-1]
			else:
				return moves_opponent[-1]
		elif strategy == "susp_tft":
			if not moves_user:
				return False
			else:
				return moves_user[-1]
		elif strategy == "hard_majo":
			coops = np.sum(moves_user)
			defects = len(moves_user) - coops
			return (coops > defects)
		elif strategy == "per_dc":
			return bool(len(moves_user) % 2)
		elif strategy == "all_c":
			return True
		elif strategy == "all_d":
			return False
		elif strategy == "random":
			return np.random.choice([True, False])
		else:
			raise ValueError("Unknown strategy.")

	@staticmethod
	def score(p1, p2):
		if p1:
			if p2:
				return 2, 2
			else:
				return -1, 3
		else:
			if p2:
				return 3, -1
			else:
				return 0, 0


if __name__ == "__main__":
	game = Game(1)
	#game.generate("robot", True)
	'''
	for player in game.STRATEGIES[:-1]:
		score = 0
		print(player, ":")
		for opponent in game.STRATEGIES[:-1]:
			move_player = []
			move_opponent = []
			print(opponent, end=" ")
			for play in range(5):
				p1 = game.ai(player, move_opponent, move_player)
				p2 = game.ai(opponent, move_player, move_opponent)
				move_player.append(p1)
				move_opponent.append(p2)
				print(p1, p2, end=", ")
				score += game.score(p1, p2)[0]
			print()
		print(player, score)
		print()
	'''
	'''
	score = 0
	for i in range(10000):
		score += game.score(np.random.choice([True, False]), np.random.choice([False, True]))[0]
	print(score / 10000)
	'''
