from decimal import Decimal, InvalidOperation

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from sqlalchemy.orm import selectinload

from app.database import SessionLocal
from app.models.mill import Mill
from app.models.sample_correction import SampleCorrection
from app.models.viscosity_sample import ViscositySample
from app.serializers import viscosity_sample_json
from app.utils import error, normalize_datetime

bp = Blueprint("viscosity_samples", __name__, url_prefix="/api/viscosity-samples")


def _validate_create(body: dict) -> str | None:
    mill_id = int(body.get("millId") or 0)
    if mill_id <= 0:
        return "请选择研磨机"

    db = SessionLocal()
    try:
        if not db.get(Mill, mill_id):
            return "研磨机不存在"
    finally:
        db.close()

    sampled_at = str(body.get("sampledAt", "")).strip()
    if not sampled_at:
        return "取样时间不能为空"

    viscosity = _parse_positive_decimal(body.get("viscosityPaS"))
    if viscosity is None:
        return "粘度(Pa·s)必须大于 0"

    return None


def _parse_positive_decimal(raw) -> Decimal | None:
    if raw is None or raw == "":
        return None
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, ValueError):
        return None
    if not value.is_finite() or value <= 0:
        return None
    return value


def _get_sample(db, item_id: int) -> ViscositySample | None:
    return (
        db.query(ViscositySample)
        .options(selectinload(ViscositySample.corrections))
        .filter(ViscositySample.id == item_id)
        .one_or_none()
    )


@bp.get("")
@jwt_required()
def list_samples():
    db = SessionLocal()
    try:
        rows = (
            db.query(ViscositySample)
            .options(selectinload(ViscositySample.corrections))
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
        row = _get_sample(db, item_id)
        if not row:
            return error("粘度取样记录不存在", 404)
        # 与列表走同一个序列化器，保证两处有效粘度口径完全一致。
        return jsonify(viscosity_sample_json(row, include_corrections=True))
    finally:
        db.close()


@bp.post("")
@jwt_required()
def create_sample():
    body = request.get_json(silent=True) or {}
    err = _validate_create(body)
    if err:
        return error(err, 400)

    temp_raw = body.get("tempC")
    temp_c = None
    if temp_raw is not None and temp_raw != "":
        temp_c = Decimal(str(temp_raw))

    db = SessionLocal()
    try:
        row = ViscositySample(
            mill_id=int(body["millId"]),
            sampled_at=normalize_datetime(str(body["sampledAt"])),
            viscosity_pa_s=Decimal(str(body["viscosityPaS"])),
            temp_c=temp_c,
            notes=str(body.get("notes", "")).strip() or None,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        row = _get_sample(db, row.id)
        return jsonify(viscosity_sample_json(row, include_corrections=True)), 201
    finally:
        db.close()


@bp.post("/<int:item_id>/corrections")
@jwt_required()
def add_correction(item_id: int):
    body = request.get_json(silent=True) or {}

    viscosity = _parse_positive_decimal(body.get("viscosityPaS"))
    if viscosity is None:
        return error("更正粘度(Pa·s)必须大于 0", 400)

    reason = str(body.get("reason", "")).strip()
    if not reason:
        return error("更正原因不能为空", 400)

    db = SessionLocal()
    try:
        row = _get_sample(db, item_id)
        if not row:
            return error("粘度取样记录不存在", 404)

        # 仅追加更正行；原取样行的 viscosity_pa_s 与 sampled_at 永不修改。
        correction = SampleCorrection(
            sample_id=row.id,
            viscosity_pa_s=viscosity,
            reason=reason,
        )
        db.add(correction)
        db.commit()
        row = _get_sample(db, row.id)
        return jsonify(viscosity_sample_json(row, include_corrections=True)), 201
    finally:
        db.close()


@bp.put("/<int:item_id>")
@jwt_required()
def update_sample(item_id: int):
    body = request.get_json(silent=True) or {}

    mill_id = int(body.get("millId") or 0)
    if mill_id <= 0:
        return error("请选择研磨机", 400)

    db = SessionLocal()
    try:
        if not db.get(Mill, mill_id):
            return error("研磨机不存在", 400)

        row = _get_sample(db, item_id)
        if not row:
            return error("粘度取样记录不存在", 404)

        # 粘度与取样时间是测量原始事实，只能通过 /corrections 追加更正，
        # 不允许 PUT 覆盖原 viscosityPaS 来假装更正。
        if body.get("viscosityPaS") is not None:
            submitted = _parse_positive_decimal(body.get("viscosityPaS"))
            if submitted is None or submitted != Decimal(row.viscosity_pa_s):
                return error("原始粘度不可修改，请使用“追加更正”功能", 400)
        if str(body.get("sampledAt", "")).strip():
            submitted_at = normalize_datetime(str(body["sampledAt"]))
            if submitted_at != row.sampled_at:
                return error("取样时间不可修改", 400)

        temp_raw = body.get("tempC")
        temp_c = None
        if temp_raw is not None and temp_raw != "":
            temp_c = Decimal(str(temp_raw))

        row.mill_id = mill_id
        row.temp_c = temp_c
        row.notes = str(body.get("notes", "")).strip() or None
        db.commit()
        row = _get_sample(db, row.id)
        return jsonify(viscosity_sample_json(row, include_corrections=True))
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
