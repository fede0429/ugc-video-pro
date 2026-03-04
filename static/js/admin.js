/**
 * js/admin.js
 * Admin panel logic: user management + invite code management
 * Requires: api.js, dashboard.js (for showToast)
 */

const Admin = (() => {
  'use strict';

  function toast(type, title, msg) {
    if (window.Dashboard && Dashboard.showToast) {
      Dashboard.showToast(type, title, msg);
    }
  }

  function escapeHtml(str) {
    if (str == null) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function formatDate(isoString) {
    if (!isoString) return '—';
    const d = new Date(isoString);
    return d.toLocaleString('zh-CN', {
      year: 'numeric', month: '2-digit', day: '2-digit',
    });
  }

  // ── User Management ─────────────────────────────────────────────

  let _users = [];

  async function loadUsers() {
    const loadingEl = document.getElementById('usersLoading');
    const tableEl   = document.getElementById('usersTable');
    const tbody     = document.getElementById('usersTableBody');

    if (loadingEl) loadingEl.style.display = 'block';
    if (tableEl)   tableEl.style.display   = 'none';

    try {
      const data = await API.getUsers();
      _users = Array.isArray(data) ? data : (data.users || []);

      if (loadingEl) loadingEl.style.display = 'none';
      if (tableEl)   tableEl.style.display   = 'block';
      if (tbody)     renderUsersTable(tbody);

    } catch (err) {
      if (loadingEl) loadingEl.style.display = 'none';
      toast('error', '加载用户失败', err.message);
    }
  }

  function renderUsersTable(tbody) {
    tbody.innerHTML = '';

    if (_users.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="6" style="text-align:center;padding:var(--sp-8);color:var(--text-muted);">
            暂无用户数据
          </td>
        </tr>
      `;
      return;
    }

    _users.forEach(user => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${escapeHtml(user.email)}</td>
        <td>${escapeHtml(user.display_name || '—')}</td>
        <td>
          <span class="badge ${user.role === 'admin' ? 'badge-admin' : 'badge-user'}">
            ${user.role === 'admin' ? '管理员' : '普通用户'}
          </span>
        </td>
        <td>
          <span class="badge ${user.is_active ? 'badge-completed' : 'badge-failed'}">
            ${user.is_active ? '已激活' : '已停用'}
          </span>
        </td>
        <td style="white-space:nowrap">${formatDate(user.created_at)}</td>
        <td>
          <div class="table-actions">
            <button class="btn btn-secondary btn-sm" onclick="Admin.openEditUser('${user.id}')">
              编辑
            </button>
            <button class="btn btn-danger btn-sm" onclick="Admin.confirmDeactivate('${user.id}', ${user.is_active})">
              ${user.is_active ? '停用' : '启用'}
            </button>
          </div>
        </td>
      `;
      tbody.appendChild(tr);
    });
  }

  function openEditUser(userId) {
    const user = _users.find(u => String(u.id) === String(userId));
    if (!user) return;

    document.getElementById('editUserId').value    = user.id;
    document.getElementById('editUserEmail').value  = user.email || '';
    document.getElementById('editUserRole').value   = user.role  || 'user';
    document.getElementById('editUserActive').value = String(user.is_active !== false);

    const modal = document.getElementById('editUserModal');
    if (modal) modal.classList.add('open');
  }

  function initEditUserModal() {
    const modal     = document.getElementById('editUserModal');
    const closeBtn  = document.getElementById('editUserModalClose');
    const cancelBtn = document.getElementById('editUserCancel');
    const saveBtn   = document.getElementById('editUserSave');

    if (!modal) return;

    function closeModal() { modal.classList.remove('open'); }

    closeBtn?.addEventListener('click', closeModal);
    cancelBtn?.addEventListener('click', closeModal);

    modal.addEventListener('click', (e) => {
      if (e.target === modal) closeModal();
    });

    saveBtn?.addEventListener('click', async () => {
      const id       = document.getElementById('editUserId').value;
      const role     = document.getElementById('editUserRole').value;
      const isActive = document.getElementById('editUserActive').value === 'true';

      saveBtn.disabled = true;
      try {
        await API.updateUser(id, { role, is_active: isActive });
        toast('success', '用户已更新', '');
        closeModal();
        loadUsers();
      } catch (err) {
        toast('error', '更新失败', err.message);
      } finally {
        saveBtn.disabled = false;
      }
    });
  }

  function confirmDeactivate(userId, isActive) {
    const action = isActive ? '停用' : '启用';
    if (!confirm(`确认${action}该用户？`)) return;
    toggleUserActive(userId, !isActive);
  }

  async function toggleUserActive(userId, newState) {
    try {
      await API.updateUser(userId, { is_active: newState });
      toast('success', newState ? '用户已启用' : '用户已停用', '');
      loadUsers();
    } catch (err) {
      toast('error', '操作失败', err.message);
    }
  }

  function initCreateUser() {
    const btn = document.getElementById('createUserBtn');
    if (!btn) return;

    btn.addEventListener('click', () => {
      // Simple prompt-based creation (could be a modal in a full app)
      const email = prompt('新用户邮筱：');
      if (!email) return;
      const name  = prompt('显示名称：') || email.split('@')[0];
      const pwd   = prompt('初始密码（至少8位）：');
      if (!pwd || pwd.length < 8) {
        toast('warning', '密码太短', '至少需要8位');
        return;
      }

      API.createUser({ email, display_name: name, password: pwd, role: 'user' })
        .then(() => {
          toast('success', '用户已创建', email);
          loadUsers();
        })
        .catch(err => {
          toast('error', '创建失败', err.message);
        });
    });
  }

  // ── Invite Code Management ─────────────────────────────────────────

  let _inviteCodes = [];

  async function loadInviteCodes() {
    const loadingEl = document.getElementById('inviteCodesLoading');
    const listEl    = document.getElementById('inviteCodesList');

    if (loadingEl) loadingEl.style.display = 'block';
    if (listEl)    listEl.innerHTML = '';

    try {
      const data = await API.getInviteCodes();
      _inviteCodes = Array.isArray(data) ? data : (data.codes || data.invite_codes || []);

      if (loadingEl) loadingEl.style.display = 'none';
      renderInviteCodes();

    } catch (err) {
      if (loadingEl) loadingEl.style.display = 'none';
      toast('error', '加载邀请码失败', err.message);
    }
  }

  function renderInviteCodes() {
    const listEl = document.getElementById('inviteCodesList');
    if (!listEl) return;
    listEl.innerHTML = '';

    if (_inviteCodes.length === 0) {
      listEl.innerHTML = `
        <div class="empty-state" style="padding:var(--sp-8);">
          <div class="empty-icon">🎫</div>
          <div class="empty-title">还没有邀请码</div>
          <div class="empty-desc">点击上方「生成」按鈕创建邀请码</div>
        </div>
      `;
      return;
    }

    _inviteCodes.forEach(code => {
      const item = document.createElement('div');
      item.className = 'invite-code-item';

      const isUsed = !!code.used_by || !code.is_active;
      const statusBadge = isUsed
        ? `<span class="badge badge-failed">已使用</span>`
        : `<span class="badge badge-completed">未使用</span>`;

      const expiresText = code.expires_at
        ? `到期: ${formatDate(code.expires_at)}`
        : '永久有效';

      item.innerHTML = `
        <div class="invite-code-value">${escapeHtml(code.code)}</div>
        <div style="font-family:var(--font-sans);font-size:var(--text-xs);color:var(--text-muted);">${expiresText}</div>
        <div class="invite-code-status">${statusBadge}</div>
        <div class="invite-code-copy" onclick="Admin.copyCode('${escapeHtml(code.code)}')" title="复制邀请码">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><rect x="4" y="4" width="8" height="8" rx="1" stroke="currentColor" stroke-width="1.2"/><path d="M2 10V3a1 1 0 011-1h7" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/></svg>
          复制
        </div>
      `;
      listEl.appendChild(item);
    });
  }

  function copyCode(code) {
    if (navigator.clipboard) {
      navigator.clipboard.writeText(code).then(() => {
        toast('success', '已复制', code);
      });
    } else {
      // Fallback
      const ta = document.createElement('textarea');
      ta.value = code;
      ta.style.position = 'fixed';
      ta.style.opacity  = '0';
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
      toast('success', '已复制', code);
    }
  }

  function initGenerateCodes() {
    const btn = document.getElementById('generateCodesBtn');
    if (!btn) return;

    btn.addEventListener('click', async () => {
      const countEl = document.getElementById('inviteCount');
      const count   = parseInt(countEl?.value || '1', 10);

      if (!count || count < 1 || count > 50) {
        toast('warning', '数量无效', '请输入 1-50 之间的数字');
        return;
      }

      btn.disabled = true;
      btn.textContent = '生成中...';

      try {
        const data = await API.generateInviteCodes(count);
        toast('success', `已生成 ${count} 个邀请码`, '');
        loadInviteCodes();
      } catch (err) {
        toast('error', '生成失败', err.message);
      } finally {
        btn.disabled   = false;
        btn.textContent = '生成';
      }
    });
  }

  // ── Init ───────────────────────────────────────────────────────────────────

  function init() {
    initEditUserModal();
    initCreateUser();
    initGenerateCodes();
  }

  // Call init once DOM is ready (deferred from dashboard.js)
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // ── Public ────────────────────────────────────────────────────────────────

  return {
    loadUsers,
    loadInviteCodes,
    openEditUser,
    confirmDeactivate,
    copyCode,
  };
})();

window.Admin = Admin;
