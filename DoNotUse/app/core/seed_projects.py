"""Seed the 40 ATL experiments + their bills-of-materials (from the official
ATL_Inventory_ExperimentWise list). Idempotent: only inserts if projects empty.

Item usage maths uses qty_num (first integer parsed from the quantity string);
'As required' / fractions → qty_num = None (shown but not summed)."""
import re
from sqlalchemy.orm import Session


def _qty_num(q):
    if not q:
        return None
    m = re.search(r"\d+", q)
    return int(m.group()) if m else None


# (exp_no, name, [(item, qty), ...])
PROJECTS = [
    (1, "Learning Ohm's Law through Simulation and Hands-on Activities", [
        ("Breadboard", "1"), ("9V Battery with Clip", "1"), ("Red LEDs", "4"),
        ("Resistor 2.2KΩ", "1"), ("Resistor 4.7KΩ", "1"), ("Resistor 22KΩ", "1"),
        ("Resistor 47KΩ", "1"), ("Multimeter", "1"), ("Jumper Wires", "As required"),
        ("Digital Multimeter", "1"), ("Calculator", "1")]),
    (2, "DC Motor Wheel Balancing Project", [
        ("Plastic pulley / Old CD", "1"), ("DC Motor", "1"), ("Mini Rocker Switch (SPST)", "1"),
        ("BO Motor Wheel", "1"), ("9V Battery with Clip", "1"), ("Nuts and Bolts", "As required"),
        ("Glue Gun", "1"), ("Glue Sticks", "As required"), ("Soldering Kit", "1 Set"),
        ("Wire Stripper", "1"), ("Spanners", "1 Set"), ("Sandpaper", "As required"),
        ("Multimeter", "1"), ("Gloves and Safety Goggles", "1 Set")]),
    (3, "Building a Wired Remote-Controlled Car (Velocity & Acceleration)", [
        ("Printable template for RC car chassis", "1"), ("Foam board", "1"), ("Breadboard", "1"),
        ("Wires and jumper cables", "As required"), ("Copper tape", "As required"),
        ("3.2V Li-ion batteries with holder", "2"), ("300 RPM BO Motors", "2"), ("BO Motor Wheels", "2"),
        ("PWM DC Motor Speed Controller", "1"), ("Push Buttons", "2"), ("Paper glue", "1"),
        ("Soldering Kit", "1 Set"), ("Wire Stripper", "1"), ("Multimeter", "1"),
        ("Screwdriver", "1"), ("Hot Glue Gun with Sticks", "1"), ("Scissors", "1"),
        ("Paper Cutter", "1"), ("Cutting Mat", "1"), ("Hand Gloves", "1 Set")]),
    (4, "Making a Model of Newton's Boat", [
        ("Printable template for the boat", "1"), ("A4 Size Foam Board", "1"),
        ("Ribbon Cables", "As required"), ("9V Battery", "1"), ("Rocker Switch", "1"),
        ("DC Motor", "1"), ("Propeller", "1"), ("Paper Glue", "1"), ("Water Tub (Small)", "1"),
        ("Double-Sided Tape", "As required"), ("Soldering Kit", "1 Set"), ("Wire Stripper", "1"),
        ("Multimeter", "1"), ("Hot Glue Gun with Glue Sticks", "1"), ("Scissors", "1"),
        ("Paper Cutter", "1"), ("Cutting Mat", "1"), ("Hand Gloves", "1 Set")]),
    (5, "Vehicle Speed Detection System using IR Sensors", [
        ("Arduino Uno", "1"), ("IR Sensor", "2"), ("Breadboard", "1"), ("16x2 LCD Display", "1"),
        ("I2C Connector (for LCD)", "1"), ("5V Piezo Buzzer", "1"), ("9V Battery", "1"),
        ("9V Battery Clip", "1"), ("Jumper Cables", "As required"), ("Wooden Plank/Board", "1"),
        ("USB Cable", "1"), ("Power Supply (USB Power Bank)", "1"), ("Hot Glue Gun with Glue Sticks", "1"),
        ("Multimeter", "1"), ("Precision Screwdriver", "1")]),
    (6, "Making a Model for Autonomous Emergency Braking System", [
        ("Arduino Nano", "1"), ("Zero PCB", "1"), ("Ultrasonic Sensor (HC-SR04)", "1"),
        ("3.7V 3000 mAh Li-ion Batteries", "2"), ("Battery Holder", "1"), ("Rocker ON/OFF Switch", "1"),
        ("300 RPM BO Motor", "1"), ("BO Motor Wheel", "1"), ("L298N Motor Driver", "1"),
        ("Wooden Plank/Board", "1"), ("Wooden Block", "1"), ("Jumper/Connecting Wires", "As required"),
        ("Arduino Nano USB Cable", "1"), ("Power Supply (USB Battery Bank)", "1"),
        ("Hot Glue Gun with Glue", "1"), ("Computer with Arduino IDE", "1"), ("Multimeter", "1"),
        ("Precision Screwdriver", "1"), ("Soldering Kit", "1 Set"), ("Wire Cutter/Stripper", "1"),
        ("Hand Gloves", "1 Set"), ("Cutting Mat", "1")]),
    (7, "DIY Paper Speaker: Exploring Sound Waves and Electromagnetism", [
        ("Cardstock Paper (Thick)", "As required"), ("Speaker Template", "1"),
        ("Neodymium Magnets (25mm x 12mm)", "2"), ("Enameled Copper Wire (28-30 gauge)", "1"),
        ("AUX Cable", "1"), ("2-Position Spring Wire Connector", "1"), ("Scissors", "1"),
        ("Tape", "As required"), ("Sandpaper", "As required"), ("Ruler", "1"), ("Compass", "1"),
        ("Wire Stripper", "1"), ("Soldering Kit", "1 Set"), ("Multimeter", "1"),
        ("Hot Glue Gun with Sticks", "1"), ("Cutting Mat", "1"), ("Hand Gloves", "1 Set")]),
    (8, "Blood Donor and Receiver Compatibility Model", [
        ("LEDs", "As required"), ("Diodes (IN4007)", "As required"), ("Push Buttons", "As required"),
        ("3V Coin Battery", "1"), ("Soldering Kit", "1 Set"), ("Wire Stripper", "1"),
        ("Wires", "As required"), ("Switch", "1"), ("Zero PCB", "1"), ("Multimeter", "1"),
        ("Screwdriver", "1"), ("Hot Glue Gun with Sticks", "1")]),
    (9, "Blood Donor/Receiver Compatibility Model using Arduino Uno & Block Coding", [
        ("Arduino Uno", "1"), ("HC-05 Bluetooth Module", "1"), ("LEDs", "8"), ("Breadboard", "1"),
        ("Jumper Wires", "As required"), ("Mobile Phone with Dabble App", "1"),
        ("Computer with PictoBlox Software", "1"), ("USB Cable for Arduino", "1"),
        ("Power Bank / Battery Pack", "1")]),
    (10, "DIY Model: Five Stages of Blood Circulation (Tinkercad + Electronics)", [
        ("Blue LEDs", "33-36"), ("Green LEDs", "12"), ("Red LEDs", "30-32"), ("Push Buttons", "5"),
        ("3V Coin Cell Battery with Holder", "1"), ("Single-core Wires", "As required"),
        ("Printable Blood Circulation Template", "1"), ("Foam Board (A4 Size)", "1"), ("Paper Glue", "1"),
        ("Soldering Kit", "1 Set"), ("Wire Cutter/Stripper", "1"), ("Multimeter", "1"),
        ("Paper Cutter", "1"), ("Cutting Mat", "1"), ("Tinkercad Simulation Platform", "1")]),
    (11, "Animation of Five Stages of Blood Circulation (Scratch/PictoBlox)", [
        ("Notebook and Pen", "1"), ("Computer/Laptop", "1"), ("Speakers/Headphones", "1"),
        ("Microphone", "0-1"), ("Scratch Software", "1"), ("PictoBlox Software", "1"),
        ("Diagram of Human Blood Circulatory System", "1"), ("Internet Connection", "1")]),
    (12, "Sex Determination Model using Arduino, PictoBlox & Dabble", [
        ("Arduino Uno", "1"), ("HC-05 Bluetooth Module", "1"), ("Red LEDs", "2-4"), ("Green LED", "1-2"),
        ("Breadboard", "1"), ("Jumper Wires", "10-15"), ("Mobile Phone with Dabble Application", "1"),
        ("Computer with PictoBlox Software", "1"), ("USB Cable for Arduino", "1"),
        ("Power Bank / Battery Pack", "0-1"), ("PictoBlox Software", "1"), ("Dabble Mobile Application", "1")]),
    (13, "Building a Functional Gripper using Cardboard", [
        ("Cardboard sheet", "1-2"), ("Plastic straws", "5-10"), ("Strings or thin ropes", "2-3 m"),
        ("Rubber bands", "4-6"), ("Ice cream sticks", "5-8"), ("Zip ties / Cable ties", "4-6"),
        ("Markers or pencils", "1-2"), ("Hot glue gun with sticks", "1"), ("Scissors", "1"),
        ("Paper cutter / Craft knife", "1"), ("Ruler", "1"), ("Hole puncher", "0-1"),
        ("Cutting mat", "1"), ("Hand gloves", "1 pair")]),
    (14, "Demonstration of Electrolysis of Water using Pencil Electrodes", [
        ("Plastic cup/jar", "1"), ("Common salt", "As required"), ("Graphite pencils", "2"),
        ("Water", "As required"), ("Foam board", "1"), ("Stirrer", "1"), ("9V Battery with clip", "1"),
        ("9V DC Power Adapter", "0-1"), ("Crocodile clips (red and black)", "2 pairs"),
        ("Paper cutter / knife", "1"), ("Sharpener", "1"), ("Wire stripper", "1")]),
    (15, "Detect & Measure CO2 from Acid-Base Reaction (Arduino + MQ-135)", [
        ("Arduino Uno", "1"), ("MQ-135 Gas Sensor", "1"), ("16x2 LCD Display with I2C Connector", "1"),
        ("Breadboard", "1"), ("Jumper Cables", "15-20"), ("USB Cable", "1"),
        ("Power Supply (USB Power Bank)", "1"), ("Vinegar (Acetic Acid)", "As required"),
        ("Baking Soda", "As required"), ("Old Plastic Jar", "1"), ("Glass/Plastic Beaker", "1"),
        ("Plastic Pipe and Funnel", "1 set"), ("Paper tape", "1"), ("Hot glue gun with glue sticks", "1"),
        ("Computer with Arduino IDE", "1"), ("Battery-Operated Drill Machine", "1"), ("Drill Bits", "1 set"),
        ("Precision screwdriver", "1"), ("Multimeter", "0-1"), ("Cutting mat", "1"), ("Hand gloves", "1 pair")]),
    (16, "Detecting Heat from Exothermic Chemical Reactions using Arduino", [
        ("Arduino Uno", "1"), ("DS18B20 Waterproof Temperature Sensor", "1"), ("4.7K ohm Resistor", "1"),
        ("16x2 LCD with I2C Module", "1"), ("Small Breadboard", "1"), ("Wooden Plank/Board", "1"),
        ("Jumper/Connecting Wires", "15-20"), ("Arduino USB Cable", "1"), ("9V Battery or 9V DC Adapter", "1"),
        ("Hot glue gun with glue sticks", "1"), ("Computer with Arduino IDE", "1"), ("Multimeter", "0-1"),
        ("Precision screwdriver", "1"), ("Soldering Kit", "1 set"), ("Wire Cutter/Stripper", "1"),
        ("Hand gloves", "1 pair"), ("Cutting mat", "1"), ("Zinc metal", "2 g"),
        ("Hydrochloric Acid (HCl)", "5 g"), ("Sodium Hydroxide (NaOH)", "4 g"),
        ("Concentrated Sulfuric Acid", "8-10 drops"), ("Distilled Water", "20 ml"),
        ("Test Tubes & Test Tube Stand", "1 set"), ("Safety Gear (Gloves, Goggles, Apron)", "1 set"),
        ("Dropper", "1"), ("Weighing scale", "1")]),
    (17, "Machine Learning based pH Card Recognition System", [
        ("Printed pH indicator cards", "8"), ("Standard images for each pH value", "8"),
        ("Cardboard/Foam Board", "1"), ("Pencil/Marker", "1-2"), ("Scissors", "1"), ("Paper Glue", "1"),
        ("Scissors and Paper Cutter", "1 set"), ("Cutting Mat", "1"),
        ("Computer with Internet Access and Webcam", "1"), ("Color Printer", "1"),
        ("External Webcam", "0-1"), ("PictoBlox Software with Login Credentials", "1"),
        ("PictoBlox Machine Learning Environment", "1"), ("PictoBlox Text-to-Speech Extension", "1")]),
    (18, "Building Models of Clinometers for Measuring Height", [
        ("180-degree protractor", "1"), ("30 cm rulers", "2"), ("Foam board", "1"), ("Thread", "1-2 m"),
        ("Paper cutter", "1"), ("Hand gloves", "1 pair"), ("Marker pen or pencil", "1-2"),
        ("Separate ruler", "1"), ("Hot glue gun with glue sticks", "1")]),
    (19, "Making a Model to Learn Trigonometric Ratios", [
        ("Printed templates of the model", "1 set"), ("A4 size papers", "3"),
        ("Colored chart sheet / cardstock sheet", "0-1"), ("A4 size foam board sheets", "2"),
        ("Marker pen or pencil and ruler", "1 set"), ("Soft board push pins", "5-10"),
        ("Bold colored markers", "2-3"), ("Scissors", "1"), ("Paper cutter", "1"), ("Cutting mat", "1"),
        ("Hand gloves", "1 pair"), ("Paper glue", "1")]),
    (20, "Calculating Surface Areas of Paper 3D Shapes (2D Net Pull-Up Models)", [
        ("Pre-designed printable templates of 2D nets", "1 set"), ("Cardstock paper", "2-3 sheets"),
        ("Strings (thin and durable)", "1-2 m"), ("Paper glue", "1"), ("Needle", "1"),
        ("Cardboard sheets", "1-2"), ("Pencils", "1-2"), ("Ruler", "1"), ("Scissors", "1"),
        ("Cutting mat", "1"), ("Eraser", "1"), ("Calculator", "1")]),
    (21, "Constructing a Pythagorean Theorem Model (Graph Paper & Cardboard)", [
        ("Graph Paper", "1-2 sheets"), ("Printable Template of Pythagorean Theorem", "1 set"),
        ("Cardboard", "1-2"), ("Ruler", "1"), ("Pencil", "1"), ("Scissors", "1"), ("Eraser", "1"),
        ("Sharpener", "1"), ("Color Markers", "2-3"), ("Paper Glue", "1"),
        ("Cardboard Pieces", "As required"), ("Cutting Mat", "1"), ("GeoGebra", "0-1")]),
    (22, "Temperature & Humidity Monitoring System with Data Visualization", [
        ("Arduino Uno", "1"), ("DHT11 Sensor", "1"), ("Breadboard", "1"), ("Jumper Cables", "10-15"),
        ("USB Cable", "1"), ("Power Supply (USB Power Bank)", "1"), ("Multimeter", "0-1"),
        ("Internet Connection", "1"), ("Arduino IDE Software", "1"), ("Arduino Cloud", "1"),
        ("Microsoft Excel", "1"), ("Computer with Arduino IDE and MS Excel", "1")]),
    (23, "Creating Pie Charts using Teachable Machine, Image Recognition & MS Excel", [
        ("Apples", "2-3"), ("Bananas", "2-3"), ("Computer with PictoBlox, Internet & Webcam", "1"),
        ("External Webcam", "0-1"), ("Headphones with Mic and Speakers", "1"), ("Internet Connection", "1"),
        ("PictoBlox Software with Login Credentials", "1"), ("Google Teachable Machine", "1"),
        ("Microsoft Excel", "1"), ("Google Drive", "1")]),
    (24, "Measuring Mass, Force, and Pressure Using a Load Cell", [
        ("Arduino Uno", "1"), ("Small Breadboard", "1"), ("HX711 ADC Module", "1"),
        ("Load Cell (40 kg)", "1"), ("3D Printed Parts for Mounting Load Cell", "1 set"),
        ("12V DC Adapter", "1"), ("16x2 LCD Screen", "1"), ("I2C Connector for LCD", "1"),
        ("Foam Board", "1"), ("Connecting Wires", "15-20"), ("Soldering Kit", "1 set"),
        ("Hot Glue Gun with Glue Sticks", "1"), ("Multimeter", "1"), ("Precision Screwdriver", "1"),
        ("Wire Cutter/Stripper", "1"), ("Arduino IDE Software", "1")]),
    (25, "Building a Decibel Meter with Sound-Sensitive LEDs using Arduino", [
        ("Arduino Uno", "1"), ("Sound Sensor Module (KY-037)", "1"), ("LEDs (multiple colours)", "5-10"),
        ("Resistors (220Ω)", "5-10"), ("Jumper Cables", "15-20"), ("Breadboard", "1"),
        ("OLED Display Module (0.96-inch I2C)", "1"), ("USB Cable", "1"), ("Soldering Kit", "0-1"),
        ("Multimeter", "0-1"), ("Screwdriver", "0-1"), ("Arduino IDE Software", "1"),
        ("Computer with Arduino IDE", "1")]),
    (26, "Constructing a Pantograph: Understanding Simple Machines", [
        ("Pantograph Template", "1 set"), ("Cardboard/Foam Board", "1-2"), ("Scale/Ruler", "1"),
        ("Scissors", "1"), ("Cutter Blade", "1"), ("Wooden Base", "1"), ("A4 Sheets", "2-3"),
        ("Pencils/Markers", "1-2"), ("Paper Glue", "1"), ("Battery Operated Drill", "1"),
        ("Drill Bits (6-8 mm)", "1 set"), ("Nuts and Bolts (M6-M8)", "4-6"), ("Washers", "4-6")]),
    (27, "Making an Air Powered Car", [
        ("Empty Plastic Bottle", "1"), ("Balloon", "1"), ("Levelling Pipe", "1"), ("Paper Straws", "2"),
        ("Plastic Bottle Caps", "4"), ("Bamboo Skewers", "2"), ("Rubber Bands", "0-2"),
        ("3D Printed Parts", "0-1 set"), ("Hot Glue Gun with Glue Sticks", "1"), ("Scissors", "1"),
        ("Craft Knife", "1"), ("Ruler", "1"), ("Marker", "1"), ("Hand Drill", "1"),
        ("3D Printer with PLA Filament", "0-1")]),
    (28, "Making a DIY Model of Newton's Disc", [
        ("Printable Templates for Newton's Disc", "1 set"), ("Foam Board", "1"), ("Cardboard", "1"),
        ("Ribbon Cables", "1-2"), ("3.7V Li-ion Batteries with Holder", "2"), ("Rocker Switch", "1"),
        ("DC Motor", "1"), ("Paper Glue", "1"), ("Soldering Kit", "1 set"), ("Wire Stripper", "1"),
        ("Multimeter", "1"), ("Hot Glue Gun with Glue Sticks", "1"), ("Scissors", "1"),
        ("Paper Cutter", "1"), ("Cutting Mat", "1"), ("Hand Gloves", "1 pair"),
        ("Colored Sketch Pens (VIBGYOR)", "0-1 set")]),
    (29, "Making a Jumping Paper Frog with LED Eyes", [
        ("Cardstock Sheet", "1"), ("Scissors", "1"), ("Red Marker or Pen", "1"),
        ("Copper Conductive Tape", "1 roll"), ("Red LEDs", "2"), ("3.3V Coin Cell Battery", "1"),
        ("Clear/Cello Tape", "0-1"), ("Paper Glue", "1"), ("Ruler", "1"), ("Tweezers", "1"),
        ("Soldering Kit", "1 set"), ("Wire Cutter/Stripper", "1"), ("Hand Gloves", "1 pair"),
        ("Cutting Mat", "1"), ("Paperclips/Clamps", "0-2")]),
    (30, "Making a Model Demonstrating 'Persistence of Vision' (POV)", [
        ("Printed Template of Running Horse", "1 set"), ("18650 Li-ion Batteries (3.7V)", "2"),
        ("Battery Holder", "1"), ("300 RPM BO Motor", "1"), ("Bamboo Skewer / Toothpick", "1-2"),
        ("Ribbon Cable / Wires", "1-2"), ("Rocker Switch", "1"), ("Wooden Board (15x15 cm)", "1"),
        ("Scissors", "1"), ("Marker Pen or Pencil with Ruler", "1 set"),
        ("Pencil, Scale and Black Sketch Pen", "1 set"), ("Hand Gloves", "1 pair"),
        ("Hot Glue Gun with Glue Sticks", "1"), ("Paper Glue / Glue Stick", "1"),
        ("Soldering Kit", "1 set"), ("Wire Stripper", "1"), ("Multimeter", "1"), ("Mini Hack Saw", "1")]),
    (31, "Making Water Level Detecting Alarm", [
        ("9V Battery with Battery Clip", "1"), ("Rocker ON/OFF Switch", "1"), ("Resistors (220 Ω)", "4"),
        ("LEDs (1 Red, 1 Orange, 2 Green)", "4"), ("Piezo Buzzer", "1"), ("NPN Transistor (BC547)", "4"),
        ("Wires", "10-15"), ("Probes (Metal or Wires)", "2-4"), ("Cardboard", "1"), ("Glass/Plastic Jar", "1"),
        ("Paper Cutter / Knife", "1"), ("Pencil and Ruler", "1 set"), ("Soldering Kit", "1 set"),
        ("Hot Glue Gun with Glue", "1"), ("Wire Cutter / Stripper", "1"), ("Multimeter", "1"),
        ("Safety Gloves", "1 pair"), ("Cutting Mat", "1")]),
    (32, "Making Artistic Circuits using Dough (Conductors & Insulators)", [
        ("All-purpose Flour", "1 cup"), ("Water", "1/2 cup"), ("Salt", "1/4 cup"), ("Vegetable Oil", "1 tbsp"),
        ("Cream of Tartar / Lemon Juice", "1 tbsp"), ("Edible Food Color", "0-1"),
        ("Battery (3V/9V) with Holder", "1"), ("5mm LEDs", "2-4"), ("Piezo Buzzer", "1"),
        ("DC Toy Motor with Propeller", "1"), ("Mixing Bowls / Trays / Sauce Pan", "1 set"),
        ("Measuring Cups and Spoons", "1 set"), ("Stirring Sticks / Spoons / Ladle", "1 set"),
        ("Gas Stove / Induction Top", "1"), ("Cloth", "1")]),
    (33, "Making a DIY Salt-water Battery", [
        ("Zinc Plate (Anode)", "1"), ("Copper Plate (Cathode)", "1"), ("Water", "As required"),
        ("Salt (Sodium Chloride)", "As required"), ("Hydrogen Peroxide", "As required"),
        ("Piezo Buzzer", "1"), ("5mm LEDs", "1-2"), ("Crocodile Clips", "2"),
        ("Glass Beaker / Waste Jar", "1"), ("Kitchen Weighing Scale", "1"), ("Multimeter", "1"),
        ("Hand Gloves", "1 pair"), ("Cloth", "1"), ("Stirring Stick / Spoon", "1"), ("Measuring Spoon", "1")]),
    (34, "Identifying Junk and Healthy Food Using Electronics", [
        ("Copper Tape", "1 roll"), ("RGB LED / RGB Module", "1"), ("220 Ohm Resistor", "1"),
        ("3.3V Battery with Holder", "1"), ("Healthy Food Stickers", "1 set"), ("Junk Food Stickers", "1 set"),
        ("Ribbon Cables", "5-10"), ("Buzzer", "1"), ("Hot Glue Gun", "1"), ("Ruler", "1"), ("Pencil", "1"),
        ("Cutting Tools (Scissors / Precision Cutter)", "1"), ("Cutting Mat", "1"), ("Wire Stripper", "1"),
        ("Multimeter", "0-1"), ("Soldering Kit", "1 set"), ("Hand Gloves", "1 pair")]),
    (35, "Animation Showing Healthy and Junk Food (Scratch/PictoBlox)", [
        ("Images of Foods", "1 set"), ("Background Images", "1 set"), ("Notebook and Pen/Pencil", "1"),
        ("Computer or Tablet", "1"), ("Internet Access", "1"), ("Headphones with Mic and Speakers", "1"),
        ("Scratch or PictoBlox Software", "1"), ("Image Editing Software (Canva)", "0-1")]),
    (36, "Animation: Self-Pollination & Cross-Pollination (Scratch/PictoBlox)", [
        ("Pre-designed Images (flower, pollen, bee, wind)", "1 set"),
        ("Sound Files (wind, bee buzz, thunderstorm)", "1 set"), ("Notebook and Pen/Pencil", "1"),
        ("Computer or Tablet", "1"), ("Internet Access", "1"), ("Headphones with Mic and Speakers", "1"),
        ("Scratch or PictoBlox Software", "1"), ("Image Editing Software (Canva)", "0-1")]),
    (37, "Making a DIY Model to Learn Types of Triangles", [
        ("180-degree Protractor", "1"), ("Foam Board", "1"), ("Printable Template", "1 set"),
        ("Paper Glue", "1"), ("M4 Screws and Nuts", "3-4"), ("Paper Cutter", "1"), ("Cutting Mat", "1"),
        ("Cordless Drilling Machine with 5mm Drill Bit", "1"), ("Hand Gloves", "1 pair"),
        ("Safety Goggles", "1"), ("Marker Pen / Pencil", "1"), ("Ruler", "1"), ("Screwdriver", "1")]),
    (38, "Understanding Algebraic Identities using Cardboard Tiles", [
        ("Printed Templates of Tiles", "1 set"), ("Cardboard or Foam Board Sheets", "1-2"),
        ("Glue or Adhesive", "1"), ("Instruction Manual (QR-based)", "1"), ("Blank A4 Sheets / Notebook", "2-3"),
        ("Ruler", "0-1"), ("Pencil", "1"), ("Cutting Tools (Scissors / Precision Cutter)", "1"),
        ("Cutting Mat", "1"), ("Hand Gloves", "1 pair")]),
    (39, "Constructing a DIY Electronic Model to Understand Fractions", [
        ("5mm Red LEDs", "16"), ("Foam Board", "1"), ("Printable Template", "1 set"), ("Paper Glue", "1"),
        ("Copper Tape (10 mm width)", "1 roll"), ("Push Buttons", "4"), ("Resistor (220-470 Ω)", "4-6"),
        ("9V Battery with Battery Clip", "1"), ("Soldering Kit", "1 set"), ("Paper Cutter", "1"),
        ("Cutting Mat", "1"), ("Hand Gloves", "1 pair"), ("Marker Pen or Pencil", "1"), ("Ruler", "1"),
        ("Geometrical Compass", "1"), ("Color Sketch Pens", "1 set"), ("Polypad", "0-1")]),
    (40, "DIY Model to Learn Types of Quadrilaterals (Paper Electronics)", [
        ("Printed Template of 'Match the Pair' Circuit", "1 set"), ("Foam Board Box Template", "1 set"),
        ("Colored Templates (Quadrilaterals & Types)", "1 set"), ("A4 Size Foam Board Sheets", "2"),
        ("Copper Tape (10 mm width)", "1 roll"), ("Paper Tape / Masking Tape", "1"),
        ("9V Battery with Battery Clip", "1"), ("5V Active Buzzer", "1"), ("Double-sided Tape", "1"),
        ("Crocodile Clip Cables (Red & Black)", "2"), ("Scissors", "1"),
        ("Marker Pen / Pencil and Ruler", "1 set"), ("Paper Cutter", "1"), ("Hand Gloves", "1 pair"),
        ("Hot Glue Gun with Glue Sticks", "1"), ("Paper Glue", "1"), ("Soldering Kit", "1 set"),
        ("Wire Stripper", "1"), ("Multimeter", "1"), ("MathsIsFun", "0-1")]),
]


def seed_projects(db: Session):
    from app.models.reports import Project, ProjectItem
    if db.query(Project).first():
        return  # already seeded
    for exp_no, name, items in PROJECTS:
        p = Project(exp_no=exp_no, name=name, is_active=True)
        db.add(p); db.flush()
        for item_name, qty in items:
            db.add(ProjectItem(project_id=p.id, item_name=item_name,
                               quantity=qty, qty_num=_qty_num(qty)))
    db.commit()
