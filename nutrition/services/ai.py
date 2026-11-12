"""Claude vision recognition and the privacy-aware nutrition assistant.

Both calls go to the Anthropic Messages API from the server, using ANTHROPIC_API_KEY from the
environment. Photos are re-encoded in memory (EXIF/GPS removed, max 1568 px) and never stored.
Without a key the app still works: the user selects the dish and portion by hand.
"""
from __future__ import annotations

import base64
import io
import json
import urllib.error
import urllib.request

from django.conf import settings

API_URL = "https://api.anthropic.com/v1/messages"


class AIUnavailable(Exception):
    pass


def enabled() -> bool:
    return bool(settings.ANTHROPIC_API_KEY)


def clean_image(fileobj) -> tuple[str, str]:
    """Strip metadata and downscale; return (base64, media_type)."""
    from PIL import Image, ImageOps

    img = Image.open(fileobj)
    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((1568, 1568))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88)          # re-encoding drops EXIF/GPS
    return base64.standard_b64encode(buf.getvalue()).decode(), "image/jpeg"


def _call(messages: list, max_tokens: int = 700, system: str | None = None) -> str:
    if not enabled():
        raise AIUnavailable("ANTHROPIC_API_KEY is not set")
    body = {"model": settings.ANV_VISION_MODEL, "max_tokens": max_tokens, "messages": messages}
    if system:
        body["system"] = system
    req = urllib.request.Request(API_URL, data=json.dumps(body).encode(), method="POST", headers={
        "x-api-key": settings.ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            data = json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise AIUnavailable(f"AI service error {e.code}") from e
    except urllib.error.URLError as e:
        raise AIUnavailable("AI service unreachable") from e
    return "".join(b.get("text", "") for b in data.get("content", []))


def _json(text: str) -> dict:
    return json.loads(text[text.find("{"): text.rfind("}") + 1])


def recognise(image_b64: str, media_type: str, dish_list: list[tuple[str, str, str]]) -> dict:
    catalogue = "; ".join(f"{c} = {en} / {ar}" for c, en, ar in dish_list)
    prompt = (
        "You are a dietitian's assistant for Arabic (Levantine, Gulf, Egyptian) food. Look at the photo.\n"
        f"1. Pick the closest dish_id from: {catalogue}. If none fits use \"other\" and give other_name.\n"
        "2. Estimate the edible portion on the plate in grams with a low-high range; use any plate, spoon, hand or bank card as scale.\n"
        "3. Guess the preparation style \"home\", \"restaurant\" or \"light\" from visible oil, ghee, nuts and fried items.\n"
        "4. Separately give your own direct image-only estimate of kcal, protein_g, fat_g, carb_g for the portion, ignoring any recipe table.\n"
        'Reply with only JSON: {"is_food":true,"dish_id":"","other_name":"","confidence":0.0,'
        '"top3":[{"dish_id":"","confidence":0.0}],"portion_g":0,"portion_low":0,"portion_high":0,"style":"home",'
        '"reference_object":"none","visible_components":[],"direct_estimate":{"kcal":0,"protein_g":0,"fat_g":0,"carb_g":0},'
        '"notes":"one short sentence"}')
    text = _call([{"role": "user", "content": [
        {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_b64}},
        {"type": "text", "text": prompt}]}])
    return _json(text)


ASSISTANT_SYSTEM = (
    "You are a careful clinical-nutrition research assistant for the ArabNutriVision project (University of Petra). "
    "You receive only aggregated, de-identified intake numbers computed by a recipe-aware composition table for Arabic dishes. "
    "Answer in the language of the question (Arabic or English), be concise, cite the numbers you use, flag hidden-fat sources "
    "(oil, ghee, tahini, fatty meat) when relevant, state that values come from provisional draft recipes, and never give a diagnosis.")


def ask_assistant(question: str, summary: dict) -> str:
    content = f"De-identified intake summary (JSON):\n{json.dumps(summary, ensure_ascii=False)}\n\nQuestion: {question}"
    return _call([{"role": "user", "content": content}], max_tokens=900, system=ASSISTANT_SYSTEM).strip()
