#!/usr/bin/env python
# -*- coding: utf-8 -*-

import numpy as np
import asyncio


class Game:

	F_NICKS = [f'Űr-Tibi_{i}' for i in range(20)]  # TODO: add list of names
	M_NICKS = [f'Ős Klára {i}' for i in range(20)]  # TODO: ad list of names
	COLORS = ["red", "green"]
	STRATEGIES = ["tft", "grim", "pavlov", "susp_tft", "hard_majo", "per_dc", "all_c", "all_d", "random"]
	STAGES = ["temple", "jail", "lab", "home", "forest", "station", "beach", "junkyard", "tron"]
	OPPONENTS = ["mirror", "unknown", "doctor", "pirate", "robot", "king", "old", "young", "foreigner"]
	DUPLICATE_FROM = 2
	DUPLICATE_TO = 4
	NUMBER_OF_GAMES = 5
	WAIT_BETWEEN_GAMES = 1.5
	WAIT_AT_MATCH_START = 2.5

	def __init__(self, seed):
		self.seed = seed
		self.color = ""

		self.current = -1

		self.bots = []
		self.score_subject_current = 0
		self.score_subject_all = 0
		self.score_bot_current = 0
		self.score_bot_all = 0
		self.move_subject = None
		self.move_bot = None

	def generate(self, avatar, gender):
		"""Generate environment and opponents based on seed"""
		np.random.seed(self.seed)
		self.current = 7  # -1
		self.score_subject_current = 0
		self.score_subject_all = 0
		self.score_bot_current = 0
		self.score_bot_all = 0
		self.color = np.random.choice(self.COLORS)

		self.bots = []
		self.move_subject = None
		self.move_bot = None

		opponents = np.random.permutation(self.OPPONENTS)
		genders = np.random.choice([False, True], size=9)
		# in case the same avatar with same gender is among the opponents,
		# (besides the mirror opponent), flip its gender
		if avatar in opponents:
			genders[np.where(opponents == avatar)[0]] = not gender
		# change mirror opponent to the same as player's avatar & gender
		mirror = np.where(opponents == "mirror")
		opponents[mirror] = avatar
		genders[mirror] = gender

		# generate names based on opponents' gender
		f_nicks = np.random.permutation(self.F_NICKS)
		m_nicks = np.random.permutation(self.M_NICKS)
		nicks = []
		for i, g in enumerate(genders):
			if g:
				nicks.append(f_nicks[i])
			else:
				nicks.append(m_nicks[i])

		# create a copy of a certain opponent for rematch
		strategies = self._rematch(np.random.permutation(self.STRATEGIES))
		stages = self._rematch(np.random.permutation(self.STAGES))
		opponents = self._rematch(opponents)
		genders = self._rematch(genders)
		nicks = self._rematch(nicks)
		rounds = np.ones(len(strategies)) * self.NUMBER_OF_GAMES
		# create bots based on generated data
		for nick, opponent, gender, stage, strategy, round \
				in zip(nicks, opponents, genders, stages, strategies, rounds):
			self.bots.append(Bot(nick, opponent, gender, stage, strategy, round))
		return self

	def _rematch(self, data):
		"""Include the same opponent and environment twice"""
		return np.concatenate((data[:self.DUPLICATE_TO],
							   [data[self.DUPLICATE_FROM]],
							   data[self.DUPLICATE_TO:]))

	def search(self):
		if not self.bots:
			raise ValueError("Environment is not yet generated")
		self.move_subject = None
		self.move_bot = None
		self.score_subject_current = 0
		self.score_bot_current = 0
		self.current += 1
		if self.current >= len(self.bots):
			return -1
		return self.current

	def get_environment(self):
		if not self.bots:
			raise ValueError("Environment is not yet generated")
		if self.current >= len(self.bots):
			raise ValueError("Game is already over, no more environments are available")
		env = self.bots[self.current].get_environment()
		env["wait"] = self.WAIT_AT_MATCH_START  # wait at match start
		env["color"] = self.color  # color is same for all bots
		# resend values in case it was a reconnect
		env["search"] = self.current
		env["score_subject"] = self.score_subject_current
		env["score_bot"] = self.score_bot_current
		return env

	def play_subject(self, move):
		if not self.bots:
			raise ValueError("Environment is not yet generated")
		self.move_subject = move
		return self.move_bot is not None

	async def play_bot(self):
		if not self.bots:
			raise ValueError("Environment is not yet generated")
		await asyncio.sleep(np.random.rand() * 4 + self.WAIT_BETWEEN_GAMES)
		self.move_bot = self.bots[self.current].move()
		return self.move_subject is not None

	def score_game(self):
		if not self.bots:
			raise ValueError("Environment is not yet generated")
		if self.move_bot is None or self.move_subject is None:
			raise ValueError("Both subject and bot has to make a move")
		rounds_left, gain_bot, gain_subject = self.bots[self.current].play(self.move_bot, self.move_subject)

		tmp_bot, tmp_subject = self.move_bot, self.move_subject
		self.move_bot = None
		self.move_subject = None

		self.score_bot_current += gain_bot
		self.score_bot_all += gain_bot
		self.score_subject_current += gain_subject
		self.score_subject_all += gain_subject

		return {
			"rounds_left": int(rounds_left),
			"gain_bot": int(gain_bot),
			"gain_subject": int(gain_subject),
			"score_bot": int(self.score_bot_current),
			"score_subject": int(self.score_subject_current),
			"move_bot": bool(tmp_bot),
			"move_subject": bool(tmp_subject)
		}

	def is_playing(self):
		if not self.bots:
			return False
		if self.current < 0:
			return False
		if self.current >= len(self.bots):
			return False
		if not self.bots[self.current].round:
			return False
		return True

	def readable(self):
    	# readable format
		return [bot.get_environment() for bot in self.bots]


