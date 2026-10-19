import { ref, watch } from "vue";
import {
  changeItems,
  resources as seedResources,
  type ChangeItem,
  type Resource,
  type ResourcePerson,
} from "../../data";

const RESOURCE_STORAGE_KEY = "digital-asset-platform-demo-resources";
const CHANGE_STORAGE_KEY = "digital-asset-platform-demo-changes";
const DEMO_USER_ID = "person-wangqiang";

function cloneSeedResources(): Resource[] {
  return seedResources.map((resource) => ({
    ...resource,
    relations: [...resource.relations],
    people: [...(resource.people ?? [])],
    attributes: { ...resource.attributes },
  }));
}

function loadDemoValue<T>(key: string, fallback: T): T {
  try {
    const saved = window.localStorage.getItem(key);
    return saved ? (JSON.parse(saved) as T) : fallback;
  } catch {
    return fallback;
  }
}

function saveDemoValue(key: string, value: unknown): void {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Keep the current interaction usable when browser storage is unavailable.
  }
}

export function personIdForDemoName(name: string): string {
  if (name === "王强") return DEMO_USER_ID;
  return `person-${name.trim().toLowerCase().replace(/[^a-z0-9\u4e00-\u9fa5]+/g, "-")}`;
}

export function useDemoWorkspace() {
  const resources = ref<Resource[]>(loadDemoValue(RESOURCE_STORAGE_KEY, cloneSeedResources()));
  const changes = ref<ChangeItem[]>(loadDemoValue(CHANGE_STORAGE_KEY, [...changeItems]));

  watch(resources, (value) => saveDemoValue(RESOURCE_STORAGE_KEY, value), { deep: true });
  watch(changes, (value) => saveDemoValue(CHANGE_STORAGE_KEY, value), { deep: true });

  function hasCurrentUserRelationship(resource: Resource): boolean {
    return resource.people?.some((person) => person.personId === DEMO_USER_ID) ?? false;
  }

  function createResource(input: Omit<Resource, "id" | "code">): Resource {
    const resource: Resource = {
      ...input,
      id: `res-${Date.now()}`,
      code: `RES-${String(resources.value.length + 1).padStart(4, "0")}`,
    };
    resources.value.unshift(resource);
    return resource;
  }

  function updateResource(resourceId: string, changes: Pick<Resource, "name" | "provider" | "purpose" | "department" | "attributes">): Resource | null {
    const resource = resources.value.find((item) => item.id === resourceId);
    if (!resource) return null;
    Object.assign(resource, changes);
    return resource;
  }

  function createOwnerChange(resourceId: string, proposedOwner: string, reason: string): void {
    const resource = resources.value.find((item) => item.id === resourceId);
    if (!resource) return;
    const normalizedOwner = proposedOwner.trim();
    changes.value.unshift({
      id: `change-${Date.now()}`,
      resourceId: resource.id,
      resource: resource.name,
      action: "负责人变更",
      current: `负责人：${resource.owner}`,
      proposed: `拟议负责人：${normalizedOwner}`,
      executor: "待指定",
      status: "待执行",
      reason: reason.trim() || "负责人交接",
      proposedOwner: normalizedOwner,
    });
  }

  function advanceChange(change: ChangeItem): string | null {
    if (change.status === "待执行") {
      change.status = "执行中";
      return "事项已开始处理";
    }
    if (change.status === "执行中") {
      change.status = "待确认";
      return "事项已提交核实";
    }
    if (change.status !== "待确认") return null;

    if (change.action === "负责人变更" && change.proposedOwner && change.resourceId) {
      const resource = resources.value.find((item) => item.id === change.resourceId);
      if (resource) {
        const people = resource.people ?? [];
        const withoutOldOwner = people.filter((person) => person.role !== "owner");
        const newOwner = change.proposedOwner;
        const existing = withoutOldOwner.find((person) => person.personName === newOwner && person.role === "maintainer");
        const nextOwner: ResourcePerson = existing
          ? { ...existing, role: "owner" }
          : { personId: personIdForDemoName(newOwner), personName: newOwner, role: "owner" };
        resource.people = [...withoutOldOwner, nextOwner];
        resource.owner = newOwner;
      }
    }
    change.status = "已完成";
    return "事项已确认完成，当前资源事实已更新";
  }

  function restoreSeedData(): void {
    resources.value = cloneSeedResources();
    changes.value = [...changeItems];
  }

  return { resources, changes, hasCurrentUserRelationship, createResource, updateResource, createOwnerChange, advanceChange, restoreSeedData };
}
