from flask import Flask
from flask_login import LoginManager
from dotenv import load_dotenv
import os

load_dotenv()

login_manager = LoginManager()

def create_app(test_config=None):
    app = Flask(__name__, static_folder='static', template_folder='templates')
    app.config.from_mapping(
        SECRET_KEY=os.getenv('SECRET_KEY', 'dev-secret'),
        UPLOAD_FOLDER=os.path.join(os.path.dirname(__file__), 'static', 'uploads')
    )
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    # register blueprints
    from .routes.auth import auth_bp
    from .routes.resume import resume_bp
    from .routes.interview import interview_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(resume_bp)
    app.register_blueprint(interview_bp)

    # user_loader for Flask-Login (simple default)
    from bson.objectid import ObjectId
    @login_manager.user_loader
    def load_user(user_id):
        # Retrieve user by _id from MongoDB
        from pymongo import MongoClient
        MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/interview_app')
        client = MongoClient(MONGO_URI)
        db = client.get_default_database() if client else client['interview_app']
        user_doc = db.users.find_one({'_id': ObjectId(user_id)})
        if not user_doc:
            return None
        from .routes.auth import User
        return User(user_doc)

    return app
