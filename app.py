from flask import Flask, request, jsonify
from functools import wraps
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    jwt_required,
    get_jwt_identity,
)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from datetime import datetime

app = Flask(__name__)

# Database configuration
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///task.db"
app.config["JWT_SECRET_KEY"] = "super-secret-key"  # Change this in production
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = False  # Token do't expire (for simplicity)

# Initialize the extensions
db = SQLAlchemy(app)
jwt = JWTManager(app)
limiter = Limiter(app, key_func=get_remote_address)

# Define tier permissions
TIER_PERMISSIONS = {
    "free": {"max_requests": 5},
    "paid": {"max_requests": float("inf")},
}


# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False)
    password = db.Column(db.String(120), nullable=False)
    tier = db.Column(db.String(50), nullable=False, default="free")
    created_at = db.Column(db.DateTime, default=datetime.now)
    request_count = db.Column(db.Integer, default=0)


class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(500), nullable=False)
    status = db.Column(db.String(50), nullable=False, default="pending")
    due_date = db.Column(db.DateTime, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)


# Create the database
db.create_all()


# Middleware to check free-tier limits
def check_free_tier_limits(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        if (
            user.tier == "free"
            and user.request_count >= TIER_PERMISSIONS["free"]["max_requests"]
        ):
            return jsonify(
                {
                    "error": "Free tier limit exceeded",
                    "message": "Upgrade to a paid plain.",
                }
            ), 403

        user.request_count += 1
        db.session.commit()
        return f(*args, **kwargs)

    return decorated_function



if __name__ == "__main__":
    app.run(debug=True)
