from pydantic import BaseModel, ConfigDict


class LookupItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    label: str
    description: str | None = None
    icon: str | None = None


class LookupsResponse(BaseModel):
    gender: list[LookupItem]
    diet_preference: list[LookupItem]
    activity_level: list[LookupItem]
    mizaj_types: list[LookupItem]
    languages: list[LookupItem]
    hakeem_gender_preference: list[LookupItem]
    health_interest: list[LookupItem]
    health_flag: list[LookupItem]
    post_categories: list[LookupItem]
