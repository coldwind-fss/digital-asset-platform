/* eslint-disable */
// Generated from ../../../../backend/openapi/v1.openapi.json. Do not edit by hand.
export interface components {
  schemas: {
    "AccountProfilePatch": {
    "login_methods"?: Array<components["schemas"]["LoginMethod"]>;
    "account_role"?: components["schemas"]["AccountRole"] | null;
    "scope_label"?: string | null;
  };
    "AccountRole": "master" | "administrator" | "member" | "service" | "unknown";
    "AccountView": {
    "identifier": string | null;
    "login_methods": Array<components["schemas"]["LoginMethod"]>;
    "account_role"?: components["schemas"]["AccountRole"] | null;
    "scope_label"?: string | null;
    "aliases"?: Array<string>;
  };
    "ApiError": {
    "code": string;
    "message": string;
    "details": Array<components["schemas"]["FieldError"]>;
    "retryable": boolean;
  };
    "ApiKeyCreate": components["schemas"]["ResourceCreateCommon"] & {
    "type_code"?: "api_key";
    "attributes"?: {
    "external_key_id"?: string | null;
  };
    [key: string]: unknown;
  };
    "ApiServiceCreate": components["schemas"]["ResourceCreateCommon"] & {
    "type_code"?: "api_service";
    "attributes"?: {
    "endpoint"?: string | null;
    "metric_scope"?: string | null;
    "environment"?: string | null;
    "external_instance_id"?: string | null;
  };
    [key: string]: unknown;
  };
    "ApplicationCreate": components["schemas"]["ResourceCreateCommon"] & {
    "type_code"?: "application";
    "attributes"?: {
    "tech_stack"?: Array<string>;
    "endpoint"?: string | null;
    "environment"?: string | null;
  };
    [key: string]: unknown;
  };
    "AuthExchangeRequest": {
    "provider": string;
    "code": string;
    "state": string;
  };
    "BindingCreate": {
    "expected_version": number;
    "purpose": components["schemas"]["BindingPurpose"];
    "contact_identity_id": string;
  } | {
    "expected_version": number;
    "purpose": components["schemas"]["BindingPurpose"];
    "contact": components["schemas"]["ContactIdentityInput"];
  };
    "BindingEnvelope": {
    "data": components["schemas"]["BindingView"];
    "error": null;
    "meta": components["schemas"]["Meta"];
  };
    "BindingPage": {
    "items": Array<components["schemas"]["BindingView"]>;
    "pagination": components["schemas"]["Pagination"];
  };
    "BindingPageEnvelope": {
    "data": components["schemas"]["BindingPage"];
    "error": null;
    "meta": components["schemas"]["Meta"];
  };
    "BindingPurpose": "registration" | "login" | "recovery" | "mfa";
    "BindingView": {
    "id": string;
    "account_resource_id": string;
    "contact": components["schemas"]["ContactIdentityView"];
    "purpose": components["schemas"]["BindingPurpose"];
    "confirmation": components["schemas"]["RelationConfirmation"];
    "valid_from": string;
    "valid_to": string | null;
    "version": number;
  };
    "BudgetEntry": {
    "amount": string;
    "currency": string;
    "period": string;
    "meaning": string;
  };
    "BusinessSpaceCreate": components["schemas"]["ResourceCreateCommon"] & {
    "type_code"?: "business_space";
    "attributes"?: {
    "external_instance_id"?: string | null;
    "environment"?: string | null;
    "region"?: string | null;
    "scope_label"?: string | null;
  };
    [key: string]: unknown;
  };
    "ChangeAction": "change_owner" | "change_organization" | "remove_use" | "transfer_controller" | "change_binding" | "change_mailbox_address" | "change_management_relation" | "revoke_credential_grant" | "revoke_credential" | "grant_use" | "change_visibility" | "rotate_credential" | "replace_key" | "disable_resource" | "retire_resource" | "reactivate_resource";
    "ChangeCaseCreate": {
    "case_type": "change" | "transfer" | "offboard";
    "reason": string;
    "coordinator_person_id": string;
    "subject_person_id"?: string | null;
  };
    "ChangeCaseEnvelope": {
    "data": components["schemas"]["ChangeCaseView"];
    "error": null;
    "meta": components["schemas"]["Meta"];
  };
    "ChangeCasePage": {
    "items": Array<components["schemas"]["ChangeCaseView"]>;
    "pagination": components["schemas"]["Pagination"];
  };
    "ChangeCasePageEnvelope": {
    "data": components["schemas"]["ChangeCasePage"];
    "error": null;
    "meta": components["schemas"]["Meta"];
  };
    "ChangeCasePatch": {
    "expected_version": number;
    "reason"?: string;
    "coordinator_person_id"?: string;
    "subject_person_id"?: string | null;
  };
    "ChangeCaseView": {
    "id": string;
    "case_type": "change" | "transfer" | "offboard";
    "subject_person_id": string | null;
    "coordinator_person_id": string;
    "reason": string;
    "status": "draft" | "active" | "completed" | "completed_with_exceptions" | "cancelled";
    "version": number;
    "created_at": string;
    "closed_at": string | null;
  };
    "ChangeDiscoveryEnvelope": {
    "data": components["schemas"]["ChangeDiscoveryResult"];
    "error": null;
    "meta": components["schemas"]["Meta"];
  };
    "ChangeDiscoveryItem": {
    "resource": components["schemas"]["ResourceSummary"];
    "paths": Array<components["schemas"]["DiscoveryPath"]>;
    "requires_manual_review": boolean;
  };
    "ChangeDiscoveryRequest": {
    "subject_person_id": string;
  } | {
    "resource_ids": Array<string>;
  };
    "ChangeDiscoveryResult": {
    "items": Array<components["schemas"]["ChangeDiscoveryItem"]>;
    "coverage": "visible_known_relations";
  };
    "ChangeItemCreate": {
    "resource_id": string;
    "assignee_person_id": string | null;
    "proposal": components["schemas"]["ChangeItemProposal"];
  };
    "ChangeItemEnvelope": {
    "data": components["schemas"]["ChangeItemView"];
    "error": null;
    "meta": components["schemas"]["Meta"];
  };
    "ChangeItemPage": {
    "items": Array<components["schemas"]["ChangeItemView"]>;
    "pagination": components["schemas"]["Pagination"];
  };
    "ChangeItemPageEnvelope": {
    "data": components["schemas"]["ChangeItemPage"];
    "error": null;
    "meta": components["schemas"]["Meta"];
  };
    "ChangeItemPatch": {
    "expected_version": number;
    "assignee_person_id"?: string | null;
    "proposal"?: components["schemas"]["ChangeItemProposal"];
  };
    "ChangeItemProposal": {
    "action": "change_owner";
    "assignment_id"?: string | null;
    "to_person_id": string;
  } | {
    "action": "change_organization";
    "company_id"?: string | null;
    "owning_department_id"?: string | null;
  } | {
    "action": "remove_use";
    "assignment_id": string;
  } | {
    "action": "transfer_controller";
    "assignment_id": string;
    "to_person_id": string;
  } | {
    "action": "change_binding";
    "binding_id": string;
    "new_contact_identity_id": string;
    "purpose"?: "registration" | "login" | "recovery" | "mfa" | null;
  } | {
    "action": "change_mailbox_address";
    "binding_id"?: string | null;
    "new_contact_identity_id": string;
  } | {
    "action": "change_management_relation";
    "relation_id": string;
    "proposed_target_id": string;
  } | {
    "action": "revoke_credential_grant";
    "credential_grant_id": string;
    "operation_id": string;
  } | {
    "action": "revoke_credential";
    "credential_id": string;
    "operation_id": string;
  } | {
    "action": "grant_use";
    "person_id": string;
  } | {
    "action": "change_visibility";
    "visibility_scope": "restricted" | "department" | "company";
  } | {
    "action": "rotate_credential";
    "credential_id": string;
    "operation_id": string;
  } | {
    "action": "replace_key";
    "replacement_resource_id": string;
  } | {
    "action": "disable_resource";
  } | {
    "action": "retire_resource";
  } | {
    "action": "reactivate_resource";
  };
    "ChangeItemView": {
    "id": string;
    "case_id": string;
    "resource_id": string;
    "action": components["schemas"]["ChangeAction"];
    "assignee_person_id": string | null;
    "proposal": components["schemas"]["ChangeItemProposal"];
    "status": "pending" | "in_progress" | "awaiting_confirmation" | "completed" | "cancelled" | "failed" | "cancellation_requested";
    "version": number;
    "non_secret_result": string | null;
  };
    "CloudResourceCreate": components["schemas"]["ResourceCreateCommon"] & {
    "type_code"?: "cloud_resource";
    "attributes"?: {
    "endpoint"?: string | null;
    "external_instance_id"?: string | null;
    "specification"?: string | null;
    "resource_kind"?: string | null;
    "region"?: string | null;
    "environment"?: string | null;
  };
    [key: string]: unknown;
  };
    "CompanyLinkCreate": {
    "company_id": string;
    "role": "owner" | "represented";
  };
    "CompanyLinkView": {
    "company": components["schemas"]["OrganizationSummary"];
    "role": "owner" | "represented";
    "confirmation": components["schemas"]["RelationConfirmation"];
    "valid_from": string;
    "valid_to": string | null;
    "assignment_id": string;
  };
    "CompanyPage": {
    "items": Array<components["schemas"]["CompanyPickerOption"]>;
    "pagination": components["schemas"]["Pagination"];
  };
    "CompanyPageEnvelope": {
    "data": components["schemas"]["CompanyPage"];
    "error": null;
    "meta": components["schemas"]["Meta"];
  };
    "CompanyPickerOption": {
    "id": string;
    "display_name": string;
    "status": string;
  };
    "ConfirmChangeRequest": {
    "expected_version": number;
    "confirmation_note": string;
  };
    "ConfirmLifecycleRequest": {
    "expected_version": number;
    "lifecycle": "unknown" | "in_use";
    "basis": string;
  };
    "ContactIdentityInput": unknown & unknown & unknown;
    "ContactIdentityView": {
    "id": string;
    "kind": components["schemas"]["ContactKind"];
    "masked_value": string;
    "ownership": "company" | "personal" | "unknown";
    "verification": components["schemas"]["Verification"];
    "mailbox_account"?: components["schemas"]["ResourceSummary"] | null;
    "custodian"?: components["schemas"]["PersonSummary"] | null;
  };
    "ContactKind": "email" | "phone";
    "CredentialAttachRequest": {
    "expected_version": number;
    "stage_token": string;
    "kind": "password" | "api_key" | "certificate_pin" | "other";
  };
    "CredentialGrantCreate": {
    "person_id": string;
    "capability": "view" | "rotate";
    "valid_to": string;
    "reason": string;
    "expected_version": number;
  };
    "CredentialGrantEnvelope": {
    "data": components["schemas"]["CredentialGrantView"];
    "error": null;
    "meta": components["schemas"]["Meta"];
  };
    "CredentialGrantView": {
    "id": string;
    "credential_id": string;
    "person_id": string;
    "capability": "view" | "rotate";
    "valid_from": string;
    "valid_to": string;
    "reason": string;
    "version": number;
  };
    "CredentialOperationView": {
    "operation_id": string;
    "status": "pending" | "succeeded" | "failed";
    "safe_result": components["schemas"]["SafeOperationResult"] | null;
    "retryable": boolean;
  };
    "CredentialRevealEnvelope": {
    "data": components["schemas"]["CredentialRevealView"];
    "error": null;
    "meta": components["schemas"]["Meta"];
  };
    "CredentialRevealRequest": {
    "reason": string;
  };
    "CredentialRevealView": {
    "secret_value": string;
  };
    "CredentialStorageCorrection": {
    "expected_version": number;
    "stage_token": string;
    "reason": string;
  };
    "DepartmentPage": {
    "items": Array<components["schemas"]["DepartmentPickerOption"]>;
    "pagination": components["schemas"]["Pagination"];
  };
    "DepartmentPageEnvelope": {
    "data": components["schemas"]["DepartmentPage"];
    "error": null;
    "meta": components["schemas"]["Meta"];
  };
    "DepartmentPickerOption": {
    "id": string;
    "display_name": string;
    "parent_department_id": string | null;
    "status": string;
  };
    "DiscoveryPath": "resource_person" | "resource_relation" | "account_binding" | "credential_grant";
    "DomainCreate": components["schemas"]["ResourceCreateCommon"] & {
    "type_code"?: "domain";
    "attributes"?: {
    "domain_name"?: string | null;
    "renewal_note"?: string | null;
    "expires_on"?: string | null;
    "registrar"?: string | null;
    "registered_on"?: string | null;
  };
    [key: string]: unknown;
  };
    "ErrorEnvelope": {
    "data": null;
    "error": components["schemas"]["ApiError"];
    "meta": components["schemas"]["Meta"];
  };
    "ExpectedVersionRequest": {
    "expected_version": number;
  };
    "FieldError": {
    "field": string;
    "code": string;
    "message": string;
  };
    "FileEnvelope": {
    "data": components["schemas"]["FileObjectView"];
    "error": null;
    "meta": components["schemas"]["Meta"];
  };
    "FileObjectView": {
    "id": string;
    "safe_name": string;
    "media_type": string;
    "byte_size": number;
    "scan_state": "pending" | "clean" | "rejected";
    "created_at": string;
    "content_available": boolean;
  };
    "FileUpload": {
    "file": string;
    "classification"?: string;
  };
    "Health": {
    "status": "ok";
    "service": string;
    "release_id": string;
    "checked_at": string;
  };
    "HealthEnvelope": {
    "data": components["schemas"]["Health"];
    "error": null;
    "meta": components["schemas"]["Meta"];
  };
    "HistoryEntry": {
    "id": string;
    "event_type": string;
    "occurred_at": string;
    "actor": components["schemas"]["PersonSummary"] | null;
    "change_summary": string;
  };
    "HistoryPage": {
    "items": Array<components["schemas"]["HistoryEntry"]>;
    "pagination": components["schemas"]["Pagination"];
  };
    "HistoryPageEnvelope": {
    "data": components["schemas"]["HistoryPage"];
    "error": null;
    "meta": components["schemas"]["Meta"];
  };
    "IdempotencyResult": {
    "status": "pending" | "completed";
    "http_status": 200 | 201 | 202 | null;
    "safe_result": components["schemas"]["IdempotencySafeResult"] | null;
    "retryable": boolean;
  };
    "IdempotencyResultEnvelope": {
    "data": components["schemas"]["IdempotencyResult"];
    "error": null;
    "meta": components["schemas"]["Meta"];
  };
    "IdempotencySafeResult": {
    "resource_id"?: string;
    "change_case_id"?: string;
    "change_item_id"?: string;
    "file_id"?: string;
    "operation_id"?: string;
  };
    "IdentityAccountCreateRequest": {
    "username": string;
    "display_name": string;
    "person_id"?: string | null;
    "department_id"?: string | null;
    "role"?: "admin" | "resource_manager" | "member";
    "scopes"?: Array<components["schemas"]["IdentityScopeInput"]>;
  };
    "IdentityAccountPage": {
    "items": Array<components["schemas"]["Identityapp__modules__identity_access__api__schemas__AccountView"]>;
    "pagination": {
    [key: string]: number | boolean;
  };
  };
    "IdentityAccountPatchRequest": {
    "expected_version": number;
    "display_name"?: string | null;
    "department_id"?: string | null;
    "role"?: "admin" | "resource_manager" | "member" | null;
    "status"?: "active" | "inactive" | null;
    "scopes"?: Array<components["schemas"]["IdentityScopeInput"]> | null;
  };
    "IdentityBootstrapRequest": {
    "username": string;
    "display_name": string;
    "password": string;
    "bootstrap_token": string;
  };
    "IdentityBootstrapStatus": {
    "initialized": boolean;
    "setup_available": boolean;
    "read_only"?: boolean;
  };
    "IdentityDepartmentCreateRequest": {
    "name": string;
    "parent_id"?: string | null;
  };
    "IdentityDepartmentManagementPage": {
    "items": Array<components["schemas"]["IdentityDepartmentView"]>;
    "pagination": {
    [key: string]: number | boolean;
  };
  };
    "IdentityDepartmentPatchRequest": {
    "expected_version": number;
    "name"?: string | null;
    "parent_id"?: string | null;
    "status"?: "active" | "inactive" | null;
  };
    "IdentityDepartmentView": {
    "id": string;
    "name": string;
    "parent_id": string | null;
    "status": string;
    "version": number;
  };
    "IdentityHTTPValidationError": {
    "detail"?: Array<components["schemas"]["IdentityValidationError"]>;
    [key: string]: unknown;
  };
    "IdentityLoginRequest": {
    "username": string;
    "password": string;
  };
    "IdentityOperationResult": {
    "message": string;
  };
    "IdentityPageSize": 25 | 50 | 100;
    "IdentityPasswordChangeRequest": {
    "current_password": string;
    "new_password": string;
  };
    "IdentityReauthenticationRequest": {
    "password": string;
  };
    "IdentityResponseMeta": {
    "request_id": string;
  };
    "IdentityScopeInput": {
    "kind": "department" | "resource";
    "target_id": string;
    "permission": "read" | "manage";
  };
    "IdentitySessionView": {
    "account_id": string;
    "person_id": string;
    "username": string;
    "display_name": string;
    "department_id": string | null;
    "role": "admin" | "resource_manager" | "member";
    "capabilities": Array<string>;
    "expires_at": string;
    "csrf_token": string;
    "must_change_password": boolean;
    "read_only"?: boolean;
  };
    "IdentitySuccessEnvelope_AccountPage_": {
    "data": components["schemas"]["IdentityAccountPage"];
    "error": null;
    "meta": components["schemas"]["IdentityResponseMeta"];
  };
    "IdentitySuccessEnvelope_AccountView_": {
    "data": components["schemas"]["Identityapp__modules__identity_access__api__schemas__AccountView"];
    "error": null;
    "meta": components["schemas"]["IdentityResponseMeta"];
  };
    "IdentitySuccessEnvelope_BootstrapStatus_": {
    "data": components["schemas"]["IdentityBootstrapStatus"];
    "error": null;
    "meta": components["schemas"]["IdentityResponseMeta"];
  };
    "IdentitySuccessEnvelope_DepartmentManagementPage_": {
    "data": components["schemas"]["IdentityDepartmentManagementPage"];
    "error": null;
    "meta": components["schemas"]["IdentityResponseMeta"];
  };
    "IdentitySuccessEnvelope_DepartmentView_": {
    "data": components["schemas"]["IdentityDepartmentView"];
    "error": null;
    "meta": components["schemas"]["IdentityResponseMeta"];
  };
    "IdentitySuccessEnvelope_OperationResult_": {
    "data": components["schemas"]["IdentityOperationResult"];
    "error": null;
    "meta": components["schemas"]["IdentityResponseMeta"];
  };
    "IdentitySuccessEnvelope_SessionView_": {
    "data": components["schemas"]["IdentitySessionView"];
    "error": null;
    "meta": components["schemas"]["IdentityResponseMeta"];
  };
    "IdentitySuccessEnvelope_TokenIssuedView_": {
    "data": components["schemas"]["IdentityTokenIssuedView"];
    "error": null;
    "meta": components["schemas"]["IdentityResponseMeta"];
  };
    "IdentityTokenIssuedView": {
    "account": components["schemas"]["Identityapp__modules__identity_access__api__schemas__AccountView"];
    "action_token": string;
    "expires_at": string;
  };
    "IdentityTokenRedemptionRequest": {
    "action_token": string;
    "new_password": string;
  };
    "IdentityValidationError": {
    "loc": Array<string | number>;
    "msg": string;
    "type": string;
    "input"?: unknown;
    "ctx"?: {
    [key: string]: unknown;
  };
    [key: string]: unknown;
  };
    "Identityapp__modules__identity_access__api__schemas__AccountView": {
    "id": string;
    "person_id": string;
    "username": string;
    "display_name": string;
    "department_id": string | null;
    "role": "admin" | "resource_manager" | "member";
    "status": string;
    "version": number;
    "scopes": Array<components["schemas"]["IdentityScopeInput"]>;
  };
    "InitialFactsRequest": unknown | unknown | unknown;
    "Lifecycle": "unknown" | "in_use" | "disabled" | "retired";
    "LoginContext": {
    "provider": string;
    "authorization_url": string;
    "state": string;
    "expires_at": string;
  };
    "LoginContextEnvelope": {
    "data": components["schemas"]["LoginContext"];
    "error": null;
    "meta": components["schemas"]["Meta"];
  };
    "LoginMethod": "password" | "otp" | "qr" | "sso" | "api_token" | "unknown";
    "LogoutEnvelope": {
    "data": components["schemas"]["LogoutResult"];
    "error": null;
    "meta": components["schemas"]["Meta"];
  };
    "LogoutRequest": Record<string, never>;
    "LogoutResult": {
    "revoked": true;
  };
    "MailboxAccountCreate": components["schemas"]["ResourceCreateCommon"] & {
    "type_code"?: "mailbox_account";
    "account"?: components["schemas"]["MailboxAccountInput"];
    [key: string]: unknown;
  };
    "MailboxAccountInput": {
    "identifier"?: string | null;
    "login_methods"?: Array<components["schemas"]["LoginMethod"]>;
    "aliases"?: Array<string>;
  };
    "MailboxContactIdentityOption": {
    "id": string;
    "kind": "email";
    "masked_value": string;
    "ownership": "company" | "personal" | "unknown";
    "verification": components["schemas"]["Verification"];
  };
    "MailboxContactIdentityPage": {
    "items": Array<components["schemas"]["MailboxContactIdentityOption"]>;
    "pagination": components["schemas"]["Pagination"];
  };
    "MailboxContactIdentityPageEnvelope": {
    "data": components["schemas"]["MailboxContactIdentityPage"];
    "error": null;
    "meta": components["schemas"]["Meta"];
  };
    "MaterialCreate": {
    "kind": "entry";
    "title"?: string | null;
    "url": string;
    "classification"?: string | null;
  } | {
    "kind": "note";
    "title"?: string | null;
    "body": string;
    "classification"?: string | null;
  } | {
    "kind": "attachment";
    "title"?: string | null;
    "file_ref": string;
    "classification"?: string | null;
  };
    "MaterialEnvelope": {
    "data": components["schemas"]["MaterialView"];
    "error": null;
    "meta": components["schemas"]["Meta"];
  };
    "MaterialPage": {
    "items": Array<components["schemas"]["MaterialView"]>;
    "pagination": components["schemas"]["Pagination"];
  };
    "MaterialPageEnvelope": {
    "data": components["schemas"]["MaterialPage"];
    "error": null;
    "meta": components["schemas"]["Meta"];
  };
    "MaterialPatch": {
    "expected_version": number;
    "kind": "entry";
    "changes": {
    "title"?: string | null;
    "url"?: string;
    "classification"?: string | null;
  };
  } | {
    "expected_version": number;
    "kind": "note";
    "changes": {
    "title"?: string | null;
    "body"?: string;
    "classification"?: string | null;
  };
  } | {
    "expected_version": number;
    "kind": "attachment";
    "changes": {
    "title"?: string | null;
    "classification"?: string | null;
  };
  };
    "MaterialView": {
    "id": string;
    "version": number;
    "kind": "entry";
    "title": string | null;
    "url": string;
    "classification": string | null;
    "created_at": string;
    "updated_at": string;
  } | {
    "id": string;
    "version": number;
    "kind": "note";
    "title": string | null;
    "body": string;
    "classification": string | null;
    "created_at": string;
    "updated_at": string;
  } | {
    "id": string;
    "version": number;
    "kind": "attachment";
    "title": string | null;
    "file_ref": string;
    "scan_state": "pending" | "clean" | "rejected";
    "classification": string | null;
    "created_at": string;
    "updated_at": string;
  };
    "Meta": {
    "request_id": string;
  };
    "MyResourcePage": {
    "items": Array<components["schemas"]["MyResourceSummary"]>;
    "pagination": components["schemas"]["Pagination"];
  };
    "MyResourcePageEnvelope": {
    "data": components["schemas"]["MyResourcePage"];
    "error": null;
    "meta": components["schemas"]["Meta"];
  };
    "MyResourceSummary": components["schemas"]["ResourceFields"] & {
    "my_roles": Array<"owner" | "maintainer" | "use" | "controller">;
    [key: string]: unknown;
  };
    "OperationEnvelope": {
    "data": components["schemas"]["CredentialOperationView"];
    "error": null;
    "meta": components["schemas"]["Meta"];
  };
    "OrganizationSummary": {
    "id": string;
    "display_name": string;
  };
    "Pagination": {
    "page": number;
    "page_size": 25 | 50 | 100;
    "total": number;
    "has_next": boolean;
  };
    "PersonAssignmentCreate": {
    "person_id": string;
    "role": "owner" | "maintainer" | "use" | "controller";
  };
    "PersonAssignmentView": {
    "person": components["schemas"]["PersonSummary"];
    "role": "owner" | "maintainer" | "use" | "controller";
    "confirmation": components["schemas"]["RelationConfirmation"];
    "valid_from": string;
    "valid_to": string | null;
    "assignment_id": string;
  };
    "PersonPage": {
    "items": Array<components["schemas"]["PersonPickerOption"]>;
    "pagination": components["schemas"]["Pagination"];
  };
    "PersonPageEnvelope": {
    "data": components["schemas"]["PersonPage"];
    "error": null;
    "meta": components["schemas"]["Meta"];
  };
    "PersonPickerOption": {
    "id": string;
    "display_name": string;
    "department": components["schemas"]["OrganizationSummary"] | null;
    "status": "active" | "inactive" | "unknown";
  };
    "PersonSummary": {
    "id": string;
    "display_name": string;
  };
    "PlatformAccountCreate": components["schemas"]["ResourceCreateCommon"] & {
    "type_code"?: "platform_account";
    "account"?: components["schemas"]["PlatformAccountInput"];
    [key: string]: unknown;
  };
    "PlatformAccountInput": {
    "identifier"?: string | null;
    "login_methods"?: Array<components["schemas"]["LoginMethod"]>;
    "account_role"?: components["schemas"]["AccountRole"] | null;
    "scope_label"?: string | null;
  };
    "RecordExecutionRequest": {
    "expected_version": number;
    "evidence_ids": Array<string>;
    "non_secret_result": string | null;
  };
    "RelationConfirmation": "proposed" | "confirmed";
    "RelationCreate": {
    "target_id": string;
    "relation_type": components["schemas"]["RelationType"];
    "note"?: string | null;
  };
    "RelationEnvelope": {
    "data": components["schemas"]["ResourceRelationView"];
    "error": null;
    "meta": components["schemas"]["Meta"];
  };
    "RelationPage": {
    "items": Array<components["schemas"]["ResourceRelationView"]>;
    "pagination": components["schemas"]["Pagination"];
    "coverage": "visible_known_relations";
  };
    "RelationPageEnvelope": {
    "data": components["schemas"]["RelationPage"];
    "error": null;
    "meta": components["schemas"]["Meta"];
  };
    "RelationType": "uses" | "managed_by" | "part_of" | "contains" | "depends_on";
    "ResourceAttributes": Record<string, never> | {
    "external_key_id"?: string | null;
  } | {
    "plan"?: string | null;
    "budgets"?: Array<components["schemas"]["BudgetEntry"]>;
    "renewal_day"?: number | null;
    "expires_on"?: string | null;
    "payment_label"?: string | null;
    "settlement_mode"?: string | null;
    "seats"?: number | null;
    "billing_cycle"?: "month" | "year" | "custom" | null;
  } | {
    "external_instance_id"?: string | null;
    "environment"?: string | null;
    "region"?: string | null;
    "scope_label"?: string | null;
  } | {
    "tech_stack"?: Array<string>;
    "endpoint"?: string | null;
    "environment"?: string | null;
  } | {
    "external_instance_id"?: string | null;
    "environment"?: string | null;
    "endpoint"?: string | null;
    "metric_scope"?: string | null;
  } | {
    "specification"?: string | null;
    "resource_kind"?: string | null;
    "environment"?: string | null;
    "external_instance_id"?: string | null;
    "region"?: string | null;
    "endpoint"?: string | null;
  } | {
    "registrar"?: string | null;
    "expires_on"?: string | null;
    "renewal_note"?: string | null;
    "registered_on"?: string | null;
    "domain_name"?: string | null;
  };
    "ResourceCreate": components["schemas"]["PlatformAccountCreate"] | components["schemas"]["MailboxAccountCreate"] | components["schemas"]["ApiKeyCreate"] | components["schemas"]["SubscriptionCreate"] | components["schemas"]["BusinessSpaceCreate"] | components["schemas"]["ApplicationCreate"] | components["schemas"]["ApiServiceCreate"] | components["schemas"]["CloudResourceCreate"] | components["schemas"]["DomainCreate"];
    "ResourceCreateCommon": {
    "name": string;
    "type_code": components["schemas"]["ResourceType"];
    "provider_name"?: string | null;
    "purpose"?: string | null;
    "owning_department_id"?: string | null;
    "people"?: Array<components["schemas"]["PersonAssignmentCreate"]>;
    "company_links"?: Array<components["schemas"]["CompanyLinkCreate"]>;
    "usage_mode"?: "normal" | "test" | "standby" | null;
    "relations"?: Array<components["schemas"]["RelationCreate"]>;
    "materials"?: Array<components["schemas"]["MaterialCreate"]>;
    "platform_id"?: string | null;
    "source_note"?: string;
    "lifecycle"?: "unknown" | "in_use";
    [key: string]: unknown;
  };
    "ResourceEnvelope": {
    "data": components["schemas"]["ResourceView"];
    "error": null;
    "meta": components["schemas"]["Meta"];
  };
    "ResourceFields": {
    "id": string;
    "code": string;
    "name": string;
    "type_code": components["schemas"]["ResourceType"];
    "provider_name": string | null;
    "purpose": string | null;
    "owning_department": components["schemas"]["OrganizationSummary"] | null;
    "confirmed_company": components["schemas"]["OrganizationSummary"] | null;
    "owner": components["schemas"]["PersonSummary"] | null;
    "lifecycle": components["schemas"]["Lifecycle"];
    "verification": components["schemas"]["Verification"];
    "version": number;
    "updated_at": string;
    [key: string]: unknown;
  };
    "ResourcePage": {
    "items": Array<components["schemas"]["ResourceSummary"]>;
    "pagination": components["schemas"]["Pagination"];
  };
    "ResourcePageEnvelope": {
    "data": components["schemas"]["ResourcePage"];
    "error": null;
    "meta": components["schemas"]["Meta"];
  };
    "ResourcePatch": {
    "expected_version": number;
    "changes": {
    "name"?: string;
    "provider_name"?: string | null;
    "purpose"?: string | null;
    "usage_mode"?: "normal" | "test" | "standby" | null;
    "attributes"?: components["schemas"]["ResourceAttributes"];
    "account"?: components["schemas"]["AccountProfilePatch"];
  };
  };
    "ResourceRelationCreate": {
    "expected_version": number;
    "target_id": string;
    "relation_type": components["schemas"]["RelationType"];
    "note"?: string | null;
  };
    "ResourceRelationView": {
    "id": string;
    "source": components["schemas"]["ResourceSummary"];
    "target": components["schemas"]["ResourceSummary"];
    "relation_type": components["schemas"]["RelationType"];
    "direction": "outgoing" | "incoming";
    "confirmation": components["schemas"]["RelationConfirmation"];
    "valid_from": string;
    "valid_to": string | null;
    "note": string | null;
    "version": number;
  };
    "ResourceSummary": components["schemas"]["ResourceFields"];
    "ResourceType": "platform_account" | "mailbox_account" | "api_key" | "service_subscription" | "business_space" | "application" | "api_service" | "cloud_resource" | "domain";
    "ResourceView": components["schemas"]["ResourceFields"] & {
    "usage_mode": "normal" | "test" | "standby" | null;
    "visibility_scope": "restricted" | "department" | "company";
    "people": Array<components["schemas"]["PersonAssignmentView"]>;
    "company_links": Array<components["schemas"]["CompanyLinkView"]>;
    "attributes": components["schemas"]["ResourceAttributes"];
    "account": components["schemas"]["AccountView"] | null;
    "credential_status": "not_saved" | "pending" | "saved" | "failed" | "superseded" | "revoked";
    "missing_fields": Array<string>;
    "capabilities": {
    [key: string]: boolean;
  };
    "created_at": string;
    "platform_id"?: string | null;
    "subscription_summary"?: components["schemas"]["Stage2BasicSubscriptionSummary"] | null;
    [key: string]: unknown;
  };
    "SafeOperationResult": {
    "resource_id"?: string;
    "credential_id"?: string;
    "credential_status"?: "not_saved" | "pending" | "saved" | "failed";
  };
    "SecretStageCreate": {
    "kind": "password" | "api_key" | "certificate_pin" | "other";
    "secret_value": string;
  };
    "SecretStageEnvelope": {
    "data": components["schemas"]["SecretStageView"];
    "error": null;
    "meta": components["schemas"]["Meta"];
  };
    "SecretStageView": {
    "stage_token": string;
    "expires_at": string;
  };
    "Session": {
    "subject_id": string;
    "person_id": string;
    "system_capabilities": Array<string>;
    "csrf_token": string;
  };
    "SessionEnvelope": {
    "data": components["schemas"]["Session"];
    "error": null;
    "meta": components["schemas"]["Meta"];
  };
    "SourcePage": {
    "items": Array<components["schemas"]["SourceReference"]>;
    "pagination": components["schemas"]["Pagination"];
  };
    "SourcePageEnvelope": {
    "data": components["schemas"]["SourcePage"];
    "error": null;
    "meta": components["schemas"]["Meta"];
  };
    "SourceReference": {
    "source_record_id": string;
    "source_kind": string;
    "safe_name": string;
    "captured_at": string;
    "disposition": "mapped" | "pending" | "excluded" | "reference";
    "mapping_status": string;
    "field_path": string | null;
  };
    "Stage2AttachmentMaterialView": {
    "id": string;
    "version": number;
    "kind": "attachment";
    "title": string | null;
    "file_ref": string;
    "scan_state": "pending" | "clean" | "rejected";
    "classification": string | null;
    "created_at": string;
    "updated_at": string;
  };
    "Stage2BasicSubscriptionSummary": {
    "id": string;
    "plan": string | null;
    "seats_total": number | null;
    "seats_assigned": number | null;
    "billing_cycle": string | null;
    "starts_on": string | null;
    "ends_on": string | null;
  };
    "Stage2BatchPage": {
    "items": Array<components["schemas"]["Stage2BatchView"]>;
    "pagination": {
    [key: string]: number | boolean;
  };
  };
    "Stage2BatchView": {
    "id": string;
    "type_code": string;
    "label": string;
    "mapping": {
    [key: string]: string;
  };
    "status": "preview" | "committed" | "expired";
    "version": number;
    "created_at": string;
    "expires_at": string;
    "committed_at": string | null;
    "results": Array<components["schemas"]["Stage2ImportRow"]>;
  };
    "Stage2BindingCreateRequest": {
    "expected_version": number;
    "purpose": components["schemas"]["Stage2BindingPurpose"];
    "contact_identity_id"?: string | null;
    "contact"?: components["schemas"]["Stage2ContactIdentityInput"] | null;
  };
    "Stage2BindingPage": {
    "items": Array<components["schemas"]["Stage2BindingView"]>;
    "pagination": components["schemas"]["Stage2Pagination"];
  };
    "Stage2BindingPurpose": "registration" | "login" | "recovery" | "mfa";
    "Stage2BindingView": {
    "id": string;
    "account_resource_id": string;
    "contact": components["schemas"]["Stage2ContactIdentityView"];
    "purpose": components["schemas"]["Stage2BindingPurpose"];
    "confirmation": "proposed" | "confirmed";
    "valid_from": string;
    "valid_to": string | null;
    "version": number;
  };
    "Stage2CatalogPage": {
    "items": Array<components["schemas"]["Stage2CatalogView"]>;
    "pagination": {
    [key: string]: number | boolean;
  };
  };
    "Stage2CatalogPatch": {
    "expected_version": number;
    "name"?: string | null;
    "description"?: string | null;
    "website"?: string | null;
    "status"?: "active" | "inactive" | "unknown" | null;
  };
    "Stage2CatalogView": {
    "id": string;
    "kind": "company" | "platform" | "identity";
    "name": string;
    "status": string;
    "version": number;
    "website"?: string | null;
    "description"?: string | null;
    "registration_identifier"?: string | null;
    "identity_kind"?: string | null;
    "ownership"?: string | null;
    "masked_value"?: string | null;
    "company_id"?: string | null;
    "provider"?: string | null;
  };
    "Stage2ChangeBindingProposal": {
    "action": "change_binding";
    "binding_id": string;
    "new_contact_identity_id": string;
    "purpose"?: "registration" | "login" | "recovery" | "mfa" | null;
  };
    "Stage2ChangeCaseCreate": {
    "case_type": "change" | "transfer" | "offboard";
    "reason": string;
    "coordinator_person_id": string;
    "subject_person_id"?: string | null;
  };
    "Stage2ChangeCasePage": {
    "items": Array<components["schemas"]["Stage2ChangeCaseView"]>;
    "pagination": components["schemas"]["Stage2Pagination"];
  };
    "Stage2ChangeCasePatch": {
    "expected_version": number;
    "reason"?: string | null;
    "coordinator_person_id"?: string | null;
    "subject_person_id"?: string | null;
  };
    "Stage2ChangeCaseView": {
    "available_actions"?: Array<string>;
    "id": string;
    "case_type": "change" | "transfer" | "offboard";
    "subject_person_id": string | null;
    "coordinator_person_id": string;
    "reason": string;
    "status": "draft" | "active" | "completed" | "completed_with_exceptions" | "cancelled";
    "version": number;
    "created_at": string;
    "closed_at": string | null;
  };
    "Stage2ChangeItemCreate": {
    "resource_id": string;
    "assignee_person_id"?: string | null;
    "proposal": components["schemas"]["Stage2ChangeOwnerProposal"] | components["schemas"]["Stage2ChangeOrganizationProposal"] | components["schemas"]["Stage2RemoveUseProposal"] | components["schemas"]["Stage2TransferControllerProposal"] | components["schemas"]["Stage2ChangeBindingProposal"] | components["schemas"]["Stage2ChangeMailboxAddressProposal"] | components["schemas"]["Stage2ChangeManagementRelationProposal"] | components["schemas"]["Stage2RevokeCredentialGrantProposal"] | components["schemas"]["Stage2RevokeCredentialProposal"] | components["schemas"]["Stage2GrantUseProposal"] | components["schemas"]["Stage2ChangeVisibilityProposal"] | components["schemas"]["Stage2RotateCredentialProposal"] | components["schemas"]["Stage2ReplaceKeyProposal"] | components["schemas"]["Stage2DisableResourceProposal"] | components["schemas"]["Stage2RetireResourceProposal"] | components["schemas"]["Stage2ReactivateResourceProposal"];
  };
    "Stage2ChangeItemPage": {
    "items": Array<components["schemas"]["Stage2ChangeItemView"]>;
    "pagination": components["schemas"]["Stage2Pagination"];
  };
    "Stage2ChangeItemPatch": {
    "expected_version": number;
    "assignee_person_id"?: string | null;
    "proposal"?: components["schemas"]["Stage2ChangeOwnerProposal"] | components["schemas"]["Stage2ChangeOrganizationProposal"] | components["schemas"]["Stage2RemoveUseProposal"] | components["schemas"]["Stage2TransferControllerProposal"] | components["schemas"]["Stage2ChangeBindingProposal"] | components["schemas"]["Stage2ChangeMailboxAddressProposal"] | components["schemas"]["Stage2ChangeManagementRelationProposal"] | components["schemas"]["Stage2RevokeCredentialGrantProposal"] | components["schemas"]["Stage2RevokeCredentialProposal"] | components["schemas"]["Stage2GrantUseProposal"] | components["schemas"]["Stage2ChangeVisibilityProposal"] | components["schemas"]["Stage2RotateCredentialProposal"] | components["schemas"]["Stage2ReplaceKeyProposal"] | components["schemas"]["Stage2DisableResourceProposal"] | components["schemas"]["Stage2RetireResourceProposal"] | components["schemas"]["Stage2ReactivateResourceProposal"] | null;
  };
    "Stage2ChangeItemView": {
    "available_actions"?: Array<string>;
    "id": string;
    "case_id": string;
    "resource_id": string;
    "action": string;
    "assignee_person_id": string | null;
    "proposal": components["schemas"]["Stage2ChangeOwnerProposal"] | components["schemas"]["Stage2ChangeOrganizationProposal"] | components["schemas"]["Stage2RemoveUseProposal"] | components["schemas"]["Stage2TransferControllerProposal"] | components["schemas"]["Stage2ChangeBindingProposal"] | components["schemas"]["Stage2ChangeMailboxAddressProposal"] | components["schemas"]["Stage2ChangeManagementRelationProposal"] | components["schemas"]["Stage2RevokeCredentialGrantProposal"] | components["schemas"]["Stage2RevokeCredentialProposal"] | components["schemas"]["Stage2GrantUseProposal"] | components["schemas"]["Stage2ChangeVisibilityProposal"] | components["schemas"]["Stage2RotateCredentialProposal"] | components["schemas"]["Stage2ReplaceKeyProposal"] | components["schemas"]["Stage2DisableResourceProposal"] | components["schemas"]["Stage2RetireResourceProposal"] | components["schemas"]["Stage2ReactivateResourceProposal"];
    "status": "pending" | "in_progress" | "awaiting_confirmation" | "completed" | "cancelled" | "failed" | "cancellation_requested";
    "version": number;
    "non_secret_result": string | null;
    "executed_by_person_id"?: string | null;
    "confirmed_by_person_id"?: string | null;
    "executed_at"?: string | null;
    "confirmed_at"?: string | null;
    "execution_history"?: Array<{
    [key: string]: unknown;
  }>;
  };
    "Stage2ChangeMailboxAddressProposal": {
    "action": "change_mailbox_address";
    "binding_id"?: string | null;
    "new_contact_identity_id": string;
  };
    "Stage2ChangeManagementRelationProposal": {
    "action": "change_management_relation";
    "relation_id": string;
    "proposed_target_id": string;
  };
    "Stage2ChangeOrganizationProposal": {
    "action": "change_organization";
    "company_id"?: string | null;
    "owning_department_id"?: string | null;
  };
    "Stage2ChangeOwnerProposal": {
    "action": "change_owner";
    "assignment_id"?: string | null;
    "to_person_id": string;
  };
    "Stage2ChangeVisibilityProposal": {
    "action": "change_visibility";
    "visibility_scope": "restricted" | "department" | "company";
  };
    "Stage2CommitInput": {
    "expected_version": number;
    "skip_rows"?: Array<number>;
  };
    "Stage2CompanyCreate": {
    "name": string;
    "registration_identifier"?: string | null;
    "description"?: string | null;
  };
    "Stage2CompanyLinkCreate": {
    "company_id": string;
    "role": string;
  };
    "Stage2CompanyPage": {
    "items": Array<components["schemas"]["Stage2CompanyPickerOption"]>;
    "pagination": components["schemas"]["Stage2Pagination"];
  };
    "Stage2CompanyPickerOption": {
    "id": string;
    "display_name": string;
    "status": string;
  };
    "Stage2ConfirmChangeRequest": {
    "expected_version": number;
    "confirmation_note": string;
  };
    "Stage2ConnectionCreate": {
    "resource_id": string;
    "credential_id": string;
    "provider"?: "deepseek";
    "label": string;
    "scheduled"?: boolean;
    "interval_seconds"?: number;
  };
    "Stage2ConnectionPage": {
    "items": Array<components["schemas"]["Stage2ConnectionView"]>;
    "pagination": {
    [key: string]: number | boolean;
  };
  };
    "Stage2ConnectionPatch": {
    "expected_version": number;
    "credential_id"?: string | null;
    "status"?: "active" | "inactive" | null;
    "scheduled"?: boolean | null;
    "interval_seconds"?: number | null;
  };
    "Stage2ConnectionView": {
    "id": string;
    "resource_id": string;
    "provider": string;
    "label": string;
    "credential_id": string;
    "credential_version": number;
    "status": string;
    "scheduled": boolean;
    "interval_seconds": number;
    "last_attempt_at": string | null;
    "last_success_at": string | null;
    "last_error_code": string | null;
    "version": number;
    "stale": boolean;
  };
    "Stage2ContactIdentityInput": {
    "kind": components["schemas"]["Stage2ContactKind"];
    "value": string;
    "ownership": string;
    "mailbox_account_id"?: string | null;
    "mailbox_association_role"?: "alias" | null;
    "custodian_person_id"?: string | null;
    "provider"?: string | null;
    "label"?: string | null;
    "company_id"?: string | null;
  };
    "Stage2ContactIdentityView": {
    "id": string;
    "kind": components["schemas"]["Stage2ContactKind"];
    "masked_value": string;
    "ownership": string;
    "verification": string;
    "mailbox_account"?: unknown | null;
    "custodian"?: unknown | null;
  };
    "Stage2ContactKind": "email" | "phone" | "third_party";
    "Stage2CredentialAttachRequest": {
    "expected_version": number;
    "stage_token": string;
    "kind": "password" | "api_key" | "certificate_pin" | "other";
  };
    "Stage2CredentialGrantCreate": {
    "person_id": string;
    "capability": "view" | "rotate";
    "valid_to": string;
    "reason": string;
    "expected_version": number;
  };
    "Stage2CredentialGrantPage": {
    "items": Array<components["schemas"]["Stage2CredentialGrantView"]>;
    "pagination": {
    [key: string]: number | boolean;
  };
  };
    "Stage2CredentialGrantView": {
    "id": string;
    "credential_id": string;
    "person_id": string;
    "capability": "view" | "rotate";
    "valid_from": string;
    "valid_to": string | null;
    "reason": string;
    "version": number;
  };
    "Stage2CredentialMetadata": {
    "id": string;
    "resource_id": string;
    "kind": string;
    "status": string;
    "version": number;
    "created_at": string;
  };
    "Stage2CredentialMetadataPage": {
    "items": Array<components["schemas"]["Stage2CredentialMetadata"]>;
    "pagination": {
    [key: string]: number | boolean;
  };
  };
    "Stage2CredentialOperationView": {
    "operation_id": string;
    "status": "pending" | "succeeded" | "failed";
    "safe_result": components["schemas"]["Stage2SafeOperationResult"] | null;
    "retryable": boolean;
  };
    "Stage2CredentialRevealRequest": {
    "reason": string;
  };
    "Stage2CredentialRevealView": {
    "secret_value": string;
  };
    "Stage2DeclarationInput": {
    "expected_version": number;
    "relation_kind": "managed_by" | "part_of" | "contains" | "depends_on" | "uses" | "platform" | "company" | "owner" | "registration" | "login" | "recovery" | "mfa";
    "state": "unknown" | "not_applicable" | "verified_absent";
    "reason": string;
    "source": string;
  };
    "Stage2DeclarationPage": {
    "items": Array<components["schemas"]["Stage2DeclarationView"]>;
    "pagination": {
    [key: string]: number | boolean;
  };
  };
    "Stage2DeclarationView": {
    "id": string;
    "resource_id": string;
    "relation_kind": string;
    "state": string;
    "reason": string;
    "source": string;
    "ended_at": string | null;
    "created_at": string;
  };
    "Stage2DepartmentPage": {
    "items": Array<components["schemas"]["Stage2DepartmentPickerOption"]>;
    "pagination": components["schemas"]["Stage2Pagination"];
  };
    "Stage2DepartmentPickerOption": {
    "id": string;
    "display_name": string;
    "parent_department_id": string | null;
    "status": string;
  };
    "Stage2DisableResourceProposal": {
    "action": "disable_resource";
  };
    "Stage2EndFile": {
    "expected_version": number;
    "reason": string;
  };
    "Stage2EntryMaterialView": {
    "id": string;
    "version": number;
    "kind": "entry";
    "title": string | null;
    "url": string;
    "classification": string | null;
    "created_at": string;
    "updated_at": string;
  };
    "Stage2ExpectedVersionRequest": {
    "expected_version": number;
    "closure_note"?: string | null;
  };
    "Stage2ExpenseCreate": {
    "expected_version": number;
    "amount": number | string;
    "currency": "CNY" | "USD" | "EUR" | "GBP" | "HKD" | "JPY" | "SGD" | "AUD" | "CAD" | "CHF";
    "kind": "actual" | "budget";
    "recorded_on": string;
    "period_id"?: string | null;
    "corrects_entry_id"?: string | null;
    "source": string;
  };
    "Stage2ExpensePage": {
    "items": Array<components["schemas"]["Stage2ExpenseView"]>;
    "pagination": {
    [key: string]: number | boolean;
  };
  };
    "Stage2ExpenseView": {
    "id": string;
    "resource_id": string;
    "period_id": string | null;
    "corrects_entry_id": string | null;
    "amount": string;
    "currency": string;
    "kind": string;
    "recorded_on": string;
    "source": string;
    "void_reason": string | null;
    "version": number;
  };
    "Stage2FactActionInput": {
    "expected_version": number;
    "reason": string;
    "lifecycle"?: "unknown" | "in_use" | null;
  };
    "Stage2FilePage": {
    "items": Array<components["schemas"]["Stage2FileView"]>;
    "pagination": {
    [key: string]: number | boolean;
  };
  };
    "Stage2FileView": {
    "id": string;
    "resource_id": string;
    "filename": string;
    "media_type": string;
    "size_bytes": number;
    "status": "available" | "replaced" | "ended";
    "classification": "normal" | "restricted" | "sensitive";
    "check_policy": string;
    "replaces_file_id": string | null;
    "version": number;
    "created_at": string;
    "ended_at": string | null;
  };
    "Stage2GrantUseProposal": {
    "action": "grant_use";
    "person_id": string;
  };
    "Stage2GraphDeclaration": {
    "relation_kind": string;
    "state": "unknown" | "not_applicable" | "verified_absent";
  };
    "Stage2GraphEdge": {
    "id": string;
    "source": string;
    "target": string;
    "relation": string;
    "confirmation": string;
  };
    "Stage2GraphNode": {
    "id": string;
    "key": string;
    "kind": "resource" | "company" | "platform" | "person" | "identity";
    "label": string;
    "type_code": string;
    "verification": string;
    "lifecycle": string | null;
    "declarations"?: Array<components["schemas"]["Stage2GraphDeclaration"]>;
  };
    "Stage2HTTPValidationError": {
    "detail"?: Array<components["schemas"]["Stage2ValidationError"]>;
    [key: string]: unknown;
  };
    "Stage2HistoryPage": {
    "items": Array<components["schemas"]["Stage2HistoryView"]>;
    "pagination": {
    [key: string]: number | boolean;
  };
  };
    "Stage2HistoryView": {
    "id": string;
    "event_type": string;
    "occurred_at": string;
    "actor_person_id": string | null;
    "safe_before": {
    [key: string]: unknown;
  } | null;
    "safe_after": {
    [key: string]: unknown;
  } | null;
  };
    "Stage2IdentityCreate": {
    "kind": "phone" | "email" | "third_party";
    "value": string;
    "label"?: string | null;
    "provider"?: string | null;
    "ownership"?: "company" | "personal" | "unknown";
    "company_id"?: string | null;
    "custodian_person_id"?: string | null;
  };
    "Stage2IdentityMetadata": {
    "id": string;
    "label": string | null;
    "provider": string | null;
    "version": number;
  };
    "Stage2IdentityPatch": {
    "expected_version": number;
    "label"?: string | null;
    "provider"?: string | null;
  };
    "Stage2ImportRow": {
    "row_number": number;
    "status": "ready" | "duplicate_candidate" | "error" | "skipped" | "created";
    "message"?: string | null;
    "candidate_ids"?: Array<string>;
    "resource_id"?: string | null;
  };
    "Stage2InitialFactsInput": {
    "expected_version": number;
    "people"?: Array<components["schemas"]["Stage2PersonAssignmentCreate"]>;
    "company_links"?: Array<components["schemas"]["Stage2CompanyLinkCreate"]>;
    "source_note": string;
  };
    "Stage2JobPage": {
    "items": Array<components["schemas"]["Stage2JobView"]>;
    "pagination": {
    [key: string]: number | boolean;
  };
  };
    "Stage2JobView": {
    "id": string;
    "resource_id": string;
    "connection_id": string;
    "status": string;
    "attempts": number;
    "available_at": string;
    "lease_until": string | null;
    "last_error_code": string | null;
    "finished_at": string | null;
  };
    "Stage2LedgerCreate": {
    "plan"?: string | null;
    "seats_total"?: number | null;
    "seats_assigned"?: number | null;
    "billing_cycle"?: "month" | "year" | "custom";
    "reminder_days"?: Array<number>;
    "resource_id": string;
  };
    "Stage2LedgerPage": {
    "items": Array<components["schemas"]["Stage2LedgerView"]>;
    "pagination": {
    [key: string]: number | boolean;
  };
  };
    "Stage2LedgerPatch": {
    "plan"?: string | null;
    "seats_total"?: number | null;
    "seats_assigned"?: number | null;
    "billing_cycle"?: "month" | "year" | "custom";
    "reminder_days"?: Array<number>;
    "expected_version": number;
    "reason": string;
  };
    "Stage2LedgerView": {
    "plan"?: string | null;
    "seats_total"?: number | null;
    "seats_assigned"?: number | null;
    "billing_cycle"?: "month" | "year" | "custom";
    "reminder_days"?: Array<number>;
    "id": string;
    "resource_id": string;
    "version": number;
    "current_period"?: components["schemas"]["Stage2PeriodView"] | null;
    "active_users": number;
  };
    "Stage2LocalGraph": {
    "center": string;
    "nodes": Array<components["schemas"]["Stage2GraphNode"]>;
    "edges": Array<components["schemas"]["Stage2GraphEdge"]>;
    "truncated": boolean;
    "coverage": "visible_known_relations";
  };
    "Stage2MailboxContactIdentityOption": {
    "id": string;
    "kind": "email";
    "masked_value": string;
    "ownership": string;
    "verification": string;
  };
    "Stage2MailboxContactIdentityPage": {
    "items": Array<components["schemas"]["Stage2MailboxContactIdentityOption"]>;
    "pagination": components["schemas"]["Stage2Pagination"];
  };
    "Stage2MaterialCreateRequest": {
    "kind": "entry" | "note" | "attachment";
    "title"?: string | null;
    "url"?: string | null;
    "body"?: string | null;
    "file_ref"?: string | null;
    "classification"?: string | null;
  };
    "Stage2MaterialPage": {
    "items": Array<components["schemas"]["Stage2EntryMaterialView"] | components["schemas"]["Stage2NoteMaterialView"] | components["schemas"]["Stage2AttachmentMaterialView"]>;
    "pagination": components["schemas"]["Stage2Pagination"];
  };
    "Stage2MaterialPatchChanges": {
    "title"?: string | null;
    "url"?: string | null;
    "body"?: string | null;
    "classification"?: string | null;
  };
    "Stage2MaterialPatchRequest": {
    "expected_version": number;
    "kind": "entry" | "note" | "attachment";
    "changes": components["schemas"]["Stage2MaterialPatchChanges"];
  };
    "Stage2MoneySummary": {
    "currency": string;
    "kind": string;
    "period": string;
    "amount": string;
  };
    "Stage2MyResourcePage": {
    "items": Array<components["schemas"]["MyResourceSummary"]>;
    "pagination": components["schemas"]["Stage2Pagination"];
  };
    "Stage2NoteMaterialView": {
    "id": string;
    "version": number;
    "kind": "note";
    "title": string | null;
    "body": string;
    "classification": string | null;
    "created_at": string;
    "updated_at": string;
  };
    "Stage2NotificationPreferencePatch": {
    "expected_version": number;
    "show_due": boolean;
  };
    "Stage2NotificationPreferenceView": {
    "show_due": boolean;
    "version": number;
  };
    "Stage2OrganizationSummary": {
    "id": string;
    "display_name": string;
  };
    "Stage2PageSize": 25 | 50 | 100;
    "Stage2Pagination": {
    "page": number;
    "page_size": number;
    "total": number;
    "has_next": boolean;
  };
    "Stage2PeriodCreate": {
    "expected_version": number;
    "starts_on": string;
    "ends_on": string;
    "planned_amount"?: number | string | null;
    "currency": "CNY" | "USD" | "EUR" | "GBP" | "HKD" | "JPY" | "SGD" | "AUD" | "CAD" | "CHF";
    "source": string;
  };
    "Stage2PeriodPage": {
    "items": Array<components["schemas"]["Stage2PeriodView"]>;
    "pagination": {
    [key: string]: number | boolean;
  };
  };
    "Stage2PeriodView": {
    "id": string;
    "resource_id": string;
    "starts_on": string;
    "ends_on": string;
    "planned_amount": string | null;
    "currency": string;
    "source": string;
    "void_reason": string | null;
    "version": number;
  };
    "Stage2PersonAssignmentCreate": {
    "person_id": string;
    "role": string;
  };
    "Stage2PersonCreate": {
    "display_name": string;
    "department_id"?: string | null;
    "status"?: "active" | "inactive" | "unknown";
  };
    "Stage2PersonPage": {
    "items": Array<components["schemas"]["Stage2PersonPickerOption"]>;
    "pagination": components["schemas"]["Stage2Pagination"];
  };
    "Stage2PersonPatch": {
    "display_name": string;
    "department_id"?: string | null;
    "status"?: "active" | "inactive" | "unknown";
    "expected_version": number;
  };
    "Stage2PersonPickerOption": {
    "id": string;
    "display_name": string;
    "department": components["schemas"]["Stage2OrganizationSummary"] | null;
    "status": string;
  };
    "Stage2PersonView": {
    "id": string;
    "display_name": string;
    "department_id": string | null;
    "status": string;
    "version": number;
  };
    "Stage2PlatformCreate": {
    "name": string;
    "website"?: string | null;
  };
    "Stage2PrepareOperationInput": {
    "expected_version": number;
    "action": "replace" | "revoke" | "revoke_grant";
    "stage_token"?: string | null;
    "grant_id"?: string | null;
    "reason": string;
  };
    "Stage2PreparedOperationView": {
    "id": string;
    "resource_id": string;
    "credential_id": string;
    "action": string;
    "status": string;
    "expires_at": string;
    "result_credential_id": string | null;
  };
    "Stage2PreviewInput": {
    "type_code": "platform_account" | "mailbox_account" | "api_key" | "service_subscription" | "business_space" | "application" | "api_service" | "cloud_resource" | "domain";
    "label": string;
    "csv_content": string;
    "mapping"?: {
    [key: string]: string;
  };
  };
    "Stage2ProviderCapability": {
    "provider"?: "deepseek";
    "metric"?: "account_balance";
    "endpoint"?: "https://api.deepseek.com/user/balance";
    "unit"?: "money";
    "currencies"?: Array<string>;
    "official_documentation"?: string;
    "checked_on"?: string;
    "per_key_usage"?: false;
  };
    "Stage2ProviderPage": {
    "items": Array<components["schemas"]["Stage2ProviderCapability"]>;
  };
    "Stage2ReactivateResourceProposal": {
    "action": "reactivate_resource";
  };
    "Stage2RecordExecutionRequest": {
    "expected_version": number;
    "evidence_ids": Array<string>;
    "non_secret_result"?: string | null;
    "outcome"?: "succeeded" | "failed";
  };
    "Stage2RelationPage": {
    "items": Array<components["schemas"]["Stage2ResourceRelationView"]>;
    "pagination": components["schemas"]["Stage2Pagination"];
    "coverage"?: "visible_known_relations";
  };
    "Stage2ReminderPage": {
    "unread_total": number;
    "items": Array<components["schemas"]["Stage2ReminderView"]>;
    "pagination": {
    [key: string]: number | boolean;
  };
  };
    "Stage2ReminderResult": {
    "processed": number;
  };
    "Stage2ReminderView": {
    "resource_name": string;
    "id": string;
    "resource_id": string;
    "due_on": string;
    "window_days": number;
    "status": string;
    "read": boolean;
  };
    "Stage2RemoveUseProposal": {
    "action": "remove_use";
    "assignment_id": string;
  };
    "Stage2ReplaceKeyProposal": {
    "action": "replace_key";
    "replacement_resource_id": string;
  };
    "Stage2ResourcePage": {
    "items": Array<components["schemas"]["ResourceSummary"]>;
    "pagination": components["schemas"]["Stage2Pagination"];
  };
    "Stage2ResourceRelationCreateRequest": {
    "expected_version": number;
    "target_id": string;
    "relation_type": "uses" | "managed_by" | "part_of" | "contains" | "depends_on";
    "note"?: string | null;
  };
    "Stage2ResourceRelationView": {
    "id": string;
    "source": components["schemas"]["ResourceSummary"];
    "target": components["schemas"]["ResourceSummary"];
    "relation_type": "uses" | "managed_by" | "part_of" | "contains" | "depends_on";
    "direction": "outgoing" | "incoming";
    "confirmation": "proposed" | "confirmed";
    "valid_from": string;
    "valid_to": string | null;
    "note": string | null;
    "version": number;
  };
    "Stage2ResourceRole": {
    "id": string;
    "resource_id": string;
    "resource_name": string;
    "person_id": string;
    "person_name": string;
    "role": string;
    "confirmation": string;
    "valid_from": string;
    "valid_to": string | null;
  };
    "Stage2ResourceRolePage": {
    "items": Array<components["schemas"]["Stage2ResourceRole"]>;
    "pagination": {
    [key: string]: number | boolean;
  };
  };
    "Stage2ResourceType": "platform_account" | "mailbox_account" | "api_key" | "service_subscription" | "business_space" | "application" | "api_service" | "cloud_resource" | "domain";
    "Stage2ResponseMeta": {
    "request_id": string;
  };
    "Stage2RetireResourceProposal": {
    "action": "retire_resource";
  };
    "Stage2RevokeCredentialGrantProposal": {
    "action": "revoke_credential_grant";
    "credential_grant_id": string;
    "operation_id": string;
  };
    "Stage2RevokeCredentialProposal": {
    "action": "revoke_credential";
    "credential_id": string;
    "operation_id": string;
  };
    "Stage2RotateCredentialProposal": {
    "action": "rotate_credential";
    "credential_id": string;
    "operation_id": string;
  };
    "Stage2SafeOperationResult": {
    "resource_id"?: string | null;
    "credential_id"?: string | null;
    "credential_status"?: "not_saved" | "pending" | "saved" | "failed" | null;
  };
    "Stage2SecretStageCreate": {
    "kind": "password" | "api_key" | "certificate_pin" | "other";
    "secret_value": string;
    "resource_id"?: string | null;
    "purpose"?: "attach" | "replace";
  };
    "Stage2SecretStageView": {
    "stage_token": string;
    "expires_at": string;
  };
    "Stage2SnapshotPage": {
    "items": Array<components["schemas"]["Stage2SnapshotView"]>;
    "pagination": {
    [key: string]: number | boolean;
  };
  };
    "Stage2SnapshotView": {
    "id": string;
    "resource_id": string;
    "connection_id": string;
    "currency": string;
    "total_balance": string;
    "granted_balance": string;
    "topped_up_balance": string;
    "is_available": boolean;
    "collected_at": string;
    "meaning"?: "account_balance";
  };
    "Stage2SourcePage": {
    "items": Array<components["schemas"]["Stage2SourceView"]>;
    "pagination": {
    [key: string]: number | boolean;
  };
  };
    "Stage2SourceView": {
    "id": string;
    "source_kind": string;
    "label": string;
    "source_ref": string | null;
    "created_at": string;
  };
    "Stage2SuccessEnvelope_Annotated_Union_EntryMaterialView__NoteMaterialView__AttachmentMaterialView___FieldInfo_annotation_NoneType__required_True__discriminator__kind____": {
    "data": components["schemas"]["Stage2EntryMaterialView"] | components["schemas"]["Stage2NoteMaterialView"] | components["schemas"]["Stage2AttachmentMaterialView"];
    "error": null;
    "meta": components["schemas"]["Stage2ResponseMeta"];
  };
    "Stage2SuccessEnvelope_BatchPage_": {
    "data": components["schemas"]["Stage2BatchPage"];
    "error": null;
    "meta": components["schemas"]["Stage2ResponseMeta"];
  };
    "Stage2SuccessEnvelope_BatchView_": {
    "data": components["schemas"]["Stage2BatchView"];
    "error": null;
    "meta": components["schemas"]["Stage2ResponseMeta"];
  };
    "Stage2SuccessEnvelope_BindingPage_": {
    "data": components["schemas"]["Stage2BindingPage"];
    "error": null;
    "meta": components["schemas"]["Stage2ResponseMeta"];
  };
    "Stage2SuccessEnvelope_BindingView_": {
    "data": components["schemas"]["Stage2BindingView"];
    "error": null;
    "meta": components["schemas"]["Stage2ResponseMeta"];
  };
    "Stage2SuccessEnvelope_CatalogPage_": {
    "data": components["schemas"]["Stage2CatalogPage"];
    "error": null;
    "meta": components["schemas"]["Stage2ResponseMeta"];
  };
    "Stage2SuccessEnvelope_CatalogView_": {
    "data": components["schemas"]["Stage2CatalogView"];
    "error": null;
    "meta": components["schemas"]["Stage2ResponseMeta"];
  };
    "Stage2SuccessEnvelope_ChangeCasePage_": {
    "data": components["schemas"]["Stage2ChangeCasePage"];
    "error": null;
    "meta": components["schemas"]["Stage2ResponseMeta"];
  };
    "Stage2SuccessEnvelope_ChangeCaseView_": {
    "data": components["schemas"]["Stage2ChangeCaseView"];
    "error": null;
    "meta": components["schemas"]["Stage2ResponseMeta"];
  };
    "Stage2SuccessEnvelope_ChangeItemPage_": {
    "data": components["schemas"]["Stage2ChangeItemPage"];
    "error": null;
    "meta": components["schemas"]["Stage2ResponseMeta"];
  };
    "Stage2SuccessEnvelope_ChangeItemView_": {
    "data": components["schemas"]["Stage2ChangeItemView"];
    "error": null;
    "meta": components["schemas"]["Stage2ResponseMeta"];
  };
    "Stage2SuccessEnvelope_CompanyPage_": {
    "data": components["schemas"]["Stage2CompanyPage"];
    "error": null;
    "meta": components["schemas"]["Stage2ResponseMeta"];
  };
    "Stage2SuccessEnvelope_ConnectionPage_": {
    "data": components["schemas"]["Stage2ConnectionPage"];
    "error": null;
    "meta": components["schemas"]["Stage2ResponseMeta"];
  };
    "Stage2SuccessEnvelope_ConnectionView_": {
    "data": components["schemas"]["Stage2ConnectionView"];
    "error": null;
    "meta": components["schemas"]["Stage2ResponseMeta"];
  };
    "Stage2SuccessEnvelope_CredentialGrantPage_": {
    "data": components["schemas"]["Stage2CredentialGrantPage"];
    "error": null;
    "meta": components["schemas"]["Stage2ResponseMeta"];
  };
    "Stage2SuccessEnvelope_CredentialGrantView_": {
    "data": components["schemas"]["Stage2CredentialGrantView"];
    "error": null;
    "meta": components["schemas"]["Stage2ResponseMeta"];
  };
    "Stage2SuccessEnvelope_CredentialMetadataPage_": {
    "data": components["schemas"]["Stage2CredentialMetadataPage"];
    "error": null;
    "meta": components["schemas"]["Stage2ResponseMeta"];
  };
    "Stage2SuccessEnvelope_CredentialOperationView_": {
    "data": components["schemas"]["Stage2CredentialOperationView"];
    "error": null;
    "meta": components["schemas"]["Stage2ResponseMeta"];
  };
    "Stage2SuccessEnvelope_CredentialRevealView_": {
    "data": components["schemas"]["Stage2CredentialRevealView"];
    "error": null;
    "meta": components["schemas"]["Stage2ResponseMeta"];
  };
    "Stage2SuccessEnvelope_DeclarationPage_": {
    "data": components["schemas"]["Stage2DeclarationPage"];
    "error": null;
    "meta": components["schemas"]["Stage2ResponseMeta"];
  };
    "Stage2SuccessEnvelope_DeclarationView_": {
    "data": components["schemas"]["Stage2DeclarationView"];
    "error": null;
    "meta": components["schemas"]["Stage2ResponseMeta"];
  };
    "Stage2SuccessEnvelope_DepartmentPage_": {
    "data": components["schemas"]["Stage2DepartmentPage"];
    "error": null;
    "meta": components["schemas"]["Stage2ResponseMeta"];
  };
    "Stage2SuccessEnvelope_ExpensePage_": {
    "data": components["schemas"]["Stage2ExpensePage"];
    "error": null;
    "meta": components["schemas"]["Stage2ResponseMeta"];
  };
    "Stage2SuccessEnvelope_ExpenseView_": {
    "data": components["schemas"]["Stage2ExpenseView"];
    "error": null;
    "meta": components["schemas"]["Stage2ResponseMeta"];
  };
    "Stage2SuccessEnvelope_FilePage_": {
    "data": components["schemas"]["Stage2FilePage"];
    "error": null;
    "meta": components["schemas"]["Stage2ResponseMeta"];
  };
    "Stage2SuccessEnvelope_FileView_": {
    "data": components["schemas"]["Stage2FileView"];
    "error": null;
    "meta": components["schemas"]["Stage2ResponseMeta"];
  };
    "Stage2SuccessEnvelope_HistoryPage_": {
    "data": components["schemas"]["Stage2HistoryPage"];
    "error": null;
    "meta": components["schemas"]["Stage2ResponseMeta"];
  };
    "Stage2SuccessEnvelope_IdentityMetadata_": {
    "data": components["schemas"]["Stage2IdentityMetadata"];
    "error": null;
    "meta": components["schemas"]["Stage2ResponseMeta"];
  };
    "Stage2SuccessEnvelope_JobPage_": {
    "data": components["schemas"]["Stage2JobPage"];
    "error": null;
    "meta": components["schemas"]["Stage2ResponseMeta"];
  };
    "Stage2SuccessEnvelope_JobView_": {
    "data": components["schemas"]["Stage2JobView"];
    "error": null;
    "meta": components["schemas"]["Stage2ResponseMeta"];
  };
    "Stage2SuccessEnvelope_LedgerPage_": {
    "data": components["schemas"]["Stage2LedgerPage"];
    "error": null;
    "meta": components["schemas"]["Stage2ResponseMeta"];
  };
    "Stage2SuccessEnvelope_LedgerView_": {
    "data": components["schemas"]["Stage2LedgerView"];
    "error": null;
    "meta": components["schemas"]["Stage2ResponseMeta"];
  };
    "Stage2SuccessEnvelope_LocalGraph_": {
    "data": components["schemas"]["Stage2LocalGraph"];
    "error": null;
    "meta": components["schemas"]["Stage2ResponseMeta"];
  };
    "Stage2SuccessEnvelope_MailboxContactIdentityPage_": {
    "data": components["schemas"]["Stage2MailboxContactIdentityPage"];
    "error": null;
    "meta": components["schemas"]["Stage2ResponseMeta"];
  };
    "Stage2SuccessEnvelope_MaterialPage_": {
    "data": components["schemas"]["Stage2MaterialPage"];
    "error": null;
    "meta": components["schemas"]["Stage2ResponseMeta"];
  };
    "Stage2SuccessEnvelope_MyResourcePage_": {
    "data": components["schemas"]["Stage2MyResourcePage"];
    "error": null;
    "meta": components["schemas"]["Stage2ResponseMeta"];
  };
    "Stage2SuccessEnvelope_NotificationPreferenceView_": {
    "data": components["schemas"]["Stage2NotificationPreferenceView"];
    "error": null;
    "meta": components["schemas"]["Stage2ResponseMeta"];
  };
    "Stage2SuccessEnvelope_PeriodPage_": {
    "data": components["schemas"]["Stage2PeriodPage"];
    "error": null;
    "meta": components["schemas"]["Stage2ResponseMeta"];
  };
    "Stage2SuccessEnvelope_PeriodView_": {
    "data": components["schemas"]["Stage2PeriodView"];
    "error": null;
    "meta": components["schemas"]["Stage2ResponseMeta"];
  };
    "Stage2SuccessEnvelope_PersonPage_": {
    "data": components["schemas"]["Stage2PersonPage"];
    "error": null;
    "meta": components["schemas"]["Stage2ResponseMeta"];
  };
    "Stage2SuccessEnvelope_PersonView_": {
    "data": components["schemas"]["Stage2PersonView"];
    "error": null;
    "meta": components["schemas"]["Stage2ResponseMeta"];
  };
    "Stage2SuccessEnvelope_PreparedOperationView_": {
    "data": components["schemas"]["Stage2PreparedOperationView"];
    "error": null;
    "meta": components["schemas"]["Stage2ResponseMeta"];
  };
    "Stage2SuccessEnvelope_ProviderPage_": {
    "data": components["schemas"]["Stage2ProviderPage"];
    "error": null;
    "meta": components["schemas"]["Stage2ResponseMeta"];
  };
    "Stage2SuccessEnvelope_RelationPage_": {
    "data": components["schemas"]["Stage2RelationPage"];
    "error": null;
    "meta": components["schemas"]["Stage2ResponseMeta"];
  };
    "Stage2SuccessEnvelope_ReminderPage_": {
    "data": components["schemas"]["Stage2ReminderPage"];
    "error": null;
    "meta": components["schemas"]["Stage2ResponseMeta"];
  };
    "Stage2SuccessEnvelope_ReminderResult_": {
    "data": components["schemas"]["Stage2ReminderResult"];
    "error": null;
    "meta": components["schemas"]["Stage2ResponseMeta"];
  };
    "Stage2SuccessEnvelope_ResourcePage_": {
    "data": components["schemas"]["Stage2ResourcePage"];
    "error": null;
    "meta": components["schemas"]["Stage2ResponseMeta"];
  };
    "Stage2SuccessEnvelope_ResourceRelationView_": {
    "data": components["schemas"]["Stage2ResourceRelationView"];
    "error": null;
    "meta": components["schemas"]["Stage2ResponseMeta"];
  };
    "Stage2SuccessEnvelope_ResourceRolePage_": {
    "data": components["schemas"]["Stage2ResourceRolePage"];
    "error": null;
    "meta": components["schemas"]["Stage2ResponseMeta"];
  };
    "Stage2SuccessEnvelope_ResourceView_": {
    "data": components["schemas"]["ResourceView"];
    "error": null;
    "meta": components["schemas"]["Stage2ResponseMeta"];
  };
    "Stage2SuccessEnvelope_SecretStageView_": {
    "data": components["schemas"]["Stage2SecretStageView"];
    "error": null;
    "meta": components["schemas"]["Stage2ResponseMeta"];
  };
    "Stage2SuccessEnvelope_SnapshotPage_": {
    "data": components["schemas"]["Stage2SnapshotPage"];
    "error": null;
    "meta": components["schemas"]["Stage2ResponseMeta"];
  };
    "Stage2SuccessEnvelope_SourcePage_": {
    "data": components["schemas"]["Stage2SourcePage"];
    "error": null;
    "meta": components["schemas"]["Stage2ResponseMeta"];
  };
    "Stage2SuccessEnvelope_SummaryView_": {
    "data": components["schemas"]["Stage2SummaryView"];
    "error": null;
    "meta": components["schemas"]["Stage2ResponseMeta"];
  };
    "Stage2SuccessEnvelope_WorkerStatus_": {
    "data": components["schemas"]["Stage2WorkerStatus"];
    "error": null;
    "meta": components["schemas"]["Stage2ResponseMeta"];
  };
    "Stage2SummaryView": {
    "items": Array<components["schemas"]["Stage2MoneySummary"]>;
  };
    "Stage2TransferControllerProposal": {
    "action": "transfer_controller";
    "assignment_id": string;
    "to_person_id": string;
  };
    "Stage2ValidationError": {
    "loc": Array<string | number>;
    "msg": string;
    "type": string;
    "input"?: unknown;
    "ctx"?: {
    [key: string]: unknown;
  };
    [key: string]: unknown;
  };
    "Stage2VersionReason": {
    "expected_version": number;
    "reason": string;
  };
    "Stage2VersionReasonRequest": {
    "expected_version": number;
    "reason": string;
  };
    "Stage2WorkerStatus": {
    "counts": {
    [key: string]: number;
  };
    "recent_heartbeat": boolean;
    "last_seen_at": string | null;
  };
    "SubscriptionCreate": components["schemas"]["ResourceCreateCommon"] & {
    "type_code"?: "service_subscription";
    "attributes"?: {
    "plan"?: string | null;
    "budgets"?: Array<components["schemas"]["BudgetEntry"]>;
    "renewal_day"?: number | null;
    "expires_on"?: string | null;
    "payment_label"?: string | null;
    "settlement_mode"?: string | null;
    "seats"?: number | null;
    "billing_cycle"?: "month" | "year" | "custom" | null;
  };
    [key: string]: unknown;
  };
    "Verification": "unverified" | "verified" | "needs_review";
    "VerifyResourceRequest": {
    "expected_version": number;
    "verification_basis": string;
  };
    "VersionReasonRequest": {
    "expected_version": number;
    "reason": string;
  };
  };
}

export type ApiSchemas = components["schemas"];
