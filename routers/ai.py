
import json
import re
from datetime import date, timedelta, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.models.chat import ChatSession
from src.models.chat_message import ChatMessage
from src.models import User, Doctor, Specialization, DoctorSlot
from src.services.groq_service import ask_groq


router = APIRouter(
    prefix="/api/ai",
    tags=["AI Assistant"]
)


# ============================================================
# AI SYSTEM PROMPT
# ============================================================

def build_system_prompt(specialization_names):
    specialization_list = ", ".join(specialization_names)

    return f"""
You are the AI assistant for Vijayvargiya Clinic.

Your job is to:

1. Understand the patient's health problem.
2. Provide general health information.
3. Identify which medical specialization is most relevant.
4. Recommend doctors only from the specializations provided by the clinic.
5. Never claim to diagnose the patient.
6. Never prescribe medicines.
7. For emergency symptoms, advise immediate medical care.
8. Keep medical advice general and encourage professional evaluation when appropriate.
9. Do not invent doctors, specialties, appointment slots, prices, or clinic information.
10. If the patient asks about appointment availability, the clinic backend will provide the actual availability.
11. Never invent an appointment count.
12. Do not say that a doctor has a certain number of slots unless that information is provided by the clinic backend.

AVAILABLE CLINIC SPECIALIZATIONS:

{specialization_list}

IMPORTANT:

Return your answer in EXACTLY this JSON format:

{{
    "specialization": "EXACT specialization name from the list",
    "response": "Your helpful response to the patient"
}}

If you cannot determine a suitable specialization, use:

{{
    "specialization": null,
    "response": "Your helpful response"
}}

The specialization must exactly match one of the available clinic specializations.
"""


# ============================================================
# EXTRACT JSON FROM GROQ RESPONSE
# ============================================================

def extract_ai_json(text: str):

    if not text:
        return {
            "specialization": None,
            "response": ""
        }

    text = text.strip()

    # --------------------------------------------------------
    # 1. Direct JSON
    # --------------------------------------------------------

    try:
        result = json.loads(text)

        if isinstance(result, dict):
            return {
                "specialization": result.get("specialization"),
                "response": result.get("response", "")
            }

    except (json.JSONDecodeError, TypeError):
        pass

    # --------------------------------------------------------
    # 2. JSON inside markdown code block
    # --------------------------------------------------------

    code_block_match = re.search(
        r"```(?:json)?\s*(\{.*?\})\s*```",
        text,
        re.DOTALL | re.IGNORECASE
    )

    if code_block_match:

        try:
            result = json.loads(
                code_block_match.group(1)
            )

            if isinstance(result, dict):
                return {
                    "specialization": result.get(
                        "specialization"
                    ),
                    "response": result.get(
                        "response",
                        ""
                    )
                }

        except (json.JSONDecodeError, TypeError):
            pass

    # --------------------------------------------------------
    # 3. Find JSON object inside normal text
    # --------------------------------------------------------

    decoder = json.JSONDecoder()

    for match in re.finditer(r"\{", text):

        try:

            result, _ = decoder.raw_decode(
                text[match.start():]
            )

            if isinstance(result, dict):

                return {
                    "specialization": result.get(
                        "specialization"
                    ),
                    "response": result.get(
                        "response",
                        ""
                    )
                }

        except json.JSONDecodeError:
            continue

    # --------------------------------------------------------
    # 4. Fallback
    # --------------------------------------------------------

    return {
        "specialization": None,
        "response": text
    }


# ============================================================
# DETECT APPOINTMENT DATE FROM USER MESSAGE
# ============================================================

