import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


CONTRACT = json.loads(
    (Path(__file__).parents[1] / "openapi" / "v1.openapi.json").read_text(encoding="utf-8")
)
SCHEMAS = CONTRACT["components"]["schemas"]
REQUIRED_S1_OPERATIONS = {
    "getLoginContext", "exchangeAuthCode", "logoutSession",
    "listPeople", "listDepartments", "listCompanies",
    "setInitialResourceFacts", "verifyResource", "confirmResourceLifecycle", "archiveResource", "unarchiveResource",
    "listResourceRelations", "createResourceRelation", "endResourceRelation",
    "listResourceBindings", "createResourceBinding", "listMailboxContactIdentities",
    "listResourceMaterials", "createResourceMaterial", "patchResourceMaterial",
    "uploadFile", "downloadFileContent", "listResourceHistory", "listResourceSources",
    "discoverResourceImpacts", "getIdempotencyResult",
}
RESOURCE_CREATE = Draft202012Validator(
    {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "components": {"schemas": SCHEMAS},
        "$ref": "#/components/schemas/ResourceCreate",
    },
    format_checker=FormatChecker(),
)
CHANGE_CASE_PATCH = Draft202012Validator(
    {"$schema": "https://json-schema.org/draft/2020-12/schema", "components": {"schemas": SCHEMAS}, "$ref": "#/components/schemas/ChangeCasePatch"},
    format_checker=FormatChecker(),
)
CHANGE_ITEM_PATCH = Draft202012Validator(
    {"$schema": "https://json-schema.org/draft/2020-12/schema", "components": {"schemas": SCHEMAS}, "$ref": "#/components/schemas/ChangeItemPatch"},
    format_checker=FormatChecker(),
)


def component_validator(name: str) -> Draft202012Validator:
    return Draft202012Validator(
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "components": {"schemas": SCHEMAS},
            "$ref": f"#/components/schemas/{name}",
        },
        format_checker=FormatChecker(),
    )


INITIAL_FACTS = component_validator("InitialFactsRequest")
BINDING_CREATE = component_validator("BindingCreate")
MATERIAL_PATCH = component_validator("MaterialPatch")
RESOURCE_PATCH = component_validator("ResourcePatch")


def valid_resource(type_code: str) -> dict[str, object]:
    return {"name": "test", "type_code": type_code}


def is_valid(schema: Draft202012Validator, instance: object) -> bool:
    return not list(schema.iter_errors(instance))


def test_openapi_component_schemas_are_valid_json_schemas() -> None:
    for name, schema in SCHEMAS.items():
        Draft202012Validator.check_schema(schema)


def test_all_missing_s1_operations_are_in_the_machine_contract() -> None:
    operation_ids = {
        operation["operationId"]
        for path_item in CONTRACT["paths"].values()
        for method, operation in path_item.items()
        if method in {"get", "post", "put", "patch", "delete"}
    }
    assert REQUIRED_S1_OPERATIONS <= operation_ids
    identity_operations = {"getBootstrapStatus", "bootstrapAdministrator", "loginLocalAccount", "getLocalSession", "logoutLocalSession", "changeLocalPassword", "reauthenticateLocalSession", "redeemAccountToken", "listLocalAccounts", "createLocalAccount", "patchLocalAccount", "issueAccountRecoveryToken", "createDepartment", "patchDepartment"}
    assert identity_operations <= operation_ids
    for path_item in CONTRACT["paths"].values():
        for operation in path_item.values():
            if isinstance(operation, dict) and operation.get("operationId") in identity_operations:
                assert operation["x-implementation-status"] == "implemented-v3-stage1"


