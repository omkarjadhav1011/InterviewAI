import os
import logging

from flask import Flask, jsonify, request
from flask_login import LoginManager
from dotenv import load_dotenv

load_dotenv()

login_manager = LoginManager()

# Configure logging early
log_level = logging.DEBUG if os.getenv('FLASK_ENV') == 'development' else logging.INFO
logging.basicConfig(
    level=log_level,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
)
# Attach the secret-redaction filter to the root logger so every handler benefits
from .utils.secrets_filter import RedactSecretsFilter
logging.getLogger().addFilter(RedactSecretsFilter())

logger = logging.getLogger(__name__)


def create_app(test_config=None):
    app = Flask(__name__, static_folder='static', template_folder='templates')

    # Secret key: require in production, generate random default in dev
    secret = os.getenv('SECRET_KEY', '')
    if not secret:
        if os.getenv('FLASK_ENV') == 'production':
            raise RuntimeError('SECRET_KEY must be set in production')
        import secrets
        secret = secrets.token_hex(32)
        logger.warning('SECRET_KEY not set; using random key (sessions will not persist across restarts)')

    # Load shared defaults from BaseConfig (timeouts, fallback questions, etc.)
    from config import BaseConfig
    app.config.from_object(BaseConfig)

    app.config.update(
        SECRET_KEY=secret,
        UPLOAD_FOLDER=os.path.join(os.path.dirname(__file__), 'static', 'uploads'),
        MAX_CONTENT_LENGTH=16 * 1024 * 1024,  # 16 MB upload limit (Flask-level)
    )
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Initialize shared MongoDB connection
    from .extensions import init_db
    init_db(app)

    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    # Warn about missing optional API keys at startup
    for key in ('GEMINI_API_KEY', 'VAPI_API_KEY', 'ASSEMBLYAI_API_KEY'):
        if not os.getenv(key):
            logger.warning('%s not configured; related features will use fallbacks', key)

    # Register Blueprints
    from .routes.auth import auth_bp
    from .routes.resume import resume_bp
    from .routes.interview import interview_bp
    from .routes.transcription import transcription_bp
    from .routes.results_api import results_api_bp
    from .routes.profile_api import profile_api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(resume_bp)
    app.register_blueprint(interview_bp)
    app.register_blueprint(transcription_bp)
    app.register_blueprint(results_api_bp)
    app.register_blueprint(profile_api_bp)

    # Health check
    @app.route('/health')
    def health():
        from .extensions import get_db
        try:
            get_db().command('ping')
            db_ok = True
        except Exception:
            db_ok = False
        status = 200 if db_ok else 503
        return jsonify({"status": "ok" if db_ok else "degraded", "db": db_ok}), status

    # Global Error Handlers
    def _is_api(req):
        return req.path.startswith('/api/') or req.is_json

    @app.errorhandler(413)
    def request_entity_too_large(e):
        return jsonify({"status": "error", "error": "file too large (max 16 MB)"}), 413

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

    # Flask-Login User Loader (uses shared DB)
    from bson.objectid import ObjectId

    @login_manager.user_loader
    def load_user(user_id):
        from .extensions import get_db
        from .routes.auth import User
        try:
            db = get_db()
            user_doc = db.users.find_one({'_id': ObjectId(user_id)})
            if not user_doc:
                return None
            return User(user_doc)
        except Exception:
            return None

    return app
