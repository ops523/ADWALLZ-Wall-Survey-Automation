# Pack 4D.1 — Wall Surface Model Selection Policy

## Status

Architecture decision locked.

This document defines the production requirements for the wall-surface
detection model. It does not select a specific model.

---

## 1. Objective

The detection model must identify visually plausible advertising wall/facade
surfaces in street-level imagery.

The model is responsible for:

- locating wall/facade surfaces;
- returning confidence;
- returning geometry;
- preserving deterministic model/version metadata.

The model is NOT responsible for:

- estimating real-world square footage;
- deciding floor number;
- deciding obstruction severity;
- deciding commercial suitability;
- deciding whether a wall has owner permission;
- approving inventory for execution.

Those decisions remain downstream pipeline stages.

---

## 2. Required model task

Production models must implement:

`wall_surface_detection`

The preferred task is segmentation or instance segmentation capable of
returning polygon/mask geometry.

Bounding-box-only models remain technically supported as a fallback.

Preferred geometry order:

1. polygon
2. mask
3. bounding box

---

## 3. Runtime

The production inference boundary is:

`ONNX -> ONNX Runtime`

The application architecture must remain framework-neutral.

Training frameworks are not part of the runtime contract.

A training framework may be used during experimentation only if its licensing
and deployment implications are independently verified.

---

## 4. CPU requirement

CPU inference is mandatory.

GPU acceleration may be added later, but the system must remain functional
without CUDA or a dedicated GPU.

This is important for:

- development;
- CI;
- local operations;
- low-cost cloud deployment;
- deterministic fallback operation.

---

## 5. Licensing

A model cannot enter the production registry unless commercial use is
explicitly permitted by its license.

The following are mandatory metadata:

- license name;
- commercial-use permission;
- attribution requirement, if any;
- source URL;
- model version.

Unknown or ambiguous licensing means:

`NOT APPROVED FOR PRODUCTION`

The system must not infer commercial permission from popularity or from
the fact that model weights are downloadable.

---

## 6. Artifact integrity

Every production model must have:

- exact `.onnx` artifact;
- model ID;
- model version;
- SHA-256 checksum;
- documented source;
- documented input dimensions;
- documented output schema.

Model artifacts must not be silently replaced.

A model update creates a new model version and requires evaluation.

---

## 7. Dataset policy

The currently available high-rise wall reference images are valuable for:

- defining the visual target;
- establishing positive examples;
- establishing negative examples;
- identifying hard negatives;
- designing annotation guidelines.

They are not sufficient by themselves to train a production model.

Production training/evaluation should eventually contain substantially more
diverse imagery covering:

- different Indian regions;
- different road types;
- different building styles;
- different lighting;
- different camera providers;
- perspective distortion;
- partial visibility;
- walls with windows;
- walls with minor signage;
- stained/aged walls;
- commercial upper-floor walls;
- side walls;
- difficult obstructions;
- unsuitable ground-floor frontage.

---

## 8. Model-selection criteria

A candidate model should be evaluated against:

### A. Detection quality

- precision;
- recall;
- F1;
- false-positive rate;
- false-negative rate.

### B. Geometry quality

For segmentation-capable models:

- polygon/mask quality;
- IoU;
- boundary quality.

### C. Operational performance

- CPU inference time;
- memory consumption;
- model size;
- batch behaviour;
- cold-start time.

### D. Production constraints

- commercial license;
- reproducible weights;
- ONNX export;
- deterministic preprocessing;
- CPU compatibility;
- maintainability.

---

## 9. Important distinction

A high-confidence wall detection is NOT automatically a usable ADWALLZ wall.

The intended pipeline is:

CanonicalImageAsset
    |
    v
Wall Surface Detection
    |
    v
Candidate Filtering / Deduplication
    |
    v
Dimensions + Floor Estimation
    |
    v
Obstruction Analysis
    |
    v
Commercial Quality Scoring
    |
    v
Human Review
    |
    v
Field Verification

This separation must be preserved.

---

## 10. Current architecture decision

The project will not hard-code a specific computer-vision framework.

The current architecture is:

Image
  -> canonical preprocessing
  -> ONNX model
  -> DetectionResult
  -> wall_surface candidate filtering
  -> downstream commercial assessment

A model can therefore be replaced without changing:

- CanonicalImageAsset;
- DetectionResult;
- WallDetector;
- WallSurfaceOutputAdapter;
- candidate filtering;
- future dimensions/floor stages.

---

## 11. Next step

Pack 4D.2:

High-rise reference dataset and annotation format.

4D.2 will define:

- positive/negative/hard-negative dataset structure;
- image IDs;
- annotation IDs;
- polygon annotation format;
- class definitions;
- annotation provenance;
- train/validation/test split rules;
- dataset manifest;
- annotation QA rules.

No production model will be selected until the evaluation dataset and
annotation contract are defined.
