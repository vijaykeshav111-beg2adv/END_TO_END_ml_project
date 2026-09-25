import sys
from datetime import date
from urllib.parse import quote

import uvicorn
from fastapi import Depends, FastAPI, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from passlib.context import CryptContext
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from src.config.database import get_db
from src.exception import CustomException
from src.logger import get_logger
from src.models import Appointment, Doctor, DoctorSlot, Specialization, User

from src.pipeline.predict_pipeline import CustomData, PredictPipeline
from nlp_pretrained.ner_tagger import extract_entities, get_pos_tags
from nlp_pretrained.embedding import most_similar_words
from nlp_pretrained.sentiment_analyzer import analyze_sentiment


logger = get_logger(__name__)

app = FastAPI(
    title="Vijayvargiya Clinic",
    description="Digital Healthcare Platform",
    version="2.0.0",
)

app.add_middleware(
    SessionMiddleware,
    secret_key="vijayvargiya-clinic-development-secret-change-later",
    max_age=60 * 60 * 24 * 7,
    same_site="lax",
    https_only=False,
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ============================================================
# AUTH HELPERS
# ============================================================

def _safe_password(password: str) -> str:
    raw = password.encode("utf-8")[:72]
    return raw.decode("utf-8", errors="ignore")


def hash_password(password: str) -> str:
    return pwd_context.hash(_safe_password(password))


def verify_password(password: str, hashed_password: str) -> bool:
    try:
        return pwd_context.verify(_safe_password(password), hashed_password)
    except Exception:
        return False


def get_current_patient(request: Request, db: Session):
    user_id = request.session.get("user_id")
    role = request.session.get("role")

    if not user_id or role != "patient":
        return None

    return (
        db.query(User)
        .filter(User.id == user_id, User.role == "patient")
        .first()
    )


def login_redirect(request: Request, target: str):
    request.session["post_login_redirect"] = target
    encoded = quote(target, safe="")
    return RedirectResponse(f"/login?next={encoded}", status_code=303)


# ============================================================
# HOME
# ============================================================

@app.get("/", response_class=HTMLResponse)
async def home(request: Request, db: Session = Depends(get_db)):
    specializations = (
        db.query(Specialization)
        .order_by(Specialization.name)
        .all()
    )

    return templates.TemplateResponse(
        request,
        "index.html",
        {"specializations": specializations},
    )


# ============================================================
# AUTH: SIGNUP
# ============================================================

@app.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    return templates.TemplateResponse(
        request,
        "auth/signup.html",
        {"error": None, "form_data": {}},
    )


@app.post("/signup", response_class=HTMLResponse)
async def signup_patient(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    phone: str | None = Form(None),
    password: str = Form(...),
    confirm_password: str = Form(...),
    date_of_birth: date | None = Form(None),
    gender: str | None = Form(None),
    db: Session = Depends(get_db),
):
    form_data = {
        "full_name": full_name,
        "email": email,
        "phone": phone or "",
        "date_of_birth": date_of_birth or "",
        "gender": gender or "",
    }

    full_name = full_name.strip()
    email = email.strip().lower()
    phone = phone.strip() if phone else None

    if not full_name or not email:
        return templates.TemplateResponse(
            request,
            "auth/signup.html",
            {"error": "Name and email are required.", "form_data": form_data},
            status_code=400,
        )

    if password != confirm_password:
        return templates.TemplateResponse(
            request,
            "auth/signup.html",
            {"error": "Passwords do not match.", "form_data": form_data},
            status_code=400,
        )

    if len(password) < 6:
        return templates.TemplateResponse(
            request,
            "auth/signup.html",
            {"error": "Password must contain at least 6 characters.", "form_data": form_data},
            status_code=400,
        )

    if gender and gender not in {"male", "female", "other"}:
        return templates.TemplateResponse(
            request,
            "auth/signup.html",
            {"error": "Invalid gender selection.", "form_data": form_data},
            status_code=400,
        )

    if db.query(User).filter(User.email == email).first():
        return templates.TemplateResponse(
            request,
            "auth/signup.html",
            {"error": "An account with this email already exists.", "form_data": form_data},
            status_code=400,
        )

    if phone and db.query(User).filter(User.phone == phone).first():
        return templates.TemplateResponse(
            request,
            "auth/signup.html",
            {"error": "An account with this phone number already exists.", "form_data": form_data},
            status_code=400,
        )

    try:
        patient = User(
            full_name=full_name,
            email=email,
            phone=phone,
            password_hash=hash_password(password),
            role="patient",
            date_of_birth=date_of_birth,
            gender=gender,
        )
        db.add(patient)
        db.commit()
        db.refresh(patient)

        request.session.clear()
        request.session["user_id"] = patient.id
        request.session["role"] = "patient"

        return RedirectResponse("/patient/dashboard", status_code=303)
    except IntegrityError:
        db.rollback()
        return templates.TemplateResponse(
            request,
            "auth/signup.html",
            {"error": "This account information already exists.", "form_data": form_data},
            status_code=400,
        )
    except Exception as exc:
        db.rollback()
        logger.exception("Signup error: %s", exc)
        raise CustomException(exc, sys)


# ============================================================
# AUTH: LOGIN
# ============================================================

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, next: str | None = Query(None)):
    if next and next.startswith("/"):
        request.session["post_login_redirect"] = next

    return templates.TemplateResponse(
        request,
        "auth/login.html",
        {"error": None, "next": next or ""},
    )


