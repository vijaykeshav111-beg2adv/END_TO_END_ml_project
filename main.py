import sys
import uvicorn

from datetime import date
from urllib.parse import quote

from fastapi import (
    FastAPI,
    Form,
    Request,
    Depends,
    Query,
)

from fastapi.responses import (
    HTMLResponse,
    RedirectResponse,
)

from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from starlette.middleware.sessions import SessionMiddleware

from src.config.database import get_db
from src.exception import CustomException
from src.logger import get_logger

from src.models import (
    User,
    Doctor,
    DoctorSlot,
    Appointment,
    Specialization,
)

from src.pipeline.predict_pipeline import (
    CustomData,
    PredictPipeline,
)

from nlp_pretrained.ner_tagger import (
    get_pos_tags,
    extract_entities,
)

from nlp_pretrained.embedding import (
    most_similar_words,
)

from nlp_pretrained.sentiment_analyzer import (
    analyze_sentiment,
)

from routers.auth import (
    router as auth_router,
    get_current_patient,
    get_current_doctor,
)


# ============================================================
# LOGGER
# ============================================================

logger = get_logger(__name__)


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="Vijayvargiya Clinic",
    description="Digital Healthcare Platform",
    version="2.0.0",
)


# ============================================================
# SESSION MIDDLEWARE
# ============================================================

app.add_middleware(
    SessionMiddleware,
    secret_key="vijayvargiya-clinic-development-secret-change-later",
    max_age=60 * 60 * 24 * 7,
    same_site="lax",
    https_only=False,
)


# ============================================================
# STATIC FILES
# ============================================================

app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static",
)


# ============================================================
# TEMPLATES
# ============================================================

templates = Jinja2Templates(
    directory="templates"
)


# ============================================================
# AUTH ROUTER
# ============================================================

app.include_router(auth_router)


# ============================================================
# HOME PAGE
# ============================================================

@app.get(
    "/",
    response_class=HTMLResponse,
)
async def home(
    request: Request,
    db: Session = Depends(get_db),
):

    logger.info("Clinic homepage accessed")

    try:

        # ----------------------------------------------------
        # SPECIALIZATIONS
        # ----------------------------------------------------

        specializations = (
            db.query(Specialization)
            .order_by(
                Specialization.name
            )
            .all()
        )

        # ----------------------------------------------------
        # AVAILABLE DOCTORS
        # ----------------------------------------------------

        doctor_results = (
            db.query(
                Doctor,
                User,
                Specialization,
            )
            .join(
                User,
                Doctor.user_id == User.id,
            )
            .join(
                Specialization,
                Doctor.specialization_id
                == Specialization.id,
            )
            .filter(
                Doctor.is_available == True
            )
            .order_by(
                Doctor.id
            )
            .all()
        )

        doctors = []

        for (
            doctor,
            doctor_user,
            specialization,
        ) in doctor_results:

            doctors.append(
                {
                    "doctor": doctor,
                    "user": doctor_user,
                    "specialization": specialization,
                }
            )

        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "specializations": specializations,
                "doctors": doctors,
            },
        )

    except Exception as exc:

        logger.exception(
            "Homepage error: %s",
            exc,
        )

        raise CustomException(
            exc,
            sys,
        )


# ============================================================
# PATIENT DASHBOARD
# ============================================================

