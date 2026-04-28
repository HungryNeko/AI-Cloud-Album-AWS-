from flask import Flask
from flask_cors import CORS
from config import Config
from routes.auth import auth_bp
from routes.images import images_bp
from routes.jobs import jobs_bp
from routes.utils import utils_bp
from routes.map import map_bp
from routes.collections import collections_bp

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    CORS(app, resources={
        r"/api/*": {
            "origins": [
                "http://ee547-project-group5-ai-cloud-album-frontend.s3-website-us-west-1.amazonaws.com"
            ]
        }
    })

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(images_bp, url_prefix="/api/images")
    app.register_blueprint(jobs_bp, url_prefix="/api/jobs")
    app.register_blueprint(utils_bp, url_prefix="/api/utils")
    app.register_blueprint(map_bp, url_prefix="/api/map")
    app.register_blueprint(collections_bp, url_prefix="/api/collections")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app

app = Flask(__name__)

@app.errorhandler(Exception)
def handle_exception(e):
    return {
        "error": str(e)
    }, 500

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=True)