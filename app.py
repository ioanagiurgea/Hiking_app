from flask import Flask
from extensions import db
from flask_jwt_extended import JWTManager
from datetime import timedelta
app = Flask(__name__)


app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:nori@localhost:5432/hiking_app'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config["JWT_SECRET_KEY"] = "cheie-secreta-foarte-buna"
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=2)

db.init_app(app)
jwt = JWTManager(app)

from routes import main
app.register_blueprint(main)

if __name__ == "__main__":
    app.run(debug=True)