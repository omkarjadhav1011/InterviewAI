from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user, UserMixin
from pymongo import MongoClient
import os
import bcrypt

auth_bp = Blueprint('auth', __name__)

# TODO: Use a proper Mongo client config and connection pooling
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/interview_app')
client = MongoClient(MONGO_URI)
db = client.get_default_database() if client else client['interview_app']
users = db.users


class User(UserMixin):
    # Minimal User wrapper for Flask-Login
    def __init__(self, user_doc):
        self.id = str(user_doc.get('_id'))
        self.username = user_doc.get('username')
        self.email = user_doc.get('email')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        if users.find_one({'email': email}):
            flash('Email already registered')
            return redirect(url_for('auth.register'))
        pw_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        users.insert_one({'username': username, 'email': email, 'password': pw_hash, 'keywords': [], 'results': []})
        flash('Registered. Please login.')
        return redirect(url_for('auth.login'))
    return render_template('register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user_doc = users.find_one({'email': email})
        if user_doc and bcrypt.checkpw(password.encode('utf-8'), user_doc['password']):
            user = User(user_doc)
            login_user(user)
            flash('Logged in')
            return redirect(url_for('resume.home'))
        flash('Invalid credentials')
        return redirect(url_for('auth.login'))
    return render_template('login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out')
    return redirect(url_for('auth.login'))
