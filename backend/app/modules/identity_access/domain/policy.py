"""Framework-independent, default-deny authorization decision engine."""

from dataclasses import dataclass, field
from enum import StrEnum


class DenialCode(StrEnum):
    AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    REAUTHENTICATION_REQUIRED = "REAUTHENTICATION_REQUIRED"
    AUDIT_UNAVAILABLE = "AUDIT_UNAVAILABLE"


@dataclass(frozen=True)
class PolicySubject:
    subject_id: str | None
    capabilities: frozenset[str] = field(default_factory=frozenset)
    authenticated: bool = False


@dataclass(frozen=True)
class PolicyFacts:
    """Facts are supplied by owning modules; unknown facts never imply access."""

    resource_visible: bool | None = None
    action_allowed: bool | None = None
    scope_allowed: bool | None = None
    credential_grant_active: bool | None = None
    recent_authentication: bool | None = None
    audit_available: bool | None = None


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    denial_code: DenialCode | None = None


class PolicyEngine:
    def decide(
        self,
        subject: PolicySubject,
        capability: str,
        *,
        facts: PolicyFacts | None = None,
        resource_id: str | None = None,
        requires_scope: bool = False,
        requires_action: bool = False,
        credential_access: bool = False,
    ) -> PolicyDecision:
        if not subject.authenticated or not subject.subject_id:
            return PolicyDecision(False, DenialCode.AUTHENTICATION_REQUIRED)
        if capability not in subject.capabilities:
            return PolicyDecision(False, DenialCode.PERMISSION_DENIED)

        resolved_facts = facts or PolicyFacts()
        if resource_id is not None and resolved_facts.resource_visible is not True:
            return PolicyDecision(False, DenialCode.RESOURCE_NOT_FOUND)
        if requires_scope and resolved_facts.scope_allowed is not True:
            return PolicyDecision(False, DenialCode.PERMISSION_DENIED)
        if requires_action and resolved_facts.action_allowed is not True:
            return PolicyDecision(False, DenialCode.PERMISSION_DENIED)
        if credential_access:
            if resolved_facts.credential_grant_active is not True:
                return PolicyDecision(False, DenialCode.PERMISSION_DENIED)
            if resolved_facts.recent_authentication is not True:
                return PolicyDecision(False, DenialCode.REAUTHENTICATION_REQUIRED)
            if resolved_facts.audit_available is not True:
                return PolicyDecision(False, DenialCode.AUDIT_UNAVAILABLE)
        return PolicyDecision(True)
