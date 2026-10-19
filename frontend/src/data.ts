export type ResourceType =
  | "platform_account"
  | "mailbox_account"
  | "api_key"
  | "service_subscription"
  | "business_space"
  | "application";

export type Lifecycle = "unknown" | "in_use" | "disabled" | "retired";

export interface ResourceRelation {
  kind: "uses" | "managed_by" | "part_of";
  label: string;
  targetId?: string;
}

export interface ResourcePerson {
  personId: string;
  personName: string;
  role: "owner" | "maintainer" | "user" | "controller";
}

export interface Resource {
  id: string;
  code: string;
  name: string;
  type: ResourceType;
  provider: string;
  purpose: string;
  department: string;
  owner: string;
  people?: ResourcePerson[];
  lifecycle: Lifecycle;
  verification: "unverified" | "verified" | "needs_review";
  usageMode: "normal" | "test" | "standby";
  visibility: "restricted" | "department" | "company";
  credentialState?: "saved" | "not_saved";
  attributes: Record<string, string>;
  relations: ResourceRelation[];
}

export interface ChangeItem {
  id: string;
  resourceId?: string;
  resource: string;
  action: string;
  current: string;
  proposed: string;
  executor: string;
  status: "待执行" | "执行中" | "待确认" | "已完成";
  reason: string;
  proposedOwner?: string;
}

export const typeLabels: Record<ResourceType, string> = {
  platform_account: "平台账号",
  mailbox_account: "邮箱账号",
  api_key: "API 密钥",
  service_subscription: "软件 / 服务订阅",
  business_space: "店铺 / 业务空间",
  application: "系统 / 应用",
};

export const typeDescriptions: Record<ResourceType, string> = {
  platform_account: "可独立登录、授权或停用的平台账号",
  mailbox_account: "一个可以独立维护的邮箱账号",
  api_key: "需要独立管理、撤销或替换的 API Key",
  service_subscription: "实际购买、续费或停用的服务项",
  business_space: "独立业务范围、店铺或工作环境",
  application: "可独立使用、维护或交接的系统应用",
};

export const resources: Resource[] = [
  {
    id: "res-deepseek-account",
    code: "RES-0001",
    name: "DeepSeek 公司账号",
    type: "platform_account",
    provider: "DeepSeek",
    purpose: "公司统一管理和使用 DeepSeek 能力",
    department: "技术中心",
    owner: "待补充",
    people: [{ personId: "person-wangqiang", personName: "王强", role: "maintainer" }],
    lifecycle: "in_use",
    verification: "needs_review",
    usageMode: "normal",
    visibility: "restricted",
    attributes: { 登录方式: "密码 + MFA", 账号角色: "master", 登录标识: "ds-admin•••" },
    relations: [
      { kind: "managed_by", label: "管理 2 个 API 密钥" },
      { kind: "part_of", label: "归属于：AI 能力服务" },
    ],
  },
  {
    id: "res-mailbox-ops",
    code: "RES-0002",
    name: "运营中心企业邮箱",
    type: "mailbox_account",
    provider: "企业邮箱",
    purpose: "业务通知、平台注册与找回",
    department: "运营中心",
    owner: "林晓",
    people: [
      { personId: "person-linxiao", personName: "林晓", role: "owner" },
      { personId: "person-wangqiang", personName: "王强", role: "user" },
    ],
    lifecycle: "in_use",
    verification: "verified",
    usageMode: "normal",
    visibility: "department",
    credentialState: "saved",
    attributes: { 邮箱地址: "ops•••@example.com", 入口: "https://mail.example.com" },
    relations: [{ kind: "uses", label: "被 4 个账号作为找回邮箱" }],
  },
  {
    id: "res-test1-key",
    code: "RES-0003",
    name: "test1_key",
    type: "api_key",
    provider: "DeepSeek",
    purpose: "待补充",
    department: "技术中心",
    owner: "待补充",
    people: [{ personId: "person-wangqiang", personName: "王强", role: "maintainer" }],
    lifecycle: "unknown",
    verification: "needs_review",
    usageMode: "test",
    visibility: "restricted",
    credentialState: "saved",
    attributes: { "Key 标识": "ds-key-••••-test1", 凭据状态: "已受保护保存" },
    relations: [
      { kind: "managed_by", label: "由 DeepSeek 公司账号管理", targetId: "res-deepseek-account" },
      { kind: "uses", label: "被钉钉生图应用使用", targetId: "res-image-app" },
    ],
  },
  {
    id: "res-chatgpt-plus",
    code: "RES-0004",
    name: "ChatGPT Plus",
    type: "service_subscription",
    provider: "OpenAI",
    purpose: "团队日常研究与内容辅助",
    department: "产品中心",
    owner: "周宁",
    people: [{ personId: "person-zhouning", personName: "周宁", role: "user" }],
    lifecycle: "in_use",
    verification: "verified",
    usageMode: "normal",
    visibility: "department",
    attributes: { 套餐: "Plus", 续费日: "每月 12 日", 计费状态: "按月" },
    relations: [{ kind: "uses", label: "由 3 位成员使用" }],
  },
  {
    id: "res-jd-shop",
    code: "RES-0005",
    name: "京东旗舰店",
    type: "business_space",
    provider: "京东",
    purpose: "品牌商品在线经营",
    department: "电商中心",
    owner: "赵敏",
    people: [{ personId: "person-zhaomin", personName: "赵敏", role: "owner" }],
    lifecycle: "in_use",
    verification: "verified",
    usageMode: "normal",
    visibility: "company",
    attributes: { 外部空间编号: "JD-SHOP-•••", 入口: "https://shop.jd.com", 业务范围: "旗舰店" },
    relations: [{ kind: "uses", label: "使用京东子账号登录" }],
  },
  {
    id: "res-image-app",
    code: "RES-0006",
    name: "钉钉生图应用",
    type: "application",
    provider: "钉钉",
    purpose: "内部图片生成工作流",
    department: "技术中心",
    owner: "王强",
    people: [{ personId: "person-wangqiang", personName: "王强", role: "owner" }],
    lifecycle: "in_use",
    verification: "needs_review",
    usageMode: "test",
    visibility: "restricted",
    attributes: { 入口: "钉钉工作台", 技术栈: "Webhook + API", 部署说明: "待补充" },
    relations: [{ kind: "uses", label: "使用 test1_key", targetId: "res-test1-key" }],
  },
];

export const changeItems: ChangeItem[] = [
  {
    id: "change-001",
    resource: "test1_key",
    action: "Key 替换",
    current: "现有 Key 保持有效",
    proposed: "登记新 Key，并逐项核实应用配置",
    executor: "王强",
    status: "待执行",
    reason: "测试 Key 的负责人和用途待确认",
  },
  {
    id: "change-002",
    resource: "运营中心企业邮箱",
    action: "补充负责人",
    current: "负责人：林晓",
    proposed: "待确认接任人",
    executor: "人事协同",
    status: "待确认",
    reason: "离职交接盘点事项",
  },
];
