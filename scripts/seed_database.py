from datetime import date, timedelta

from sqlalchemy import text

from src.config.database import SessionLocal


# ============================================================
# 1. SPECIALIZATIONS
# ============================================================

specializations = [
    ("General Medicine", "Common adult health conditions."),
    ("Cardiology", "Heart and cardiovascular care."),
    ("Dermatology", "Skin, hair, and nail care."),
    ("Orthopedics", "Bones, joints, and muscles."),
    ("Neurology", "Brain and nervous system care."),
    ("Pediatrics", "Child healthcare."),
    ("Gynecology", "Women's reproductive healthcare."),
    ("ENT", "Ear, nose, and throat care."),
]


# ============================================================
# 2. DOCTORS
# ============================================================

doctor_data = [
    (
        "Aarav Sharma",
        "aarav.sharma@vijayvargiyaclinic.com",
        "General Medicine",
        "MBBS, MD",
        8,
        500,
    ),
    (
        "Rohan Mehta",
        "rohan.mehta@vijayvargiyaclinic.com",
        "General Medicine",
        "MBBS, MD",
        10,
        600,
    ),
    (
        "Vivek Gupta",
        "vivek.gupta@vijayvargiyaclinic.com",
        "General Medicine",
        "MBBS, MD",
        7,
        500,
    ),
    (
        "Arjun Verma",
        "arjun.verma@vijayvargiyaclinic.com",
        "General Medicine",
        "MBBS, MD",
        12,
        700,
    ),
    (
        "Rahul Kapoor",
        "rahul.kapoor@vijayvargiyaclinic.com",
        "Cardiology",
        "MBBS, MD, DM Cardiology",
        12,
        1200,
    ),
    (
        "Ankit Sharma",
        "ankit.sharma@vijayvargiyaclinic.com",
        "Cardiology",
        "MBBS, MD, DM Cardiology",
        9,
        1000,
    ),
    (
        "Karan Malhotra",
        "karan.malhotra@vijayvargiyaclinic.com",
        "Cardiology",
        "MBBS, MD, DM Cardiology",
        15,
        1500,
    ),
    (
        "Aditya Jain",
        "aditya.jain@vijayvargiyaclinic.com",
        "Cardiology",
        "MBBS, MD, DM Cardiology",
        8,
        1000,
    ),
    (
        "Neha Sharma",
        "neha.sharma@vijayvargiyaclinic.com",
        "Dermatology",
        "MBBS, MD Dermatology",
        7,
        700,
    ),
    (
        "Priya Mehta",
        "priya.mehta@vijayvargiyaclinic.com",
        "Dermatology",
        "MBBS, MD Dermatology",
        10,
        800,
    ),
    (
        "Riya Kapoor",
        "riya.kapoor@vijayvargiyaclinic.com",
        "Dermatology",
        "MBBS, MD Dermatology",
        6,
        600,
    ),
    (
        "Simran Gupta",
        "simran.gupta@vijayvargiyaclinic.com",
        "Dermatology",
        "MBBS, MD Dermatology",
        11,
        900,
    ),
    (
        "Manish Verma",
        "manish.verma@vijayvargiyaclinic.com",
        "Orthopedics",
        "MBBS, MS Orthopedics",
        10,
        800,
    ),
    (
        "Nitin Sharma",
        "nitin.sharma@vijayvargiyaclinic.com",
        "Orthopedics",
        "MBBS, MS Orthopedics",
        13,
        1000,
    ),
    (
        "Saurabh Jain",
        "saurabh.jain@vijayvargiyaclinic.com",
        "Orthopedics",
        "MBBS, MS Orthopedics",
        8,
        700,
    ),
    (
        "Mohit Agarwal",
        "mohit.agarwal@vijayvargiyaclinic.com",
        "Orthopedics",
        "MBBS, MS Orthopedics",
        15,
        1100,
    ),
    (
        "Rajiv Mehta",
        "rajiv.mehta@vijayvargiyaclinic.com",
        "Neurology",
        "MBBS, MD, DM Neurology",
        14,
        1200,
    ),
    (
        "Amit Kapoor",
        "amit.kapoor@vijayvargiyaclinic.com",
        "Neurology",
        "MBBS, MD, DM Neurology",
        9,
        1000,
    ),
    (
        "Vikas Sharma",
        "vikas.sharma@vijayvargiyaclinic.com",
        "Neurology",
        "MBBS, MD, DM Neurology",
        11,
        1100,
    ),
    (
        "Deepak Gupta",
        "deepak.gupta@vijayvargiyaclinic.com",
        "Neurology",
        "MBBS, MD, DM Neurology",
        7,
        900,
    ),
    (
        "Pooja Sharma",
        "pooja.sharma@vijayvargiyaclinic.com",
        "Pediatrics",
        "MBBS, MD Pediatrics",
        8,
        600,
    ),
    (
        "Anjali Verma",
        "anjali.verma@vijayvargiyaclinic.com",
        "Pediatrics",
        "MBBS, MD Pediatrics",
        10,
        700,
    ),
    (
        "Kavita Mehta",
        "kavita.mehta@vijayvargiyaclinic.com",
        "Pediatrics",
        "MBBS, MD Pediatrics",
        6,
        500,
    ),
    (
        "Shweta Jain",
        "shweta.jain@vijayvargiyaclinic.com",
        "Pediatrics",
        "MBBS, MD Pediatrics",
        12,
        800,
    ),
    (
        "Drishti Kapoor",
        "drishti.kapoor@vijayvargiyaclinic.com",
        "Gynecology",
        "MBBS, MD Gynecology",
        9,
        800,
    ),
    (
        "Nisha Sharma",
        "nisha.sharma@vijayvargiyaclinic.com",
        "Gynecology",
        "MBBS, MD Gynecology",
        11,
        900,
    ),
    (
        "Meena Gupta",
        "meena.gupta@vijayvargiyaclinic.com",
        "Gynecology",
        "MBBS, MD Gynecology",
        7,
        700,
    ),
    (
        "Ayesha Khan",
        "ayesha.khan@vijayvargiyaclinic.com",
        "Gynecology",
        "MBBS, MD Gynecology",
        13,
        1000,
    ),
    (
        "Rakesh Verma",
        "rakesh.verma@vijayvargiyaclinic.com",
        "ENT",
        "MBBS, MS ENT",
        10,
        700,
    ),
    (
        "Sandeep Sharma",
        "sandeep.sharma@vijayvargiyaclinic.com",
        "ENT",
        "MBBS, MS ENT",
        8,
        600,
    ),
    (
        "Tarun Mehta",
        "tarun.mehta@vijayvargiyaclinic.com",
        "ENT",
        "MBBS, MS ENT",
        12,
        800,
    ),
    (
        "Akash Gupta",
        "akash.gupta@vijayvargiyaclinic.com",
        "ENT",
        "MBBS, MS ENT",
        6,
        500,
    ),
]


