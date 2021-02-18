from flask import Flask, redirect, render_template, url_for, session, request
from flask_socketio import SocketIO, send, emit, join_room, leave_room, close_room, rooms, disconnect
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField
from wtforms.validators import InputRequired, Email, Length
from werkzeug.security import generate_password_hash, check_password_hash
from forms import *
from user import *
from sentences import *

# dictionary to keep track of all the rooms
# name          number of users active     room is playing    usernames connected to not allow the refresh
# "room name": [0,                         False,             ["",""]]
r = {}
u = {}

@login_manager.user_loader
def load_user(user_id):
	return User.query.get(int(user_id))

@app.route("/")
def home():
	top = User.query.order_by(User.average.desc()).limit(3)
	if current_user.is_authenticated:
		return render_template("home.html", username=current_user.username, f=top[0].username + ", " + str(int(top[0].average)) + " WPM", s=top[1].username + ", " + str(int(top[1].average)) + " WPM", t=top[2].username + ", " + str(int(top[2].average)) + " WPM")
	return render_template("home.html", f=top[0].username + ", " + str(int(top[0].average)) + " WPM" , s=top[1].username + ", " + str(int(top[1].average)) + " WPM", t=top[2].username + ", " + str(int(top[2].average)) + " WPM")

@app.route('/about')
def about():
	return render_template("about.html", username=current_user.username)

@socketio.on('connect')
@login_required
def connect():
	u[current_user.username] = request.sid
	emit("listener", 'connected')

@socketio.on('join')
def on_join(data):
	global r

	room_name = data['room name']
	username = data['username']
	practice = data['practice']

	if practice:
		socketio.emit("practice", get_sentence("r"), room=request.sid)
		return

	# if the room exists
	if room_name in r:
		# running through all active users
		for x in r[room_name][2]:
			# if user is already active then not letting him join again
			if current_user.username == x:
				join_room(room_name)
				return

	while(True):
	
		# if the room exists
		if room_name in r:
			# if the room is waiting for players
			if r[room_name][1] == False:

				# adding user to room
				r[room_name][0] = r[room_name][0] + 1
				r[room_name][2].append(str(current_user.username))
				join_room(room_name)
				break
			else:
				# if the room is full and someone wants to join
				# creating a new room with increasing counter name
				if int(room_name[2:4]) + 1 < 10:
					room_name = room_name[0:2] + "0" + str(int(room_name[2:4]) + 1)
				else:
					room_name = room_name[0:2] + str(int(room_name[2:4]) + 1)

				# adding user to room
				if room_name not in r:
					r[room_name] = [1, False, list()]
					r[room_name][2].append(str(current_user.username))
					join_room(room_name)
					break
		else:
			# init room with one player
			r[room_name] = [1, False, list()]
			r[room_name][2].append(str(current_user.username))
			join_room(room_name)
			break
	# if the room is full then the game starts
	if r[room_name][0] == int(room_name[0]):
		r[room_name][1] = True
		join_room(room_name)

		# sending all users in room
		usernames = ""
		for x in range(len(r[room_name][2])):
			usernames += r[room_name][2][x] + "|"

		socketio.emit("listener", usernames + "join" + get_sentence(room_name[1]), room=room_name)

@app.route("/waiting/<ID>")
@login_required
def waiting(ID):

	if ID == "add later":
		return "Not finished yet for upload!"

	return render_template("game.html", ID=ID, username=current_user.username)

@socketio.on('get room')
def get_room(data):
	global r

	room = data['room name']
	username = data['username']

	# making sure the player doesent enter twice
	if request.sid != u[username] and current_user.username not in r[roomName][2]:
		return

	while(True):
		if room in r:
			if r[room][1] == False:
				break
			else:
				if int(room[2:4]) + 1 < 10:
					room = room[0:2] + "0" + str(int(room[2:4]) + 1)
				else:
					room = room[0:2] + str(int(room[2:4]) + 1)
				if room not in r:
					break
		else:
			break
	
	socketio.emit("room asign", room, room=request.sid)

# this function sends the place of each racer to his room
@socketio.on('selector')
def connect(data):
	room_name = data['room name']
	username = data['username']

	socketio.emit("selector sender", {'username':username}, room=room_name)

@socketio.on('exit')
def exit(data):

	roomName = data['room name']
	leave_room(roomName)

@socketio.on('finish')
def finish(data):

	wordsPerMinute = data['wpm']
	roomName = data['room name']

	# decreasing the amount of players in room
	r[roomName][0] = r[roomName][0] - 1
	if r[roomName][0] == 0:
		close_room(roomName)
		del r[roomName]

	# adding score to player
	newW = ""
	if current_user.wpm == "":
		newW = str(int(wordsPerMinute))
	else:
		newW = current_user.wpm + " " + str(int(wordsPerMinute))

	# calculating new average and adding one to total races
	numList = list(map(int, newW.split()))
	avg = sum(numList)/len(numList)
	newT = int(current_user.total) + 1

	# adding new values to user
	user = User.query.filter_by(username=current_user.username).first()
	user.total = newT
	user.wpm = newW
	user.average = avg
	db.session.commit()

@app.route("/profile")
@login_required
def profile():
	newwpm = current_user.wpm
	if current_user.wpm == None:
		newwpm = ""
	newtotal = current_user.total
	if current_user.total == None:
		newtotal = ""
	newaverage = current_user.average
	if current_user.average == None:
		newaverage = 0
	return render_template('profile.html', username=current_user.username, wpm=newwpm, total=newtotal, avg=int(newaverage))

@app.route('/login', methods=['GET', 'POST'])
def login():
	form = LoginForm()

	if form.validate_on_submit():
		user = User.query.filter_by(username=form.username.data).first()
		if user:
			if check_password_hash(user.password, form.password.data):
				login_user(user, remember=form.remember.data)
				return render_template('login.html', form=form, error="pass")
		
		return render_template('login.html', form=form, error="error")

	return render_template('login.html', form=form)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
	form = RegisterForm()

	if form.validate_on_submit():

		if User.query.filter_by(email=form.email.data).first() or User.query.filter_by(username=form.username.data).first():
			return render_template('signup.html', form=form, error="error")

		hashed_password = generate_password_hash(form.password.data, method='sha256')
		new_user = User(username=form.username.data, email=form.email.data, password=hashed_password, wpm="", total=0)
		db.session.add(new_user)
		db.session.commit()
		login_user(new_user)
		db.session.commit()

		return render_template('signup.html', form=form, error="pass")

	return render_template('signup.html', form=form)

@app.route('/logout')
@login_required
def logout():
	logout_user()
	return redirect(url_for('home'))

if __name__ == "__main__":
	socketio.run(app, debug=True)