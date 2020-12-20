from flask import Flask, redirect, render_template, url_for, session, request
from flask_socketio import SocketIO, send, emit, join_room, leave_room, close_room, rooms, disconnect
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField
from wtforms.validators import InputRequired, Email, Length
from werkzeug.security import generate_password_hash, check_password_hash
import random


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = "gnli^sd*bfl!ids#dbfl@dsf"
socketio = SocketIO(app)
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# dictionary to keep track of all the rooms
# name          number of users active     room is playing    usernames connected to not allow the refresh
# "room name": [0,                         False,             ["",""]]
r = {}
u = {}

class LoginForm(FlaskForm):
	username = StringField('username', validators=[InputRequired(), Length(min=4, max=15)])
	password = PasswordField('password', validators=[InputRequired(), Length(min=8, max=80)])
	remember = BooleanField('remember me')

class RegisterForm(FlaskForm):
	email = StringField('email', validators=[InputRequired(), Email(message='invalid email'), Length(max=50)])
	username = StringField('username', validators=[InputRequired(), Length(min=4, max=15)])
	password = PasswordField('password', validators=[InputRequired(), Length(min=8, max=80)])

class User(UserMixin, db.Model):
	id = db.Column(db.Integer, primary_key=True)
	username = db.Column(db.String(15), unique=True)
	email = db.Column(db.String(50), unique=True)
	password = db.Column(db.String(80))
	wpm = db.Column(db.String(80))
	total = db.Column(db.Integer)
	average = db.Column(db.Integer)


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
	return redirect(url_for('home'))

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
	return render_template('profile.html', username=current_user.username, wpm=current_user.wpm, total=current_user.total, avg=int(current_user.average))

@app.route('/login', methods=['GET', 'POST'])
def login():
	form = LoginForm()

	if form.validate_on_submit():
		user = User.query.filter_by(username=form.username.data).first()
		if user:
			if check_password_hash(user.password, form.password.data):
				login_user(user, remember=form.remember.data)
				return redirect(url_for('home'))

	return render_template('login.html', form=form)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
	form = RegisterForm()

	if form.validate_on_submit():

		hashed_password = generate_password_hash(form.password.data, method='sha256')
		new_user = User(username=form.username.data, email=form.email.data, password=hashed_password, wpm="", total=0)
		db.session.add(new_user)
		db.session.commit()
		login_user(new_user)
		db.session.commit()

		return redirect(url_for('home'))

	return render_template('signup.html', form=form)

@app.route('/logout')
@login_required
def logout():
	logout_user()
	return redirect(url_for('home'))

