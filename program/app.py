import os
from flask import Flask, render_template, request, redirect, url_for, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, ChatMessage
from flask_login import LoginManager, login_user, logout_user, current_user, login_required
import requests
import json
from datetime import datetime

OLLAMA_API = "http://localhost:11434"
LLAMA_MODEL = "llama2:7b"

def create_app():
    app = Flask(__name__, template_folder="templates")
    app.config['SECRET_KEY'] = "dev-secret"
    app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///voice_chat.db"
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = "login"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # --------------------------
    # ROUTES
    # --------------------------

    @app.route("/")
    def index():
        return redirect(url_for("dashboard")) if current_user.is_authenticated else redirect(url_for("login"))

    @app.route("/signup", methods=["GET", "POST"])
    def signup():
        if request.method == "POST":
            username = request.form["username"].strip()
            password = request.form["password"]

            if User.query.filter_by(username=username).first():
                return render_template("signup.html", error="Username already exists")

            u = User(username=username, password_hash=generate_password_hash(password))
            db.session.add(u)
            db.session.commit()
            return redirect(url_for("login"))

        return render_template("signup.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            username = request.form["username"]
            password = request.form["password"]

            u = User.query.filter_by(username=username).first()
            if not u or not check_password_hash(u.password_hash, password):
                return render_template("login.html", error="Invalid username or password")

            login_user(u)
            return redirect(url_for("dashboard"))

        return render_template("login.html")

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        return redirect(url_for("login"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        return render_template("dashboard.html", username=current_user.username)

    @app.route("/history")
    @login_required
    def history():
        msgs = ChatMessage.query.filter_by(user_id=current_user.id).order_by(ChatMessage.created_at.asc()).all()
        return render_template("history.html", messages=msgs)

    @app.route("/api/history", methods=["GET"])
    @login_required
    def api_history():
        msgs = ChatMessage.query.filter_by(user_id=current_user.id).order_by(ChatMessage.created_at.asc()).all()
        return jsonify([
            {"role": m.role, "text": m.text, "created_at": m.created_at.isoformat()}
            for m in msgs
        ])

    # ----------------------------------------------------------
    # FIXED CHAT ENDPOINT — WORKS WITH OLLAMA STREAMING
    # ----------------------------------------------------------
    @app.route("/api/chat", methods=["POST"])
    @login_required
    def api_chat():
        data = request.json
        if not data or "text" not in data:
            return jsonify({"error": "no text"}), 400

        user_text = data["text"].strip()

        # Save user message
        um = ChatMessage(user_id=current_user.id, role="user", text=user_text)
        db.session.add(um)
        db.session.commit()

        # Call Ollama with streaming
        try:
            payload = {
                "model": LLAMA_MODEL,
                "prompt": user_text,
                "stream": True
            }

            response = requests.post(
                f"{OLLAMA_API}/api/generate",
                json=payload,
                stream=True,
                timeout=60
            )

            assistant_text = ""

            for line in response.iter_lines():
                if not line:
                    continue

                try:
                    chunk = line.decode("utf-8")
                    data = json.loads(chunk)
                    assistant_text += data.get("response", "")
                except:
                    pass

        except Exception as e:
            assistant_text = f"Error contacting model: {str(e)}"

        # Save assistant reply
        am = ChatMessage(user_id=current_user.id, role="assistant", text=assistant_text)
        db.session.add(am)
        db.session.commit()

        return jsonify({"reply": assistant_text})

    # ----------------------------------------------------------
    # CLEAR CHAT ENDPOINT
    # ----------------------------------------------------------
    @app.route("/api/clear-chat", methods=["POST"])
    @login_required
    def api_clear_chat():
        """Delete all chat messages for the current user"""
        try:
            # Delete all messages for current user
            deleted_count = ChatMessage.query.filter_by(user_id=current_user.id).delete()
            db.session.commit()
            
            print(f"Deleted {deleted_count} messages for user {current_user.id}")
            
            return jsonify({
                "success": True, 
                "message": "Chat cleared successfully",
                "deleted_count": deleted_count
            })
        except Exception as e:
            db.session.rollback()
            print(f"Error clearing chat: {str(e)}")
            return jsonify({
                "success": False, 
                "error": str(e)
            }), 500

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, port=5000)