@app.post("/login", response_class=HTMLResponse)
async def login_patient(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    next: str | None = Form(None),
    db: Session = Depends(get_db),
):
    email = email.strip().lower()

    user = db.query(User).filter(User.email == email).first()

    if not user or user.role != "patient" or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            {"error": "Invalid email or password.", "next": next or ""},
            status_code=401,
        )

    destination = next or request.session.get("post_login_redirect") or "/patient/dashboard"
    if not destination.startswith("/"):
        destination = "/patient/dashboard"

    request.session.clear()
    request.session["user_id"] = user.id
    request.session["role"] = "patient"

    return RedirectResponse(destination, status_code=303)


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)


# ============================================================
# DOCTORS LIST
# ============================================================

@app.get("/doctors", response_class=HTMLResponse)
async def doctors_page(
    request: Request,
    specialization: int | None = Query(None),
    db: Session = Depends(get_db),
):
    specializations = (
        db.query(Specialization)
        .order_by(Specialization.name)
        .all()
    )

    query = (
        db.query(Doctor, User, Specialization)
        .join(User, Doctor.user_id == User.id)
        .join(Specialization, Doctor.specialization_id == Specialization.id)
        .filter(Doctor.is_available.is_(True))
    )

    selected_specialization = None
    if specialization:
        selected_specialization = (
            db.query(Specialization)
            .filter(Specialization.id == specialization)
            .first()
        )
        query = query.filter(Doctor.specialization_id == specialization)

    rows = query.order_by(Doctor.id).all()

    doctors = [
        {
            "doctor": doctor,
            "user": doctor_user,
            "specialization": specialization_obj,
        }
        for doctor, doctor_user, specialization_obj in rows
    ]

    return templates.TemplateResponse(
        request,
        "doctors/list.html",
        {
            "doctors": doctors,
            "specializations": specializations,
            "selected_specialization": selected_specialization,
        },
    )


# ============================================================
# DOCTOR DETAIL
# ============================================================

