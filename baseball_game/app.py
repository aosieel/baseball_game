import json
import os
from flask import Flask, render_template, request, redirect, url_for, jsonify
import time
from threading import Thread
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = 'supersecretkey'

def load_rooms():
    try:
        with open('rooms.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_rooms(rooms):
    with open('rooms.json', 'w') as f:
        json.dump(rooms, f, indent=4)

def cleanup_rooms():
    while True:
        time.sleep(60)  # 매 1분마다 체크
        rooms = load_rooms()
        current_time = datetime.now()
        updated_rooms = {}
        for room_name, data in rooms.items():
            end_time_str = data.get('end_time')
            created_time_str = data.get('created_time')
            if end_time_str:
                end_time = datetime.strptime(end_time_str, '%Y-%m-%d %H:%M:%S')
                if (current_time - end_time) < timedelta(minutes=3):
                    updated_rooms[room_name] = data
            elif created_time_str:
                created_time = datetime.strptime(created_time_str, '%Y-%m-%d %H:%M:%S')
                if (current_time - created_time) < timedelta(minutes=60):  # 60분 이상 된 방은 삭제
                    updated_rooms[room_name] = data
        if len(rooms) != len(updated_rooms):
            save_rooms(updated_rooms)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/create_room', methods=['POST'])
def create_room():
    room_name = request.form['room_name']
    rooms = load_rooms()
    if room_name in rooms:
        return "Room already exists", 400
    rooms[room_name] = {
        'host': request.remote_addr,
        'guest': None,
        'turn': 'host',
        'host_number': None,
        'guest_number': None,
        'host_guesses': [],
        'guest_guesses': [],
        'winner': None,
        'host_submitted': False,
        'guest_submitted': False,
        'created_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    save_rooms(rooms)
    return redirect(url_for('waiting_room', room_name=room_name, role='host'))

@app.route('/join_room', methods=['POST'])
def join_room():
    room_name = request.form['room_name']
    rooms = load_rooms()
    if room_name in rooms:
        if rooms[room_name]['guest'] is None:
            rooms[room_name]['guest'] = request.remote_addr
            save_rooms(rooms)
            return redirect(url_for('waiting_room', room_name=room_name, role='guest'))
        else:
            return "Room is full", 400
    return "Room does not exist", 404

@app.route('/waiting_room')
def waiting_room():
    room_name = request.args.get('room_name')
    role = request.args.get('role')
    rooms = load_rooms()
    room_data = rooms.get(room_name, {})
    return render_template('waiting_room.html', room_name=room_name, role=role, room_data=room_data)

@app.route('/submit_number', methods=['POST'])
def submit_number():
    room_name = request.form['room_name']
    role = request.form['role']
    secret_number = request.form['secret_number']
    rooms = load_rooms()

    if role == 'host':
        rooms[room_name]['host_number'] = secret_number
        rooms[room_name]['host_submitted'] = True
    else:
        if rooms[room_name]['host_submitted']:
            rooms[room_name]['guest_number'] = secret_number
            rooms[room_name]['guest_submitted'] = True
        else:
            return jsonify({"error": "Host must submit their number first"}), 400

    save_rooms(rooms)

    if rooms[room_name]['host_submitted'] and rooms[room_name]['guest_submitted']:
        return jsonify({"redirect": url_for('play_game', room_name=room_name, role=role)}), 200
    else:
        return jsonify({"success": True}), 200

@app.route('/check_submission_status', methods=['GET'])
def check_submission_status():
    room_name = request.args.get('room_name')
    rooms = load_rooms()
    status = {
        'host_submitted': rooms[room_name].get('host_submitted', False),
        'guest_submitted': rooms[room_name].get('guest_submitted', False)
    }
    return jsonify(status)

@app.route('/check_player_joined')
def check_player_joined():
    room_name = request.args.get('room_name')
    rooms = load_rooms()
    if rooms[room_name]['guest']:
        return jsonify(player_joined=True)
    return jsonify(player_joined=False)

@app.route('/game')
def play_game():
    room_name = request.args.get('room_name')
    role = request.args.get('role')
    rooms = load_rooms()
    if room_name in rooms:
        room = rooms[room_name]
        return render_template('game.html', room_name=room_name, role=role, room=room)
    else:
        return "Room not found", 404

@app.route('/game_state')
def game_state():
    room_name = request.args.get('room_name')
    rooms = load_rooms()
    room_data = rooms[room_name]
    return jsonify({
        'turn': room_data['turn'],
        'host_guesses': room_data['host_guesses'],
        'guest_guesses': room_data.get('guest_guesses', []),
        'winner': room_data.get('winner', None)
    })

def calculate_result(secret, guess):
    strikes = 0
    balls = 0
    
    for i in range(len(secret)):
        if guess[i] == secret[i]:
            strikes += 1
        elif guess[i] in secret:
            balls += 1

    return f"{strikes} S, {balls} B", strikes == len(secret)

def is_valid_guess(guess):
    if not guess.isdigit():
        return False, "Guess must be a number."
    if len(guess) != 3:
        return False, "Guess must be a 3-digit number."
    if len(set(guess)) != len(guess):
        return False, "Guess must not have duplicate digits."
    return True, ""

def is_valid_number(number):
    return is_valid_guess(number)

@app.route('/submit_guess', methods=['POST'])
def submit_guess():
    room_name = request.form['room_name']
    role = request.form['role']
    guess = request.form['guess_number']
    rooms = load_rooms()

    if room_name in rooms:
        room = rooms[room_name]
        
        # Validate the guess
        if len(guess) != 3 or not guess.isdigit() or len(set(guess)) != len(guess):
            return jsonify({'error': 'Guess must be a 3-digit number with no duplicate digits.'}), 400

        if role != 'guest':  # Host or None
            if room['turn'] == 'host':
                result, is_correct = calculate_result(room['guest_number'], guess)
                room['host_guesses'].append({'guess': guess, 'result': result})
                if is_correct:
                    room['winner'] = 'host'
                    room['end_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # 게임 종료 시각 기록
                else:
                    room['turn'] = 'guest'
            else:
                return jsonify({'error': "It's not your turn"}), 400
        elif role == 'guest':
            if room['turn'] == 'guest':
                result, is_correct = calculate_result(room['host_number'], guess)
                room['guest_guesses'].append({'guess': guess, 'result': result})
                if is_correct:
                    room['winner'] = 'guest'
                    room['end_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # 게임 종료 시각 기록
                else:
                    room['turn'] = 'host'
            else:
                return jsonify({'error': "It's not your turn"}), 400
        save_rooms(rooms)
        return jsonify({'success': True}), 200
    else:
        return jsonify({'error': "Room not found"}), 404

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    cleanup_thread = Thread(target=cleanup_rooms)
    cleanup_thread.daemon = True
    cleanup_thread.start()
    app.run(host='0.0.0.0', port=port)
