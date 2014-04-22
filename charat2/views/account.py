from bcrypt import gensalt, hashpw
from flask import g, render_template, redirect, request, url_for
from sqlalchemy.orm.exc import NoResultFound
from urlparse import urlparse

from charat2.model import User
from charat2.model.connections import use_db
from charat2.model.validators import username_validator, reserved_usernames

def referer_or_home():
    if "Referer" in request.headers:
        r = urlparse(request.headers["Referer"])
        return r.scheme+"://"+r.netloc+r.path
    return url_for("home")

@use_db
def login_get():
    if g.user is not None:
        return redirect(url_for("home"))
    return render_template("login.html", log_in_error=request.args.get("log_in_error"))

@use_db
def register_get():
    form = SignupForm()
    if g.user is not None:
        return redirect(url_for("home"))
    return render_template("register.html", register_error=request.args.get("register_error"), form)

@use_db
def login_post():
    # Check username, lowercase to make it case-insensitive.
    try:
        user = g.db.query(User).filter(
            User.username==request.form["username"].lower()
        ).one()
    except NoResultFound:
        return redirect(referer_or_home()+"?log_in_error=The username or password you entered is incorrect.")
    # Check password.
    if hashpw(
        request.form["password"].encode(),
        user.password.encode()
    )!=user.password:
        return redirect(referer_or_home()+"?log_in_error=The username or password you entered is incorrect.")
    g.redis.set("session:" + g.session_id, user.id)
    return redirect(referer_or_home())

@use_db
def logout():
    if "session" in request.cookies:
        g.redis.delete("session:" + request.cookies["session"])
    return redirect(referer_or_home())

@use_db
def register():
    # Don't accept blank fields.
    if request.form["username"]=="" or request.form["password"]=="":
        return redirect(referer_or_home()+"?register_error=Please enter a username and password.")
    # Make sure the two passwords match.
    if request.form["password"]!=request.form["password_again"]:
        return redirect(referer_or_home()+"?register_error=The two passwords didn't match.")
    # Check username against username_validator.
    username = request.form["username"].lower()[:50]
    if username_validator.match(username) is None:
        return redirect(referer_or_home()+"?register_error=Usernames can only contain letters, numbers, hyphens and underscores.")
    # XXX DON'T ALLOW USERNAMES STARTING WITH GUEST_.
    # Make sure this username hasn't been taken before.
    # Also check against reserved usernames.
    existing_username = g.db.query(User.id).filter(
        User.username==username
    ).count()
    if existing_username==1 or username in reserved_usernames:
        return redirect(referer_or_home()+"?register_error=The username "+username+" has already been taken.")
    new_user = User(
        username=username,
        password=hashpw(request.form["password"].encode(), gensalt()),
    )
    g.db.add(new_user)
    g.db.flush()
    g.redis.set("session:" + g.session_id, new_user.id)
    g.db.commit()
    return redirect(referer_or_home())

