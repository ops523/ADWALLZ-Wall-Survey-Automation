from src.detection.candidate_filter import (
    CandidateFilterConfig,
    FilteredWallCandidates,
    filter_wall_candidates,
)
from src.detection.models import (
    BoundingBox,
    DetectionCandidate,
    DetectionResult,
)
from src.detection.onnx_detector import (
    ONNXModelSpec,
    ONNXWallDetector,
)
from src.detection.service import DetectionService
from src.detection.wall_surface import (
    WallSurfaceModelConfig,
    WallSurfaceReference,
    is_wall_surface_class,
)
from src.detection.wall_surface_adapter import (
    WallSurfaceOutputAdapter,
)

__all__ = [
    "BoundingBox",
    "DetectionCandidate",
    "DetectionResult",
    "DetectionService",
    "ONNXModelSpec",
    "ONNXWallDetector",
    "WallSurfaceModelConfig",
    "WallSurfaceReference",
    "WallSurfaceOutputAdapter",
    "CandidateFilterConfig",
    "FilteredWallCandidates",
    "filter_wall_candidates",
    "is_wall_surface_class",
]

from .model_registry import (
    DetectionModelRegistry,
    DetectionModelSpec,
    ModelLicenseInfo,
    validate_model_artifact,
)

from .dataset import (
    ANNOTATION_POLYGON,
    ANNOTATION_VERSION,
    CATEGORY_HARD_NEGATIVE,
    CATEGORY_NEGATIVE,
    CATEGORY_POSITIVE,
    DATASET_VERSION,
    SPLIT_TEST,
    SPLIT_TRAIN,
    SPLIT_VALIDATION,
    DatasetManifest,
    PolygonPoint,
    ReferenceImageRecord,
    WallSurfaceAnnotation,
    calculate_sha256,
    normalize_image_id,
    write_manifest,
)

from .dataset_validator import (
    DatasetValidationResult,
    validate_dataset_files,
)

from .annotation_prep import (
    ANNOTATION_STATUS_ANNOTATED,
    ANNOTATION_STATUS_IN_PROGRESS,
    ANNOTATION_STATUS_NO_TARGET,
    ANNOTATION_STATUS_PENDING,
    ANNOTATION_STATUS_REVIEW_REQUIRED,
    SPLIT_UNASSIGNED,
    AnnotationPrepManifest,
    AnnotationTask,
    build_annotation_prep_manifest,
    stable_annotation_id,
    validate_annotation_prep_manifest,
    write_annotation_prep_manifest,
)
