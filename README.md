# ADWALLZ Wall Survey Automation

Automated discovery and screening of advertising walls across Indian cities,
towns and villages using:

- OpenStreetMap (OSM) road geometry
- Street View imagery
- Computer vision
- AI wall/facade analysis
- Human review
- Field verification

---

# Pack 1 — Road Network & Sampling Engine

Pack 1 establishes the geographic foundation of the system.

The system accepts a target using:

- State
- District
- Pincode
- Town / Village / City
- Optional Road / Highway
- Sampling interval

The Pincode is a mandatory geographic identifier because Indian place names
are frequently duplicated.

Example:

    State: Andhra Pradesh
    District: Nandyal
    Pincode: 518422
    Place: Atmakur
    Road: State Highway 57

The target identity is preserved throughout the pipeline.

---

## Target Identity

A target is represented as:

    State
      ↓
    District
      ↓
    Pincode
      ↓
    Place
      ↓
    Road

Every generated survey point retains:

    state
    district
    pincode
    place_name
    road_name

This allows later Street View images, AI candidates and field verification
records to remain associated with the exact requested target.

---

# Architecture

    TARGET INPUT
         |
         v
    State + District + Pincode + Place
         |
         v
    Nominatim target validation
         |
         v
    Target coordinates / bounding area
         |
         v
    OSM / Overpass road discovery
         |
         v
    Road geometry
         |
         v
    20m sampling
         |
         v
    Road bearing
         |
         +----------------+
         |                |
         v                v
    Heading - 90°     Heading + 90°
         |                |
         +-------+--------+
                 |
                 v
          Street View
          (Pack 2)
                 |
                 v
          AI Wall Detection
          (future pack)
                 |
                 v
          Human Review
                 |
                 v
          Field Verification

---

# Installation

Create a virtual environment:

    python -m venv .venv

Linux/macOS:

    source .venv/bin/activate

Windows:

    .venv\Scripts\activate

Install dependencies:

    pip install -r requirements.txt

---

# Environment

Copy:

    .env.example

to:

    .env

Then adjust values if required.

---

# Example

Generate survey points for Atmakur:

    python -m src.cli \
      --state "Andhra Pradesh" \
      --district "Nandyal" \
      --pincode "518422" \
      --place "Atmakur" \
      --road "State Highway 57" \
      --interval 20

Default output:

    output/survey_points.csv

Custom output:

    python -m src.cli \
      --state "Andhra Pradesh" \
      --district "Nandyal" \
      --pincode "518422" \
      --place "Atmakur" \
      --road "State Highway 57" \
      --interval 20 \
      --output output/atmakur_sh57.csv

---

# Important Geographic Rule

Do NOT identify a target using place name alone.

Incorrect:

    Atmakur

Correct:

    Andhra Pradesh
    Nandyal
    518422
    Atmakur

The system must retain the original target values even when the external
geocoder returns a normalized spelling.

---

# Pack 1 Output

The generated CSV contains:

    state
    district
    pincode
    place_name
    road_name
    road_type
    osm_way_id
    latitude
    longitude
    road_bearing
    heading_left
    heading_right
    sample_distance_m

---

# Sampling

The default sampling interval is:

    20 metres

The interval can be changed:

    --interval 15

or:

    --interval 25

Sampling is performed using geodesic distance rather than treating latitude
and longitude as planar metres.

---

# Road Headings

For every sample point:

    road bearing = direction of road travel

Two Street View headings are generated:

    heading_left  = bearing - 90°
    heading_right = bearing + 90°

All headings are normalized to:

    0° <= heading < 360°

This allows Pack 2 to request imagery looking toward both sides of the road.

---

# What Pack 1 Does NOT Do

Pack 1 does not yet:

- download Street View imagery
- detect walls
- estimate wall dimensions
- detect floors
- detect obstructions
- score wall quality
- approve/reject walls

Those functions will be added in subsequent packs.

---

# Data Flow

The original target:

    state
    district
    pincode
    place_name

is never discarded.

For example:

    Andhra Pradesh
    Nandyal
    518422
    Atmakur

will remain attached to every survey point generated for that target.

---

# Testing

Run:

    pytest -v

Compile:

    python -m py_compile src/cli.py

---

# Future Packs

Pack 1:
    Target validation + OSM road network + sampling

Pack 2:
    Street View acquisition

Pack 3:
    Image preprocessing

Pack 4:
    AI wall/facade detection

Pack 5:
    Wall dimensions + floor estimation

Pack 6:
    Obstruction detection

Pack 7:
    Wall quality scoring

Pack 8:
    Candidate review dashboard

Pack 9:
    Field verification

Pack 10:
    AIMS integration