@app.get(
    "/patient/dashboard",
    response_class=HTMLResponse,
)
async def patient_dashboard(
    request: Request,
    db: Session = Depends(get_db),
):

    patient = get_current_patient(
        request,
        db,
    )

    if not patient:

        request.session.clear()

        return RedirectResponse(
            "/login",
            status_code=303,
        )

    # --------------------------------------------------------
    # PATIENT APPOINTMENTS
    # --------------------------------------------------------

    appointments = (
        db.query(Appointment)
        .filter(
            Appointment.patient_id
            == patient.id
        )
        .order_by(
            Appointment.created_at.desc()
        )
        .all()
    )

    appointment_data = []

    for appointment in appointments:

        # ----------------------------------------------------
        # DOCTOR
        # ----------------------------------------------------

        doctor_result = (
            db.query(
                Doctor,
                User,
                Specialization,
            )
            .join(
                User,
                Doctor.user_id == User.id,
            )
            .join(
                Specialization,
                Doctor.specialization_id
                == Specialization.id,
            )
            .filter(
                Doctor.id
                == appointment.doctor_id
            )
            .first()
        )

        # ----------------------------------------------------
        # SLOT
        # ----------------------------------------------------

        slot = (
            db.query(DoctorSlot)
            .filter(
                DoctorSlot.id
                == appointment.slot_id
            )
            .first()
        )

        if doctor_result:

            (
                doctor,
                doctor_user,
                specialization,
            ) = doctor_result

            appointment_data.append(
                {
                    "appointment": appointment,
                    "doctor": doctor,
                    "doctor_user": doctor_user,
                    "specialization": specialization,
                    "slot": slot,
                }
            )

    # --------------------------------------------------------
    # AVAILABLE DOCTORS
    # --------------------------------------------------------

    doctor_results = (
        db.query(
            Doctor,
            User,
            Specialization,
        )
        .join(
            User,
            Doctor.user_id == User.id,
        )
        .join(
            Specialization,
            Doctor.specialization_id
            == Specialization.id,
        )
        .filter(
            Doctor.is_available == True
        )
        .order_by(
            Doctor.id
        )
        .all()
    )

    doctors = []

    for (
        doctor,
        doctor_user,
        specialization,
    ) in doctor_results:

        doctors.append(
            {
                "doctor": doctor,
                "user": doctor_user,
                "specialization": specialization,
            }
        )

    return templates.TemplateResponse(
        request,
        "patient/dashboard.html",
        {
            "patient": patient,
            "appointments": appointment_data,
            "doctors": doctors,
        },
    )


# ============================================================
# DOCTOR DASHBOARD
# ============================================================

@app.get(
    "/doctor/dashboard",
    response_class=HTMLResponse,
)
async def doctor_dashboard(
    request: Request,
    db: Session = Depends(get_db),
):

    # --------------------------------------------------------
    # CURRENT DOCTOR
    # --------------------------------------------------------

    doctor_user = get_current_doctor(
        request,
        db,
    )

    if not doctor_user:

        request.session.clear()

        return RedirectResponse(
            "/login",
            status_code=303,
        )

    # --------------------------------------------------------
    # DOCTOR PROFILE
    # --------------------------------------------------------

    doctor_result = (
        db.query(
            Doctor,
            Specialization,
        )
        .join(
            Specialization,
            Doctor.specialization_id
            == Specialization.id,
        )
        .filter(
            Doctor.user_id
            == doctor_user.id
        )
        .first()
    )

    if not doctor_result:

        return HTMLResponse(
            content="""
            <h2>Doctor profile not found</h2>
            <p>
                Your doctor account is not connected
                to a doctor profile.
            </p>
            """,
            status_code=404,
        )

    doctor, specialization = doctor_result

    # --------------------------------------------------------
    # APPOINTMENTS
    # --------------------------------------------------------

    appointments = (
        db.query(Appointment)
        .filter(
            Appointment.doctor_id
            == doctor.id
        )
        .order_by(
            Appointment.created_at.desc()
        )
        .all()
    )

    # --------------------------------------------------------
    # STATISTICS
    # --------------------------------------------------------

    total_appointments = len(
        appointments
    )

    pending_appointments = sum(
        1
        for appointment in appointments
        if appointment.status == "pending"
    )

    confirmed_appointments = sum(
        1
        for appointment in appointments
        if appointment.status == "confirmed"
    )

    completed_appointments = sum(
        1
        for appointment in appointments
        if appointment.status == "completed"
    )
    cancelled_appointments = sum(
    1
    for appointment in appointments
    if appointment.status == "cancelled"
    )
    
    
    # --------------------------------------------------------
    # APPOINTMENT DATA
    # --------------------------------------------------------

    appointment_data = []

    for appointment in appointments:

        patient = (
            db.query(User)
            .filter(
                User.id
                == appointment.patient_id
            )
            .first()
        )

        slot = (
            db.query(DoctorSlot)
            .filter(
                DoctorSlot.id
                == appointment.slot_id
            )
            .first()
        )

        appointment_data.append(
            {
                "appointment": appointment,
                "patient": patient,
                "slot": slot,
            }
        )

    # --------------------------------------------------------
    # TODAY'S APPOINTMENTS
    # --------------------------------------------------------

    today_appointments = []

    for item in appointment_data:

        slot = item["slot"]

        if (
            slot
            and slot.slot_date == date.today()
        ):

            today_appointments.append(
                item
            )

    # --------------------------------------------------------
    # RENDER DASHBOARD
    # --------------------------------------------------------

    return templates.TemplateResponse(
        request,
        "doctor/dashboard.html",
        {
            "doctor_user": doctor_user,
            "doctor": doctor,
            "specialization": specialization,

            "appointments": appointment_data,

            "today_appointments":
                today_appointments,

            "total_appointments":
                total_appointments,

            "pending_appointments":
                pending_appointments,

            "confirmed_appointments":
                confirmed_appointments,

            "completed_appointments":
                completed_appointments,
            "cancelled_appointments":
                cancelled_appointments,
        },
    )


