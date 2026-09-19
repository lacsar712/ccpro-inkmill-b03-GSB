from decimal import Decimal

from app.models.grind_pass import GrindPass
from app.models.mill import Mill
from app.models.sample_correction import SampleCorrection
from app.models.user import User
from app.models.viscosity_sample import ViscositySample
from app.models.workshop import Workshop
from app.utils import dt_to_json


def _num(value: Decimal | float | int | None) -> float | None:
    if value is None:
        return None
    return float(value)


def user_json(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "displayName": user.display_name,
        "role": user.role,
    }


def workshop_json(row: Workshop) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "site": row.site,
        "notes": row.notes,
    }


def mill_json(row: Mill) -> dict:
    return {
        "id": row.id,
        "workshopId": row.workshop_id,
        "millCode": row.mill_code,
        "pigmentBase": row.pigment_base,
        "bowlLiters": _num(row.bowl_liters) or 0,
        "status": row.status,
    }


def sample_correction_json(row: SampleCorrection) -> dict:
    return {
        "id": row.id,
        "sampleId": row.sample_id,
        "viscosityPaS": _num(row.viscosity_pa_s) or 0,
        "reason": row.reason,
        "correctedAt": dt_to_json(row.corrected_at),
    }


def _latest_correction(row: ViscositySample) -> SampleCorrection | None:
    """有效更正经 (corrected_at, id) 升序关系的最后一条即最新一条。"""
    corrections = list(row.corrections or [])
    return corrections[-1] if corrections else None


def viscosity_sample_json(row: ViscositySample) -> dict:
    original = _num(row.viscosity_pa_s) or 0
    latest = _latest_correction(row)
    effective = (_num(latest.viscosity_pa_s) or 0) if latest else original
    corrections = list(row.corrections or [])
    # 历史按最新在前返回,便于前端直接展示。
    history = [sample_correction_json(c) for c in reversed(corrections)]
    return {
        "id": row.id,
        "millId": row.mill_id,
        "sampledAt": dt_to_json(row.sampled_at),
        "viscosityPaS": original,
        "originalViscosityPaS": original,
        "effectiveViscosityPaS": effective,
        "correctionCount": len(corrections),
        "tempC": _num(row.temp_c),
        "notes": row.notes,
        "corrections": history,
    }


def grind_pass_json(row: GrindPass) -> dict:
    return {
        "id": row.id,
        "millId": row.mill_id,
        "startedAt": dt_to_json(row.started_at),
        "passNo": row.pass_no,
        "durationMin": _num(row.duration_min) or 0,
        "mediaType": row.media_type,
        "operatorName": row.operator_name,
    }