@app.get("/doctors/{doctor_id}", response_class=HTMLResponse)
async def doctor_detail(
    doctor_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    result = (
        db.query(Doctor, User, Specialization)
        .join(User, Doctor.user_id == User.id)
        .join(Specialization, Doctor.specialization_id == Specialization.id)
        .filter(Doctor.id == doctor_id, Doctor.is_available.is_(True))
        .first()
    )

    if not result:
        return templates.TemplateResponse(
            request,
            "doctors/detail.html",
            {"not_found": True, "doctor": None, "doctor_user": None, "specialization": None, "slots": []},
            status_code=404,
        )

    doctor, doctor_user, specialization = result

    slots = (
        db.query(DoctorSlot)
        .filter(
            DoctorSlot.doctor_id == doctor.id,
            DoctorSlot.status == "available",
            DoctorSlot.slot_date >= date.today(),
        )
        .order_by(DoctorSlot.slot_date, DoctorSlot.start_time)
        .all()
    )

    return templates.TemplateResponse(
        request,
        "doctors/detail.html",
        {
            "not_found": False,
            "doctor": doctor,
            "doctor_user": doctor_user,
            "specialization": specialization,
            "slots": slots,
        },
    )


# ============================================================
# APPOINTMENT BOOKING PAGE
# ============================================================

@app.get("/appointments/book", response_class=HTMLResponse)
async def booking_page_query(
    request: Request,
    slot_id: int | None = Query(None),
    db: Session = Depends(get_db),
):
    return await _booking_page(request, slot_id, db)


@app.get("/appointments/book/{slot_id}", response_class=HTMLResponse)
async def booking_page_path(
    slot_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    return await _booking_page(request, slot_id, db)


async def _booking_page(request: Request, slot_id: int | None, db: Session):
    if not slot_id:
        return RedirectResponse("/doctors", status_code=303)

    patient = get_current_patient(request, db)
    if not patient:
        return login_redirect(request, f"/appointments/book?slot_id={slot_id}")

    slot = (
        db.query(DoctorSlot)
        .filter(DoctorSlot.id == slot_id)
        .first()
    )

    if not slot or slot.status != "available":
        return templates.TemplateResponse(
            request,
            "appointments/book.html",
            {"error": "This slot is no longer available.", "slot": slot},
            status_code=409,
        )

    result = (
        db.query(Doctor, User, Specialization)
        .join(User, Doctor.user_id == User.id)
        .join(Specialization, Doctor.specialization_id == Specialization.id)
        .filter(Doctor.id == slot.doctor_id)
        .first()
    )

    if not result:
        return templates.TemplateResponse(
            request,
            "appointments/book.html",
            {"error": "Doctor information could not be loaded.", "slot": slot},
            status_code=404,
        )

    doctor, doctor_user, specialization = result

    return templates.TemplateResponse(
        request,
        "appointments/book.html",
        {
            "error": None,
            "patient": patient,
            "slot": slot,
            "doctor": doctor,
            "doctor_user": doctor_user,
            "specialization": specialization,
        },
    )


# ============================================================
# CREATE APPOINTMENT
# ============================================================

@app.post("/appointments", response_class=HTMLResponse)
async def create_appointment(
    request: Request,
    slot_id: int = Form(...),
    problem_summary: str = Form(...),
    appointment_type: str = Form(...),
    db: Session = Depends(get_db),
):
    patient = get_current_patient(request, db)
    if not patient:
        return login_redirect(request, f"/appointments/book?slot_id={slot_id}")

    problem_summary = problem_summary.strip()
    if appointment_type not in {"online", "in_person"}:
        return RedirectResponse(f"/appointments/book?slot_id={slot_id}", status_code=303)

    if not problem_summary:
        return templates.TemplateResponse(
            request,
            "appointments/book.html",
            {"error": "Please describe the reason for your visit."},
            status_code=400,
        )

    try:
        # The lock is on ONE row only. Booking slot 10 can never book
        # slot 20 or the same time for another doctor.
        slot = (
            db.query(DoctorSlot)
            .filter(DoctorSlot.id == slot_id)
            .with_for_update()
            .first()
        )

        if not slot:
            db.rollback()
            return templates.TemplateResponse(
                request,
                "appointments/book.html",
                {"error": "Appointment slot not found."},
                status_code=404,
            )

        if slot.status != "available":
            db.rollback()
            return templates.TemplateResponse(
                request,
                "appointments/book.html",
                {"error": "This slot was just booked by another patient."},
                status_code=409,
            )

        appointment = Appointment(
            patient_id=patient.id,
            doctor_id=slot.doctor_id,
            slot_id=slot.id,
            problem_summary=problem_summary,
            status="pending",
            appointment_type=appointment_type,
        )

        db.add(appointment)
        slot.status = "booked"
        db.commit()
        db.refresh(appointment)

        result = (
            db.query(Doctor, User, Specialization)
            .join(User, Doctor.user_id == User.id)
            .join(Specialization, Doctor.specialization_id == Specialization.id)
            .filter(Doctor.id == appointment.doctor_id)
            .first()
        )

        doctor, doctor_user, specialization = result

        return templates.TemplateResponse(
            request,
            "appointments/success.html",
            {
                "appointment": appointment,
                "patient": patient,
                "doctor": doctor,
                "doctor_user": doctor_user,
                "specialization": specialization,
                "slot": slot,
            },
        )

    except IntegrityError:
        db.rollback()
        return templates.TemplateResponse(
            request,
            "appointments/book.html",
            {"error": "This appointment slot is already booked."},
            status_code=409,
        )
    except Exception as exc:
        db.rollback()
        logger.exception("Appointment creation error: %s", exc)
        raise CustomException(exc, sys)


# ============================================================
# PATIENT DASHBOARD
# ============================================================
@app.get(
    "/patient/dashboard",
    response_class=HTMLResponse
)
async def patient_dashboard(
    request: Request,
    db: Session = Depends(get_db)
):
    # ------------------------------------------------
    # Get logged-in patient
    # ------------------------------------------------

    patient = get_current_patient(request, db)

    if not patient:
        return RedirectResponse(
            "/login",
            status_code=303
        )

    # ------------------------------------------------
    # Get patient's appointments
    # ------------------------------------------------

    appointments = (
        db.query(Appointment)
        .filter(
            Appointment.patient_id == patient.id
        )
        .order_by(
            Appointment.created_at.desc()
        )
        .all()
    )

    appointment_data = []

    # ------------------------------------------------
    # Build appointment information
    # ------------------------------------------------

    for appointment in appointments:

        result = (
            db.query(
                Doctor,
                User,
                Specialization,
                DoctorSlot
            )
            .join(
                User,
                Doctor.user_id == User.id
            )
            .join(
                Specialization,
                Doctor.specialization_id
                == Specialization.id
            )
            .join(
                DoctorSlot,
                DoctorSlot.id
                == appointment.slot_id
            )
            .filter(
                Doctor.id
                == appointment.doctor_id
            )
            .filter(
                DoctorSlot.doctor_id
                == Doctor.id
            )
            .first()
        )

        if result:

            doctor, doctor_user, specialization, slot = result

            appointment_data.append(
                {
                    "appointment": appointment,
                    "doctor": doctor,
                    "doctor_user": doctor_user,
                    "specialization": specialization,
                    "slot": slot
                }
            )

    # ------------------------------------------------
    # Get available doctors
    # ------------------------------------------------

    doctor_results = (
        db.query(
            Doctor,
            User,
            Specialization
        )
        .join(
            User,
            Doctor.user_id == User.id
        )
        .join(
            Specialization,
            Doctor.specialization_id
            == Specialization.id
        )
        .filter(
            Doctor.is_available.is_(True)
        )
        .order_by(
            Doctor.id
        )
        .all()
    )

    doctors = []

    for doctor, doctor_user, specialization in doctor_results:

        doctors.append(
            {
                "doctor": doctor,
                "user": doctor_user,
                "specialization": specialization
            }
        )

    # ------------------------------------------------
    # Render dashboard
    # ------------------------------------------------

    return templates.TemplateResponse(
        request,
        "patient/dashboard.html",
        {
            "patient": patient,
            "appointments": appointment_data,
            "doctors": doctors
        }
    )
# ============================================================
# COVID SCREENING
# ============================================================

@app.get("/predict", response_class=HTMLResponse)
async def predict_form(request: Request):
    return templates.TemplateResponse(request, "predict.html", {"result": None})


@app.post("/predict", response_class=HTMLResponse)
async def predict_result(
    request: Request,
    age: int = Form(...),
    gender: str = Form(...),
    fever: float = Form(...),
    cough: str = Form(...),
    city: str = Form(...),
):
    try:
        custom_data = CustomData(
            age=age,
            gender=gender,
            fever=fever,
            cough=cough,
            city=city,
        )
        data_df = custom_data.get_data_as_dataframe()
        result, probability = PredictPipeline().predict(data_df)

        return templates.TemplateResponse(
            request,
            "predict.html",
            {
                "result": result,
                "probability": probability,
                "form_data": {
                    "age": age,
                    "gender": gender,
                    "fever": fever,
                    "cough": cough,
                    "city": city,
                },
            },
        )
    except Exception as exc:
        logger.exception("Prediction error: %s", exc)
        raise CustomException(exc, sys)


# ============================================================
# NLP
# ============================================================

@app.get("/pretrained-nlp", response_class=HTMLResponse)
async def pretrained_nlp_form(request: Request):
    return templates.TemplateResponse(
        request,
        "pretrained_nlp.html",
        {"result": None, "form_data": {"query": ""}, "error": None},
    )


@app.post("/pretrained-nlp", response_class=HTMLResponse)
async def pretrained_nlp_analysis(request: Request, query: str = Form(...)):
    query = query.strip()
    if not query:
        return templates.TemplateResponse(
            request,
            "pretrained_nlp.html",
            {"result": None, "form_data": {"query": ""}, "error": "Please enter some text."},
        )

    try:
        pos_tags = get_pos_tags(query)
        entities = extract_entities(query)
        sentiment = analyze_sentiment(query)
        similar_words = []

        first_word = query.split()[0].lower()
        try:
            similar_words = most_similar_words(first_word, topn=5)
        except Exception:
            pass

        result = {
            "query": query,
            "pos_tags": pos_tags,
            "entities": entities,
            "similar_words": similar_words,
            "sentiment": sentiment,
        }

        return templates.TemplateResponse(
            request,
            "pretrained_nlp.html",
            {"result": result, "form_data": {"query": query}, "error": None},
        )
    except Exception as exc:
        logger.exception("NLP analysis error: %s", exc)
        return templates.TemplateResponse(
            request,
            "pretrained_nlp.html",
            {"result": None, "form_data": {"query": query}, "error": str(exc)},
        )


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
async def health_check():
    return {"status": "ok", "application": "Vijayvargiya Clinic"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