def detect_requested_date(user_message: str):
    """
    Detect whether the patient is asking for appointments
    for today, tomorrow, or a specific date.

    Returns:
        date object or None
    """

    if not user_message:
        return None

    text = user_message.lower().strip()

    today = date.today()

    # --------------------------------------------------------
    # TODAY
    # --------------------------------------------------------

    today_keywords = [
        "today",
        "for today",
        "available today",
        "appointment today",
        "appointments today",
        "slot today",
        "slots today"
    ]

    for keyword in today_keywords:

        if keyword in text:
            return today

    # --------------------------------------------------------
    # TOMORROW
    # --------------------------------------------------------

    tomorrow_keywords = [
        "tomorrow",
        "for tomorrow",
        "available tomorrow",
        "appointment tomorrow",
        "appointments tomorrow",
        "slot tomorrow",
        "slots tomorrow"
    ]

    for keyword in tomorrow_keywords:

        if keyword in text:
            return today + timedelta(days=1)

    # --------------------------------------------------------
    # DD-MM-YYYY
    # DD/MM/YYYY
    # DD.MM.YYYY
    # --------------------------------------------------------

    date_match = re.search(
        r"\b(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})\b",
        text
    )

    if date_match:

        try:

            day = int(
                date_match.group(1)
            )

            month = int(
                date_match.group(2)
            )

            year = int(
                date_match.group(3)
            )

            return date(
                year,
                month,
                day
            )

        except ValueError:
            return None

    # --------------------------------------------------------
    # YYYY-MM-DD
    # --------------------------------------------------------

    iso_match = re.search(
        r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b",
        text
    )

    if iso_match:

        try:

            year = int(
                iso_match.group(1)
            )

            month = int(
                iso_match.group(2)
            )

            day = int(
                iso_match.group(3)
            )

            return date(
                year,
                month,
                day
            )

        except ValueError:
            return None

    return None


# ============================================================
# FIND RECOMMENDED DOCTORS
# ============================================================

def get_recommended_doctors(
    db: Session,
    specialization_name: str,
    requested_date=None,
):

    if not specialization_name:
        return []

    # --------------------------------------------------------
    # FIND DOCTORS
    # --------------------------------------------------------

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
            Doctor.is_available == True,
            Specialization.name
            == specialization_name,
        )
        .order_by(
            Doctor.id.asc()
        )
        .all()
    )

    doctors = []

    for (
        doctor,
        doctor_user,
        specialization,
    ) in result:

        # ----------------------------------------------------
        # AVAILABLE SLOTS
        # ----------------------------------------------------

        slot_query = (
            db.query(DoctorSlot)
            .filter(
                DoctorSlot.doctor_id
                == doctor.id,

                DoctorSlot.status
                == "available",
            )
        )

        # ----------------------------------------------------
        # IMPORTANT:
        #
        # If the patient asks "today", only today's slots
        # are counted.
        #
        # If the patient asks "tomorrow", only tomorrow's
        # slots are counted.
        #
        # If the patient does not specify a date, all
        # currently available slots are counted.
        # ----------------------------------------------------

        if requested_date is not None:

            slot_query = slot_query.filter(
                DoctorSlot.slot_date
                == requested_date
            )

        slots = (
            slot_query
            .order_by(
                DoctorSlot.slot_date.asc(),
                DoctorSlot.start_time.asc(),
            )
            .all()
        )

        doctors.append(
            {
                "doctor_id": doctor.id,

                "name": (
                    doctor_user.full_name
                    if doctor_user
                    else "Doctor"
                ),

                "specialization":
                    specialization.name,

                "qualification":
                    doctor.qualification,

                "experience_years":
                    doctor.experience_years,

                "consultation_fee":
                    float(
                        doctor.consultation_fee
                    )
                    if doctor.consultation_fee
                    is not None
                    else None,

                "clinic_address":
                    doctor.clinic_address,

                "profile_image":
                    getattr(
                        doctor,
                        "profile_image",
                        None
                    ),

                "is_available":
                    doctor.is_available,

                # ALL matching slots are returned.
                # No .limit(5)
                "available_slots": [

                    {
                        "slot_id": slot.id,

                        "date": str(
                            slot.slot_date
                        ),

                        "start_time": str(
                            slot.start_time
                        ),

                        "end_time": str(
                            slot.end_time
                        ),

                    }

                    for slot in slots
                ],
            }
        )

    return doctors


# ============================================================
# CHAT ENDPOINT
# ============================================================

