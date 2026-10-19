import base64
import os
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.config import Settings
from app.modules.credentials.api.schemas import CredentialAttachRequest, CredentialGrantCreate, CredentialRevealRequest, SecretStageCreate
from app.modules.credentials.application.service import attach_credential, create_credential_grant, create_secret_stage, reveal_credential
from app.modules.materials.api.schemas import MaterialCreateRequest
from app.modules.materials.application.service import create_material, list_materials
from app.modules.resources.public import get_resource
from app.platform.db.models import AuditEvent, CredentialGrant, CredentialRef, CredentialStage, Material, Person, Resource
from app.platform.db.target import create_database_engine
from app.platform.http.errors import ApiException


pytestmark = pytest.mark.skipif(
    os.getenv("DAP_POSTGRES_TESTS") != "1",
    reason="requires the isolated CI PostgreSQL service",
)


def _crypto_settings() -> Settings:
    settings = Settings.from_environment()
    return Settings.model_validate(
        {
            **settings.model_dump(),
            "credential_master_key": base64.urlsafe_b64encode(b"integration-test-master-key-32!!").decode("ascii"),
        }
    )


def test_postgres_persists_resource_material_and_encrypted_credential_flow() -> None:
    settings = _crypto_settings()
    engine = create_database_engine(settings)
    session = Session(engine)
    resource_id: UUID | None = None
    person_id: UUID | None = None
    stage_id: UUID | None = None
    credential_id: UUID | None = None
    try:
        resource = Resource(
            code=f"ci-credential-{uuid4().hex[:12]}",
            name="CI credential resource",
            type_code="platform_account",
        )
        person = Person(display_name="CI credential reader", status="active")
        session.add_all([resource, person])
        session.commit()
        resource_id = resource.id
        person_id = person.id

        stage, stage_token = create_secret_stage(
            session,
            settings,
            SecretStageCreate(kind="password", secret_value="synthetic-integration-secret"),
        )
        stage_id = stage.id
        credential_id = attach_credential(
            session,
            settings,
            resource.id,
            CredentialAttachRequest(expected_version=1, stage_token=stage_token, kind="password"),
            actor_id=person.id,
            request_id=uuid4(),
        )

        stored_credential = session.get(CredentialRef, credential_id)
        stored_stage = session.get(CredentialStage, stage.id)
        assert stored_credential is not None
        assert stored_credential.ciphertext is not None
        assert b"synthetic-integration-secret" not in stored_credential.ciphertext
        assert stored_stage is not None and stored_stage.consumed_at is not None

        with pytest.raises(ApiException) as replay_error:
            attach_credential(
                session,
                settings,
                resource.id,
                CredentialAttachRequest(expected_version=2, stage_token=stage_token, kind="password"),
                actor_id=person.id,
                request_id=uuid4(),
            )
        assert replay_error.value.code == "STAGE_EXPIRED"

        create_credential_grant(
            session,
            credential_id,
            CredentialGrantCreate(
                person_id=person.id,
                capability="view",
                valid_to=datetime.now(UTC) + timedelta(minutes=30),
                reason="CI integration test",
                expected_version=1,
            ),
            actor_id=person.id,
            request_id=uuid4(),
        )
        assert reveal_credential(
            session,
            settings,
            credential_id,
            CredentialRevealRequest(reason="CI integration reveal"),
            actor_id=person.id,
            request_id=uuid4(),
        ) == "synthetic-integration-secret"

        created_material = create_material(
            session,
            resource.id,
            MaterialCreateRequest(kind="note", title="Runbook", body="Use the approved access procedure."),
            actor_id=person.id,
            request_id=uuid4(),
        )
        assert created_material.version == 1
        materials, total = list_materials(session, resource.id, page=1, page_size=25)
        assert total == 1
        assert materials[0].body == "Use the approved access procedure."
        assert materials[0].version == 1
        assert get_resource(session, resource.id).version == 3
    finally:
        session.rollback()
        if resource_id is not None:
            session.execute(delete(AuditEvent).where(AuditEvent.resource_id == resource_id))
            session.execute(delete(Material).where(Material.resource_id == resource_id))
            session.execute(
                delete(CredentialGrant).where(
                    CredentialGrant.credential_id.in_(
                        session.query(CredentialRef.id).filter(CredentialRef.resource_id == resource_id)
                    )
                )
            )
            session.execute(delete(CredentialRef).where(CredentialRef.resource_id == resource_id))
            session.execute(delete(Resource).where(Resource.id == resource_id))
        if person_id is not None:
            session.execute(delete(Person).where(Person.id == person_id))
        if stage_id is not None:
            session.execute(delete(CredentialStage).where(CredentialStage.id == stage_id))
        session.commit()
        session.close()
        engine.dispose()
