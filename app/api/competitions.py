from fastapi import APIRouter, HTTPException

from app.config.competition_config import load_competition_config
from app.transformations.competition_structure import (
    normalize_competition_structure,
)


router = APIRouter(
    prefix="/competitions",
    tags=["Competitions"],
)


@router.get("/sub16-fdm-2025-2026")
def get_sub16_fdm_competition():
    try:
        config = load_competition_config(
            "sub16_fdm_2025_2026.json"
        )

        return normalize_competition_structure(config)

    except FileNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error