# ============================================================
# UPDATE APPOINTMENT STATUS
# ============================================================

@app.post(
    "/doctor/appointments/{appointment_id}/status"
)
async def update_appointment_status(
    appointment_id: int,
    status: str = Form(...),
    request: Request = None,
    db: Session = Depends(get_db),
):

    doctor_user = get_current_doctor(
        request,
        db,
    )

    if not doctor_user:

        return RedirectResponse(
            "/login",
            status_code=303,
        )

    # --------------------------------------------------------
    # DOCTOR
    # --------------------------------------------------------

    doctor = (
        db.query(Doctor)
        .filter(
            Doctor.user_id
            == doctor_user.id
        )
        .first()
    )

    if not doctor:

        return HTMLResponse(
            "Doctor profile not found.",
            status_code=404,
        )

    # --------------------------------------------------------
    # APPOINTMENT
    # --------------------------------------------------------

    appointment = (
        db.query(Appointment)
        .filter(
            Appointment.id
            == appointment_id,
            Appointment.doctor_id
            == doctor.id,
        )
        .first()
    )

    if not appointment:

        return HTMLResponse(
            "Appointment not found.",
            status_code=404,
        )

    # --------------------------------------------------------
    # VALID STATUS
    # --------------------------------------------------------

    allowed_statuses = {
        "pending",
        "confirmed",
        "completed",
        "cancelled",
    }

    if status not in allowed_statuses:

        return HTMLResponse(
            "Invalid appointment status.",
            status_code=400,
        )

    # --------------------------------------------------------
    # VALID TRANSITIONS
    # --------------------------------------------------------

    current_status = appointment.status

    valid_transitions = {
        "pending": {
            "confirmed",
            "cancelled",
        },
        "confirmed": {
            "completed",
            "cancelled",
        },
        "completed": set(),
        "cancelled": set(),
    }

    if status not in valid_transitions.get(
        current_status,
        set(),
    ):

        return HTMLResponse(
            f"Cannot change appointment "
            f"from '{current_status}' "
            f"to '{status}'.",
            status_code=400,
        )

    # --------------------------------------------------------
    # UPDATE
    # --------------------------------------------------------

    appointment.status = status

    db.commit()

    logger.info(
        "Appointment status updated. "
        "appointment_id=%s doctor_id=%s "
        "old_status=%s new_status=%s",
        appointment.id,
        doctor.id,
        current_status,
        status,
    )

    return RedirectResponse(
        "/doctor/dashboard",
        status_code=303,
    )


# ============================================================
# DOCTORS LIST
# ============================================================

