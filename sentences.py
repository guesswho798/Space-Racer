import random

def get_sentence(mode):

	f = open("sentences.txt", "r")
	s = f.readlines()

	options = list()

	if mode == "z":
		b = 0
		for sentence in s:
			if sentence == "++++++\n":
				b = b + 1
			elif b == 0:
				options.append(sentence)
	elif mode == "r":
		b = 0
		for sentence in s:
			if sentence == "++++++\n":
				b = b + 1
			elif b == 1:
				options.append(sentence)
	elif mode == "c":
		b = 0
		for sentence in s:
			if sentence == "++++++\n":
				b = b + 1
			elif b == 2:
				options.append(sentence)



	n = random.randint(0, len(options)-1)
	return options[n][0:len(options[n])-1]