def test_every_runtime_route_has_a_canonical_contract_and_cookie_name_matches() -> None:
    from app.config import Settings
    from app.main import create_app
    runtime = create_app(Settings(auth_provider="local")).openapi()
    actual = {(path.removeprefix("/api/v1"),method) for path,item in runtime["paths"].items() for method in item if method in {"get","post","patch","put","delete"}}
    declared = {(path,method) for path,item in CONTRACT["paths"].items() for method in item if method in {"get","post","patch","put","delete"}}
    assert actual <= declared
    assert CONTRACT["components"]["securitySchemes"]["SessionCookie"]["name"] == Settings().auth_cookie_name


def test_resource_create_covers_all_nine_v3_types() -> None:
    types = SCHEMAS["ResourceType"]["enum"]
    mapping = SCHEMAS["ResourceCreate"]["discriminator"]["mapping"]

    assert len(types) == 9
    assert set(types) == set(mapping)
    for type_code in types:
        assert is_valid(RESOURCE_CREATE, valid_resource(type_code))


def test_common_create_fields_preserve_person_and_company_relationships() -> None:
    common = {
        **valid_resource("application"),
        "owning_department_id": "00000000-0000-4000-8000-000000000001",
        "people": [
            {"person_id": "00000000-0000-4000-8000-000000000002", "role": "owner"},
            {"person_id": "00000000-0000-4000-8000-000000000003", "role": "use"},
        ],
        "company_links": [
            {"company_id": "00000000-0000-4000-8000-000000000004", "role": "owner"},
            {"company_id": "00000000-0000-4000-8000-000000000005", "role": "represented"},
        ],
    }
    assert is_valid(RESOURCE_CREATE, common)
    assert not is_valid(RESOURCE_CREATE, {**common, "people": [{**common["people"][0], "confirmation": "confirmed"}]})
    assert not is_valid(RESOURCE_CREATE, {**common, "company_id": "00000000-0000-4000-8000-000000000004"})
    assert not is_valid(RESOURCE_CREATE, {**common, "owner_person_id": "00000000-0000-4000-8000-000000000002"})
    resource_view = SCHEMAS["ResourceView"]["allOf"][1]
    assert "company_links" in resource_view["required"]
    assert resource_view["properties"]["company_links"]["items"]["$ref"].endswith("CompanyLinkView")


def test_resource_create_rejects_unknown_fields_and_secret_values() -> None:
    assert not is_valid(RESOURCE_CREATE, {**valid_resource("api_key"), "unexpected": "value"})
    assert not is_valid(
        RESOURCE_CREATE,
        {**valid_resource("api_key"), "attributes": {"external_key_id": "public-id", "secret_value": "do-not-store"}},
    )
    assert not is_valid(RESOURCE_CREATE, {**valid_resource("api_key"), "account": {"identifier": "x"}})


def test_type_specific_resource_fields_are_constrained() -> None:
    assert not is_valid(RESOURCE_CREATE, {**valid_resource("mailbox_account"), "account": {"identifier": "not-an-email"}})
    assert not is_valid(
        RESOURCE_CREATE,
        {**valid_resource("service_subscription"), "attributes": {"renewal_day": 32}},
    )
    assert is_valid(
        RESOURCE_CREATE,
        {
            **valid_resource("service_subscription"),
            "attributes": {
                "budgets": [
                    {"amount": "0.00", "currency": "USD", "period": "month", "meaning": "budget"},
                    {"amount": "100.00", "currency": "RMB", "period": "month", "meaning": "budget"},
                ],
                "payment_label": "corporate card",
                "settlement_mode": "monthly",
            },
        },
    )


