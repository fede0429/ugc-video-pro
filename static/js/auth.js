/**
 * js/auth.js
 * Login and register page logic for UGC Video Pro
 */

const AuthPage = (() => {
  'use strict';

  // ── Toast (shared utility, works on auth pages) ──────────────────

  function showToast(type, title, message) {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const icons = {
      success: `<svg width="18" height="18" viewBox="0 0 18 18" fill="none"><circle cx="9" cy="9" r="8" stroke="#22c55e" stroke-width="1.5"/><path d="M5.5 9l2.5 2.5 4.5-5" stroke="#22c55e" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>`,
      error:   `<svg width="18" height="18" viewBox="0 0 18 18" fill="none"><circle cx="9" cy="9" r="8" stroke="#ef4444" stroke-width="1.5"/><path d="M9 5v4M9 12v.5" stroke="#ef4444" stroke-width="1.5" stroke-linecap="round"/></svg>`,
      warning: `<svg width="18" height="18" viewBox="0 0 18 18" fill="none"><path d="M9 2L17 16H1L9 2Z" stroke="#f59e0b" stroke-width="1.5" stroke-linejoin="round"/><path d="M9 7v4M9 13v.5" stroke="#f59e0b" stroke-width="1.5" stroke-linecap="round"/></svg>`,
      info:    `<svg width="18" height="18" viewBox="0 0 18 18" fill="none"><circle cx="9" cy="9" r="8" stroke="#3b82f6" stroke-width="1.5"/><path d="M9 8v5M9 5.5v.5" stroke="#3b82f6" stroke-width="1.5" stroke-linecap="round"/></svg>`,
    };

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
      <div class="toast-icon">${icons[type] || icons.info}</div>
      <div class="toast-body">
        <div class="toast-title">${title}</div>
        ${message ? `<div class="toast-message">${message}</div>` : ''}
      </div>
    `;

    container.appendChild(toast);

    setTimeout(() => {
      toast.classList.add('leaving');
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }

  // ── Form Helpers ─────────────────────────────────────────────

  function showError(elementId, msg) {
    const el = document.getElementById(elementId);
    if (!el) return;
    el.textContent = msg;
    el.classList.add('visible');
    // Also mark input as error
    const inputId = elementId.replace('Error', '');
    const input = document.getElementById(inputId);
    if (input) input.classList.add('error');
  }

  function clearError(elementId) {
    const el = document.getElementById(elementId);
    if (!el) return;
    el.textContent = '';
    el.classList.remove('visible');
    const inputId = elementId.replace('Error', '');
    const input = document.getElementById(inputId);
    if (input) input.classList.remove('error');
  }

  function clearAllErrors() {
    document.querySelectorAll('.form-error').forEach(el => {
      el.textContent = '';
      el.classList.remove('visible');
    });
    document.querySelectorAll('.form-input.error').forEach(el => {
      el.classList.remove('error');
    });
  }

  function setGlobalError(elementId, msg) {
    const el = document.getElementById(elementId);
    if (!el) return;
    el.textContent = msg;
    el.classList.add('visible');
  }

  function clearGlobalMsg(elementId) {
    const el = document.getElementById(elementId);
    if (!el) return;
    el.textContent = '';
    el.classList.remove('visible');
  }

  function setButtonLoading(btnId, textId, spinnerId, loading) {
    const btn  = document.getElementById(btnId);
    const text = document.getElementById(textId);
    const spinner = document.getElementById(spinnerId);
    if (!btn) return;
    btn.disabled = loading;
    if (text) text.style.display = loading ? 'none' : '';
    if (spinner) spinner.style.display = loading ? 'block' : 'none';
  }

  // ── Email Validation ────────────────────────────────────────────

  function isValidEmail(email) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
  }

  // ── Login Page ────────────────────────────────────────────────────

  function initLogin() {
    // Redirect if already authenticated
    if (API.isAuthenticated()) {
      window.location.href = 'index.html';
      return;
    }

    const form = document.getElementById('loginForm');
    if (!form) return;

    const emailInput    = document.getElementById('email');
    const passwordInput = document.getElementById('password');

    // Clear errors on input
    emailInput.addEventListener('input', () => clearError('emailError'));
    passwordInput.addEventListener('input', () => clearError('passwordError'));

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      clearAllErrors();
      clearGlobalMsg('loginError');

      const email    = emailInput.value.trim();
      const password = passwordInput.value;

      // Client-side validation
      let valid = true;

      if (!email) {
        showError('emailError', '请输入邮筱地址');
        valid = false;
      } else if (!isValidEmail(email)) {
        showError('emailError', '请输入有效的邮筱格式');
        valid = false;
      }

      if (!password) {
        showError('passwordError', '请输入密码');
        valid = false;
      }

      if (!valid) return;

      // Submit
      setButtonLoading('loginBtn', 'loginBtnText', 'loginSpinner', true);

      try {
        await API.login(email, password);
        window.location.href = 'index.html';
      } catch (err) {
        const msg = err.message === 'HTTP 401'
          ? '邮筱或密码错误，请重试'
          : (err.message || '登录失败，请稍后再试');
        setGlobalError('loginError', msg);
        showToast('error', '登录失败', msg);
      } finally {
        setButtonLoading('loginBtn', 'loginBtnText', 'loginSpinner', false);
      }
    });

    // Enter key support
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') form.requestSubmit();
    });
  }

  // ── Register Page ───────────────────────────────────────────────

  function initRegister() {
    // Redirect if already authenticated
    if (API.isAuthenticated()) {
      window.location.href = 'index.html';
      return;
    }

    const form = document.getElementById('registerForm');
    if (!form) return;

    const emailInput          = document.getElementById('email');
    const displayNameInput    = document.getElementById('displayName');
    const passwordInput       = document.getElementById('password');
    const confirmPasswordInput = document.getElementById('confirmPassword');
    const inviteCodeInput     = document.getElementById('inviteCode');

    // Auto-uppercase invite code
    inviteCodeInput.addEventListener('input', () => {
      const pos = inviteCodeInput.selectionStart;
      inviteCodeInput.value = inviteCodeInput.value.toUpperCase();
      inviteCodeInput.setSelectionRange(pos, pos);
      clearError('inviteCodeError');
    });

    // Clear errors on input
    emailInput.addEventListener('input',           () => clearError('emailError'));
    displayNameInput.addEventListener('input',     () => clearError('displayNameError'));
    passwordInput.addEventListener('input',        () => clearError('passwordError'));
    confirmPasswordInput.addEventListener('input', () => clearError('confirmPasswordError'));

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      clearAllErrors();
      clearGlobalMsg('registerError');
      clearGlobalMsg('registerSuccess');

      const email           = emailInput.value.trim();
      const displayName     = displayNameInput.value.trim();
      const password        = passwordInput.value;
      const confirmPassword = confirmPasswordInput.value;
      const inviteCode      = inviteCodeInput.value.trim().toUpperCase();

      // Validation
      let valid = true;

      if (!email) {
        showError('emailError', '请输入邮筱地址');
        valid = false;
      } else if (!isValidEmail(email)) {
        showError('emailError', '请输入有效的邮筱格式');
        valid = false;
      }

      if (!displayName) {
        showError('displayNameError', '请输入显示名称');
        valid = false;
      } else if (displayName.length < 2) {
        showError('displayNameError', '名称至少需要2个字符');
        valid = false;
      }

      if (!password) {
        showError('passwordError', '请输入密码');
        valid = false;
      } else if (password.length < 8) {
        showError('passwordError', '密码至少需要8位字符');
        valid = false;
      }

      if (!confirmPassword) {
        showError('confirmPasswordError', '请确认密码');
        valid = false;
      } else if (password !== confirmPassword) {
        showError('confirmPasswordError', '两次输入的密码不一致');
        valid = false;
      }

      if (!inviteCode) {
        showError('inviteCodeError', '请输入邀请码');
        valid = false;
      }

      if (!valid) return;

      setButtonLoading('registerBtn', 'registerBtnText', 'registerSpinner', true);

      try {
        await API.register(email, displayName, password, inviteCode);

        // Show success, then redirect to login
        const successEl = document.getElementById('registerSuccess');
        if (successEl) {
          successEl.textContent = '注册成功！正在跳转到登录页面...';
          successEl.classList.add('visible');
        }

        showToast('success', '注册成功', '账户已创建，请登录');

        setTimeout(() => {
          window.location.href = 'login.html';
        }, 1800);

      } catch (err) {
        let msg = err.message || '注册失败，请稍后再试';

        // Handle specific errors
        if (err.status === 400) {
          if (msg.toLowerCase().includes('invite')) {
            msg = '邀请码无效或已被使用';
            showError('inviteCodeError', msg);
          } else if (msg.toLowerCase().includes('email') || msg.toLowerCase().includes('already')) {
            msg = '该邮筱已被注册';
            showError('emailError', msg);
          }
        }

        setGlobalError('registerError', msg);
        showToast('error', '注册失败', msg);
      } finally {
        setButtonLoading('registerBtn', 'registerBtnText', 'registerSpinner', false);
      }
    });
  }

  // ── Public ────────────────────────────────────────────────────────────────

  return { initLogin, initRegister, showToast };
})();

window.AuthPage = AuthPage;
