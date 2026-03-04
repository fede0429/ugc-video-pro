/**
 * js/api.js
 * API client for UGC Video Pro
 * Handles JWT auth, token refresh, and all HTTP calls to the backend.
 */

const API = (() => {
  'use strict';

  const BASE_URL = '';  // Same-origin
  const TOKEN_KEY  = 'ugcvp_access_token';
  const REFRESH_KEY = 'ugcvp_refresh_token';

  // ── Token Management ──────────────────────────────────────────

  function getToken()    { return localStorage.getItem(TOKEN_KEY); }
  function setToken(t)   { localStorage.setItem(TOKEN_KEY, t); }
  function removeToken() { localStorage.removeItem(TOKEN_KEY); }

  function getRefreshToken()    { return localStorage.getItem(REFRESH_KEY); }
  function setRefreshToken(t)   { localStorage.setItem(REFRESH_KEY, t); }
  function removeRefreshToken() { localStorage.removeItem(REFRESH_KEY); }

  function clearAuth() {
    removeToken();
    removeRefreshToken();
  }

  function isAuthenticated() {
    return !!getToken();
  }

  // ── JWT Decode (no library needed) ────────────────────────────

  function decodeToken(token) {
    try {
      const payload = token.split('.')[1];
      const decoded = atob(payload.replace(/-/g, '+').replace(/_/g, '/'));
      return JSON.parse(decoded);
    } catch {
      return null;
    }
  }

  function isTokenExpired(token) {
    const decoded = decodeToken(token);
    if (!decoded || !decoded.exp) return true;
    return decoded.exp * 1000 < Date.now() + 30000; // 30s buffer
  }

  // ── Token Refresh ─────────────────────────────────────────────

  let _refreshPromise = null;

  async function refreshAccessToken() {
    if (_refreshPromise) return _refreshPromise;

    _refreshPromise = (async () => {
      const refreshToken = getRefreshToken();
      if (!refreshToken) throw new Error('No refresh token');

      const res = await fetch(`${BASE_URL}/api/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });

      if (!res.ok) {
        clearAuth();
        throw new Error('Refresh failed');
      }

      const data = await res.json();
      setToken(data.access_token);
      if (data.refresh_token) setRefreshToken(data.refresh_token);
      return data.access_token;
    })().finally(() => { _refreshPromise = null; });

    return _refreshPromise;
  }

  // ── Core Fetch Wrapper ─────────────────────────────────────────

  async function apiFetch(url, options = {}) {
    let token = getToken();

    // Auto-refresh if expired
    if (token && isTokenExpired(token)) {
      try {
        token = await refreshAccessToken();
      } catch {
        clearAuth();
        window.location.href = 'login.html';
        return;
      }
    }

    const headers = {
      ...(options.headers || {}),
    };

    // Don't set Content-Type for FormData (browser sets it with boundary)
    if (!(options.body instanceof FormData)) {
      if (!headers['Content-Type']) {
        headers['Content-Type'] = 'application/json';
      }
    }

    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`${BASE_URL}${url}`, {
      ...options,
      headers,
    });

    // Handle 401 — try refresh once
    if (response.status === 401 && token) {
      try {
        const newToken = await refreshAccessToken();
        headers['Authorization'] = `Bearer ${newToken}`;
        const retryRes = await fetch(`${BASE_URL}${url}`, {
          ...options,
          headers,
        });
        if (retryRes.status === 401) {
          clearAuth();
          window.location.href = 'login.html';
          return;
        }
        return parseResponse(retryRes);
      } catch {
        clearAuth();
        window.location.href = 'login.html';
        return;
      }
    }

    return parseResponse(response);
  }

  async function parseResponse(response) {
    const contentType = response.headers.get('content-type') || '';

    if (!response.ok) {
      let errorMsg = `HTTP ${response.status}`;
      if (contentType.includes('application/json')) {
        const err = await response.json().catch(() => ({}));
        errorMsg = err.detail || err.message || errorMsg;
      }
      const error = new Error(errorMsg);
      error.status = response.status;
      throw error;
    }

    if (response.status === 204) return null;  // No content

    if (contentType.includes('application/json')) {
      return response.json();
    }

    // For file downloads, return the response itself
    return response;
  }

  // ── Auth Endpoints ────────────────────────────────────────────

  async function login(email, password) {
    const data = await apiFetch('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    if (data) {
      setToken(data.access_token);
      if (data.refresh_token) setRefreshToken(data.refresh_token);
    }
    return data;
  }

  async function register(email, displayName, password, inviteCode) {
    return apiFetch('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify({
        email,
        display_name: displayName,
        password,
        invite_code: inviteCode,
      }),
    });
  }

  async function getMe() {
    return apiFetch('/api/auth/me');
  }

  async function changePassword(currentPassword, newPassword) {
    return apiFetch('/api/auth/password', {
      method: 'PUT',
      body: JSON.stringify({
        current_password: currentPassword,
        new_password: newPassword,
      }),
    });
  }

  function logout() {
    clearAuth();
    window.location.href = 'login.html';
  }

  // ── Video Endpoints ───────────────────────────────────────────

  async function generateVideo(formData) {
    // formData is a FormData object (multipart)
    return apiFetch('/api/video/generate', {
      method: 'POST',
      body: formData,
      // Don't set Content-Type — browser sets multipart/form-data + boundary
    });
  }

  async function getVideoTasks(page = 1, limit = 20) {
    return apiFetch(`/api/video/tasks?page=${page}&limit=${limit}`);
  }

  async function getVideoTask(id) {
    return apiFetch(`/api/video/tasks/${id}`);
  }

  async function downloadVideo(id) {
    const response = await apiFetch(`/api/video/download/${id}`);
    return response; // Raw Response object for blob download
  }

  async function deleteVideoTask(id) {
    return apiFetch(`/api/video/tasks/${id}`, { method: 'DELETE' });
  }

  // ── Admin Endpoints ───────────────────────────────────────────

  async function getUsers() {
    return apiFetch('/api/admin/users');
  }

  async function createUser(data) {
    return apiFetch('/api/admin/users', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async function updateUser(id, data) {
    return apiFetch(`/api/admin/users/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async function deleteUser(id) {
    return apiFetch(`/api/admin/users/${id}`, { method: 'DELETE' });
  }

  async function generateInviteCodes(count) {
    return apiFetch('/api/admin/invite-codes', {
      method: 'POST',
      body: JSON.stringify({ count }),
    });
  }

  async function getInviteCodes() {
    return apiFetch('/api/admin/invite-codes');
  }

  // ── WebSocket Helper ───────────────────────────────────────────

  function createProgressWebSocket(taskId, callbacks = {}) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const token = getToken();
    const url = `${protocol}//${host}/api/ws/progress/${taskId}?token=${encodeURIComponent(token || '')}`;

    let ws = null;
    let reconnectTimer = null;
    let reconnectCount = 0;
    const MAX_RECONNECTS = 5;
    let closed = false;

    function connect() {
      ws = new WebSocket(url);

      ws.onopen = () => {
        reconnectCount = 0;
        if (callbacks.onOpen) callbacks.onOpen();
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (callbacks.onMessage) callbacks.onMessage(data);
        } catch {
          // ignore malformed messages
        }
      };

      ws.onerror = (error) => {
        if (callbacks.onError) callbacks.onError(error);
      };

      ws.onclose = (event) => {
        if (closed) return;
        if (callbacks.onClose) callbacks.onClose(event);

        // Reconnect on unexpected close
        if (!event.wasClean && reconnectCount < MAX_RECONNECTS) {
          reconnectCount++;
          const delay = Math.min(1000 * Math.pow(1.5, reconnectCount), 10000);
          reconnectTimer = setTimeout(connect, delay);
        }
      };
    }

    connect();

    return {
      close() {
        closed = true;
        clearTimeout(reconnectTimer);
        if (ws) ws.close(1000, 'done');
      },
      send(data) {
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify(data));
        }
      },
    };
  }

  // ── Public API ──────────────────────────────────────────────

  return {
    // Auth state
    getToken,
    setToken,
    removeToken,
    getRefreshToken,
    setRefreshToken,
    clearAuth,
    isAuthenticated,
    decodeToken,

    // Auth endpoints
    login,
    register,
    getMe,
    changePassword,
    logout,

    // Video endpoints
    generateVideo,
    getVideoTasks,
    getVideoTask,
    downloadVideo,
    deleteVideoTask,

    // Admin endpoints
    getUsers,
    createUser,
    updateUser,
    deleteUser,
    generateInviteCodes,
    getInviteCodes,

    // WebSocket
    createProgressWebSocket,

    // Low-level
    apiFetch,
  };
})();

// Make globally available
window.API = API;
