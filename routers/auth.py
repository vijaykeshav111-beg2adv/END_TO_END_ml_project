import sys
from datetime import date
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from passlib.context import CryptContext
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.exception import CustomException
from src.logger import get_logger
from src.models import User


router = APIRouter(
    tags=["Authentication"]
)

logger = get_logger(__name__)

templates = Jinja2Templates(
    directory="templates"
)

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)


# ============================================================
# PASSWORD HELPERS
# ============================================================

def _safe_password(password: str) -> str:
    """
    bcrypt supports a maximum of 72 bytes.
    """
    raw = password.encode("utf-8")[:72]

    return raw.decode(
        "utf-8",
        errors="ignore"
    )


def hash_password(password: str) -> str:
    return pwd_context.hash(
        _safe_password(password)
    )


def verify_password(
    password: str,
    hashed_password: str
) -> bool:

    try:
        return pwd_context.verify(
            _safe_password(password),
            hashed_password
        )

    except Exception:
        return False


# ============================================================
# CURRENT PATIENT
# ============================================================

def get_current_patient(
    request: Request,
    db: Session
):

    user_id = request.session.get("user_id")
    role = request.session.get("role")

    if not user_id:
        return None

    if role != "patient":
        return None

    return (
        db.query(User)
        .filter(
            User.id == user_id,
            User.role == "patient"
        )
        .first()
    )


# ============================================================
# LOGIN REDIRECT HELPER
# ============================================================

def login_redirect(
    request: Request,
    target: str
):

    request.session["post_login_redirect"] = target

    encoded = quote(
        target,
        safe=""
    )

    return RedirectResponse(
        f"/login?next={encoded}",
        status_code=303
    )


# ============================================================
# SIGNUP PAGE
# ============================================================

@router.get(
    "/signup",
    response_class=HTMLResponse
)
async def signup_page(
    request: Request
):

    return templates.TemplateResponse(
        request,
        "auth/signup.html",
        {
            "error": None,
            "form_data": {}
        }
    )


# ============================================================
# SIGNUP
# ============================================================

@router.post(
    "/signup",
    response_class=HTMLResponse
)
async def signup_patient(
    request: Request,

    full_name: str = Form(...),

    email: str = Form(...),

    phone: str | None = Form(None),

    password: str = Form(...),

    confirm_password: str = Form(...),

    date_of_birth: date | None = Form(None),

    gender: str | None = Form(None),

    db: Session = Depends(get_db)
):

    form_data = {
        "full_name": full_name,
        "email": email,
        "phone": phone or "",
        "date_of_birth": (
            date_of_birth.isoformat()
            if date_of_birth
            else ""
        ),
        "gender": gender or ""
    }

    # --------------------------------------------------------
    # CLEAN INPUT
    # --------------------------------------------------------

    full_name = full_name.strip()

    email = email.strip().lower()

    phone = (
        phone.strip()
        if phone
        else None
    )

    # --------------------------------------------------------
    # BASIC VALIDATION
    # --------------------------------------------------------

    if not full_name:

        return templates.TemplateResponse(
            request,
            "auth/signup.html",
            {
                "error": "Full name is required.",
                "form_data": form_data
            },
            status_code=400
        )

    if not email:

        return templates.TemplateResponse(
            request,
            "auth/signup.html",
            {
                "error": "Email is required.",
                "form_data": form_data
            },
            status_code=400
        )

    if password != confirm_password:

        return templates.TemplateResponse(
            request,
            "auth/signup.html",
            {
                "error": "Passwords do not match.",
                "form_data": form_data
            },
            status_code=400
        )

    if len(password) < 6:

        return templates.TemplateResponse(
            request,
            "auth/signup.html",
            {
                "error": "Password must contain at least 6 characters.",
                "form_data": form_data
            },
            status_code=400
        )

    # --------------------------------------------------------
    # GENDER VALIDATION
    # --------------------------------------------------------

    if gender and gender not in {
        "male",
        "female",
        "other"
    }:

        return templates.TemplateResponse(
            request,
            "auth/signup.html",
            {
                "error": "Invalid gender selection.",
                "form_data": form_data
            },
            status_code=400
        )

    # --------------------------------------------------------
    # EMAIL DUPLICATE
    # --------------------------------------------------------

    existing_email = (
        db.query(User)
        .filter(
            User.email == email
        )
        .first()
    )

    if existing_email:

        return templates.TemplateResponse(
            request,
            "auth/signup.html",
            {
                "error": "An account with this email already exists.",
                "form_data": form_data
            },
            status_code=400
        )

    # --------------------------------------------------------
    # PHONE DUPLICATE
    # --------------------------------------------------------

    if phone:

        existing_phone = (
            db.query(User)
            .filter(
                User.phone == phone
            )
            .first()
        )

        if existing_phone:

            return templates.TemplateResponse(
                request,
                "auth/signup.html",
                {
                    "error": "This phone number is already registered.",
                    "form_data": form_data
                },
                status_code=400
            )

    # --------------------------------------------------------
    # CREATE PATIENT
    # --------------------------------------------------------

    try:

        patient = User(
            full_name=full_name,
            email=email,
            phone=phone,
            password_hash=hash_password(password),
            role="patient",
            date_of_birth=date_of_birth,
            gender=gender
        )

        db.add(patient)

        db.commit()

        db.refresh(patient)

        # ----------------------------------------------------
        # LOGIN AFTER SIGNUP
        # ----------------------------------------------------

        request.session.clear()

        request.session["user_id"] = patient.id

        request.session["role"] = "patient"

        return RedirectResponse(
            "/patient/dashboard",
            status_code=303
        )

    except IntegrityError:

        db.rollback()

        return templates.TemplateResponse(
            request,
            "auth/signup.html",
            {
                "error": "This account information already exists.",
                "form_data": form_data
            },
            status_code=400
        )

    except Exception as exc:

        db.rollback()

        logger.exception(
            "Signup error: %s",
            exc
        )

        raise CustomException(
            exc,
            sys
        )


