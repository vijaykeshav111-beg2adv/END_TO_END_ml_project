from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import Enum
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import Text
from sqlalchemy.sql import func

from src.config.database import Base


class Appointment(Base):

    __tablename__ = "appointments"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    patient_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    doctor_id = Column(
        Integer,
        ForeignKey("doctors.id"),
        nullable=False,
        index=True
    )

    slot_id = Column(
        Integer,
        ForeignKey("doctor_slots.id"),
        nullable=False,
        unique=True,
        index=True
    )

    problem_summary = Column(
        Text,
        nullable=True
    )

    status = Column(
        Enum(
            "pending",
            "confirmed",
            "completed",
            "cancelled"
        ),
        nullable=False,
        default="pending"
    )

    appointment_type = Column(
        Enum(
            "online",
            "in_person"
        ),
        nullable=False,
        default="in_person"
    )

    created_at = Column(
        DateTime,
        server_default=func.now()
    )

    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now()
    )