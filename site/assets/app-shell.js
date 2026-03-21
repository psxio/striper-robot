export const $ = (id) => document.getElementById(id);

export function getToken() {
  return localStorage.getItem("strype_token");
}

export function setToken(token) {
  localStorage.setItem("strype_token", token);
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

/** Read a cookie value by name. */
function getCookie(name) {
  const match = document.cookie.match(new RegExp("(?:^|;\\s*)" + name + "=([^;]*)"));
  return match ? decodeURIComponent(match[1]) : null;
}

/** Attempt a silent token refresh using the httpOnly refresh-token cookie.
 *  Returns true if a new access token was stored successfully. */
async function tryRefresh() {
  try {
    const csrfToken = getCookie("csrf_token");
    const resp = await fetch("/api/auth/refresh", {
      method: "POST",
      credentials: "include",
      headers: csrfToken ? { "X-CSRF-Token": csrfToken } : {},
    });
    if (!resp.ok) return false;
    const data = await resp.json();
    if (data.token) {
      setToken(data.token);
      return true;
    }
  } catch (_) {
    // Network error or JSON parse failure
  }
  return false;
}

/** @type {Promise<boolean>|null} — in-flight refresh deduplicate */
let _refreshPromise = null;

export async function apiFetch(path, options = {}) {
  const token = getToken();
  if (!token) {
    redirectToPlatform();
    return null;
  }

  const buildHeaders = (currentToken) => {
    const headers = new Headers(options.headers || {});
    headers.set("Authorization", `Bearer ${currentToken}`);
    if (options.orgId) {
      headers.set("X-Organization-ID", options.orgId);
    }
    if (options.body && !(options.body instanceof FormData) && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    return headers;
  };

  let resp = await fetch(path, { ...options, headers: buildHeaders(token) });

  // On 401, try a single silent token refresh then retry the original request.
  if (resp.status === 401) {
    if (!_refreshPromise) {
      _refreshPromise = tryRefresh().finally(() => { _refreshPromise = null; });
    }
    const refreshed = await _refreshPromise;
    if (refreshed) {
      const newToken = getToken();
      resp = await fetch(path, { ...options, headers: buildHeaders(newToken) });
    }
  }

  if (resp.status === 401) {
    // Refresh failed or second 401 — log out
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

/**
 * Inject an email-verification banner if the user's email is not yet verified.
 * Call this after loading the session and rendering the page. Idemponent.
 *
 * @param {object} user - The /api/auth/me response object.
 * @param {string} [containerId] - ID of a container to prepend the banner to.
 *   If omitted the banner is prepended to document.body.
 */
export function showVerificationBannerIfNeeded(user, containerId) {
  if (!user || user.email_verified) return;
  if (document.getElementById("__email-verify-banner")) return;

  const banner = document.createElement("div");
  banner.id = "__email-verify-banner";
  banner.style.cssText = [
    "background:#d29922;color:#0d1117;padding:8px 16px;font-size:13px;",
    "display:flex;align-items:center;justify-content:space-between;gap:12px;",
    "position:sticky;top:0;z-index:9999;",
  ].join("");
  banner.innerHTML = `
    <span>Please verify your email address to unlock all features.</span>
    <div style="display:flex;gap:8px;align-items:center;flex-shrink:0;">
      <button id="__resend-verify-btn" style="background:rgba(0,0,0,0.2);border:none;color:#0d1117;
        padding:4px 12px;border-radius:4px;cursor:pointer;font-size:12px;font-weight:600;">
        Resend email
      </button>
      <button onclick="this.closest('#__email-verify-banner').remove()"
        style="background:none;border:none;font-size:18px;cursor:pointer;line-height:1;color:#0d1117;">×</button>
    </div>
  `;

  const container = containerId ? document.getElementById(containerId) : document.body;
  if (container) container.prepend(banner);

  document.getElementById("__resend-verify-btn")?.addEventListener("click", async (e) => {
    const btn = e.currentTarget;
    btn.disabled = true;
    btn.textContent = "Sending…";
    try {
      await apiFetch("/api/auth/resend-verification", { method: "POST" });
      btn.textContent = "Sent!";
    } catch (_) {
      btn.textContent = "Failed—try again";
      btn.disabled = false;
    }
  });
}

  link.click();
  link.remove();
  URL.revokeObjectURL(objectUrl);
}