@router.post("/chat")
async def chat_with_groq(
    request: Request,
    db: Session = Depends(get_db),
):

    # ========================================================
    # CHECK LOGIN
    # ========================================================

    patient_id = request.session.get(
        "user_id"
    )

    print("================================")
    print("AI CHAT REQUEST")
    print("patient_id:", patient_id)
    print("================================")

    if not patient_id:

        raise HTTPException(
            status_code=401,
            detail="Please login first."
        )

    # ========================================================
    # VERIFY USER
    # ========================================================

    patient = (
        db.query(User)
        .filter(
            User.id == patient_id,
            User.role == "patient"
        )
        .first()
    )

    if not patient:

        raise HTTPException(
            status_code=401,
            detail="Patient account not found."
        )

    # ========================================================
    # READ REQUEST JSON
    # ========================================================

    try:

        data = await request.json()

        print(
            "Request data:",
            data
        )

    except Exception as exc:

        print(
            "JSON ERROR:",
            repr(exc)
        )

        raise HTTPException(
            status_code=400,
            detail="Invalid JSON request."
        )

    user_message = data.get(
        "message",
        ""
    )

    if not isinstance(
        user_message,
        str
    ):

        raise HTTPException(
            status_code=400,
            detail="Message must be text."
        )

    user_message = user_message.strip()

    if not user_message:

        raise HTTPException(
            status_code=400,
            detail="Message is required."
        )

    print(
        "User message:",
        user_message
    )

    # ========================================================
    # DETECT REQUESTED DATE
    # ========================================================

    requested_date = detect_requested_date(
        user_message
    )

    print(
        "Requested appointment date:",
        requested_date
    )

    # ========================================================
    # GET SPECIALIZATIONS
    # ========================================================

    try:

        specializations = (
            db.query(Specialization)
            .order_by(
                Specialization.name.asc()
            )
            .all()
        )

        specialization_names = [
            specialization.name
            for specialization
            in specializations
        ]

        print(
            "Clinic specializations:",
            specialization_names
        )

    except Exception as exc:

        print(
            "SPECIALIZATION ERROR:",
            repr(exc)
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to load clinic "
                "specializations."
            )
        )

    # ========================================================
    # FIND OR CREATE CHAT SESSION
    # ========================================================

    try:

        chat_session = (
            db.query(ChatSession)
            .filter(
                ChatSession.patient_id
                == patient_id
            )
            .order_by(
                ChatSession.id.desc()
            )
            .first()
        )

        if not chat_session:

            print(
                "Creating new chat session"
            )

            chat_session = ChatSession(
                patient_id=patient_id
            )

            db.add(
                chat_session
            )

            db.commit()

            db.refresh(
                chat_session
            )

        print(
            "Chat session:",
            chat_session.id
        )

    except Exception as exc:

        db.rollback()

        print(
            "DATABASE SESSION ERROR:",
            repr(exc)
        )

        raise HTTPException(
            status_code=500,
            detail=(
                f"Database error: {str(exc)}"
            )
        )

    # ========================================================
    # SAVE USER MESSAGE
    # ========================================================

    try:

        user_chat = ChatMessage(
            session_id=chat_session.id,
            role="user",
            message=user_message,
        )

        db.add(
            user_chat
        )

        db.commit()

        print(
            "User message saved"
        )

    except Exception as exc:

        db.rollback()

        print(
            "MESSAGE SAVE ERROR:",
            repr(exc)
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Message database error: "
                f"{str(exc)}"
            )
        )

    # ========================================================
    # GET CHAT HISTORY
    # ========================================================

    try:

        previous_messages = (
            db.query(ChatMessage)
            .filter(
                ChatMessage.session_id
                == chat_session.id
            )
            .order_by(
                ChatMessage.id.asc()
            )
            .all()
        )

        messages = [

            {
                "role": "system",

                "content":
                    build_system_prompt(
                        specialization_names
                    ),
            }

        ]

        for msg in previous_messages:

            messages.append(
                {
                    "role": msg.role,
                    "content": msg.message,
                }
            )

        print(
            "Messages sent to Groq:",
            len(messages)
        )

    except Exception as exc:

        print(
            "HISTORY ERROR:",
            repr(exc)
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "History error: "
                f"{str(exc)}"
            )
        )

    # ========================================================
    # CALL GROQ
    # ========================================================

    try:

        print(
            "Calling Groq..."
        )

        raw_response = ask_groq(
            messages
        )

        print(
            "Groq raw response:",
            raw_response
        )

    except Exception as exc:

        db.rollback()

        print(
            "GROQ ERROR:",
            repr(exc)
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Groq API error: "
                f"{str(exc)}"
            )
        )

    # ========================================================
    # PARSE AI RESPONSE
    # ========================================================

    ai_result = extract_ai_json(
        raw_response
    )

    specialization_name = (
        ai_result.get(
            "specialization"
        )
    )

    assistant_response = (
        ai_result.get(
            "response"
        )
        or raw_response
    )

    # ========================================================
    # MAKE SURE SPECIALIZATION IS STRING
    # ========================================================

    if specialization_name:

        specialization_name = str(
            specialization_name
        ).strip()

    # ========================================================
    # VERIFY SPECIALIZATION
    # ========================================================

    if specialization_name:

        matching_specialization = (
            db.query(Specialization)
            .filter(
                Specialization.name
                == specialization_name
            )
            .first()
        )

        if not matching_specialization:

            print(
                "AI returned invalid "
                "specialization:",
                specialization_name
            )

            specialization_name = None

    # ========================================================
    # FIND DOCTORS
    # ========================================================

    recommended_doctors = []

    if specialization_name:

        recommended_doctors = (
            get_recommended_doctors(
                db,
                specialization_name,
                requested_date
            )
        )

    print(
        "Recommended specialization:",
        specialization_name
    )

    print(
        "Requested date:",
        requested_date
    )

    print(
        "Recommended doctors:",
        len(
            recommended_doctors
        )
    )

    # ========================================================
    # BUILD FINAL RESPONSE
    # ========================================================

    final_message = assistant_response

    if specialization_name:

        final_message += (
            "\n\n"
            "🏥 Recommended department: "
            f"{specialization_name}"
        )

        # ----------------------------------------------------
        # DATE INFORMATION
        # ----------------------------------------------------

        if requested_date:

            final_message += (
                "\n\n"
                "📅 Appointment date: "
                f"{requested_date.strftime('%d-%m-%Y')}"
            )

        # ----------------------------------------------------
        # DOCTORS
        # ----------------------------------------------------

        if recommended_doctors:

            final_message += (
                "\n\n"
                "Available doctors:"
            )

            for index, doctor in enumerate(
                recommended_doctors,
                start=1
            ):

                final_message += (
                    "\n\n"
                    f"{index}. "
                    f"Dr. {doctor['name']}"
                )

                if doctor[
                    "qualification"
                ]:

                    final_message += (
                        "\nQualification: "
                        f"{doctor['qualification']}"
                    )

                if doctor[
                    "experience_years"
                ] is not None:

                    final_message += (
                        "\nExperience: "
                        f"{doctor['experience_years']}"
                        " years"
                    )

                if doctor[
                    "consultation_fee"
                ] is not None:

                    final_message += (
                        "\nConsultation fee: ₹"
                        f"{doctor['consultation_fee']}"
                    )

                # ------------------------------------------------
                # EXACT SLOT COUNT
                # ------------------------------------------------

                slot_count = len(
                    doctor[
                        "available_slots"
                    ]
                )

                if requested_date:

                    final_message += (
                        "\nAvailable slots "
                        "for this date: "
                        f"{slot_count}"
                    )

                else:

                    final_message += (
                        "\nAvailable slots: "
                        f"{slot_count}"
                    )

            final_message += (
                "\n\n"
                "Please select a doctor "
                "to see the available "
                "appointment slots."
            )

        else:

            if requested_date:

                final_message += (
                    "\n\n"
                    "Currently, no available "
                    "doctor was found with "
                    "available slots on "
                    f"{requested_date.strftime('%d-%m-%Y')}."
                )

            else:

                final_message += (
                    "\n\n"
                    "Currently, no available "
                    "doctor was found in this "
                    "department."
                )

    # ========================================================
    # SAVE ASSISTANT MESSAGE
    # ========================================================

    try:

        assistant_chat = ChatMessage(
            session_id=chat_session.id,
            role="assistant",
            message=final_message,
        )

        db.add(
            assistant_chat
        )

        db.commit()

        print(
            "Assistant response saved"
        )

    except Exception as exc:

        db.rollback()

        print(
            "ASSISTANT SAVE ERROR:",
            repr(exc)
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Assistant save error: "
                f"{str(exc)}"
            )
        )

    # ========================================================
    # RETURN RESPONSE
    # ========================================================

    return {

        "success": True,

        "session_id":
            chat_session.id,

        "message":
            final_message,

        "recommendation": {

            "specialization":
                specialization_name,

            "requested_date":
                str(requested_date)
                if requested_date
                else None,

            "doctors":
                recommended_doctors,
        }
    }

