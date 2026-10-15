"""Pydantic models for job state, validation reports, and API responses."""
from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel


class JobStatus(str, Enum):
    QUEUED     = "queued"
    PROCESSING = "processing"
    REPAIRING  = "repairing"
    VALIDATING = "validating"
    COMPLETED  = "completed"
    FAILED     = "failed"


class CheckResult(str, Enum):
    PASS    = "PASS"
    WARN    = "WARN"
    FAIL    = "FAIL"
    SKIPPED = "SKIPPED"


class ValidationCheck(BaseModel):
    name:   str
    result: CheckResult
    detail: str = ""


class ValidationReport(BaseModel):
    overall:               CheckResult
    watertight:            CheckResult
    components:            CheckResult
    boundary_edges:        CheckResult
    degenerate_faces:      CheckResult
    non_manifold:          CheckResult
    normal_consistency:    CheckResult
    self_intersections:    CheckResult
    volume_mm3:            Optional[float] = None
    bounding_box_mm:       Optional[list[float]] = None
    min_wall_thickness_mm: Optional[float] = None
    checks:                list[ValidationCheck] = []
    warnings:              list[str] = []