def test_six_form_fields_match_typed_create_contracts() -> None:
    examples = [
        {**valid_resource("platform_account"), "account": {"identifier": "admin@example.test", "login_methods": ["sso", "qr"], "account_role": "administrator", "scope_label": "华东空间"}},
        {**valid_resource("mailbox_account"), "account": {"identifier": "person@example.test", "login_methods": ["password"], "aliases": ["alias@example.test"]}},
        {**valid_resource("api_key"), "attributes": {"external_key_id": "key-public-id"}, "relations": [{"target_id": "00000000-0000-4000-8000-000000000006", "relation_type": "managed_by"}]},
        {**valid_resource("service_subscription"), "attributes": {"plan": "Plus", "budgets": [{"amount": "20.00", "currency": "USD", "period": "month", "meaning": "monthly budget"}, {"amount": "140.00", "currency": "RMB", "period": "month", "meaning": "monthly budget"}], "renewal_day": 31, "payment_label": "corporate card", "settlement_mode": "monthly"}},
        {**valid_resource("business_space"), "attributes": {"external_instance_id": "shop-1", "environment": "production", "region": "east", "scope_label": "旗舰店"}},
        {**valid_resource("application"), "attributes": {"tech_stack": ["Vue", "FastAPI"]}, "materials": [{"kind": "entry", "url": "https://example.test/app"}], "relations": [{"target_id": "00000000-0000-4000-8000-000000000007", "relation_type": "uses"}]},
    ]
    assert all(is_valid(RESOURCE_CREATE, example) for example in examples)
    assert not is_valid(RESOURCE_CREATE, {**examples[0], "account": {**examples[0]["account"], "login_methods": ["invented"]}})
    assert not is_valid(RESOURCE_CREATE, {**examples[0], "account": {**examples[0]["account"], "account_role": "owner"}})
    assert not is_valid(RESOURCE_CREATE, {**examples[1], "account": {**examples[1]["account"], "aliases": ["not-email"]}})
    assert not is_valid(RESOURCE_CREATE, {**examples[2], "attributes": {"external_key_id": "public-id", "secret_value": "not-allowed"}})


def test_mailbox_contact_identities_are_reusable_without_reentering_raw_email() -> None:
    operation = CONTRACT["paths"]["/resources/{resource_id}/contact-identities"]["get"]
    response_schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
    assert operation["operationId"] == "listMailboxContactIdentities"
    assert operation["security"] == [{"SessionCookie": []}]
    assert response_schema["$ref"].endswith("Stage2SuccessEnvelope_MailboxContactIdentityPage_")
    option = SCHEMAS["MailboxContactIdentityOption"]
    assert option["properties"]["kind"]["const"] == "email"
    assert "value" not in option["properties"]
    assert "same transaction" in SCHEMAS["MailboxAccountCreate"]["description"]


def test_subscription_budgets_preserve_multiple_currencies_without_extra_fields() -> None:
    subscription = {
        **valid_resource("service_subscription"),
        "attributes": {
            "budgets": [
                {"amount": "20.00", "currency": "USD", "period": "month", "meaning": "monthly budget"},
                {"amount": "140.00", "currency": "RMB", "period": "month", "meaning": "monthly budget"},
            ]
        },
    }
    assert is_valid(RESOURCE_CREATE, subscription)
    assert [entry["currency"] for entry in subscription["attributes"]["budgets"]] == ["USD", "RMB"]
    assert [entry["amount"] for entry in subscription["attributes"]["budgets"]] == ["20.00", "140.00"]
    assert not is_valid(
        RESOURCE_CREATE,
        {**subscription, "attributes": {"budgets": [{"amount": "10", "currency": "USD", "period": "month"}]}},
    )
    assert not is_valid(
        RESOURCE_CREATE,
        {**subscription, "attributes": {"budgets": [{"amount": "10", "currency": "USD", "period": "month", "meaning": "budget", "source": "user text"}]}},
    )
    assert not is_valid(
        RESOURCE_CREATE,
        {**subscription, "attributes": {"budgets": [{"amount": "10000000000000000", "currency": "USD", "period": "month", "meaning": "budget"}]}},
    )


