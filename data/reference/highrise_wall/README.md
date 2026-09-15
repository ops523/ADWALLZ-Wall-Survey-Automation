# High-Rise Wall Surface Reference Dataset

This directory contains reference imagery for ADWALLZ high-rise
wall/facade detection.

## Detection target

The target class is:

    wall_surface

The detector should identify a visually plausible advertising wall or
facade surface, especially on the first floor and above.

Examples include:

- large upper-floor blank facades
- side walls of multi-storey buildings
- painted/plastered upper-floor walls
- commercial upper-floor wall surfaces
- road-facing upper-floor surfaces
- partially visible wall surfaces
- irregular wall surfaces suitable for later geometric estimation

## Detection is NOT commercial approval

The wall detector must not decide whether a wall is commercially usable.

Downstream stages determine:

- real-world dimensions
- square footage
- floor
- obstruction
- visibility
- windows/signage
- accessibility
- commercial suitability
- field verification

## Positive examples

A positive image contains one or more visually plausible wall surfaces.

## Negative examples

Negative examples should contain scenes where no relevant wall surface
exists.

Examples:

- ordinary road scenes
- vegetation-dominated scenes
- sky/ground
- unrelated structures

## Hard negatives

Hard negatives are especially important.

Examples:

- ground-floor shops
- shutters
- signage/hoardings
- windows-dominated facades
- narrow wall fragments
- heavily obstructed surfaces
- unsuitable residential frontage
- poles/wires/vegetation obscuring apparent walls
- surfaces that visually resemble walls but are not useful advertising walls

## Annotation policy

Reference imagery may initially have:

    annotation_status = visual_reference

This does not constitute a machine-learning ground-truth annotation.

Training data should eventually use polygon annotations wherever possible.

Bounding boxes may be retained as auxiliary annotations, but polygon geometry
is preferred because wall surfaces are frequently irregular and perspective
distorted.

## Geometry policy

Detector coordinates are image-space coordinates.

Pixel area must NEVER be interpreted as real-world square footage.

Real-world dimensions belong to Pack 5.