class Bot:

	def __init__(self, nick, avatar, gender, stage, strategy, round):
		self.nick = nick
		self.avatar = avatar
		self.gender = gender
		self.stage = stage
		self.strategy = strategy
		self.round = int(round)
		self.loading = np.random.rand() * 2.

		self.history_bot = []
		self.history_subject = []
		# print(strategy, round)

	def get_environment(self):
		return {
			"nick": str(self.nick),
			"avatar": str(self.avatar),
			"gender": bool(self.gender),
			"stage": str(self.stage),
			"loading": float(self.loading),
		}

	def reset(self):
		self.history_bot = []
		self.history_subject = []

	def play(self, bot_move, subject_move):
		b_p, s_p = self.score(bot_move, subject_move)
		self.round -= 1
		self.history_bot.append(bot_move)
		self.history_subject.append(subject_move)
		return self.round, b_p, s_p

	def move(self):
		if self.strategy == "all_c":
			"""nice, deterministic"""
			return True
		elif self.strategy == "all_d":
			"""deterministic"""
			return False
		elif self.strategy == "per_dc":  # CyclerDC / Alternating
			"""deterministic"""
			return bool(len(self.history_bot) % 2)
		elif self.strategy == "tft":
			"""nice, forgiving, retaliate"""
			return True if not self.history_subject else self.history_subject[-1]
		elif self.strategy == "grim":  # Grim trigger / Grudger / Spiteful
			"""nice, retaliate"""
			return True if not self.history_subject else (False not in self.history_subject)
		elif self.strategy == "pavlov":  # Simpleton / Win stay, lose switch
			"""nice, forgiving, retaliate, envious"""
			if not self.history_bot or not self.history_subject:
				return True
			return self.history_bot[-1] if self.history_subject[-1] else not self.history_bot[-1]
		elif self.strategy == "susp_tft":  # Mistrust
			"""forgiving, retaliate"""
			return False if not self.history_subject else self.history_subject[-1]
		elif self.strategy == "hard_majo":  # Hard Go By Majority
			"""nice, forgiving, retaliate"""
			return 2 * np.sum(self.history_subject) > len(self.history_subject)
		elif self.strategy == "random":
			"""stohastic"""
			return np.random.choice([True, False])
		else:
			raise ValueError("Unknown strategy.")

	@staticmethod
	def score(p1, p2):
		if p1:
			if p2:
				return 3, 3
			else:
				return 0, 5
		else:
			if p2:
				return 5, 0
			else:
				return 1, 1


if __name__ == "__main__":
	game = Game(1)
	game.generate("robot", True)
	for i in range(20):
		game.play(np.random.choice([True, False]))

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