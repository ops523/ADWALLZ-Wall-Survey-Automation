from __future__ import annotations

from dataclasses import dataclass

from src.osm.roads import normalize_reference


@dataclass(frozen=True)
class RoadIdentity:
    """
    A geographically scoped historical/current road identity.

    This is deliberately NOT a global road alias.

    A mapping is valid only when the supplied target matches the
    geographic scope recorded in the identity.
    """

    requested_reference: str
    historical_references: tuple[str, ...]
    current_references: tuple[str, ...]
    state: str
    district: str
    pincode: str
    place_name: str
    verification_status: str
    verification_source: str

    @property
    def normalized_requested_reference(self) -> str:
        return normalize_reference(
            self.requested_reference
        )

    @property
    def normalized_historical_references(self) -> tuple[str, ...]:
        return tuple(
            normalize_reference(value)
            for value in self.historical_references
        )

    @property
    def normalized_current_references(self) -> tuple[str, ...]:
        return tuple(
            normalize_reference(value)
            for value in self.current_references
        )


@dataclass(frozen=True)
class RoadIdentityMatch:
    identity: RoadIdentity
    matched_historical_reference: str
    current_reference: str


class RoadIdentityRegistry:
    """
    Resolve historical/current road identities only within an
    explicitly registered geographic scope.

    No fuzzy/global aliases are permitted.
    """

    def __init__(
        self,
        identities: tuple[RoadIdentity, ...] = (),
    ) -> None:
        self._identities = identities

    @property
    def identities(self) -> tuple[RoadIdentity, ...]:
        return self._identities

    def find(
        self,
        requested_reference: str,
        state: str,
        district: str,
        pincode: str,
        place_name: str,
    ) -> RoadIdentityMatch | None:
        requested = normalize_reference(
            requested_reference
        )

        if not requested:
            return None

        for identity in self._identities:
            if identity.verification_status != "VERIFIED":
                continue

            if (
                identity.state.casefold().strip()
                != state.casefold().strip()
            ):
                continue

            if (
                identity.district.casefold().strip()
                != district.casefold().strip()
            ):
                continue

            if identity.pincode.strip() != pincode.strip():
                continue

            if (
                identity.place_name.casefold().strip()
                != place_name.casefold().strip()
            ):
                continue

            historical = (
                identity.normalized_historical_references
            )

            if requested not in historical:
                continue

            current = (
                identity.normalized_current_references
            )

            if not current:
                continue

            return RoadIdentityMatch(
                identity=identity,
                matched_historical_reference=requested,
                current_reference=current[0],
            )

        return None


# ------------------------------------------------------------------
# Verified geographic identities
# ------------------------------------------------------------------
#
# IMPORTANT:
# This is intentionally narrow.
#
# SH57 -> NH67 is registered ONLY for the verified Atmakur/Nellore
# corridor represented by this target scope.
#
# It must NOT become:
#
#     SH57 -> NH67 everywhere in Andhra Pradesh.
#
# ------------------------------------------------------------------

VERIFIED_ROAD_IDENTITIES = (
    RoadIdentity(
        requested_reference="SH57",
        historical_references=(
            "SH57",
            "State Highway 57",
        ),
        current_references=(
            "NH67",
        ),
        state="Andhra Pradesh",
        district="Nellore",
        pincode="524322",
        place_name="Atmakur",
        verification_status="VERIFIED",
        verification_source=(
            "Verified historical/current corridor mapping: "
            "Badvel-Atmakur-Nellore"
        ),
    ),
)


DEFAULT_ROAD_IDENTITY_REGISTRY = RoadIdentityRegistry(
    VERIFIED_ROAD_IDENTITIES
)
