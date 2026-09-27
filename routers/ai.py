from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.models.chat import ChatSession
from src.models.chat_message import ChatMessage
from src.services.groq_service import ask_groq


router = APIRouter(
    prefix="/api/ai",
    tags=["AI Assistant"]
)


@router.post("/chat")
async def chat_with_groq(
    request: Request,
    db: Session = Depends(get_db),
):

    # -----------------------------------------
    # CHECK LOGIN
    # -----------------------------------------

    patient_id = request.session.get("user_id")

    print("================================")
    print("AI CHAT REQUEST")
    print("patient_id:", patient_id)
    print("================================")

    if not patient_id:
        raise HTTPException(
            status_code=401,
            detail="Please login first."
        )

    # -----------------------------------------
    # READ JSON
    # -----------------------------------------

    try:
        data = await request.json()

        print("Request data:", data)

    except Exception as exc:

        print("JSON ERROR:", exc)

        raise HTTPException(
            status_code=400,
            detail="Invalid JSON request."
        )

    user_message = data.get(
        "message",
        ""
    ).strip()

    if not user_message:

        raise HTTPException(
            status_code=400,
            detail="Message is required."
        )

    print("User message:", user_message)

    # -----------------------------------------
    # FIND CHAT SESSION
    # -----------------------------------------

    try:

        chat_session = (
            db.query(ChatSession)
            .filter(
                ChatSession.patient_id == patient_id
            )
            .order_by(
                ChatSession.id.desc()
            )
            .first()
        )

        if not chat_session:

            print("Creating new chat session")

            chat_session = ChatSession(
                patient_id=patient_id
            )

            db.add(chat_session)
            db.commit()
            db.refresh(chat_session)

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
            detail=f"Database error: {str(exc)}"
        )

    # -----------------------------------------
    # SAVE USER MESSAGE
    # -----------------------------------------

    try:

        user_chat = ChatMessage(
            session_id=chat_session.id,
            role="user",
            message=user_message,
        )

        db.add(user_chat)
        db.commit()

        print("User message saved")

    except Exception as exc:

        db.rollback()

        print(
            "MESSAGE SAVE ERROR:",
            repr(exc)
        )

        raise HTTPException(
            status_code=500,
            detail=f"Message database error: {str(exc)}"
        )

    # -----------------------------------------
    # GET HISTORY
    # -----------------------------------------

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
                "content": (
                    "You are the AI assistant "
                    "for Vijayvargiya Clinic. "
                    "Provide general health "
                    "information clearly. "
                    "Do not diagnose diseases. "
                    "Do not replace a qualified "
                    "doctor. "
                    "For emergencies, advise "
                    "the patient to seek "
                    "immediate medical attention."
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
            detail=f"History error: {str(exc)}"
        )

    # -----------------------------------------
    # GROQ
    # -----------------------------------------

    try:

        print("Calling Groq...")

        assistant_response = ask_groq(
            messages
        )

        print("Groq response received")

    except Exception as exc:

        db.rollback()

        print(
            "GROQ ERROR:",
            repr(exc)
        )

        raise HTTPException(
            status_code=500,
            detail=f"Groq API error: {str(exc)}"
        )

    # -----------------------------------------
    # SAVE ASSISTANT
    # -----------------------------------------

    try:

        assistant_chat = ChatMessage(
            session_id=chat_session.id,
            role="assistant",
            message=assistant_response,
        )

        db.add(assistant_chat)
        db.commit()

        print("Assistant response saved")

    except Exception as exc:

        db.rollback()

        print(
            "ASSISTANT SAVE ERROR:",
            repr(exc)
        )

        raise HTTPException(
            status_code=500,
            detail=f"Assistant database error: {str(exc)}"
        )

    # -----------------------------------------
    # RETURN
    # -----------------------------------------

    return {
        "success": True,
        "session_id": chat_session.id,
        "message": assistant_response,
    }