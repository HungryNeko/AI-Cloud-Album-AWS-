from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)
users = {
    "test": "123456"
}
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PAGES_DIR = os.path.join(BASE_DIR, "pages")
STATIC_DIR = os.path.join(BASE_DIR, "static")


@app.route('/')
def root():
    return send_from_directory(PAGES_DIR, 'index.html')


@app.route('/pages/<path:filename>')
def serve_pages(filename):
    return send_from_directory(PAGES_DIR, filename)


@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(STATIC_DIR, filename)


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