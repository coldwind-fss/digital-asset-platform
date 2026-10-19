from __future__ import annotations

from decimal import Decimal
from typing import Any
from datetime import date
import re
from urllib.parse import urlsplit


RESOURCE_TYPES = {
    "platform_account",
    "mailbox_account",
    "api_key",
    "service_subscription",
    "business_space",
    "application",
    "api_service", "cloud_resource", "domain",
}
LOGIN_METHODS = {"password", "otp", "qr", "sso", "api_token", "unknown"}

ATTRIBUTE_FIELDS: dict[str, set[str]] = {
    "platform_account": set(),
    "mailbox_account": set(),
    "api_key": {"external_key_id"},
    "service_subscription": {"plan", "budgets", "renewal_day", "expires_on", "payment_label", "settlement_mode", "seats", "billing_cycle"},
    "business_space": {"external_instance_id", "environment", "region", "scope_label"},
    "application": {"tech_stack", "endpoint", "environment"},
    "api_service": {"external_instance_id", "endpoint", "metric_scope", "environment"},
    "cloud_resource": {"external_instance_id", "resource_kind", "region", "specification", "environment", "endpoint"},
    "domain": {"domain_name", "registrar", "registered_on", "expires_on", "renewal_note"},
}


class ResourceRuleError(ValueError):
    def __init__(self, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field


def validate_attributes(type_code: str, attributes: dict[str, Any]) -> dict[str, Any]:
    if type_code not in RESOURCE_TYPES:
        raise ResourceRuleError("type_code", "资源类型不受支持")
    unknown = set(attributes) - ATTRIBUTE_FIELDS[type_code]
    if unknown:
        raise ResourceRuleError("attributes", "存在不受支持的类型属性")

    string_fields = ATTRIBUTE_FIELDS[type_code] - {"tech_stack", "budgets", "renewal_day", "seats"}
    for key in string_fields:
        value = attributes.get(key)
        if value is not None and (not isinstance(value, str) or len(value) > 2000):
            raise ResourceRuleError("attributes."+key, "属性必须是最多2000字符的字符串或未知值")
    for key in {"registered_on", "expires_on"} & attributes.keys():
        if attributes[key] is not None:
            try:
                date.fromisoformat(attributes[key])
            except (ValueError, TypeError):
                raise ResourceRuleError("attributes."+key,"日期必须使用YYYY-MM-DD") from None
    endpoint = attributes.get("endpoint")
    if endpoint:
        parsed = urlsplit(endpoint)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise ResourceRuleError("attributes.endpoint", "入口必须为无凭据的HTTP(S)URL")
    if type_code == "domain" and attributes.get("domain_name"):
        domain = attributes["domain_name"]
        if len(domain)>253 or not re.fullmatch(r"(?=.{1,253}$)(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,63}", domain):
            raise ResourceRuleError("attributes.domain_name", "域名格式不正确")
    if "seats" in attributes and attributes["seats"] is not None and (type(attributes["seats"]) is not int or not 0<=attributes["seats"]<=1000000):
        raise ResourceRuleError("attributes.seats","席位必须是非负整数")
    if attributes.get("billing_cycle") not in {None,"month","year","custom"}:
        raise ResourceRuleError("attributes.billing_cycle","计费周期不受支持")

    if type_code == "service_subscription":
        renewal_day = attributes.get("renewal_day")
        if renewal_day is not None and (not isinstance(renewal_day, int) or not 1 <= renewal_day <= 31):
            raise ResourceRuleError("attributes.renewal_day", "续费日必须在 1 到 31 之间")
        budgets = attributes.get("budgets", [])
        if not isinstance(budgets, list) or len(budgets) > 100:
            raise ResourceRuleError("attributes.budgets", "预算必须是最多 100 项的列表")
        for index, budget in enumerate(budgets):
            if not isinstance(budget, dict):
                raise ResourceRuleError(f"attributes.budgets.{index}", "预算条目格式无效")
            if set(budget) != {"amount", "currency", "period", "meaning"}:
                raise ResourceRuleError(f"attributes.budgets.{index}", "预算必须保留金额、币种、周期和语义")
            amount = budget["amount"]
            try:
                decimal_amount = Decimal(str(amount))
            except Exception as exc:
                raise ResourceRuleError(f"attributes.budgets.{index}.amount", "金额格式无效") from exc
            if not decimal_amount.is_finite() or decimal_amount < 0 or decimal_amount.as_tuple().exponent < -2 or decimal_amount >= Decimal("10000000000000000"):
                raise ResourceRuleError(f"attributes.budgets.{index}.amount", "金额必须非负且最多两位小数")
            if not all(isinstance(budget[key], str) and budget[key].strip() for key in ("currency", "period", "meaning")):
                raise ResourceRuleError(f"attributes.budgets.{index}", "预算币种、周期和语义不能为空")

    if type_code == "application":
        tech_stack = attributes.get("tech_stack", [])
        if not isinstance(tech_stack, list) or len(tech_stack) > 50 or any(not isinstance(item, str) or not item.strip() for item in tech_stack):
            raise ResourceRuleError("attributes.tech_stack", "技术栈必须是非空字符串列表")

    return attributes


def validate_account_profile(type_code: str, account: dict[str, Any] | None) -> None:
    if account is None:
        return
    if type_code not in {"platform_account", "mailbox_account"}:
        raise ResourceRuleError("account", "只有平台账号和邮箱账号可以填写账号扩展")
    allowed = {"identifier", "login_methods", "account_role", "scope_label", "aliases"}
    if set(account) - allowed:
        raise ResourceRuleError("account", "账号扩展字段不受支持")
    methods = account.get("login_methods", [])
    if not isinstance(methods, list) or len(methods) > 6 or any(method not in LOGIN_METHODS for method in methods):
        raise ResourceRuleError("account.login_methods", "登录方式不受支持")
    if type_code != "mailbox_account" and account.get("aliases"):
        raise ResourceRuleError("account.aliases", "只有邮箱账号可以填写别名")
