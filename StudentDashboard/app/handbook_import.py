from app.models import Course, Lesson


VOLUME_COURSES = [
    {
        "title": "Volume I - Learning by Doing",
        "level": "Design Thinking",
        "description": "Design Thinking foundation, problem-solving process, and real student innovation case studies.",
        "resource_url": "/static/uploads/curriculum/atl-handbook-vol-i-karnataka.pdf",
        "lessons": [
            ("Design Thinking", "Core introduction to design thinking for schools."),
            ("Children as Problem Solvers", "Understanding children as creators and problem solvers."),
            ("Why Do We Need Design Thinking?", "Purpose and need for design thinking in ATL learning."),
            ("Key Features of Design Thinking", "Main features of a design-thinking approach."),
            ("How to Engage in the Process of Design Thinking?", "Guidance for using the process in school projects."),
            ("5 Key Steps in the Process of Design Thinking", "Empathise, Define, Ideate, Prototype, and Test."),
            ("Paddy Dryer: A Sustainable Solution for Protecting Crops in Rural India", "Case study with design thinking format."),
            ("Smart Sprayer: A Lightweight, Long-Lasting Solution for Farmers", "Case study with design thinking format."),
            ("Smart-Hand Gloves for People with Paralysis: Giving Voice to Basic Needs", "Case study with design thinking format."),
            ("Hope Arm: A Functional, Affordable Prosthetic for Amputees", "Case study with design thinking format."),
            ("The Farmers' Baton: A Safety Guide for Night-Time", "Case study with design thinking format."),
            ("The Peanut Peeler: Cracking the Challenge", "Case study with design thinking format."),
            ("Sample Design Thinking Format", "Blank/sample format for students to document their own projects."),
        ],
    },
    {
        "title": "Volume II - Grades 6-8 ATL Activities",
        "level": "Grades 6-8",
        "description": "ATL-integrated classroom activity plans for Grades 6-8.",
        "resource_url": "/static/uploads/curriculum/atl-handbook-vol-ii-karnataka.pdf",
        "lessons": [
            ("Making a Model for Measuring Mass, Force, and Pressure Using a Load Cell", "Activity 1."),
            ("Building a Decibel Meter with Sound-Sensitive LEDs using Arduino", "Activity 2."),
            ("Constructing a Pantograph: Understanding Simple Machines", "Activity 3."),
            ("Making an Air Powered Car", "Activity 4."),
            ("Making a DIY model of Newton's Disc", "Activity 5."),
            ("Making a Jumping Paper Frog with LED Eyes", "Activity 6."),
            ("Making a model demonstrating Persistence of Vision (POV)", "Activity 7."),
            ("Making Water Level Detecting Alarm", "Activity 8."),
            ("Making Artistic Circuits using Dough to test Conductors and Insulators", "Activity 9."),
            ("Making a DIY Salt-water Battery", "Activity 10."),
            ("Making a Model for Identifying Junk and Healthy Food Using Electronics", "Activity 11."),
            ("Making an Animation Showing Healthy and Junk Food using Scratch or PictoBlox", "Activity 12."),
            ("Creating an Animation Showing Self-Pollination and Cross-Pollination Using Scratch or PictoBlox", "Activity 13."),
            ("Making a DIY Model to Learn Types of Triangles", "Activity 14."),
            ("Understanding Algebraic Identities using Cardboard Tiles", "Activity 15."),
            ("Constructing a DIY Electronic Model to Understand Fractions", "Activity 16."),
            ("Making a DIY Model to Learn Types of Quadrilaterals through Paper Electronics", "Activity 17."),
        ],
    },
    {
        "title": "Volume III - Grades 9-10 ATL Activities",
        "level": "Grades 9-10",
        "description": "ATL-integrated classroom activity plans for Grades 9-10.",
        "resource_url": "/static/uploads/curriculum/atl-handbook-vol-iii-karnataka.pdf",
        "lessons": [
            ("Learning Ohm's Law through Simulation and Hands-on Activities", "Activity 1."),
            ("Building a Gyroscope to Demonstrate Centrifugal Force and Inertia", "Activity 2."),
            ("Building a Wired Remote-Controlled Car and Measuring Its Velocity and Acceleration Using a Mobile App", "Activity 3."),
            ("Making a Model of Newton's Boat", "Activity 4."),
            ("Vehicle speed detection system using IR sensors", "Activity 5."),
            ("Making a Model for Autonomous Emergency Braking System", "Activity 6."),
            ("DIY Paper Speaker: Exploring Sound Waves and Electromagnetism", "Activity 7."),
            ("Blood Donor and Receiver Compatibility Model", "Activity 8."),
            ("Blood Donor and Receiver Compatibility Model Using Arduino Uno and Block Coding", "Activity 9."),
            ("DIY model that demonstrates the Five Stages of Blood Circulation using Tinkercad Simulation and Electronics", "Activity 10."),
            ("Creating an Animation of the Five Stages of Blood Circulation Using Scratch or PictoBlox", "Activity 11."),
            ("Sex Determination Model using Arduino, PictoBlox, and Dabble Application", "Activity 12."),
            ("Building a Functional Gripper using Cardboard", "Activity 13."),
            ("Demonstration of Electrolysis of Water using Pencil Electrodes", "Activity 14."),
            ("Building a Model to Detect and Measure CO2 Generated from an Acid-Base Reaction using Arduino and MQ-135 Sensor", "Activity 15."),
            ("Making a Model for Detecting Heat Generated During Exothermic Chemical Reactions using Arduino", "Activity 16."),
            ("Making Machine Learning based pH Card Recognition System", "Activity 17."),
            ("Building Models of Clinometers for Measuring Height", "Activity 18."),
            ("Making a Model to Learn Trigonometric Ratios", "Activity 19."),
            ("Calculating Surface Areas of Paper 3D Shapes using 2D Net Pull-Up Models", "Activity 20."),
            ("Constructing a Pythagorean Theorem Model using Graph Paper and Cardboard", "Activity 21."),
            ("Building a Temperature and Humidity Monitoring System with Data Visualization", "Activity 22."),
            ("Creating Pie Charts using Teachable Machine, Image Recognition and MS Excel", "Activity 23."),
        ],
    },
]


def seed_handbook_volume_courses(db):
    for volume in VOLUME_COURSES:
        course = db.query(Course).filter(Course.title == volume["title"]).first()
        if not course:
            course = Course(
                title=volume["title"],
                description=volume["description"],
                level=volume["level"],
            )
            db.add(course)
            db.flush()

        marker = db.query(Lesson).filter(Lesson.course_id == course.id, Lesson.title == "Open Full Handbook PDF").first()
        if marker:
            continue

        db.add(
            Lesson(
                course_id=course.id,
                title="Open Full Handbook PDF",
                content_type="pdf",
                content_body=f"Full PDF reference for {volume['title']}.",
                resource_url=volume["resource_url"],
                sort_order=1,
            )
        )

        for index, (title, summary) in enumerate(volume["lessons"], start=2):
            db.add(
                Lesson(
                    course_id=course.id,
                    title=title,
                    content_type="handbook_activity",
                    content_body=f"{summary}\n\nRefer to the linked handbook PDF for full instructions, diagrams, QR/video links, materials, and reflection questions.",
                    resource_url=volume["resource_url"],
                    sort_order=index,
                )
            )

    db.commit()
