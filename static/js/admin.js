/**
 * Admin panel logic: user management + invite code management
 * Requires: api.js
 */
const Admin = (() => {
  'use strict';

  function toast(type, title, msg) {
    const host = document.getElementById('adminToastHost');
    const text = [title, msg].filter(Boolean).join(' — ');
    if (!host) { alert(text); return; }
    const div = document.createElement('div');
    div.className = 'toast';
    const colors = {
      success: 'rgba(34,197,94,.25)',
      error: 'rgba(239,68,68,.25)',
      warning: 'rgba(245,158,11,.25)',
      info: 'rgba(59,130,246,.25)',
    };
    div.style.borderColor = colors[type] || 'rgba(255,255,255,.08)';
    div.textContent = text;
    host.appendChild(div);
    setTimeout(() => div.remove(), 2800);
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
      hour: '2-digit', minute: '2-digit'
    });
  }

  let _users = [];
  let _inviteCodes = [];

  async function loadUsers() {
    const loadingEl = document.getElementById('usersLoading');
    const tableEl   = document.getElementById('usersTable');
    const tbody     = document.getElementById('usersTableBody');

    if (loadingEl) loadingEl.style.display = 'block';
    if (tableEl) tableEl.style.display = 'none';

    try {
      const data = await API.getUsers();
      _users = Array.isArray(data) ? data : (data.users || []);
      if (tbody) renderUsersTable(tbody);
      updateSummary();
      if (loadingEl) loadingEl.style.display = 'none';
      if (tableEl) tableEl.style.display = '';
    } catch (err) {
      if (loadingEl) loadingEl.style.display = 'none';
      toast('error', '加载用户失败', err.message);
    }
  }

  
function updateSummary() {
  const total = _users.length;
  const active = _users.filter(u => u.is_active).length;
  const admins = _users.filter(u => u.role === 'admin').length;
  const invites = _inviteCodes.length;
  document.getElementById('summary-users') && (document.getElementById('summary-users').textContent = total);
  document.getElementById('summary-active') && (document.getElementById('summary-active').textContent = active);
  document.getElementById('summary-admins') && (document.getElementById('summary-admins').textContent = admins);
  document.getElementById('summary-invites') && (document.getElementById('summary-invites').textContent = invites);
}