# ============================================================
# LOGIN PAGE
# ============================================================

@router.get(
    "/login",
    response_class=HTMLResponse
)
async def login_page(
    request: Request,
    next: str | None = Query(None)
):

    if next and next.startswith("/"):
        request.session["post_login_redirect"] = next

    return templates.TemplateResponse(
        request,
        "auth/login.html",
        {
            "error": None,
            "next": next or ""
        }
    )


# ============================================================
# LOGIN
# ============================================================

@router.post(
    "/login",
    response_class=HTMLResponse
)
async def login_patient(
    request: Request,

    email: str = Form(...),

    password: str = Form(...),

    next: str | None = Form(None),

    db: Session = Depends(get_db)
):

    email = email.strip().lower()

    user = (
        db.query(User)
        .filter(
            User.email == email
        )
        .first()
    )

    # --------------------------------------------------------
    # VALIDATE USER
    # --------------------------------------------------------

    if not user:

        return templates.TemplateResponse(
            request,
            "auth/login.html",
            {
                "error": "Invalid email or password.",
                "next": next or ""
            },
            status_code=401
        )

    if user.role != "patient":

        return templates.TemplateResponse(
            request,
            "auth/login.html",
            {
                "error": "This login is for patient accounts.",
                "next": next or ""
            },
            status_code=403
        )

    if not verify_password(
        password,
        user.password_hash
    ):

        return templates.TemplateResponse(
            request,
            "auth/login.html",
            {
                "error": "Invalid email or password.",
                "next": next or ""
            },
            status_code=401
        )

    # --------------------------------------------------------
    # DESTINATION
    # --------------------------------------------------------

    destination = (
        next
        or request.session.get(
            "post_login_redirect"
        )
        or "/patient/dashboard"
    )

    # Prevent external redirects
    if not destination.startswith("/"):
        destination = "/patient/dashboard"

    # --------------------------------------------------------
    # CREATE SESSION
    # --------------------------------------------------------

    request.session.clear()

    request.session["user_id"] = user.id

    request.session["role"] = "patient"

    return RedirectResponse(
        destination,
        status_code=303
    )


# ============================================================
# LOGOUT
# ============================================================

@router.get(
    "/logout"
)
async def logout(
    request: Request
):

    request.session.clear()

    return RedirectResponse(
        "/",
        status_code=303
    )