@app.get(
    "/doctors",
    response_class=HTMLResponse,
)
async def doctors_page(
    request: Request,
    specialization: int | None = None,
    db: Session = Depends(get_db),
):

    try:

        selected_specialization = None

        if specialization:

            selected_specialization = (
                db.query(Specialization)
                .filter(
                    Specialization.id
                    == specialization
                )
                .first()
            )

        query = (
            db.query(
                Doctor,
                User,
                Specialization,
            )
            .join(
                User,
                Doctor.user_id == User.id,
            )
            .join(
                Specialization,
                Doctor.specialization_id
                == Specialization.id,
            )
            .filter(
                Doctor.is_available == True
            )
        )

        if specialization:

            query = query.filter(
                Doctor.specialization_id
                == specialization
            )

        results = (
            query
            .order_by(
                Doctor.id
            )
            .all()
        )

        doctors = []

        for (
            doctor,
            doctor_user,
            specialization_obj,
        ) in results:

            doctors.append(
                {
                    "doctor": doctor,
                    "user": doctor_user,
                    "specialization":
                        specialization_obj,
                }
            )

        return templates.TemplateResponse(
            request,
            "doctors/list.html",
            {
                "doctors": doctors,
                "specialization":
                    selected_specialization,
            },
        )

    except Exception as exc:

        logger.exception(
            "Doctors page error: %s",
            exc,
        )

        raise CustomException(
            exc,
            sys,
        )


# ============================================================
# DOCTOR PROFILE
# ============================================================

@app.get(
    "/doctors/{doctor_id}",
    response_class=HTMLResponse,
)
async def doctor_profile(
    doctor_id: int,
    request: Request,
    db: Session = Depends(get_db),
):

    try:

        result = (
            db.query(
                Doctor,
                User,
                Specialization,
            )
            .join(
                User,
                Doctor.user_id == User.id,
            )
            .join(
                Specialization,
                Doctor.specialization_id
                == Specialization.id,
            )
            .filter(
                Doctor.id == doctor_id
            )
            .first()
        )

        if not result:

            return templates.TemplateResponse(
                request,
                "doctors/detail.html",
                {
                    "not_found": True,
                    "doctor": None,
                    "doctor_user": None,
                    "specialization": None,
                    "slots": [],
                },
                status_code=404,
            )

        (
            doctor,
            doctor_user,
            specialization,
        ) = result

        slots = (
            db.query(DoctorSlot)
            .filter(
                DoctorSlot.doctor_id
                == doctor.id,
                DoctorSlot.status
                == "available",
                DoctorSlot.slot_date
                >= date.today(),
            )
            .order_by(
                DoctorSlot.slot_date.asc(),
                DoctorSlot.start_time.asc(),
            )
            .all()
        )

        return templates.TemplateResponse(
            request,
            "doctors/detail.html",
            {
                "doctor": doctor,
                "doctor_user": doctor_user,
                "specialization":
                    specialization,
                "slots": slots,
                "not_found": False,
            },
        )

    except Exception as exc:

        logger.exception(
            "Doctor profile error: %s",
            exc,
        )

        return templates.TemplateResponse(
            request,
            "doctors/detail.html",
            {
                "not_found": True,
                "doctor": None,
                "doctor_user": None,
                "specialization": None,
                "slots": [],
            },
            status_code=500,
        )


# ============================================================
# APPOINTMENT BOOKING PAGE
# ============================================================

