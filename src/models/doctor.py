from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import Numeric
from sqlalchemy import String
from sqlalchemy import Text

from sqlalchemy.sql import func

from src.config.database import Base


class Doctor(Base):

    __tablename__ = "doctors"


    # ==================================================
    # PRIMARY KEY
    # ==================================================

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )


    # ==================================================
    # USER
    # ==================================================

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        unique=True
    )


    # ==================================================
    # SPECIALIZATION
    # ==================================================

    specialization_id = Column(
        Integer,
        ForeignKey("specializations.id"),
        nullable=False
    )


    # ==================================================
    # PROFESSIONAL INFORMATION
    # ==================================================

    qualification = Column(
        String(255),
        nullable=True
    )


    experience_years = Column(
        Integer,
        default=0
    )


    consultation_fee = Column(
        Numeric(10, 2),
        nullable=False,
        default=0.00
    )


    # ==================================================
    # DOCTOR BIO
    # ==================================================

    bio = Column(
        Text,
        nullable=True
    )


    # ==================================================
    # PROFILE IMAGE
    # ==================================================

    profile_image = Column(
        String(255),
        nullable=True
    )


    # ==================================================
    # CLINIC
    # ==================================================

    clinic_address = Column(
        String(255),
        nullable=True
    )


    # ==================================================
    # AVAILABILITY
    # ==================================================

    is_available = Column(
        Boolean,
        nullable=False,
        default=True
    )


    # ==================================================
    # TIMESTAMPS
    # ==================================================

    created_at = Column(
        DateTime,
        server_default=func.now()
    )


    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now()
    )