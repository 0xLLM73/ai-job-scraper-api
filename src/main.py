import os
import sys
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
# DON'T CHANGE THIS !!!
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from flask import Flask, send_from_directory
from flask_cors import CORS
from src.models.user import db
from src.routes.user import user_bp
from src.routes.jobs import jobs_bp
from src.routes.forms import forms_bp

app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))

# Configuration from environment variables
secret_key = os.getenv('SECRET_KEY')
if not secret_key:
    logger.error("SECRET_KEY environment variable is required but not set!")
    logger.error("Please add SECRET_KEY to your .env file")
    sys.exit(1)

app.config['SECRET_KEY'] = secret_key
app.config['DEBUG'] = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'

# Log configuration info
logger.info(f"Flask app initialized with debug={app.config['DEBUG']}")
logger.info(f"Secret key loaded from environment: {'Yes' if app.config['SECRET_KEY'] else 'No'}")

# Enable CORS for all routes
CORS(app)

app.register_blueprint(user_bp, url_prefix='/api')
app.register_blueprint(jobs_bp, url_prefix='/api')
app.register_blueprint(forms_bp, url_prefix='/api')

# Database configuration
db_path = os.path.join(os.path.dirname(__file__), 'database', 'app.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{db_path}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

logger.info(f"Database path: {db_path}")

try:
    db.init_app(app)
    with app.app_context():
        db.create_all()
    logger.info("Database initialized successfully")
except Exception as e:
    logger.error(f"Database initialization failed: {e}")
    raise

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    static_folder_path = app.static_folder
    if static_folder_path is None:
            return "Static folder not configured", 404

    if path != "" and os.path.exists(os.path.join(static_folder_path, path)):
        return send_from_directory(static_folder_path, path)
    else:
        index_path = os.path.join(static_folder_path, 'index.html')
        if os.path.exists(index_path):
            return send_from_directory(static_folder_path, 'index.html')
        else:
            return "index.html not found", 404


if __name__ == '__main__':
    # Server configuration from environment variables
    port = int(os.getenv('FLASK_PORT', 5005))
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    debug = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    
    logger.info(f"Starting Flask server on {host}:{port} (debug={debug})")
    
    try:
        app.run(host=host, port=port, debug=debug)
    except OSError as e:
        if "Address already in use" in str(e):
            logger.error(f"Port {port} is already in use. Try a different port or kill the process using: lsof -ti:{port} | xargs kill -9")
            logger.info(f"You can also set FLASK_PORT environment variable to use a different port")
        else:
            logger.error(f"Failed to start server: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Unexpected error starting server: {e}")
        sys.exit(1)
