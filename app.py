from flask import Flask, render_template, redirect, url_for, session
from flask_cors import CORS
from authlib.integrations.flask_client import OAuth
import os

from config import BASE_DIR, SUPER_ADMIN_EMAIL
from repositories.members_repo import lookup_member
from auth import is_logged_in, is_admin, can_access_translation_module
from routes.terms     import terms_bp
from routes.members   import members_bp
from routes.sources   import sources_bp
from routes.extract   import extract_bp
from routes.translate import translate_bp

app = Flask(__name__, template_folder=os.path.join(BASE_DIR, 'templates'))
CORS(app)
app.secret_key = os.getenv("SECRET_KEY")

# ── Google OAuth ──────────────────────────────────────────────────────────
oauth  = OAuth(app)
google = oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={
        "scope": "openid email profile",
        "token_endpoint_auth_method": "client_secret_post",
    }
)

# ── Blueprints ────────────────────────────────────────────────────────────
app.register_blueprint(terms_bp)
app.register_blueprint(members_bp)
app.register_blueprint(sources_bp)
app.register_blueprint(extract_bp)
app.register_blueprint(translate_bp)


# ── Page routes ───────────────────────────────────────────────────────────
@app.route("/")
def home():
    if not is_logged_in():
        return redirect(url_for("login"))
    role = session.get("user_role", "member")
    return render_template("index.html",
                           user=session["user_email"],
                           user_name=session.get("user_name", ""),
                           is_admin=is_admin(),
                           user_role=role,
                           can_access_translation=can_access_translation_module(role),
                           super_admin=SUPER_ADMIN_EMAIL)


@app.route("/login")
def login():
    return render_template("login.html")


@app.route("/auth/google")
def auth_google():
    redirect_uri = os.environ.get("GOOGLE_REDIRECT_URI") or url_for("callback", _external=True)
    return google.authorize_redirect(redirect_uri)


@app.route("/callback")
def callback():
    token = google.authorize_access_token()
    email = token["userinfo"]["email"]
    role  = lookup_member(email)
    if role is None:
        return render_template("denied.html"), 403
    session["user_email"] = email
    session["user_name"]  = token["userinfo"].get("name", email)
    session["user_role"]  = role
    return redirect(url_for("home"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    port  = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV", "development") != "production"
    app.run(host="127.0.0.1", port=port, debug=debug)
