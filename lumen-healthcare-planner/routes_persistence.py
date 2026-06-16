"""User persistence routes — notes, overrides, shortlists, scenarios."""

import json
from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel
from db import query, execute, APP_SCHEMA

router = APIRouter(prefix="/api", tags=["persistence"])


class NoteCreate(BaseModel):
    facility_id: str
    note_text: str
    category: str = "general"


class OverrideCreate(BaseModel):
    facility_id: str
    field_name: str
    override_value: str
    reason: Optional[str] = None


class ShortlistCreate(BaseModel):
    facility_id: str
    track: str
    label: Optional[str] = None


class ScenarioCreate(BaseModel):
    name: str
    track: str
    filters_json: dict
    notes: Optional[str] = None


# --- Notes ---
@router.post("/notes")
async def create_note(note: NoteCreate):
    execute(
        f"INSERT INTO {APP_SCHEMA}.user_notes (facility_id, note_text, category) VALUES (%s, %s, %s)",
        (note.facility_id, note.note_text, note.category)
    )
    return {"status": "created"}


@router.get("/notes/{facility_id}")
async def get_notes(facility_id: str):
    return query(
        f"SELECT * FROM {APP_SCHEMA}.user_notes WHERE facility_id = %s ORDER BY created_at DESC",
        (facility_id,)
    )


@router.delete("/notes/{note_id}")
async def delete_note(note_id: int):
    execute(f"DELETE FROM {APP_SCHEMA}.user_notes WHERE id = %s", (note_id,))
    return {"status": "deleted"}


# --- Overrides ---
@router.post("/overrides")
async def create_override(override: OverrideCreate):
    execute(
        f"INSERT INTO {APP_SCHEMA}.user_overrides (facility_id, field_name, override_value, reason) VALUES (%s, %s, %s, %s)",
        (override.facility_id, override.field_name, override.override_value, override.reason)
    )
    return {"status": "created"}


@router.get("/overrides/{facility_id}")
async def get_overrides(facility_id: str):
    return query(
        f"SELECT * FROM {APP_SCHEMA}.user_overrides WHERE facility_id = %s ORDER BY created_at DESC",
        (facility_id,)
    )


# --- Shortlists ---
@router.post("/shortlist")
async def add_to_shortlist(item: ShortlistCreate):
    execute(
        f"INSERT INTO {APP_SCHEMA}.shortlists (facility_id, track, label) VALUES (%s, %s, %s) ON CONFLICT (user_id, facility_id, track) DO UPDATE SET label = EXCLUDED.label",
        (item.facility_id, item.track, item.label)
    )
    return {"status": "added"}


@router.get("/shortlist/{track}")
async def get_shortlist(track: str):
    return query(
        f"SELECT * FROM {APP_SCHEMA}.shortlists WHERE track = %s ORDER BY created_at DESC",
        (track,)
    )


@router.delete("/shortlist/{item_id}")
async def remove_from_shortlist(item_id: int):
    execute(f"DELETE FROM {APP_SCHEMA}.shortlists WHERE id = %s", (item_id,))
    return {"status": "removed"}


# --- Scenarios ---
@router.post("/scenarios")
async def save_scenario(scenario: ScenarioCreate):
    execute(
        f"INSERT INTO {APP_SCHEMA}.scenarios (name, track, filters_json, notes) VALUES (%s, %s, %s, %s)",
        (scenario.name, scenario.track, json.dumps(scenario.filters_json), scenario.notes)
    )
    return {"status": "saved"}


@router.get("/scenarios/{track}")
async def get_scenarios(track: str):
    return query(
        f"SELECT * FROM {APP_SCHEMA}.scenarios WHERE track = %s ORDER BY updated_at DESC",
        (track,)
    )


@router.delete("/scenarios/{scenario_id}")
async def delete_scenario(scenario_id: int):
    execute(f"DELETE FROM {APP_SCHEMA}.scenarios WHERE id = %s", (scenario_id,))
    return {"status": "deleted"}
