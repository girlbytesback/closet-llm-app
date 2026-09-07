from pydantic import BaseModel

class GarmentsResponse(BaseModel):
    count: int
    garments: dict[str, list[str]]

class PalettesResponse(BaseModel):
    count: int
    palettes: dict[str, list[str]]

class Hit(BaseModel):
    garment: str
    score: float

class PaletteEntry(BaseModel):
    colors: list[str]
    src: str
    matches: dict[str, list[Hit]]

class GarmentEntry(BaseModel):
    colors: list[str]
    src: str

class Meta(BaseModel):
    cutoff: float
    garment_count: int
    palette_count: int

class MatchesResponse(BaseModel):
    meta: Meta
    garments: dict[str, GarmentEntry]
    palettes: dict[str, PaletteEntry]