def test_create_materials_follow_confirmed_material_kinds() -> None:
    assert is_valid(
        RESOURCE_CREATE,
        {**valid_resource("application"), "materials": [{"kind": "entry", "url": "https://example.test/app"}]},
    )
    assert not is_valid(
        RESOURCE_CREATE,
        {**valid_resource("application"), "materials": [{"kind": "entry", "body": "missing URL"}]},
    )
    assert not is_valid(
        RESOURCE_CREATE,
        {**valid_resource("application"), "materials": [{"kind": "entry", "url": "ftp://example.test/app"}]},
    )
    assert not is_valid(
        RESOURCE_CREATE,
        {**valid_resource("application"), "materials": [{"kind": "attachment", "file_ref": "not-a-uuid"}]},
    )


def test_form_payloads_enforce_documented_string_and_collection_limits() -> None:
    assert not is_valid(RESOURCE_CREATE, {"name": "x" * 201, "type_code": "api_key"})
    assert not is_valid(
        RESOURCE_CREATE,
        {**valid_resource("application"), "attributes": {"tech_stack": ["x" * 81]}},
    )
    assert not is_valid(
        RESOURCE_CREATE,
        {**valid_resource("application"), "materials": [{"kind": "note", "body": "x" * 20001}]},
    )
    assert not is_valid(
        RESOURCE_CREATE,
        {**valid_resource("application"), "attributes": {"tech_stack": [f"stack-{i}" for i in range(51)]}},
    )


def test_initial_facts_and_relation_confirmation_are_server_controlled() -> None:
    person_id = "00000000-0000-4000-8000-000000000002"
    company_id = "00000000-0000-4000-8000-000000000003"
    assert is_valid(INITIAL_FACTS, {"expected_version": 1, "people": [{"person_id": person_id, "role": "owner"}]})
    assert is_valid(INITIAL_FACTS, {"expected_version": 1, "company_links": [{"company_id": company_id, "role": "owner"}]})
    assert not is_valid(INITIAL_FACTS, {"expected_version": 1})
    assert not is_valid(
        INITIAL_FACTS,
        {"expected_version": 1, "people": [{"person_id": person_id, "role": "owner", "confirmation": "confirmed"}]},
    )


def test_binding_contract_requires_exactly_one_contact_source_and_masks_identity() -> None:
    account_id = "00000000-0000-4000-8000-000000000004"
    person_id = "00000000-0000-4000-8000-000000000005"
    base = {"expected_version": 1, "purpose": "recovery"}
    assert is_valid(BINDING_CREATE, {**base, "contact_identity_id": account_id})
    assert is_valid(
        BINDING_CREATE,
        {**base, "contact": {"kind": "email", "value": "recovery@example.test", "ownership": "company", "mailbox_account_id": account_id, "mailbox_association_role": "alias"}},
    )
    assert not is_valid(
        BINDING_CREATE,
        {**base, "contact": {"kind": "email", "value": "not-an-email", "ownership": "company"}},
    )
    assert not is_valid(
        BINDING_CREATE,
        {**base, "contact": {"kind": "email", "value": "recovery@example.test", "ownership": "company", "mailbox_account_id": account_id, "custodian_person_id": person_id}},
    )
    assert not is_valid(
        BINDING_CREATE,
        {**base, "contact": {"kind": "email", "value": "recovery@example.test", "ownership": "company", "mailbox_account_id": account_id}},
    )
    assert not is_valid(
        BINDING_CREATE,
        {**base, "contact": {"kind": "phone", "value": "+8613800000000", "ownership": "company", "mailbox_account_id": account_id, "mailbox_association_role": "alias"}},
    )
    contact = SCHEMAS["ContactIdentityInput"]["properties"]["value"]
    assert contact["writeOnly"] is True
    assert "value" not in SCHEMAS["ContactIdentityView"]["properties"]


def test_material_patch_is_type_specific_and_attachment_reference_is_immutable() -> None:
    base = {"expected_version": 2, "kind": "entry", "changes": {"url": "https://example.test/new"}}
    assert is_valid(MATERIAL_PATCH, base)
    assert not is_valid(MATERIAL_PATCH, {**base, "kind": "note"})
    assert not is_valid(MATERIAL_PATCH, {"expected_version": 2, "kind": "attachment", "changes": {"file_ref": "00000000-0000-4000-8000-000000000006"}})


