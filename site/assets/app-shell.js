export const $ = (id) => document.getElementById(id);

export function getToken() {
  return localStorage.getItem("strype_token");
}

export function redirectToPlatform() {
  window.location.href = "platform.html";
}

export function createFlash(flashId = "flash") {
  return function flash(message) {
    const el = $(flashId);
    if (!el) return;
    el.textContent = message;
    el.classList.add("show");
    clearTimeout(flash._timer);
    flash._timer = setTimeout(() => el.classList.remove("show"), 2600);
  };
}

export function optionMarkup(items, valueKey, labelFn, emptyLabel) {
  return [
    `<option value="">${emptyLabel}</option>`,
    ...items.map((item) => `<option value="${item[valueKey]}">${labelFn(item)}</option>`),
  ].join("");
}

export function syncOrgSelect(selectEl, orgs, activeId) {
  if (!selectEl) return "";
  selectEl.innerHTML = optionMarkup(orgs, "id", (org) => `${org.name} (${org.role})`, "Select workspace");
  selectEl.value = activeId || orgs[0]?.id || "";
  return selectEl.value;
}

export async function apiFetch(path, options = {}) {
  const token = getToken();
  if (!token) {
    redirectToPlatform();
    return null;
  }

  const headers = new Headers(options.headers || {});
  headers.set("Authorization", `Bearer ${token}`);
  if (options.orgId) {
    headers.set("X-Organization-ID", options.orgId);
  }
  if (options.body && !(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const resp = await fetch(path, { ...options, headers });
  if (resp.status === 401) {
    localStorage.removeItem("strype_token");
    localStorage.removeItem("strype_user");
    redirectToPlatform();
    return null;
  }
  if (!resp.ok) {
    const data = await resp.json().catch(() => ({}));
    throw new Error(data.detail || "Request failed");
  }

  const type = resp.headers.get("content-type") || "";
  if (type.includes("application/json")) return resp.json();
  if (type.includes("application/pdf")) return resp.blob();
  return resp.text();
}

export async function loadSession(orgId = "") {
  const me = await apiFetch("/api/auth/me", { orgId });
  const orgResponse = await apiFetch("/api/organizations", { orgId });
  const orgs = orgResponse?.items || [];
  return { me, orgs };
}

export async function setActiveOrganization(organizationId) {
  return apiFetch("/api/organizations/active", {
    method: "POST",
    body: JSON.stringify({ organization_id: organizationId }),
    orgId: organizationId,
  });
}

export async function authenticatedDownload(url, filename, orgId = "") {
  const token = getToken();
  if (!token) {
    redirectToPlatform();
    return;
  }
  const headers = { Authorization: `Bearer ${token}` };
  if (orgId) headers["X-Organization-ID"] = orgId;
  const resp = await fetch(url, { headers });
  if (!resp.ok) throw new Error("Download failed");
  const blob = await resp.blob();
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(objectUrl);
}
