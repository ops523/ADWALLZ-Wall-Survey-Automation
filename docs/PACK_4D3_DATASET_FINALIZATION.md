# Pack 4D.3 — Dataset Finalization & Split Strategy

## Purpose

Pack 4D.3 defines how the validated High-Rise wall reference dataset becomes
eligible for model-training splits.

The human annotation manifest remains the source of truth for annotation.
Dataset splitting is a separate, downstream operation.

## Current Dataset Status

The current High-Rise reference dataset contains:

- 25 total images
- 10 positive images
- 12 negative images
- 3 hard-negative images
- 10 positive images with human polygons
- 15 explicit no-target records

This dataset is a validated seed/reference set.

It is **not** considered large enough for production model training or
production evaluation.

## Split Policy

Production splits use:

- Train: 70%
- Validation: 15%
- Test: 15%

Splits are deterministic.

The split assignment is based on `scene_group`, not individual image files.

## Scene Leakage Rule

The same physical scene must never appear in more than one split.

For example, if several images are captured from the same building/wall/scene,
all of them must belong to the same split.

This rule is mandatory even when the image filenames are different.

## Production Readiness Gate

A production split is blocked until:

- all positive images are annotated;
- all negative/hard-negative images are explicit no-target;
- the annotation manifest remains `unassigned`;
- at least 100 positive images exist;
- at least 100 negative/hard-negative images exist;
- scene groups are available for leakage-safe splitting.

The thresholds are intentionally conservative.

The current 10-positive / 15-non-positive reference set therefore remains
blocked from production splitting.

## Important Distinction

The current dataset may be used for:

- annotation-tool validation;
- manifest validation;
- preprocessing tests;
- detector integration tests;
- inference pipeline smoke tests;
- qualitative reference;
- future annotation guidelines.

It must not be used to make production model-performance claims.

## Future Production Dataset

Before production training, the dataset should expand substantially with:

### Positive examples

- blank upper-floor facades;
- large painted/plastered walls;
- side walls;
- commercial upper-floor walls;
- partially visible walls;
- irregular wall surfaces;
- perspective-distorted walls;
- different lighting/weather;
- different Indian cities/towns;
- different building materials.

### Negative examples

- ground-floor shops;
- shutters;
- signage;
- hoardings;
- windows-dominated facades;
- narrow walls;
- vegetation-obstructed surfaces;
- pole/wire-obstructed surfaces;
- unsuitable residential surfaces;
- insufficient visible area.

### Hard negatives

Hard negatives should specifically represent surfaces that visually resemble
a wall target but should not be detected as the desired High-Rise wall surface.

## Architectural Rule

The pipeline remains:

CanonicalImageAsset
→ wall/facade detection
→ candidate geometry
→ candidate filtering
→ dimensions/floor
→ obstruction
→ quality/commercial suitability
→ human review
→ field verification

Detection does not determine final commercial suitability.

## Output

When the dataset becomes production-ready, Pack 4D.3 creates a separate
split-assignment manifest.

The human annotation manifest is not modified to contain train/validation/test
assignments.
