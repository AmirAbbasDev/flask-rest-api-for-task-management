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
limiter = Limiter(get_remote_address, app=app)

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
with app.app_context():
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


# Routes
@app.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    if User.query.filter_by(username=username).first():
        return jsonify({"error": "User already exists"}), 400

    user = User(username=username, password=password)
    db.session.add(user)
    db.session.commit()

    return jsonify({"message": "User created successfully"}), 201


@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    user = User.query.filter_by(username=username, password=password).first()
    if user is None:
        return jsonify({"error": "Invalid credentials"}), 401

    access_token = create_access_token(identity=user.id)
    return jsonify(access_token=access_token), 200


@app.route("/tasks", methods=["GET"])
@jwt_required
@check_free_tier_limits
def get_tasks():
    page = request.args.get("page", 1, type=int)
    limit = request.args.get("limit", 10, type=int)
    status = request.args.get("status")
    due_date = request.args.get("due_date")

    query = Task.query.filter_by(created_by=get_jwt_identity())
    if status:
        query = query.filter_by(status=status)
    if due_date:
        query = query.filter_by(due_date=due_date)
    tasks = query.paginate(page=page, per_page=limit, error_out=False)
    tasks_data = [
        {
            "id": task.id,
            "title": task.title,
            "description": task.description,
            "status": task.status,
            "due_date": task.due_date.isoformat() if task.due_date else None,
            "created_at": task.created_at,
            "created_by": task.created_by,
        }
        for task in tasks.items
    ]

    return jsonify(
        {
            "tasks": tasks_data,
            "page": tasks.page,
            "limit": tasks.per_page,
            "total": tasks.total,
        }
    ), 200


if __name__ == "__main__":
    app.run(debug=True)