# ============================================================
# 3. SEED SPECIALIZATIONS
# ============================================================

def seed_specializations(db):
    print("\nAdding specializations...")

    for name, description in specializations:

        existing = db.execute(
            text(
                """
                SELECT id
                FROM specializations
                WHERE name = :name
                """
            ),
            {
                "name": name
            },
        ).fetchone()

        if existing:
            continue

        db.execute(
            text(
                """
                INSERT INTO specializations
                (
                    name,
                    description
                )
                VALUES
                (
                    :name,
                    :description
                )
                """
            ),
            {
                "name": name,
                "description": description,
            },
        )

    db.commit()

    print(
        f"Specializations processed: {len(specializations)}"
    )


# ============================================================
# 4. SEED DOCTORS
# ============================================================

def seed_doctors(db):
    print("\nAdding doctors...")

    doctor_count = 0

    for (
        name,
        email,
        specialty,
        qualification,
        experience,
        fee,
    ) in doctor_data:

        # ----------------------------------------------------
        # Find doctor user
        # ----------------------------------------------------

        user = db.execute(
            text(
                """
                SELECT id
                FROM users
                WHERE email = :email
                """
            ),
            {
                "email": email
            },
        ).fetchone()

        # ----------------------------------------------------
        # Create doctor user if not exists
        # ----------------------------------------------------

        if not user:

            db.execute(
                text(
                    """
                    INSERT INTO users
                    (
                        full_name,
                        email,
                        password_hash,
                        role
                    )
                    VALUES
                    (
                        :name,
                        :email,
                        :password,
                        'doctor'
                    )
                    """
                ),
                {
                    "name": name,
                    "email": email,
                    "password": "demo_password",
                },
            )

            db.commit()

            user = db.execute(
                text(
                    """
                    SELECT id
                    FROM users
                    WHERE email = :email
                    """
                ),
                {
                    "email": email
                },
            ).fetchone()

        # ----------------------------------------------------
        # Find specialization
        # ----------------------------------------------------

        specialization = db.execute(
            text(
                """
                SELECT id
                FROM specializations
                WHERE name = :name
                """
            ),
            {
                "name": specialty
            },
        ).fetchone()

        if not specialization:

            print(
                f"Skipping {name}: "
                f"specialization not found."
            )

            continue

        # ----------------------------------------------------
        # Check doctor profile
        # ----------------------------------------------------

        existing_doctor = db.execute(
            text(
                """
                SELECT id
                FROM doctors
                WHERE user_id = :user_id
                """
            ),
            {
                "user_id": user.id
            },
        ).fetchone()

        # ----------------------------------------------------
        # Create doctor profile
        # ----------------------------------------------------

        if not existing_doctor:

            db.execute(
                text(
                    """
                    INSERT INTO doctors
                    (
                        user_id,
                        specialization_id,
                        qualification,
                        experience_years,
                        consultation_fee,
                        clinic_address,
                        is_available
                    )
                    VALUES
                    (
                        :user_id,
                        :specialization_id,
                        :qualification,
                        :experience,
                        :fee,
                        :address,
                        TRUE
                    )
                    """
                ),
                {
                    "user_id": user.id,
                    "specialization_id": specialization.id,
                    "qualification": qualification,
                    "experience": experience,
                    "fee": fee,
                    "address": "Vijayvargiya Clinic, Jaipur",
                },
            )

            doctor_count += 1

    db.commit()

    print(
        f"New doctors created: {doctor_count}"
    )