@app.get(
    "/appointments/book",
    response_class=HTMLResponse,
)
@app.get(
    "/appointments/book/{slot_id}",
    response_class=HTMLResponse,
)
async def appointment_booking_page(
    request: Request,
    slot_id: int | None = None,
    db: Session = Depends(get_db),
):

    patient = get_current_patient(
        request,
        db,
    )

    if not patient:

        if slot_id:

            booking_url = (
                f"/appointments/book"
                f"?slot_id={slot_id}"
            )

            request.session[
                "post_login_redirect"
            ] = booking_url

            return RedirectResponse(
                f"/login?next="
                f"{quote(booking_url, safe='')}",
                status_code=303,
            )

        return RedirectResponse(
            "/login",
            status_code=303,
        )

    if not slot_id:

        return HTMLResponse(
            """
            <h2>Appointment slot missing</h2>
            <p>Please select a valid appointment slot.</p>
            <a href="/doctors">Browse Doctors</a>
            """,
            status_code=400,
        )

    slot = (
        db.query(DoctorSlot)
        .filter(
            DoctorSlot.id == slot_id,
            DoctorSlot.status == "available",
        )
        .first()
    )

    if not slot:

        return HTMLResponse(
            """
            <h2>Slot not available</h2>
            <p>
                This appointment slot is already
                booked or no longer exists.
            </p>
            <a href="/doctors">
                Choose another doctor
            </a>
            """,
            status_code=409,
        )

    result = (
        db.query(
            Doctor,
            User,
            Specialization,
        )
        .join(
            User,
            Doctor.user_id == User.id,
        )
        .join(
            Specialization,
            Doctor.specialization_id
            == Specialization.id,
        )
        .filter(
            Doctor.id == slot.doctor_id
        )
        .first()
    )

    if not result:

        return HTMLResponse(
            """
            <h2>Doctor not found</h2>
            <a href="/doctors">
                Back to Doctors
            </a>
            """,
            status_code=404,
        )

    (
        doctor,
        doctor_user,
        specialization,
    ) = result

    return templates.TemplateResponse(
        request,
        "appointments/book.html",
        {
            "patient": patient,
            "slot": slot,
            "doctor": doctor,
            "doctor_user": doctor_user,
            "specialization": specialization,
            "error": None,
        },
    )


# ============================================================
# CREATE APPOINTMENT
# ============================================================

@app.post(
    "/appointments",
    response_class=HTMLResponse,
)
async def create_appointment(
    request: Request,
    slot_id: int = Form(...),
    problem_summary: str = Form(...),
    appointment_type: str = Form(...),
    db: Session = Depends(get_db),
):

    try:

        patient = get_current_patient(
            request,
            db,
        )

        if not patient:

            booking_url = (
                f"/appointments/book"
                f"?slot_id={slot_id}"
            )

            request.session[
                "post_login_redirect"
            ] = booking_url

            return RedirectResponse(
                f"/login?next="
                f"{quote(booking_url, safe='')}",
                status_code=303,
            )

        # ----------------------------------------------------
        # TYPE
        # ----------------------------------------------------

        allowed_types = {
            "online",
            "in_person",
        }

        if appointment_type not in allowed_types:

            return HTMLResponse(
                """
                <h2>Invalid appointment type</h2>
                <p>
                    Please select online or in-person.
                </p>
                <a href="/doctors">
                    Back to Doctors
                </a>
                """,
                status_code=400,
            )

        # ----------------------------------------------------
        # PROBLEM
        # ----------------------------------------------------

        problem_summary = (
            problem_summary.strip()
        )

        if not problem_summary:

            return HTMLResponse(
                """
                <h2>Problem description required</h2>
                <p>
                    Please describe the reason
                    for your visit.
                </p>
                <a href="/doctors">
                    Back to Doctors
                </a>
                """,
                status_code=400,
            )

        # ----------------------------------------------------
        # SLOT
        # ----------------------------------------------------

        slot = (
            db.query(DoctorSlot)
            .filter(
                DoctorSlot.id == slot_id
            )
            .with_for_update()
            .first()
        )

        if not slot:

            db.rollback()

            return HTMLResponse(
                """
                <h2>Slot not found</h2>
                <a href="/doctors">
                    Back to Doctors
                </a>
                """,
                status_code=404,
            )

        if slot.status != "available":

            db.rollback()

            return HTMLResponse(
                """
                <h2>Slot already booked</h2>
                <p>
                    Please choose another time.
                </p>
                <a href="/doctors">
                    Choose another slot
                </a>
                """,
                status_code=409,
            )

        # ----------------------------------------------------
        # DUPLICATE CHECK
        # ----------------------------------------------------

        existing_appointment = (
            db.query(Appointment)
            .filter(
                Appointment.patient_id
                == patient.id,
                Appointment.slot_id
                == slot.id,
            )
            .first()
        )

        if existing_appointment:

            db.rollback()

            return HTMLResponse(
                """
                <h2>Appointment already exists</h2>
                <p>
                    You have already booked
                    this appointment.
                </p>
                <a href="/patient/dashboard">
                    Go to Dashboard
                </a>
                """,
                status_code=409,
            )

        # ----------------------------------------------------
        # CREATE
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # DOCTOR INFORMATION
        # ----------------------------------------------------

        result = (
            db.query(
                Doctor,
                User,
                Specialization,
            )
            .join(
                User,
                Doctor.user_id == User.id,
            )
            .join(
                Specialization,
                Doctor.specialization_id
                == Specialization.id,
            )
            .filter(
                Doctor.id
                == appointment.doctor_id
            )
            .first()
        )

        if not result:

            return RedirectResponse(
                "/patient/dashboard",
                status_code=303,
            )

        (
            doctor,
            doctor_user,
            specialization,
        ) = result

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

        return HTMLResponse(
            """
            <h2>Appointment could not be booked</h2>
            <p>
                This appointment slot was already
                booked. Please select another slot.
            </p>
            <a href="/doctors">
                Browse Doctors
            </a>
            """,
            status_code=409,
        )

    except Exception as exc:

        db.rollback()

        logger.exception(
            "Appointment creation error: %s",
            exc,
        )

        raise CustomException(
            exc,
            sys,
        )


