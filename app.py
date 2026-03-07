from flask import Flask, session, render_template, redirect, url_for, request
import json
import hashlib

app = Flask(__name__)
app.secret_key = 'dtfyghubjn2345678dfgh'

def create_or_retrieve():
    if 'user_state' not in session:
        init_user_state()
    return session['user_state']

def init_user_state():
    session['user_state'] = {
        'login': False,
        'user': ''
    }
    session.modified = True  

@app.route('/', methods = ["GET"])
def default_page():
    facts = [False, False, False]
    stuff = ["success", "logout", "auth_error"]
    for i in range(3):
        fact = request.args.get(stuff[i])
        if fact is not None:
            facts[i] = True
    return render_template('index.html', facts=facts)

@app.route('/login', methods = ["POST"])
def login():
    user_state = create_or_retrieve()
    uname = request.form.get("uname")
    pword = request.form.get("pword")
    pword += "saltyspitoon"
    b_pword  = pword.encode('utf-8')
    sha_obj = hashlib.sha256()
    sha_obj.update(b_pword)
    hashed_val = sha_obj.hexdigest()
    with open('credentials.json', 'r') as file:
        credentials = json.load(file)
    print(hashed_val)
    if uname in credentials and credentials[uname] == hashed_val:
        user_state['login'] = True
        user_state['user'] = uname
        session['user_state'] = user_state
        return redirect(url_for('home'))
    else:
        return redirect('/?success=false')
    
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/?logout=true')

@app.route('/home')
def home():
    user_state = create_or_retrieve()
    if user_state['login'] is True:
        return render_template('home.html')
    else:
        return redirect('/?auth_error=true')

@app.route('/create')
def create():
    user_state = create_or_retrieve()
    if user_state['login'] is True:
        return render_template('create.html')
    else:
        return redirect('/?auth_error=true')

@app.route('/simulate')
def simulate():
    user_state = create_or_retrieve()
    if user_state['login'] is True:
        return render_template('simulate.html')
    else:
        return redirect('/?auth_error=true')

@app.route('/about')
def about():
    user_state = create_or_retrieve()
    if user_state['login'] is True:
        return render_template('about.html')
    else:
        return redirect('/?auth_error=true')
    
if __name__ == '__main__':
  app.run(host='0.0.0.0', port=80, debug=True)