# ============================================================
# 5. GENERATE DOCTOR SLOTS
# ============================================================

def generate_doctor_slots(db):
    print("\nGenerating doctor slots...")

    # --------------------------------------------------------
    # Start from today
    # --------------------------------------------------------

    start_date = date.today()

    # --------------------------------------------------------
    # Six slots per day
    # --------------------------------------------------------

    slot_times = [
        ("10:00", "10:30"),
        ("10:30", "11:00"),
        ("11:00", "11:30"),
        ("17:00", "17:30"),
        ("17:30", "18:00"),
        ("18:00", "18:30"),
    ]

    # --------------------------------------------------------
    # Get all doctors
    # --------------------------------------------------------

    doctors = db.execute(
        text(
            """
            SELECT id
            FROM doctors
            WHERE is_available = TRUE
            """
        )
    ).fetchall()

    total_slots = 0

    # ========================================================
    # IMPORTANT
    # Slots are generated separately for EACH doctor.
    #
    # Example:
    #
    # Doctor 1 -> slot 10:00
    # Doctor 2 -> slot 10:00
    # Doctor 3 -> slot 10:00
    #
    # These are different records because doctor_id differs.
    # ========================================================

    for doctor in doctors:

        for day in range(7):

            slot_date = (
                start_date
                + timedelta(days=day)
            )

            for start_time, end_time in slot_times:

                # ------------------------------------------------
                # Check whether THIS doctor already has THIS slot
                # ------------------------------------------------

                existing = db.execute(
                    text(
                        """
                        SELECT id
                        FROM doctor_slots
                        WHERE doctor_id = :doctor_id
                        AND slot_date = :slot_date
                        AND start_time = :start_time
                        AND end_time = :end_time
                        """
                    ),
                    {
                        "doctor_id": doctor.id,
                        "slot_date": slot_date,
                        "start_time": start_time,
                        "end_time": end_time,
                    },
                ).fetchone()

                if existing:
                    continue

                # ------------------------------------------------
                # Create slot
                # ------------------------------------------------

                db.execute(
                    text(
                        """
                        INSERT INTO doctor_slots
                        (
                            doctor_id,
                            slot_date,
                            start_time,
                            end_time,
                            status
                        )
                        VALUES
                        (
                            :doctor_id,
                            :slot_date,
                            :start_time,
                            :end_time,
                            'available'
                        )
                        """
                    ),
                    {
                        "doctor_id": doctor.id,
                        "slot_date": slot_date,
                        "start_time": start_time,
                        "end_time": end_time,
                    },
                )

                total_slots += 1

    db.commit()

    print(
        f"New doctor slots created: {total_slots}"
    )


# ============================================================
# 6. MAIN
# ============================================================

def main():

    db = SessionLocal()

    try:

        print("=" * 60)
        print("VIJAYVARGIYA CLINIC DATABASE SEED")
        print("=" * 60)

        # Step 1
        seed_specializations(db)

        # Step 2
        seed_doctors(db)

        # Step 3
        generate_doctor_slots(db)

        print("\n" + "=" * 60)
        print("SEED COMPLETED SUCCESSFULLY")
        print("=" * 60)

    except Exception as e:

        db.rollback()

        print("\nSEED FAILED")
        print("----------------------------------------")
        print(e)

    finally:

        db.close()


# ============================================================
# 7. RUN
# ============================================================

if __name__ == "__main__":
    main()