# ============================================================
# COVID SCREENING PAGE
# ============================================================

@app.get(
    "/predict",
    response_class=HTMLResponse,
)
async def predict_form(
    request: Request,
):

    return templates.TemplateResponse(
        request,
        "predict.html",
        {
            "result": None,
        },
    )


# ============================================================
# COVID PREDICTION
# ============================================================

@app.post(
    "/predict",
    response_class=HTMLResponse,
)
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

        data_df = (
            custom_data
            .get_data_as_dataframe()
        )

        result, probability = (
            PredictPipeline()
            .predict(data_df)
        )

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

        logger.exception(
            "Prediction error: %s",
            exc,
        )

        raise CustomException(
            exc,
            sys,
        )


# ============================================================
# PRETRAINED NLP PAGE
# ============================================================

@app.get(
    "/pretrained-nlp",
    response_class=HTMLResponse,
)
async def pretrained_nlp_form(
    request: Request,
):

    return templates.TemplateResponse(
        request,
        "pretrained_nlp.html",
        {
            "result": None,
            "form_data": {
                "query": "",
            },
            "error": None,
        },
    )


# ============================================================
# PRETRAINED NLP ANALYSIS
# ============================================================

@app.post(
    "/pretrained-nlp",
    response_class=HTMLResponse,
)
async def pretrained_nlp_analysis(
    request: Request,
    query: str = Form(...),
):

    try:

        query = query.strip()

        if not query:

            return templates.TemplateResponse(
                request,
                "pretrained_nlp.html",
                {
                    "result": None,
                    "form_data": {
                        "query": "",
                    },
                    "error":
                        "Please enter some text.",
                },
            )

        # ----------------------------------------------------
        # POS
        # ----------------------------------------------------

        pos_tags = get_pos_tags(
            query
        )

        # ----------------------------------------------------
        # NER
        # ----------------------------------------------------

        entities = extract_entities(
            query
        )

        # ----------------------------------------------------
        # SENTIMENT
        # ----------------------------------------------------

        sentiment = analyze_sentiment(
            query
        )

        # ----------------------------------------------------
        # SIMILAR WORDS
        # ----------------------------------------------------

        similar_words = []

        words = query.split()

        if words:

            first_word = (
                words[0].lower()
            )

            try:

                similar_words = (
                    most_similar_words(
                        first_word,
                        topn=5,
                    )
                )

            except Exception as exc:

                logger.warning(
                    "GloVe similarity failed "
                    "for %s: %s",
                    first_word,
                    exc,
                )

                similar_words = []

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
            {
                "result": result,
                "form_data": {
                    "query": query,
                },
                "error": None,
            },
        )

    except Exception as exc:

        logger.exception(
            "NLP analysis error: %s",
            exc,
        )

        return templates.TemplateResponse(
            request,
            "pretrained_nlp.html",
            {
                "result": None,
                "form_data": {
                    "query": query,
                },
                "error": str(exc),
            },
            status_code=500,
        )


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health")
async def health_check():

    return {
        "status": "ok",
        "application":
            "Vijayvargiya Clinic",
    }


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )