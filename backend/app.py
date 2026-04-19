from flask import Flask
from config import Config
from routes.auth import auth_bp
from routes.images import images_bp

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(images_bp, url_prefix="/api/images")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=True)