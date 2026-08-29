"""Capability boundary around the integrated MIN0 CORE FORTH loader."""

from __future__ import annotations

from typing import Final

from min0_core_forth_image import IMAGE_ROLE_NORMAL, IMAGE_ROLE_RECOVERY
from min0_core_forth_loader import Min0CoreForthLoader, LoaderOrderError


PROFILE_RUNTIME: Final = "runtime"
PROFILE_MONITOR: Final = "monitor"
PROFILE_RECOVERY: Final = "recovery"
PROFILE_PROVISIONER: Final = "provisioner"

_PROFILES: Final = {
    PROFILE_RUNTIME,
    PROFILE_MONITOR,
    PROFILE_RECOVERY,
    PROFILE_PROVISIONER,
}

_PERMISSIONS: Final = {
    PROFILE_RUNTIME: frozenset({"inspect"}),
    PROFILE_MONITOR: frozenset({"inspect", "normal"}),
    PROFILE_RECOVERY: frozenset({"inspect", "normal"}),
    PROFILE_PROVISIONER: frozenset(
        {"inspect", "normal", "recovery", "trust", "root"}
    ),
}

_SESSION_MARKER = object()


class CapabilityError(RuntimeError):
    pass


class AuthorizationError(CapabilityError):
    pass


class TransactionOwnerError(CapabilityError):
    pass


class LoaderSession:
    """Opaque host-model capability; only LoaderAuthority can register one."""

    __slots__ = ("_authority", "_serial", "_label")

    def __init__(
        self,
        authority: "LoaderAuthority",
        serial: int,
        label: str,
        marker: object,
    ) -> None:
        if marker is not _SESSION_MARKER:
            raise AuthorizationError("loader sessions must be issued by the authority")
        self._authority = authority
        self._serial = serial
        self._label = label

    @property
    def label(self) -> str:
        return self._label

    def status(self) -> dict[str, object]:
        return self._authority.status(self)

    def select_boot(self) -> dict[str, object]:
        return self._authority.select_boot(self)

    def stage_root(self, raw: object, *, fail_after: str | None = None) -> int:
        return self._authority.stage_root(self, raw, fail_after=fail_after)

    def commit_root(self, *, fail_after: str | None = None) -> int:
        return self._authority.commit_root(self, fail_after=fail_after)

    def stage_trust(self, raw: object, *, fail_after: str | None = None) -> int:
        return self._authority.stage_trust(self, raw, fail_after=fail_after)

    def commit_trust(self, *, fail_after: str | None = None) -> int:
        return self._authority.commit_trust(self, fail_after=fail_after)

    def stage_image(
        self,
        raw: object,
        *,
        role: str,
        fail_after: str | None = None,
    ) -> str:
        return self._authority.stage_image(
            self, raw, role=role, fail_after=fail_after
        )

    def commit_image(
        self,
        role: str,
        slot: str,
        *,
        fail_after: str | None = None,
    ) -> int:
        return self._authority.commit_image(
            self, role, slot, fail_after=fail_after
        )

    def reject_image(self, role: str, slot: str) -> None:
        self._authority.reject_image(self, role, slot)

    def adopt_pending(self) -> dict[str, object]:
        return self._authority.adopt_pending(self)


