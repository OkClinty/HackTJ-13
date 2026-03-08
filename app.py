from flask import Flask, session, render_template, redirect, url_for, request, jsonify
import json
import hashlib

from dotheshit import solve_assignment_with_qaoa

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

def parse_edges_text(edges_text):
    edges = []
    for line_number, raw_line in enumerate(edges_text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith('#'):
            continue
        tokens = line.split()
        if len(tokens) < 2:
            raise ValueError(f"Line {line_number}: expected at least 2 values (from to [weight]).")
        edge = {
            'from': tokens[0],
            'to': tokens[1],
        }
        if len(tokens) > 2:
            edge['weight'] = tokens[2]
        edges.append(edge)

    if not edges:
        raise ValueError('No valid edges found in input.')
    return edges


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

@app.route('/api/process-edges', methods=["POST"])
def process_edges():
    user_state = create_or_retrieve()
    if user_state['login'] is not True:
        return jsonify({'ok': False, 'error': 'Unauthorized'}), 401

    payload = request.get_json(silent=True) or {}
    edges_text = payload.get('edges_text', '')

    try:
        edges = parse_edges_text(edges_text)
        fixed = fixedges(edges)
        result = fixed
    except ValueError as exc:
        return jsonify({'ok': False, 'error': str(exc)}), 400

    return jsonify({'ok': True, 'result': fixed})

def calldotheshit(fixededges):
    capacities = {
    }

    for edge in fixededges:
        node1 = edge[0]
        node2 = edge[1]
        if node1 not in capacities:
            capacities[node1] = 0
        if node2 not in capacities:
            capacities[node2] = 0
        capacities[node1] += 1
        capacities[node2] += 1

    result = solve_assignment_with_qaoa(
        edges=fixededges,
        capacities=capacities,
        num_layers=3,
        num_shots=1000,
        max_iterations=60,
        task_penalty=30.0,
        capacity_penalty=30.0,
        show_circuit=False,
        plot_trace=True,
    )

    return jsonify({'ok': True, 'result': result})

def fixedges(edges):
    fixed = []
    for edge in edges:
        node1 = edge['from']
        node2 = edge['to']
        weight = float(edge.get('weight', 1.0))
        fixed.append((node1, node2, weight))
    return fixed


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