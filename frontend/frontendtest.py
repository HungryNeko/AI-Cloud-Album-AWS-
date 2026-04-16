# use this script to simulate a server running, return fix parameters to test frontend functions.

from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

users = {
    "test": "123456"
}


@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if username in users:
        return jsonify({"msg": "Username already exists"}), 400

    users[username] = password
    return jsonify({"msg": "Register success"}), 200


@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if username not in users or users[username] != password:
        return jsonify({"msg": "Invalid username or password"}), 401

    return jsonify({"token": "test-token-123456"}), 200

if __name__ == '__main__':
    app.run(debug=True, port=5000)