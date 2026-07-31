from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.lookups.repository import LookupRepository
from app.domains.lookups.schemas import LookupItem, LookupsResponse
from app.domains.users.models import (
    ActivityLevel,
    DietPreference,
    Gender,
    HakeemGenderPreference,
    MizajType,
    PreferredLanguage,
)

# Display metadata for fixed enums (not content-managed).
ACTIVITY_META: dict[str, dict[str, str]] = {
    ActivityLevel.LOW.value: {
        "description": "Mostly sedentary, light walking",
        "icon": "weekend",
    },
    ActivityLevel.MODERATE.value: {
        "description": "Active 3-4 days a week",
        "icon": "directions-walk",
    },
    ActivityLevel.ACTIVE.value: {
        "description": "Daily exercise or manual labor",
        "icon": "fitness-center",
    },
}

MIZAJ_META: dict[str, dict[str, str]] = {
    MizajType.DAMVI.value: {
        "label": "Damvi",
        "description": "Warm & moist — sociable, energetic, and quick to recover",
    },
    MizajType.SAFRAVI.value: {
        "label": "Safravi",
        "description": "Warm & dry — sharp, driven, and heat-sensitive",
    },
    MizajType.BALGHAMI.value: {
        "label": "Balghami",
        "description": "Cold & moist — calm, steady, and slower to warm up",
    },
    MizajType.SAUDAVI.value: {
        "label": "Saudavi",
        "description": "Cold & dry — thoughtful, precise, and easily chilled",
    },
}

LANGUAGE_META: dict[str, str] = {
    PreferredLanguage.URDU.value: "Urdu",
    PreferredLanguage.ENGLISH.value: "English",
    PreferredLanguage.PUNJABI.value: "Punjabi",
}

HAKEEM_GENDER_META: dict[str, str] = {
    HakeemGenderPreference.NO_PREFERENCE.value: "No preference",
    HakeemGenderPreference.MALE.value: "Male",
    HakeemGenderPreference.FEMALE.value: "Female",
}


class LookupService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = LookupRepository(session)

    async def get_keys(self, lookup_type: str) -> set[str]:
        return await self.repo.list_keys(lookup_type)

    async def get_all(self) -> LookupsResponse:
        interests = await self.repo.list_by_type("health_interest")
        flags = await self.repo.list_by_type("health_flag")

        return LookupsResponse(
            gender=[LookupItem(key=g.value, label=g.value) for g in Gender],
            diet_preference=[
                LookupItem(key=d.value, label=d.value) for d in DietPreference
            ],
            activity_level=[
                LookupItem(
                    key=a.value,
                    label=a.value,
                    description=ACTIVITY_META[a.value]["description"],
                    icon=ACTIVITY_META[a.value]["icon"],
                )
                for a in ActivityLevel
            ],
            mizaj_types=[
                LookupItem(
                    key=m.value,
                    label=MIZAJ_META[m.value]["label"],
                    description=MIZAJ_META[m.value]["description"],
                )
                for m in MizajType
            ],
            languages=[
                LookupItem(key=lang.value, label=LANGUAGE_META[lang.value])
                for lang in PreferredLanguage
            ],
            hakeem_gender_preference=[
                LookupItem(key=pref.value, label=HAKEEM_GENDER_META[pref.value])
                for pref in HakeemGenderPreference
            ],
            health_interest=[
                LookupItem(
                    key=row.key,
                    label=row.label,
                    description=row.description,
                    icon=row.icon,
                )
                for row in interests
            ],
            health_flag=[
                LookupItem(
                    key=row.key,
                    label=row.label,
                    description=row.description,
                    icon=row.icon,
                )
                for row in flags
            ],
        )