class LoaderAuthority:
    """Trusted host owner of issued sessions and an otherwise hidden loader."""

    def __init__(self, loader: Min0CoreForthLoader) -> None:
        self._loader = loader
        self._profiles: dict[LoaderSession, str] = {}
        self._next_serial = 1
        self._owner: LoaderSession | None = None
        self._owner_domain: str | None = None
        self._owner_slot: str | None = None

    def issue(self, profile: str, *, label: str | None = None) -> LoaderSession:
        if profile not in _PROFILES:
            raise AuthorizationError("unknown loader capability profile")
        session = LoaderSession(
            self,
            self._next_serial,
            label or profile,
            _SESSION_MARKER,
        )
        self._next_serial += 1
        self._profiles[session] = profile
        return session

    def revoke(self, session: LoaderSession) -> None:
        self._profile(session)
        del self._profiles[session]
        if self._owner is session:
            self._clear_owner()

    def _profile(self, session: object) -> str:
        try:
            return self._profiles[session]  # type: ignore[index]
        except (KeyError, TypeError) as exc:
            raise AuthorizationError("unknown or revoked loader capability") from exc

    def _require(self, session: object, domain: str) -> str:
        profile = self._profile(session)
        if domain not in _PERMISSIONS[profile]:
            raise AuthorizationError(
                f"{profile} capability cannot operate the {domain} domain"
            )
        return profile

    def _require_stage_context(self, session: LoaderSession, domain: str) -> str:
        profile = self._require(session, domain)
        if profile == PROFILE_MONITOR and self._loader.select_boot()["mode"] != "normal":
            raise AuthorizationError("monitor updates require a normal boot context")
        if profile == PROFILE_RECOVERY:
            if domain != "normal":
                raise AuthorizationError("recovery capability can repair only normal images")
            if self._loader.select_boot()["mode"] != "recovery":
                raise AuthorizationError("recovery repair requires recovery boot mode")
        return profile

    def _claim(self, session: LoaderSession, domain: str, slot: str | None = None) -> None:
        if self._owner is not None:
            raise TransactionOwnerError("a loader transaction already has an owner")
        self._owner = session
        self._owner_domain = domain
        self._owner_slot = slot

    def _require_unowned(self) -> None:
        if self._owner is not None:
            raise TransactionOwnerError("finish or revoke the owned transaction first")

    def _require_owner(self, session: LoaderSession, domain: str) -> None:
        self._profile(session)
        if self._owner is not session or self._owner_domain != domain:
            raise TransactionOwnerError(
                "only the session that owns this transaction may finish it"
            )

    def _clear_owner(self) -> None:
        self._owner = None
        self._owner_domain = None
        self._owner_slot = None

    def status(self, session: object) -> dict[str, object]:
        self._require(session, "inspect")
        result = self._loader.status()
        result["transaction_owner"] = (
            None
            if self._owner is None
            else {
                "label": self._owner.label,
                "domain": self._owner_domain,
                "slot": self._owner_slot,
            }
        )
        return result

    def select_boot(self, session: object) -> dict[str, object]:
        self._require(session, "inspect")
        return self._loader.select_boot()

    def stage_root(
        self,
        session: LoaderSession,
        raw: object,
        *,
        fail_after: str | None = None,
    ) -> int:
        self._require_stage_context(session, "root")
        self._require_unowned()
        epoch = self._loader.stage_root_package(raw, fail_after=fail_after)
        self._claim(session, "root")
        return epoch

    def commit_root(
        self,
        session: LoaderSession,
        *,
        fail_after: str | None = None,
    ) -> int:
        self._require_owner(session, "root")
        committed = self._loader.commit_root(fail_after=fail_after)
        self._clear_owner()
        return committed

    def stage_trust(
        self,
        session: LoaderSession,
        raw: object,
        *,
        fail_after: str | None = None,
    ) -> int:
        self._require_stage_context(session, "trust")
        self._require_unowned()
        epoch = self._loader.stage_trust_package(raw, fail_after=fail_after)
        self._claim(session, "trust")
        return epoch

    def commit_trust(
        self,
        session: LoaderSession,
        *,
        fail_after: str | None = None,
    ) -> int:
        self._require_owner(session, "trust")
        committed = self._loader.commit_trust(fail_after=fail_after)
        self._clear_owner()
        return committed

    def stage_image(
        self,
        session: LoaderSession,
        raw: object,
        *,
        role: str,
        fail_after: str | None = None,
    ) -> str:
        domain = self._image_domain(role)
        self._require_stage_context(session, domain)
        self._require_unowned()
        if domain == "normal" and self._loader.select_boot()["mode"] == "recovery":
            slot = self._loader.stage_normal_repair_package(
                raw, fail_after=fail_after
            )
        else:
            slot = self._loader.stage_image_package(
                raw, role=role, fail_after=fail_after
            )
        self._claim(session, domain, slot)
        return slot

    def commit_image(
        self,
        session: LoaderSession,
        role: str,
        slot: str,
        *,
        fail_after: str | None = None,
    ) -> int:
        domain = self._image_domain(role)
        self._require_owner(session, domain)
        if slot != self._owner_slot:
            raise TransactionOwnerError("image slot does not match the owned transaction")
        committed = self._loader.commit_image(role, slot, fail_after=fail_after)
        self._clear_owner()
        return committed

    def reject_image(self, session: LoaderSession, role: str, slot: str) -> None:
        domain = self._image_domain(role)
        self._require_owner(session, domain)
        if slot != self._owner_slot:
            raise TransactionOwnerError("image slot does not match the owned transaction")
        self._loader.reject_image(role, slot)
        self._clear_owner()

    def adopt_pending(self, session: LoaderSession) -> dict[str, object]:
        self._profile(session)
        if self._owner is not None:
            raise TransactionOwnerError("pending transaction already has an owner")
        phase = self._loader.phase()
        if phase == "stable":
            raise LoaderOrderError("there is no persistent transaction to adopt")
        suffix = "-awaiting-commit"
        if not phase.endswith(suffix):
            raise LoaderOrderError("unknown persistent loader phase")
        domain = phase[: -len(suffix)]
        self._require(session, domain)
        slot = None
        if domain in ("normal", "recovery"):
            slot = self._loader._installer(domain).select_boot()["slot"]
        self._claim(session, domain, slot)
        return {"phase": phase, "domain": domain, "slot": slot}

    @staticmethod
    def _image_domain(role: str) -> str:
        if role == IMAGE_ROLE_NORMAL:
            return "normal"
        if role == IMAGE_ROLE_RECOVERY:
            return "recovery"
        raise AuthorizationError("unknown image capability domain")
