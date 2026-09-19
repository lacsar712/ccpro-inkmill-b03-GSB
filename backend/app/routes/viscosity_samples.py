from decimal import Decimal, InvalidOperation

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from app.database import SessionLocal
from app.models.mill import Mill
from app.models.sample_correction import SampleCorrection
from app.models.viscosity_sample import ViscositySample
from app.serializers import viscosity_sample_json
from app.utils import error, normalize_datetime

bp = Blueprint("viscosity_samples", __name__, url_prefix="/api/viscosity-samples")


def _parse_positive_viscosity(body: dict) -> tuple[Decimal | None, str | None]:
    raw = body.get("viscosityPaS")
    if raw is None or str(raw).strip() == "":
        return None, "粘度(Pa·s)必须大于 0"
    try:
        value = Decimal(str(raw).strip())
    except (InvalidOperation, ValueError):
        return None, "粘度(Pa·s)必须大于 0"
    if not value.is_finite() or value <= 0:
        return None, "粘度(Pa·s)必须大于 0"
    return value, None


def _mill_exists(mill_id: int) -> bool:
    db = SessionLocal()
    try:
        return db.get(Mill, mill_id) is not None
    finally:
        db.close()


def _validate_sample(body: dict, *, require_viscosity: bool) -> str | None:
    mill_id = int(body.get("millId") or 0)
    if mill_id <= 0:
        return "请选择研磨机"
    if not _mill_exists(mill_id):
        return "研磨机不存在"

    sampled_at = str(body.get("sampledAt", "")).strip()
    if not sampled_at:
        return "取样时间不能为空"

    if require_viscosity:
        _, err = _parse_positive_viscosity(body)
        if err:
            return err

    return None


def _parse_temp(body: dict):
    temp_raw = body.get("tempC")
    if temp_raw is None or temp_raw == "":
        return None
    return Decimal(str(temp_raw))


@bp.get("")
@jwt_required()
def list_samples():
    db = SessionLocal()
    try:
        rows = (
            db.query(ViscositySample)
            .order_by(ViscositySample.sampled_at.desc(), ViscositySample.id.desc())
            .all()
        )
        return jsonify([viscosity_sample_json(r) for r in rows])
    finally:
        db.close()


@bp.get("/<int:item_id>")
@jwt_required()
def get_sample(item_id: int):
    db = SessionLocal()
    try:
        row = db.get(ViscositySample, item_id)
        if not row:
            return error("粘度取样记录不存在", 404)
        return jsonify(viscosity_sample_json(row))
    finally:
        db.close()


@bp.post("")
@jwt_required()
def create_sample():
    body = request.get_json(silent=True) or {}
    err = _validate_sample(body, require_viscosity=True)
    if err:
        return error(err, 400)

    viscosity, _ = _parse_positive_viscosity(body)

    db = SessionLocal()
    try:
        row = ViscositySample(
            mill_id=int(body["millId"]),
            sampled_at=normalize_datetime(str(body["sampledAt"])),
            viscosity_pa_s=viscosity,
            temp_c=_parse_temp(body),
            notes=str(body.get("notes", "")).strip() or None,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return jsonify(viscosity_sample_json(row)), 201
    finally:
        db.close()


@bp.put("/<int:item_id>")
@jwt_required()
def update_sample(item_id: int):
    body = request.get_json(silent=True) or {}
    # 仅允许维护研磨机/取样时间/温度/备注。
    # 粘度只能经“更正链”追加,严禁通过 PUT 覆盖原 viscosityPaS。
    err = _validate_sample(body, require_viscosity=False)
    if err:
        return error(err, 400)

    db = SessionLocal()
    try:
        row = db.get(ViscositySample, item_id)
        if not row:
            return error("粘度取样记录不存在", 404)

        row.mill_id = int(body["millId"])
        row.sampled_at = normalize_datetime(str(body["sampledAt"]))
        row.temp_c = _parse_temp(body)
        row.notes = str(body.get("notes", "")).strip() or None
        db.commit()
        db.refresh(row)
        return jsonify(viscosity_sample_json(row))
    finally:
        db.close()


@bp.post("/<int:item_id>/corrections")
@jwt_required()
def add_correction(item_id: int):
    body = request.get_json(silent=True) or {}

    viscosity, err = _parse_positive_viscosity(body)
    if err:
        return error(err, 400)

    reason = str(body.get("reason", "") or "").strip()
    if not reason:
        return error("更正原因不能为空", 400)

    db = SessionLocal()
    try:
        sample = db.get(ViscositySample, item_id)
        if not sample:
            return error("粘度取样记录不存在", 404)

        # 仅追加更正;原取样行的 viscosity_pa_s 与 sampled_at 绝不修改。
        correction = SampleCorrection(
            sample_id=sample.id,
            viscosity_pa_s=viscosity,
            reason=reason,
        )
        db.add(correction)
        db.commit()
        db.refresh(sample)
        return jsonify(viscosity_sample_json(sample)), 201
    finally:
        db.close()


@bp.delete("/<int:item_id>")
@jwt_required()
def delete_sample(item_id: int):
    db = SessionLocal()
    try:
        row = db.get(ViscositySample, item_id)
        if not row:
            return error("粘度取样记录不存在", 404)
        db.delete(row)
        db.commit()
        return jsonify({"ok": True})
    finally:
        db.close()