def test_login_context_is_browser_bound_and_one_time_routes_avoid_generic_idempotency() -> None:
    operations = {
        operation["operationId"]: operation
        for path_item in CONTRACT["paths"].values()
        for method, operation in path_item.items()
        if method in {"get", "post", "put", "patch", "delete"}
    }
    login = operations["getLoginContext"]["responses"]["200"]
    assert "Set-Cookie" in login["headers"]
    assert "no-store" == login["headers"]["Cache-Control"]["schema"]["const"]
    for operation_id in ("exchangeAuthCode", "logoutSession", "discoverResourceImpacts"):
        operation = operations[operation_id]
        assert not any(parameter.get("$ref", "").endswith("IdempotencyKey") for parameter in operation.get("parameters", []))
    assert operations["exchangeAuthCode"]["security"] == []


def test_typed_change_proposals_cover_every_confirmed_action_once() -> None:
    actions = SCHEMAS["ChangeAction"]["enum"]
    branches = SCHEMAS["ChangeItemProposal"]["oneOf"]
    branch_actions = [branch["properties"]["action"]["const"] for branch in branches]

    assert len(branch_actions) == len(set(branch_actions))
    assert set(branch_actions) == set(actions)
    rotate = next(branch for branch in branches if branch["properties"]["action"]["const"] == "rotate_credential")
    assert "operation_id" in rotate["required"]
    replace_key = next(branch for branch in branches if branch["properties"]["action"]["const"] == "replace_key")
    assert "replacement_resource_id" in replace_key["required"]


def test_patch_contracts_allow_partial_updates_but_require_a_change() -> None:
    assert not is_valid(CHANGE_CASE_PATCH, {"expected_version": 2})
    assert is_valid(CHANGE_CASE_PATCH, {"expected_version": 2, "subject_person_id": None})
    assert is_valid(
        CHANGE_ITEM_PATCH,
        {"expected_version": 3, "assignee_person_id": None},
    )
    assert is_valid(
        CHANGE_ITEM_PATCH,
        {"expected_version": 3, "proposal": {"action": "change_owner", "to_person_id": "00000000-0000-4000-8000-000000000001"}},
    )


def test_resource_patch_has_closed_type_attributes_and_non_identity_account_fields() -> None:
    profile_update = {"expected_version": 2, "changes": {"account": {"login_methods": ["sso"], "scope_label": "华东"}}}
    attribute_update = {"expected_version": 2, "changes": {"attributes": {"external_key_id": "public-key-id"}}}
    assert is_valid(RESOURCE_PATCH, profile_update)
    assert is_valid(RESOURCE_PATCH, attribute_update)
    assert not is_valid(RESOURCE_PATCH, {"expected_version": 2, "changes": {"account": {"identifier": "new-id"}}})
    assert not is_valid(RESOURCE_PATCH, {"expected_version": 2, "changes": {"account": {"aliases": ["alias@example.test"]}}})
    assert not is_valid(RESOURCE_PATCH, {"expected_version": 2, "changes": {"attributes": {"secret_value": "not-allowed"}}})


def test_credential_secret_fields_are_not_part_of_general_resource_dtos() -> None:
    stage_input = SCHEMAS["SecretStageCreate"]["properties"]["secret_value"]
    attach_input = SCHEMAS["CredentialAttachRequest"]["properties"]["stage_token"]
    assert stage_input.get("writeOnly") is True
    assert attach_input.get("writeOnly") is True
    assert "secret_value" not in SCHEMAS["ResourceView"]["allOf"][1]["properties"]
    assert SCHEMAS["SafeOperationResult"].get("additionalProperties") is False
    assert "secret_value" not in SCHEMAS["SafeOperationResult"]["properties"]
