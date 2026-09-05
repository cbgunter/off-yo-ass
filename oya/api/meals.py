"""Meal logging by photo and free-text description -- no manual macro
entry anywhere. /analyze runs the vision call and stores the photo but
not the meal, so a wrong estimate is corrected by adding a sentence and
re-running, never by typing numbers into a form; /meals ("") is the
separate save step once the estimate looks right.
"""

from __future__ import annotations

import base64
import uuid
from datetime import UTC, datetime

import boto3
from anthropic import Anthropic
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from oya.api.auth import User, get_current_user
from oya.domain.food import get_food_snapshot
from oya.prompts.meal import SYSTEM_PROMPT, FoodItem, MealAnalysis
from oya.prompts.validate import is_clean
from oya.settings import get_settings
from oya.store.table import Entity, put_item

router = APIRouter(prefix="/api/meals", tags=["meals"])

MODEL = "claude-sonnet-5"


class AnalyzeIn(BaseModel):
    photo_base64: str | None = None
    description: str = ""


class AnalyzeOut(BaseModel):
    photo_id: str | None
    analysis: MealAnalysis


class MealIn(BaseModel):
    photo_id: str | None = None
    description: str = ""
    analysis: MealAnalysis


class MealOut(BaseModel):
    when: str
    description: str
    photo_id: str | None
    items: list[FoodItem]
    total_calories: int
    protein_g: float
    carbs_g: float
    fat_g: float
    confidence: str
    notes: str


class FoodTotals(BaseModel):
    label: str
    unit: str | None
    today: float | None
    average: float | None
    delta: float | None
    delta_pct: float | None
    days: int
    building: bool


class TodayOut(BaseModel):
    calories: FoodTotals
    meals: list[MealOut]


def _validate_photo_id(photo_id: str) -> None:
    # photo_id becomes an S3 key -- this is what keeps a client-supplied
    # value from ever reaching a path-traversal or arbitrary-object read.
    try:
        uuid.UUID(photo_id)
    except ValueError as exc:
        raise HTTPException(400, "Invalid photo id.") from exc


def _s3():
    return boto3.client("s3")


def _client() -> Anthropic:
    return Anthropic(api_key=get_settings().resolved_anthropic_api_key())


def _analyze(photo_base64: str | None, description: str) -> MealAnalysis:
    content: list[dict] = []
    if photo_base64:
        content.append(
            {
                "type": "image",
                "source": {"type": "base64", "media_type": "image/jpeg", "data": photo_base64},
            }
        )
    content.append(
        {
            "type": "text",
            "text": description.strip() or "No description given -- estimate from the photo alone.",
        }
    )

    response = _client().messages.parse(
        model=MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content}],
        output_format=MealAnalysis,
    )
    parsed = response.parsed_output
    if not is_clean(parsed.notes):
        parsed = parsed.model_copy(
            update={"notes": "Estimate based on the photo and description."}
        )
    return parsed


@router.post("/analyze")
def analyze_meal(body: AnalyzeIn, user: User = Depends(get_current_user)) -> AnalyzeOut:
    if not body.photo_base64 and not body.description.strip():
        raise HTTPException(400, "A photo or a description is required.")

    photo_id: str | None = None
    if body.photo_base64:
        photo_id = str(uuid.uuid4())
        _s3().put_object(
            Bucket=get_settings().meal_photos_bucket,
            Key=f"meals/{photo_id}.jpg",
            Body=base64.b64decode(body.photo_base64),
            ContentType="image/jpeg",
        )

    analysis = _analyze(body.photo_base64, body.description)
    return AnalyzeOut(photo_id=photo_id, analysis=analysis)


@router.post("", status_code=201)
def save_meal(body: MealIn, user: User = Depends(get_current_user)) -> MealOut:
    if body.photo_id:
        _validate_photo_id(body.photo_id)

    when = datetime.now(UTC).isoformat()
    analysis = body.analysis
    put_item(
        Entity.MEAL,
        when,
        {
            "description": body.description,
            "photo_id": body.photo_id,
            "items": [item.model_dump() for item in analysis.items],
            "total_calories": analysis.total_calories,
            "protein_g": analysis.protein_g,
            "carbs_g": analysis.carbs_g,
            "fat_g": analysis.fat_g,
            "confidence": analysis.confidence,
            "notes": analysis.notes,
        },
    )
    return MealOut(
        when=when,
        description=body.description,
        photo_id=body.photo_id,
        items=analysis.items,
        total_calories=analysis.total_calories,
        protein_g=analysis.protein_g,
        carbs_g=analysis.carbs_g,
        fat_g=analysis.fat_g,
        confidence=analysis.confidence,
        notes=analysis.notes,
    )


@router.get("/today")
def today_meals(user: User = Depends(get_current_user)) -> TodayOut:
    snapshot = get_food_snapshot()
    c = snapshot.calories
    return TodayOut(
        calories=FoodTotals(
            label=c.label,
            unit=c.unit,
            today=c.today,
            average=c.average,
            delta=c.delta,
            delta_pct=c.delta_pct,
            days=c.days,
            building=c.building,
        ),
        meals=[
            MealOut(
                when=m.when,
                description=m.description,
                photo_id=m.photo_id,
                items=[FoodItem(**item) for item in m.items],
                total_calories=m.total_calories,
                protein_g=m.protein_g,
                carbs_g=m.carbs_g,
                fat_g=m.fat_g,
                confidence=m.confidence,
                notes=m.notes,
            )
            for m in snapshot.meals
        ],
    )


@router.get("/photo/{photo_id}")
def get_photo(photo_id: str, user: User = Depends(get_current_user)) -> Response:
    _validate_photo_id(photo_id)
    s3 = _s3()
    try:
        obj = s3.get_object(Bucket=get_settings().meal_photos_bucket, Key=f"meals/{photo_id}.jpg")
    except s3.exceptions.NoSuchKey as exc:
        raise HTTPException(404, "Photo not found.") from exc
    return Response(content=obj["Body"].read(), media_type="image/jpeg")
