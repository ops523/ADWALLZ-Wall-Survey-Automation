# ADWALLZ High-Rise Wall Surface Reference Dataset

## Purpose

This dataset defines the visual target for ADWALLZ High-Rise wall-surface
detection.

The target is a visually usable wall/facade surface located on the first floor
or above and visible from the road/street-level imagery.

This dataset is for wall-surface detection.

It is NOT a commercial inventory approval dataset.

---

## Categories

### positive

The image contains one or more visually plausible High-Rise wall surfaces.

Examples:

- blank upper-floor facade;
- large painted upper-floor wall;
- side wall of a multi-storey building;
- commercial upper-floor wall;
- partially visible upper-floor wall;
- irregular but usable facade surface;
- wall containing minor windows/signage but still presenting substantial
  visible wall surface.

Positive images must contain polygon annotations for every target wall surface
that should be detected.

---

### negative

The image does not contain a suitable target wall surface.

Examples:

- ground-floor shop frontage;
- shutters;
- signage/hoardings;
- windows-dominated facade;
- extremely narrow surface;
- heavily obstructed facade;
- vegetation-dominated scene;
- unsuitable residential surface.

Negative images have no wall_surface annotations.

---

### hard_negative

A hard negative is visually similar to a positive wall but should not be
treated as a target wall surface.

Examples:

- large signboard that resembles a wall;
- ground-floor frontage that visually resembles an upper facade;
- wall mostly hidden by trees;
- facade dominated by windows;
- narrow wall with apparently large pixel area due to perspective;
- unsuitable surface that could confuse a detection model.

Hard negatives are particularly important for reducing operational false
positives.

Hard negatives have no wall_surface annotations.

---

## Annotation policy

The annotation target is the visible wall/facade surface.

Do not annotate:

- the entire building;
- roof;
- road;
- sky;
- trees;
- poles;
- vehicles;
- shop interiors;
- unrelated signage.

When a target wall is irregular, use a polygon following its visible boundary.

Polygon coordinates are normalized:

x = pixel_x / image_width
y = pixel_y / image_height

Both x and y must be in [0, 1].

Minimum polygon size is three points.

---

## Multiple walls

An image may contain multiple independently visible wall surfaces.

Each wall receives a separate annotation.

Each annotation must have a unique annotation_id.

---

## Partial visibility

Annotate only the visible wall surface.

Do not infer hidden wall geometry behind:

- vehicles;
- trees;
- poles;
- buildings;
- other obstructions.

This is a visual detection dataset, not a reconstruction dataset.

---

## Perspective

Do not correct perspective during annotation.

The polygon should represent the visible wall surface in the source image.

Real-world dimensions will be estimated in Pack 5.

Pixel area must not be interpreted as square footage.

---

## Dataset splits

The same physical scene must never appear in multiple splits.

This applies even when:

- filenames differ;
- images come from different crops;
- the same Street View capture is resized;
- the same location is photographed from nearby points.

Use `scene_group` to enforce this rule.

Recommended future target:

- train: approximately 70%
- validation: approximately 15%
- test: approximately 15%

These percentages are guidance, not a requirement for the initial reference set.

---

## Provenance

Every image must record:

- source;
- scene_group;
- SHA-256;
- dimensions;
- relative path.

Every annotation must record:

- annotator;
- annotation source;
- annotation version;
- annotation ID.

---

## Reference images currently available

The initial reference collection is intended to establish the visual definition
of High-Rise wall surfaces.

It must not be treated as a sufficiently large production training dataset.

The production dataset should eventually contain hundreds/thousands of
diverse examples and hard negatives.

---

## Downstream meaning

Detection:

    "Is this a visually plausible wall/facade surface?"

It does NOT mean:

    "Can ADWALLZ execute this wall?"

Commercial suitability is determined later by:

1. candidate filtering;
2. dimensions;
3. floor estimation;
4. obstruction analysis;
5. quality scoring;
6. human review;
7. field verification.