function renderUsersTable(tbody) {

    tbody.innerHTML = '';
    if (_users.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5"><div class="empty">暂无用户数据</div></td></tr>';
      return;
    }

    _users.forEach((user) => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>
          <strong>${escapeHtml(user.display_name || '未命名')}</strong><br>
          <span class="helper">${escapeHtml(user.email)}</span>
        </td>
        <td><span class="tag ${user.role === 'admin' ? 'admin' : 'user'}">${escapeHtml(user.role)}</span></td>
        <td><span class="tag ${user.is_active ? 'user' : 'off'}">${user.is_active ? '启用' : '停用'}</span></td>
        <td>${formatDate(user.created_at)}</td>
        <td>
          <div class="btns">
            <button class="mini-btn" data-action="edit" data-id="${user.id}">编辑</button>
            ${user.is_active ? `<button class="mini-btn danger" data-action="deactivate" data-id="${user.id}">删除 / 停用</button>` : ''}
          </div>
        </td>
      `;
      tbody.appendChild(tr);
    });

    tbody.querySelectorAll('[data-action="edit"]').forEach((btn) => {
      btn.addEventListener('click', () => openEditUser(btn.dataset.id));
    });
    tbody.querySelectorAll('[data-action="deactivate"]').forEach((btn) => {
      btn.addEventListener('click', () => confirmDeactivate(btn.dataset.id));
    });
  }

  function openEditUser(userId) {
    const user = _users.find((u) => u.id === userId);
    if (!user) return;
    const modal = document.getElementById('editUserModal');
    document.getElementById('editUserId').value = user.id;
    document.getElementById('editUserEmail').value = user.email;
    document.getElementById('editUserRole').value = user.role;
    document.getElementById('editUserActive').value = user.is_active ? 'true' : 'false';
    modal?.classList.add('open');
  }

  function confirmDeactivate(userId) {
    const user = _users.find((u) => u.id === userId);
    if (!user) return;
    if (!window.confirm(`确认停用账户 ${user.email} 吗？停用后该账号将无法继续登录。`)) return;
    API.deleteUser(userId)
      .then(() => {
        toast('success', '账户已停用', user.email);
        loadUsers();
      })
      .catch((err) => toast('error', '停用失败', err.message));
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
    modal.addEventListener('click', (e) => { if (e.target === modal) closeModal(); });

    saveBtn?.addEventListener('click', async () => {
      const id       = document.getElementById('editUserId').value;
      const role     = document.getElementById('editUserRole').value;
      const isActive = document.getElementById('editUserActive').value === 'true';
      saveBtn.disabled = true;
      try {
        await API.updateUser(id, { role, is_active: isActive });
        toast('success', '账户已更新', '');
        closeModal();
        loadUsers();
      } catch (err) {
        toast('error', '更新失败', err.message);
      } finally {
        saveBtn.disabled = false;
      }
    });
  }

  function initCreateUser() {
    const btn = document.getElementById('createUserBtn');
    if (!btn) return;
    btn.addEventListener('click', async () => {
      const email = document.getElementById('admin-create-email')?.value.trim();
      const name = document.getElementById('admin-create-name')?.value.trim() || (email || '').split('@')[0];
      const password = document.getElementById('admin-create-password')?.value || '';
      const role = document.getElementById('admin-create-role')?.value || 'user';
      if (!email) { toast('warning', '请输入邮箱', ''); return; }
      if (password.length < 8) { toast('warning', '密码太短', '至少需要 8 位'); return; }

      btn.disabled = true;
      try {
        await API.createUser({ email, display_name: name, password, role });
        toast('success', '子账户已创建', email);
        ['admin-create-email','admin-create-name','admin-create-password'].forEach((id) => {
          const el = document.getElementById(id); if (el) el.value = '';
        });
        loadUsers();
      } catch (err) {
        toast('error', '创建失败', err.message);
      } finally {
        btn.disabled = false;
      }
    });
  }

  async function loadInviteCodes() {
    const loadingEl = document.getElementById('inviteCodesLoading');
    const listEl    = document.getElementById('inviteCodesList');
    if (loadingEl) loadingEl.style.display = 'block';
    if (listEl) listEl.innerHTML = '';

    try {
      const data = await API.getInviteCodes();
      _inviteCodes = Array.isArray(data) ? data : (data.codes || []);
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
      listEl.innerHTML = '<div class="empty">暂无邀请码</div>';
      return;
    }
    _inviteCodes.forEach((code) => {
      const item = document.createElement('div');
      item.className = 'code-card';
      item.innerHTML = `
        <div style="display:flex;justify-content:space-between;gap:10px;align-items:center">
          <div>
            <strong>${escapeHtml(code.code)}</strong>
            <div class="helper">创建时间：${formatDate(code.created_at)}</div>
            <div class="helper">状态：${code.is_active ? '可用' : '失效'}${code.used_by ? ` · 已使用` : ''}</div>
          </div>
          <button class="mini-btn" type="button">复制</button>
        </div>
      `;
      item.querySelector('button')?.addEventListener('click', () => copyCode(code.code));
      listEl.appendChild(item);
    });
  }

  function copyCode(code) {
    navigator.clipboard?.writeText(code)
      .then(() => toast('success', '已复制邀请码', code))
      .catch(() => {
        const ta = document.createElement('textarea');
        ta.value = code;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
        toast('success', '已复制邀请码', code);
      });
  }

  function initGenerateCodes() {
    const btn = document.getElementById('generateCodesBtn');
    if (!btn) return;
    btn.addEventListener('click', async () => {
      const count = parseInt(document.getElementById('inviteCount')?.value || '1', 10);
      if (!count || count < 1 || count > 50) {
        toast('warning', '数量无效', '请输入 1-50 之间的数字');
        return;
      }
      btn.disabled = true;
      try {
        await API.generateInviteCodes(count);
        toast('success', `已生成 ${count} 个邀请码`, '');
        loadInviteCodes();
      } catch (err) {
        toast('error', '生成失败', err.message);
      } finally {
        btn.disabled = false;
      }
    });
  }

  function init() {
    initEditUserModal();
    initCreateUser();
    initGenerateCodes();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();

  return {
    loadUsers,
    loadInviteCodes,
    openEditUser,
    confirmDeactivate,
    copyCode,
  };
})();
window.Admin = Admin;