def get_sentence(mode):

	n = random.randint(0, 15)
	if mode == 'z':

		choices = {
			0: "Sometimes you have to just give up and win by cheating",
			1: "All you need to do is pick up the pen and begin",
			2: "Today arrived with a crash of my car through the garage door",
			3: "As he entered the church he could hear the soft voice of someone whispering into a cell phone",
			4: "He appeared to be confusingly perplexed",
			5: "You have every right to be angry, but that doesn't give you the right to be mean",
			6: "When nobody is around, the trees gossip about the people who have walked under them",
			7: "The random sentence generator generated a random sentence about a random sentence",
			8: "You're good at English when you know the difference between a man eating chicken and a man-eating chicken",
			9: "The sign said there was road work ahead so he decided to speed up",
			10: "The secret ingredient to his wonderful life was crime",
			11: "I can practically see your face and another revolutionary falls from grace",
			12: "I've found it. I've found it. I have found a reagent which is precipitated by hemoglobin, and by nothing else.",
			13: "The lyrics of the song sounded like fingernails on a chalkboard",
			14: "Whether this tale be true or false, none can tell, for none were there to witness it themselves",
			15: "The best key lime pie is still up for debate"
		}
		return choices.get(n)

	elif mode == 'r':

		choices = {
			0: "As he crossed toward the pharmacy at the corner he involuntarily turned his head because of a burst of light that had ricocheted from his temple",
			1: "On offering to help the blind man, the man who then stole his car, had not, at that precise moment, had any evil intention, quite the contrary",
			2: "My very photogenic mother died in a freak accident (picnic, lightning) when I was three, and, save for a pocket of warmth in the darkest past",
			3: "The French are certainly misunderstood: but whether the fault is theirs, in not sufficiently explaining themselves, or speaking with that exact limitation",
			4: "All I know is that I stood spellbound in his high-ceilinged studio room, with its north-facing windows in front of the heavy mahogany bureau at which Michael said he no longer worked because the room was so cold, even in midsummer",
			5: "Mac knew the score even if Aunt Ella didn't. Shot through the left lung and that was that, as they say. Believe it was that night. She buried him the next mornin'",
			6: "She was a genius of sadness, immersing herself in it, separating its numerous strands, appreciating its subtle nuances. She was a prism through which sadness could be divided into its infinite spectrum",
			7: "I learned to write because I am one of those people who somehow cannot manage the common communications of smiles and gestures, but must use words to get across things that other people would never need to say",
			8: "Whether they use the title or not, many lyrics have evocative first lines that grab the listener's attention. Often thinking of a good first line can make the rest of the lyric flow",
			9: "I am assured by our merchants, that a boy or a girl before twelve years old, is no salable commodity, and even when they come to this age, they will not yield above three pounds, or three pounds and half a crown at most, on the exchange",
			10: "Heraclitus: \"They vainly purify themselves with blood when they are defiled with it, which is like someone who has stepped into mud using mud to wash himself. Anyone who observed a person doing this would think him mad\"",
			11: "I've been up. I've been down. I've been kicked down to the ground by the voices in my head. But you said, \"Life gets tough when you get older. That's why I raised a soldier. Fight this battle to the end\"",
			12: "Consciousness, complex and subtle, can be impaired or ended by a mere stepping-up or dimming-down of any one sense intensity, which is the procedure in hypnosis",
			13: "It wasn't something that I thought about, but I knew that you were absolute in doubt. I just really wanna talk to you again, that's how I know that I'ma haunt you in the end. It wasn't something 'til you brought it up, I knew that you were tryna make it out",
			14: "Dictionaries are designed to appear authoritative. They're thick, sturdy, and precise, with pages of explanatory material and complex notational schemes that create an aura of august finality",
			15: "It doesn't matter what I say, so long as I sing with inflection that makes you feel I'll convey some inner truth or vast reflection. But I've said nothing so far"
		}
		return choices.get(n)

	elif mode == 'c':
		n = random.randint(0, 4)

		if n == 0:
			return "In the classical theory of gravity, which is based on real space-time, the universe can either have existed for an infinite time or else it had a beginning at a singularity at some finite time in the past, the latter possibility of which, in fact, the singularity theorems indicate, although the quantum theory of gravity, on the other hand, suggests a third possibility in which it is possible for space-time to be finite in extent and yet to have no singularities that formed a boundary or edge because one is using Euclidean space-times, in which the time direction is on the same footing as directions in space."
		if n == 1:
			return "A computer memory is basically some device that can be in either one of two states, an example of which is a superconducting loop of wire where, if there is an electric current flowing in the loop, it will continue to flow because there is no resistance while, on the other hand, if there is no current, the loop will continue without a current two states of memory that can be labelled one and zero."
		if n == 2:
			return "Before Darwin, American scientists typically accepted the biblically orthodox view that God directly created every type of species, with each thereafter reproducing true to form. In contrast, Darwin proposed that the interaction of several biological mechanisms naturally caused some descendants of older species gradually to evolve over countless generations into the ancestors of new species."
		if n == 3:
			return "After a series of near misses and the imposition of lesser restrictions in several places, in 1925, Tennesee became the first state to outlaw evolutionary teaching. William Jennings Bryan, an attorney as well as a politician, took his crusade to the courtroom when the American Civil Liberties Union (ACLU) instigated a judicial challenge to the Tennessee statute. In the ensuing trial of science teacher John Scopes, Bryan successfully sparred with Clarence Darrow, who represented the defendant, over science, religion, and academic freedom."

		return "Typically, legislators showed greater responsiveness to popular opinion than judges, but even the courts operated within parameters established by popular sentiment, never allowing public science to deviate too far from popular opinion, a reconciliation in which both legislators and judges avoided ruling on the scientific merits of evolution or creation, which they typically viewed as being beyond the scope of their competence and based their decisions on non-scientific factors, such as the religious nature of creationism or the social ramifications of evolutionary teaching, inevitably influenced by scientific opinion only to the extent that opinion was distilled through popular opinion either directly in the acceptance of a theory of origins or indirectly in the cultural respect afforded science generally."	

if __name__ == "__main__":
	socketio.run(app, debug=True)