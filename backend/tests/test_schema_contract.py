from sqlalchemy import Numeric

from app.platform.db.models import Base


CORE_TABLES = {
    "instance_metadata",
    "department",
    "person",
    "company",
    "resource",
    "account",
    "resource_person",
    "resource_company",
    "resource_relation",
    "contact_identity",
    "mailbox_contact_association",
    "account_binding",
    "subscription_profile",
    "subscription_budget",
    "material",
    "change_case",
    "change_item",
    "change_relation_detail",
    "audit_event",
    "credential_ref",
    "credential_grant",
    "credential_stage",
}


def test_core_schema_contains_only_the_approved_metadata_surface() -> None:
    assert CORE_TABLES <= set(Base.metadata.tables)
    assert "v1_instance_guard" not in Base.metadata.tables
    assert "credential" not in Base.metadata.tables


def test_resource_and_relationship_contracts_are_explicit() -> None:
    resource = Base.metadata.tables["resource"]
    assert {"code", "name", "type_code", "attributes", "version"} <= set(resource.c.keys())
    assert {constraint.name for constraint in resource.constraints} >= {
        "ck_resource_type_code",
        "ck_resource_lifecycle",
        "ck_resource_visibility_scope",
    }

    mailbox = Base.metadata.tables["mailbox_contact_association"]
    assert {"valid_from", "valid_to", "role", "confirmation"} <= set(mailbox.c.keys())

    budget = Base.metadata.tables["subscription_budget"]
    amount_type = budget.c.amount.type
    assert isinstance(amount_type, Numeric)
    assert amount_type.precision == 18
    assert amount_type.scale == 2


def test_change_item_does_not_store_credentials() -> None:
    change_item = Base.metadata.tables["change_item"]
    assert "non_secret_result" in change_item.c
    assert not any(
        token in column.name.lower()
        for column in change_item.c
        for token in ("password", "credential", "secret_ciphertext")
    )


def test_credential_storage_is_encrypted_and_stages_are_one_time() -> None:
    credential = Base.metadata.tables["credential_ref"]
    assert {"ciphertext", "nonce", "key_version", "version"} <= set(credential.c.keys())
    assert "protected_value" not in credential.c

    stage = Base.metadata.tables["credential_stage"]
    assert {"token_hash", "ciphertext", "nonce", "key_version", "expires_at", "consumed_at"} <= set(stage.c.keys())
