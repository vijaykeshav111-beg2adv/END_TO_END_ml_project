from sqlalchemy import Column
from sqlalchemy import Date
from sqlalchemy import DateTime
from sqlalchemy import Enum
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import Time
from sqlalchemy.sql import func

from src.config.database import Base


class DoctorSlot(Base):

    __tablename__ = "doctor_slots"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    doctor_id = Column(
        Integer,
        ForeignKey("doctors.id"),
        nullable=False,
        index=True
    )

    slot_date = Column(
        Date,
        nullable=False,
        index=True
    )

    start_time = Column(
        Time,
        nullable=False
    )

    end_time = Column(
        Time,
        nullable=False
    )

    status = Column(
        Enum(
            "available",
            "booked",
            "blocked"
        ),
        nullable=False,
        default="available",
        index=True
    )

    created_at = Column(
        DateTime,
        server_default=func.now()
    )