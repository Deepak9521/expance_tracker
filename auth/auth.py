"""User authentication and Streamlit session management using bcrypt."""

from typing import Optional, List, Dict, Any
import bcrypt
import streamlit as st
from sqlalchemy.orm import Session
from sqlalchemy import select
from database.models import User


def hash_password(plain_password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    if not plain_password:
        raise ValueError("Password cannot be empty.")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(plain_password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    if not plain_password or not hashed_password:
        return False
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False


def authenticate_user(username: str, password: str, session: Session) -> Optional[User]:
    """Authenticate user with username and password. Return User object if valid, None otherwise."""
    if not username or not password:
        return None

    clean_username = username.strip().lower()
    stmt = select(User).where(User.username == clean_username)
    user = session.execute(stmt).scalar_one_or_none()

    if user and verify_password(password, user.password_hash):
        return user
    return None


def get_all_users(session: Session) -> List[User]:
    """Fetch all fixed users ordered by ID."""
    stmt = select(User).order_by(User.id)
    return list(session.execute(stmt).scalars().all())


def login_user(user: User) -> None:
    """Store authenticated user details in Streamlit session state."""
    st.session_state["user"] = {
        "id": user.id,
        "name": user.name,
        "username": user.username,
    }


def logout_user() -> None:
    """Clear user session state and rerun the application."""
    if "user" in st.session_state:
        del st.session_state["user"]
    st.rerun()


def get_current_user() -> Optional[Dict[str, Any]]:
    """Retrieve the currently logged-in user dict from session state."""
    return st.session_state.get("user")


def is_authenticated() -> bool:
    """Check if a user is currently authenticated."""
    return st.session_state.get("user") is not None
