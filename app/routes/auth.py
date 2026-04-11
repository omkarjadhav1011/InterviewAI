import re
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user, UserMixin
import bcrypt

from ..extensions import get_db

_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')

auth_bp = Blueprint('auth', __name__)


class User(UserMixin):
    # Minimal User wrapper for Flask-Login
    def __init__(self, user_doc):
        self.id = str(user_doc.get('_id'))
        self.username = user_doc.get('username')
        self.email = user_doc.get('email')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        users = get_db().users
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        if not username or len(username) > 80:
            flash('Username is required (max 80 characters)')
            return redirect(url_for('auth.register'))
        if not _EMAIL_RE.match(email):
            flash('Enter a valid email address')
            return redirect(url_for('auth.register'))
        if len(password) < 8:
            flash('Password must be at least 8 characters')
            return redirect(url_for('auth.register'))
        if users.find_one({'email': email}):
            flash('Email already registered')
            return redirect(url_for('auth.register'))
        pw_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        users.insert_one({'username': username, 'email': email, 'password': pw_hash, 'skills': [], 'results': []})
        flash('Registered. Please login.')
        return redirect(url_for('auth.login'))
    return render_template('register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        users = get_db().users
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        if not email or not password:
            flash('Email and password are required')
            return redirect(url_for('auth.login'))
        user_doc = users.find_one({'email': email})
        if user_doc and bcrypt.checkpw(password.encode('utf-8'), user_doc['password']):
            user = User(user_doc)
            login_user(user)
            flash('Logged in')
            return redirect(url_for('resume.home'))
        flash('Invalid credentials')
        return redirect(url_for('auth.login'))
    return render_template('login.html')


@auth_bp.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    logout_user()
    flash('Logged out')
    return redirect(url_for('auth.login'))
