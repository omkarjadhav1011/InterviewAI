from flask import Flask, jsonify, request
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

    # -----------------------------
    # ✅ Register Blueprints
    # -----------------------------
    from .routes.auth import auth_bp
    from .routes.resume import resume_bp
    from .routes.interview import interview_bp
    from .routes.transcription import transcription_bp   # 👈 NEW

    app.register_blueprint(auth_bp)
    app.register_blueprint(resume_bp)
    app.register_blueprint(interview_bp)
    app.register_blueprint(transcription_bp)              # 👈 NEW

    # -----------------------------
    # ✅ Global Error Handlers
    # -----------------------------
    def _is_api(req):
        return req.path.startswith('/api/') or req.is_json

    @app.errorhandler(400)
    def bad_request(e):
        if _is_api(request):
            return jsonify({"status": "error", "error": str(e)}), 400
        return str(e), 400

    @app.errorhandler(404)
    def not_found(e):
        if _is_api(request):
            return jsonify({"status": "error", "error": "not found"}), 404
        return str(e), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        if _is_api(request):
            return jsonify({"status": "error", "error": "method not allowed"}), 405
        return str(e), 405

    @app.errorhandler(500)
    def internal_error(e):
        app.logger.exception('Unhandled server error')
        if _is_api(request):
            return jsonify({"status": "error", "error": "internal server error"}), 500
        return str(e), 500

    # -----------------------------
    # ✅ Flask-Login User Loader
    # -----------------------------
    from bson.objectid import ObjectId
    @login_manager.user_loader
    def load_user(user_id):
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
