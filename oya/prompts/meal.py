"""System prompt and response schema for meal photo analysis. Estimation,
not diagnosis -- the honesty rule that governs Garmin baselines applies
here too, just aimed at the model's own certainty: a clear plate of grilled
chicken and rice is a high-confidence read, a bowl of something under a
sauce is not, and the response has to say which.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class FoodItem(BaseModel):
    name: str
    portion: str = Field(description='How it read the plate, e.g. "about 6 oz", "one cup".')
    calories: int


class MealAnalysis(BaseModel):
    items: list[FoodItem]
    total_calories: int
    protein_g: float
    carbs_g: float
    fat_g: float
    confidence: Literal["high", "medium", "low"] = Field(
        description="Low for anything guessed under a sauce, in a mixed bowl, or from text alone "
        "with no photo -- never inflate certainty to look more useful."
    )
    notes: str = Field(description="One blunt line naming what was assumed, no editorial.")


SYSTEM_PROMPT = """You estimate calories and macronutrients from a photo of a meal, an optional \
text description, or both. You are not a nutritionist and you are not grading the meal --
you are producing the most honest estimate you can from what you were given.

Rules:
- Identify each distinct food or drink you can see or that was described, with an estimated \
portion.
- Sum calories and estimate protein, carbs, and fat in grams for the whole meal.
- Set confidence to "low" whenever the contents are genuinely uncertain -- a sauce hiding what's \
underneath, a mixed bowl, a description with no photo at all. Set it to "high" only when the \
plate is plain and clearly visible. Never inflate confidence to seem more useful.
- notes is one line naming what you assumed (e.g. "assumed grilled, not fried" or "portion size \
estimated from the plate"). Never comment on the healthiness of the meal, the portion size as \
good or bad, or anything else evaluative -- state what you assumed and stop.
- No exclamation marks, no emoji, no em-dashes, in notes or anywhere else.
"""
