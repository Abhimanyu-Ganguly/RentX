/**
 * RENTX — Core Application Logic
 * Professional E-Commerce Frontend (Vanilla JS)
 */

const API_BASE = '/api';

const app = {
  // Global State
  currentUser: null,
  currentView: 'browse',
  items: [],
  myRentals: { renter: [], owner: [] },
  activeRentalTab: 'renter',

  /**
   * UTILITIES
   */
  escapeHtml: (unsafe) => {
    if (unsafe == null) return '';
    return String(unsafe)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  },


  checkPasswordStrength: (pwd) => {
    const el = document.getElementById('password-strength');
    if (el) el.style.display = 'block';
    const len = pwd.length >= 8;
    const reqLen = document.getElementById('req-len');
    if (reqLen) {
      reqLen.innerHTML = len ? '<span style="color:var(--success)">✓ Minimum 8 characters</span>' : '<span style="color:var(--danger)">✗ Minimum 8 characters</span>';
    }
  },

  
  handleForgotPassword: async (e) => {
    e.preventDefault();
    const btn = document.getElementById('forgot-submit-btn');
    const email = document.getElementById('forgot-email').value;
    
    btn.textContent = 'Sending...';
    btn.disabled = true;

    try {
      const res = await fetch(`${API_BASE}/users/forgot-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed');
      
      app.showToast(data.detail || 'Reset link sent.', 'success');
      document.getElementById('forgot-form').reset();
      app.navigateTo('login');
    } catch (error) {
      app.showToast(error.message, 'error');
    } finally {
      btn.textContent = 'Send Reset Link';
      btn.disabled = false;
    }
  },

  handleResetPassword: async (e) => {
    e.preventDefault();
    const btn = document.getElementById('reset-submit-btn');
    const err = document.getElementById('reset-error');
    const pwd = document.getElementById('reset-pass').value;
    const confirm = document.getElementById('reset-confirm').value;
    
    err.classList.remove('active');

    if (pwd.length < 8) {
      err.textContent = 'Password must be at least 8 characters.';
      err.classList.add('active');
      return;
    }
    if (pwd !== confirm) {
      err.textContent = 'Passwords do not match.';
      err.classList.add('active');
      return;
    }

    btn.textContent = 'Resetting...';
    btn.disabled = true;

    try {
      const res = await fetch(`${API_BASE}/users/reset-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: app.resetToken || '', new_password: pwd })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Reset failed');
      
      app.showToast('Password successfully changed.', 'success');
      document.getElementById('reset-form').reset();
      app.resetToken = null;
      app.navigateTo('login');
    } catch (error) {
      err.textContent = `??? ${error.message}`;
      err.classList.add('active');
    } finally {
      btn.textContent = 'Reset Password';
      btn.disabled = false;
    }
  },

  handleLogin: async (e) => {
    e.preventDefault();
    const btn = document.getElementById('login-submit-btn');
    const err = document.getElementById('login-error');
    const email = document.getElementById('login-email').value;
    const pwd = document.getElementById('login-pass').value;
    
    err.classList.remove('active');
    btn.textContent = 'Signing in...';
    btn.disabled = true;

    try {
      const res = await fetch(`${API_BASE}/users/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email, password: pwd })
      });
      
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Login failed');
      
      app.currentUser = data;
      localStorage.setItem('sessionUserId', data.id);
      app.updateUserUI();
      app.navigateTo('browse');
      app.showToast('Welcome back!', 'success');
      document.getElementById('login-form').reset();
    } catch (error) {
      err.textContent = `⚠ ${error.message}`;
      err.classList.add('active');
    } finally {
      btn.textContent = 'Sign In';
      btn.disabled = false;
    }
  },

  handleSignup: async (e) => {
    e.preventDefault();
    const btn = document.getElementById('signup-submit-btn');
    const err = document.getElementById('signup-error');
    const name = document.getElementById('signup-name').value;
    const email = document.getElementById('signup-email').value;
    const pwd = document.getElementById('signup-pass').value;
    const confirm = document.getElementById('signup-confirm').value;
    
    err.classList.remove('active');

    if (pwd.length < 8) {
      err.textContent = 'Password must be at least 8 characters.';
      err.classList.add('active');
      return;
    }
    
    if (pwd !== confirm) {
      err.textContent = 'Passwords do not match.';
      err.classList.add('active');
      return;
    }

    btn.textContent = 'Creating Account...';
    btn.disabled = true;

    try {
      const res = await fetch(`${API_BASE}/users/signup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: name, email: email, password: pwd })
      });
      
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Signup failed');
      
      app.currentUser = data;
      localStorage.setItem('sessionUserId', data.id);
      app.updateUserUI();
      app.navigateTo('browse');
      app.showToast('Account created successfully!', 'success');
      document.getElementById('signup-form').reset();
      document.getElementById('password-strength').style.display = 'none';
    } catch (error) {
      err.textContent = `⚠ ${error.message}`;
      err.classList.add('active');
    } finally {
      btn.textContent = 'Create Account';
      btn.disabled = false;
    }
  },

  formatCurrency: (val) => {
    return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(val);
  },

  formatDate: (isoStr) => {
    if (!isoStr) return 'N/A';
    return new Date(isoStr).toLocaleDateString(undefined, {
      month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit'
    });
  },

  showToast: (message, type = 'info') => {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    let icon = 'ℹ️';
    if (type === 'success') icon = '✅';
    if (type === 'danger') icon = '❌';
    if (type === 'warning') icon = '⚠️';

    toast.innerHTML = `<span class="toast-icon">${icon}</span> <span>${app.escapeHtml(message)}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transition = 'opacity 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  },

  /**
   * INITIALIZATION
   */
  logout: () => {
    if(confirm('Are you sure you want to log out?')) {
      localStorage.removeItem('sessionUserId');
      app.currentUser = null;
      app.updateUserUI();
      app.navigateTo('login');
      app.showToast('Logged out successfully', 'success');
    }
  },

  toggleTheme: () => {
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    if (isDark) {
      document.documentElement.removeAttribute('data-theme');
      localStorage.setItem('theme', 'light');
    } else {
      document.documentElement.setAttribute('data-theme', 'dark');
      localStorage.setItem('theme', 'dark');
    }
    app.updateThemeIcon();
  },

  updateThemeIcon: () => {
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    const icon = document.getElementById('theme-icon');
    if (icon) {
      icon.textContent = isDark ? '☀' : '🌙';
    }
  },

  toggleMobileNav: () => {
    const nav = document.getElementById('mobile-nav');
    const btn = document.getElementById('hamburger-btn');
    if (nav) {
      const isOpen = nav.classList.toggle('open');
      if (btn) btn.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
    }
  },

  closeMobileNav: () => {
    const nav = document.getElementById('mobile-nav');
    const btn = document.getElementById('hamburger-btn');
    if (nav) nav.classList.remove('open');
    if (btn) btn.setAttribute('aria-expanded', 'false');
  },

  init: async () => {
    app.setupGlobalListeners();
    app.updateThemeIcon();
    app.setupForms();
    await app.fetchSessionUser();
    
    let initialView = location.hash.replace('#', '') || 'browse';
    if (initialView.includes('?')) {
        const parts = initialView.split('?');
        app.resetToken = new URLSearchParams(parts[1]).get('token');
        initialView = parts[0];
    }

    if (!app.currentUser && initialView !== 'browse' && initialView !== 'login' && initialView !== 'signup') initialView = 'login';
    app.navigateTo(initialView);
  },

  setupGlobalListeners: () => {
    // Hash routing
    window.addEventListener('hashchange', () => {
      
      let hash = location.hash.replace('#', '') || 'browse';
      if (hash.includes('?')) {
          const parts = hash.split('?');
          app.resetToken = new URLSearchParams(parts[1]).get('token');
          hash = parts[0];
      }
      app.navigateTo(hash);

    });

    // Close modals on Escape or outside click
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        document.querySelectorAll('.modal-overlay.active').forEach(modal => {
          app.closeModal(modal.id);
        });
      }
    });
    document.querySelectorAll('.modal-overlay').forEach(modal => {
      modal.addEventListener('click', (e) => {
        if (e.target === modal) app.closeModal(modal.id);
      });
    });

    // Need search debouncing
    const searchInput = document.getElementById('browse-search-input');
    if (searchInput) {
      let timeout;
      searchInput.addEventListener('input', () => {
        clearTimeout(timeout);
        timeout = setTimeout(app.loadBrowseItems, 300);
      });
    }

    // Category pills
    document.querySelectorAll('.pills .pill').forEach(pill => {
      pill.addEventListener('click', (e) => {
        document.querySelectorAll('.pills .pill').forEach(p => p.classList.remove('active', 'btn-primary'));
        e.target.classList.add('active');
        app.loadBrowseItems();
      });
    });
  },

  setupForms: () => {
    document.getElementById('list-item-form')?.addEventListener('submit', app.handleListItem);
    document.getElementById('need-search-form')?.addEventListener('submit', (e) => {
      e.preventDefault();
      app.handleNeedSearch();
    });
    document.getElementById('borrow-form')?.addEventListener('submit', app.handleBorrowSubmit);
    document.getElementById('confirm-return-form')?.addEventListener('submit', app.handleConfirmReturn);
    document.getElementById('dispute-form')?.addEventListener('submit', app.handleDisputeSubmit);
    document.getElementById('resolve-form')?.addEventListener('submit', app.handleResolveSubmit);
    
    document.getElementById('login-sample-form')?.addEventListener('submit', async (e) => {
      e.preventDefault();
      const email = document.getElementById('login-email').value;
      const pass = document.getElementById('login-pass').value;
      try {
        const user = await app.apiCall('/users/login', {
          method: 'POST',
          body: { email, password: pass }
        });
        localStorage.setItem('sessionUserId', user.id);
        app.currentUser = user;
        app.updateUserUI();
        app.showToast(`Welcome back, ${user.name}!`, 'success');
        app.navigateTo('browse');
      } catch (err) {
        app.showToast(err.message || 'Login failed', 'error');
      }
    });

    document.getElementById('signup-sample-form')?.addEventListener('submit', async (e) => {
      e.preventDefault();
      const name = document.getElementById('signup-name').value;
      const email = document.getElementById('signup-email').value;
      const pass = document.getElementById('signup-pass').value;
      try {
        const user = await app.apiCall('/users/signup', {
          method: 'POST',
          body: { name, email, password: pass }
        });
        localStorage.setItem('sessionUserId', user.id);
        app.currentUser = user;
        app.updateUserUI();
        app.showToast('Account created successfully!', 'success');
        app.navigateTo('browse');
      } catch (err) {
        app.showToast(err.message || 'Sign up failed', 'error');
      }
    });
    
    document.getElementById('update-location-form')?.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (!app.currentUser) return;
      const dorm = document.getElementById('profile-location-input').value;
      try {
        const updated = await app.apiCall(`/users/${app.currentUser.id}/location`, {
          method: 'PUT', body: { dorm }
        });
        app.currentUser.dorm = updated.dorm;
        app.showToast('Location updated successfully!', 'success');
      } catch (e) {}
    });
  },

  /**
   * NAVIGATION & VIEWS
   */
  navigateTo: (viewId) => {
    if (viewId.includes('?')) {
        const parts = viewId.split('?');
        app.resetToken = new URLSearchParams(parts[1]).get('token');
        viewId = parts[0];
    }

    const validViews = ['browse', 'need-search', 'list-item', 'rentals', 'activity', 'profile', 'passport', 'about', 'login', 'signup', 'admin', 'forgot-password', 'reset-password'];
    if (!validViews.includes(viewId)) viewId = 'browse';
    
    // Protected routes
    const protectedViews = ['list-item', 'rentals', 'activity', 'profile', 'admin'];
    if (!app.currentUser && protectedViews.includes(viewId)) {
      app.showToast('Please sign in to access this page.', 'warning');
      viewId = 'login';
    }

    // Close mobile nav on navigate
    app.closeMobileNav();

    // Update nav active states
    document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
    document.querySelector(`.nav-link[data-view="${viewId}"]`)?.classList.add('active');

    // Show correct view
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    document.getElementById(`view-${viewId}`).classList.add('active');
    
    app.currentView = viewId;

    // Load data for view
    if (viewId === 'browse') app.loadBrowseItems();
    else if (viewId === 'list-item') app.renderChecklistForm();
    else if (viewId === 'rentals') app.loadRentals();
    else if (viewId === 'activity') app.loadActivity();
    else if (viewId === 'profile') app.loadReputation();
    else if (viewId === 'admin') app.loadAdminDashboard();
  },

  openModal: (modalId) => {
    const modal = document.getElementById(modalId);
    if (modal) {
      modal.classList.add('active');
      modal.setAttribute('aria-hidden', 'false');
      const firstInput = modal.querySelector('input, select, textarea, button:not(.modal-close)');
      if (firstInput) firstInput.focus();
    }
  },

  closeModal: (modalId) => {
    const modal = document.getElementById(modalId);
    if (modal) {
      modal.classList.remove('active');
      modal.setAttribute('aria-hidden', 'true');
      const form = modal.querySelector('form');
      if (form) form.reset(); // clean up
    }
  },

  /**
   * API CLIENT
   */
  apiCall: async (endpoint, options = {}) => {
    const headers = options.headers || {};
    if (app.currentUser) headers['X-User-Id'] = app.currentUser.id;
    if (!(options.body instanceof FormData) && options.method && options.method !== 'GET') {
      headers['Content-Type'] = 'application/json';
      if (typeof options.body === 'object') options.body = JSON.stringify(options.body);
    }
    
    const response = await fetch(`${API_BASE}${endpoint}`, { ...options, headers });
    let data;
    try { data = await response.json(); } catch(e) { data = null; }

    if (!response.ok) {
      const msg = data?.detail || data?.message || `Error ${response.status}`;
      app.showToast(msg, 'danger');
      throw new Error(msg);
    }
    return data;
  },

  /**
   * AUTHENTICATION (PROTOTYPE)
   */
  fetchSessionUser: async () => {
    try {
      const savedId = localStorage.getItem('sessionUserId');
      if (savedId) {
        app.currentUser = await app.apiCall(`/users/${savedId}`);
      } else {
        app.currentUser = null;
      }
      app.updateUserUI();
    } catch (e) {
      console.warn("Session fetch failed", e);
      app.currentUser = null;
      localStorage.removeItem('sessionUserId');
      app.updateUserUI();
    }
  },

  updateUserUI: () => {
    const btn = document.getElementById('user-chip-btn');
    const loginBtn = document.getElementById('header-login-btn');
    const logoutBtn = document.getElementById('header-logout-btn');
    const adminNav = document.getElementById('nav-admin');

    if (!app.currentUser) {
      document.getElementById('current-user-name').textContent = 'Guest';
      document.getElementById('current-user-avatar').src = 'https://ui-avatars.com/api/?name=Guest&background=0ea5e9&color=fff';
      btn.onclick = () => app.navigateTo('login');
      
      if(loginBtn) loginBtn.style.display = 'block';
      btn.style.display = 'none';
      document.getElementById('header-signup-btn').style.display = 'block';
      if(logoutBtn) logoutBtn.style.display = 'none';
      if(adminNav) adminNav.style.display = 'none';
      return;
    }
    
    document.getElementById('current-user-name').textContent = app.currentUser.name;
    document.getElementById('current-user-avatar').src = app.currentUser.avatar_url || `https://ui-avatars.com/api/?name=${encodeURIComponent(app.currentUser.name)}&background=0ea5e9&color=fff`;
    localStorage.setItem('sessionUserId', app.currentUser.id);
    
    btn.onclick = () => app.navigateTo('profile');
    
    if(loginBtn) loginBtn.style.display = 'none';
    btn.style.display = 'flex';
    document.getElementById('header-signup-btn').style.display = 'none';
    if(logoutBtn) logoutBtn.style.display = 'block';
    
    if(adminNav) adminNav.style.display = (app.currentUser.is_admin ? 'block' : 'none');

    document.getElementById('nav-notifications').style.display = 'block';
    app.loadNotifications();
    if(app.notifInterval) clearInterval(app.notifInterval);
    app.notifInterval = setInterval(app.loadNotifications, 10000);

  },

  contactUser: (name) => {
    document.getElementById('contact-recipient-name').textContent = name;
    document.getElementById('contact-message-body').value = '';
    app.openModal('modal-contact');
  },

  
  
  // ===== MESSAGING SYSTEM ===== //
  
  // ===== NOTIFICATIONS SYSTEM ===== //
  notifInterval: null,
  notifications: [],

  toggleNotifications: () => {
    const dd = document.getElementById('notif-dropdown');
    if (dd.style.display === 'none' || dd.style.display === '') {
      dd.style.display = 'flex';
      app.loadNotifications();
    } else {
      dd.style.display = 'none';
    }
  },

  loadNotifications: async () => {
    if (!app.currentUser) return;
    try {
      const data = await app.apiCall('/rentals/notifications');
      app.notifications = data;
      app.renderNotifications();
    } catch(e) {
      console.error(e);
    }
  },

  renderNotifications: () => {
    const list = document.getElementById('notif-list');
    const badge = document.getElementById('notif-badge');
    const unreadCount = app.notifications.filter(n => !n.is_read).length;
    
    if (unreadCount > 0) {
      badge.textContent = unreadCount;
      badge.style.display = 'block';
    } else {
      badge.style.display = 'none';
    }
    
    if (app.notifications.length === 0) {
      list.innerHTML = `<div style="padding: 16px; text-align: center; color: var(--text-secondary); font-size: 0.9rem;">No notifications</div>`;
      return;
    }
    
    let html = '';
    app.notifications.forEach(n => {
      const bg = n.is_read ? 'transparent' : 'var(--bg-card-hover)';
      const dot = n.is_read ? '' : `<span style="display: inline-block; width: 8px; height: 8px; background: var(--primary); border-radius: 50%; margin-right: 8px;"></span>`;
      
      let icon = '🔔';
      if (n.type === 'new_request') icon = '🔵';
      else if (n.type.includes('accepted')) icon = '✅';
      else if (n.type.includes('rejected')) icon = '❌';
      else if (n.type === 'new_message') icon = '💬';
      
      const date = new Date(n.created_at);
      let dateStr = date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
      if (Date.now() - date.getTime() > 86400000) {
          dateStr = date.toLocaleDateString();
      }
      
      html += `
        <div onclick="app.handleNotificationClick(${n.id}, ${n.rental_id}, '${n.type}')" 
             style="padding: 12px; border-bottom: 1px solid var(--border); background: ${bg}; cursor: pointer; transition: background 0.2s;">
          <div style="display: flex; align-items: flex-start; gap: 8px;">
            <div style="font-size: 1.2rem;">${icon}</div>
            <div style="flex: 1;">
              <div style="display: flex; align-items: center; font-size: 0.85rem; color: var(--text-primary); font-weight: ${n.is_read ? 'normal' : 'bold'};">
                ${dot}${app.escapeHtml(n.title)}
              </div>
              <div style="font-size: 0.8rem; color: var(--text-secondary); margin-top: 2px;">
                ${app.escapeHtml(n.message)}
              </div>
              <div style="font-size: 0.7rem; color: #999; margin-top: 4px;">
                ${dateStr}
              </div>
            </div>
          </div>
        </div>
      `;
    });
    list.innerHTML = html;
  },

  handleNotificationClick: async (notifId, rentalId, type) => {
    // Mark as read
    try {
      await app.apiCall(`/rentals/notifications/${notifId}/read`, { method: 'POST' });
      app.loadNotifications();
    } catch(e) {}
    
    // Close dropdown
    document.getElementById('notif-dropdown').style.display = 'none';
    
    // Navigate based on type
    if (rentalId) {
      await app.navigateTo('profile');
      
      // We need to wait a moment for the profile to load, then ensure rentals are loaded
      setTimeout(() => {
          if (type === 'new_request' || type === 'return_request') {
              // Show owner tab
              app.activeRentalTab = 'owner';
              app.renderRentalsList();
          } else if (type === 'rental_accepted' || type === 'rental_rejected' || type === 'rental_completed') {
              // Show renter tab
              app.activeRentalTab = 'renter';
              app.renderRentalsList();
          }
          
          if (type === 'new_message') {
              // Open chat modal
              // We need to determine if we are owner or renter for this rental. 
              // To be safe, we can just check if it's in our renter list, else owner list.
              if (app.myRentals.renter.find(r => r.id === rentalId)) {
                  app.activeRentalTab = 'renter';
              } else {
                  app.activeRentalTab = 'owner';
              }
              app.renderRentalsList();
              app.openChatModal(rentalId);
          }
      }, 300);
    }
  },

  markAllNotificationsRead: async () => {
    try {
      await app.apiCall('/rentals/notifications/read-all', { method: 'POST' });
      await app.loadNotifications();
    } catch(e) {
      console.error(e);
    }
  },


  activeChatRental: null,
  activeChatInterval: null,

  openChatModal: async (rentalId) => {
    app.activeChatRental = rentalId;
    app.openModal('modal-chat');
    document.getElementById('chat-messages-container').innerHTML = '<div style="text-align:center; padding: 20px;">Loading messages...</div>';
    document.getElementById('chat-header-info').innerHTML = '';
    
    await app.loadChatData();
    
    // Auto refresh chat
    if (app.activeChatInterval) clearInterval(app.activeChatInterval);
    app.activeChatInterval = setInterval(app.loadChatData, 5000);
  },

  closeModal: (id) => {
    document.getElementById(id).style.display = 'none';
    if (id === 'modal-chat' && app.activeChatInterval) {
      clearInterval(app.activeChatInterval);
      app.activeChatInterval = null;
    }
  },

  loadChatData: async () => {
    if (!app.activeChatRental) return;
    try {
      // Find the rental details
      let rental;
      if (app.myRentals) {
        rental = (app.myRentals.renter || []).find(r => r.id === app.activeChatRental) 
                 || (app.myRentals.owner || []).find(r => r.id === app.activeChatRental);
      }
      
      if (rental) {
        document.getElementById('chat-header-info').innerHTML = `
          <strong>ITEM:</strong> ${app.escapeHtml(rental.item_title)}<br>
          <strong>OWNER:</strong> ${app.escapeHtml(rental.owner_name)}<br>
          <strong>BORROWER:</strong> ${app.escapeHtml(rental.renter_name)}<br>
          <span style="color: var(--text-secondary); font-size: 0.8rem;">
            Rental dates: ${rental.start_date} &rarr; ${rental.end_date}
          </span>
        `;
      }

      const messages = await app.apiCall(`/rentals/${app.activeChatRental}/messages`);
      const container = document.getElementById('chat-messages-container');
      
      if (!messages || messages.length === 0) {
        if (!container.innerHTML.includes('No messages yet')) {
            container.innerHTML = '<div style="text-align:center; padding: 20px; color: var(--text-secondary);">No messages yet. Say hello!</div>';
        }
        return;
      }

      let html = '';
      messages.forEach(msg => {
        const isMe = msg.sender_id === app.currentUser.id;
        const align = isMe ? 'flex-end' : 'flex-start';
        const bg = isMe ? 'var(--primary)' : '#e0e0e0';
        const color = isMe ? 'white' : 'black';
        const date = new Date(msg.created_at).toLocaleString();
        
        html += `
          <div style="display: flex; flex-direction: column; align-items: ${align}; margin-bottom: 8px;">
            <div style="font-size: 0.75rem; color: #666; margin-bottom: 2px;">
              <strong>${app.escapeHtml(msg.sender_name)}</strong> &bull; ${date}
            </div>
            <div style="background: ${bg}; color: ${color}; padding: 8px 12px; border-radius: 12px; max-width: 80%; word-wrap: break-word;">
              ${app.escapeHtml(msg.message_text)}
            </div>
          </div>
        `;
      });
      
      const isScrolledToBottom = container.scrollHeight - container.clientHeight <= container.scrollTop + 10;
      container.innerHTML = html;
      if (isScrolledToBottom) {
        container.scrollTop = container.scrollHeight;
      }
      
    } catch (e) {
      console.error("Failed to load chat", e);
    }
  },

  submitChatMessage: async (event) => {
    event.preventDefault();
    if (!app.activeChatRental) return;
    
    const input = document.getElementById('chat-input-body');
    const text = input.value.trim();
    if (!text) return;
    
    input.value = '';
    
    try {
      await app.apiCall(`/rentals/${app.activeChatRental}/messages`, {
        method: 'POST',
        body: JSON.stringify({ message_text: text })
      });
      await app.loadChatData();
      const container = document.getElementById('chat-messages-container');
      container.scrollTop = container.scrollHeight;
    } catch (e) {
      app.showToast(e.message || "Failed to send message", 'error');
      input.value = text; // Restore on failure
    }
  },

  
  submitContactMessage: (event) => {
    event.preventDefault();
    const name = document.getElementById('contact-recipient-name').textContent;
    app.closeModal('modal-contact');
    app.showToast(`Your message was securely sent to ${name}!`, 'success');
  },

  
  openOwnerReview: (rentalId) => {
    app.activeReviewRental = rentalId;
    app.openModal('modal-owner-review');
  },

  openItemReview: (rentalId) => {
    app.activeReviewRental = rentalId;
    app.openModal('modal-item-review');
  },

  submitOwnerReview: async (event) => {
    event.preventDefault();
    if (!app.activeReviewRental) return;
    
    const payload = {
      rating: parseInt(document.getElementById('owner-service-rating').value, 10),
      product_condition: document.getElementById('owner-product-condition').value,
      price_fairness: document.getElementById('owner-price-fairness').value,
      comment: document.getElementById('owner-review-comment').value
    };
    
    try {
      await app.apiCall(`/rentals/${app.activeReviewRental}/reviews/owner`, { method: 'POST', body: JSON.stringify(payload) });
      app.showToast('Owner review submitted successfully!', 'success');
      app.closeModal('modal-owner-review');
      app.loadRentals();
    } catch (e) {
      app.showToast(e.message || "Failed to submit owner review", 'error');
    }
  },

  submitItemReview: async (event) => {
    event.preventDefault();
    if (!app.activeReviewRental) return;
    
    const payload = {
      rating: parseInt(document.getElementById('item-rating').value, 10),
      product_condition: document.getElementById('item-product-condition').value,
      comment: document.getElementById('item-review-comment').value
    };
    
    try {
      await app.apiCall(`/rentals/${app.activeReviewRental}/reviews/item`, { method: 'POST', body: JSON.stringify(payload) });
      app.showToast('Item review submitted successfully!', 'success');
      app.closeModal('modal-item-review');
      app.loadRentals();
    } catch (e) {
      app.showToast(e.message || "Failed to submit item review", 'error');
    }
  },

  openAuthModal: async () => {
    app.openModal('modal-auth');
    try {
      const users = await app.apiCall('/users');
      const list = document.getElementById('demo-personas-list');
      list.innerHTML = users.map(u => `
        <button class="persona-btn" onclick="app.switchDemoUser(${u.id})">
          <img class="persona-avatar" src="${app.escapeHtml(u.avatar_url) || `https://ui-avatars.com/api/?name=${encodeURIComponent(u.name)}&background=6366f1&color=fff`}" alt="">
          <div class="persona-info">
            <div class="persona-name">${app.escapeHtml(u.name)} ${u.id === app.currentUser?.id ? '(Current)' : ''}</div>
            <div class="persona-detail">${app.escapeHtml(u.email)} &bull; ${app.escapeHtml(u.dorm)}</div>
          </div>
        </button>
      `).join('');
    } catch (e) {}
  },

  switchDemoUser: (id) => {
    localStorage.setItem('demoUserId', id);
    app.closeModal('modal-auth');
    window.location.reload();
  },

  /**
   * ACTIVITY & LEDGER
   */
  loadActivity: async () => {
    if (!app.currentUser) return;
    const container = document.getElementById('activity-timeline');
    container.innerHTML = `<div class="loading-state">Loading activity...</div>`;
    
    try {
      const allRentals = await app.apiCall('/rentals');
      let events = [];
      let totalEarned = 0;
      let totalSpent = 0;
      let escrowLocked = 0;

      allRentals.forEach(r => {
        const isOwner = r.owner_id === app.currentUser.id;
        const isRenter = r.renter_id === app.currentUser.id;
        const itemTitle = app.escapeHtml(r.item_title);

        if (r.requested_at) {
          events.push({
            time: new Date(r.requested_at),
            type: 'requested',
            icon: '📩',
            desc: isOwner 
              ? `User #${r.renter_id} requested to borrow your <strong>${itemTitle}</strong> for ${r.days} days.` 
              : `You requested to borrow <strong>${itemTitle}</strong> for ${r.days} days.`
          });
        }
        
        if (r.responded_at && r.booking_status !== 'rejected') {
          events.push({
            time: new Date(r.responded_at),
            type: 'accepted',
            icon: '🤝',
            desc: isOwner
              ? `You accepted the request for <strong>${itemTitle}</strong>. Deposit of ${app.formatCurrency(r.deposit_amount)} held.`
              : `Your request for <strong>${itemTitle}</strong> was accepted! Escrow deposit of ${app.formatCurrency(r.deposit_amount)} locked.`
          });
          if (r.deposit_status === 'held' || r.deposit_status === 'disputed') {
             escrowLocked += r.deposit_amount;
          }
        } else if (r.responded_at && r.booking_status === 'rejected') {
          events.push({
             time: new Date(r.responded_at),
             type: 'rejected',
             icon: '🚫',
             desc: isOwner ? `You rejected the request for <strong>${itemTitle}</strong>.` : `Request for <strong>${itemTitle}</strong> was declined.`
          });
        }

        if (r.returned_at) {
          events.push({
            time: new Date(r.returned_at),
            type: 'returned',
            icon: '🔄',
            desc: isOwner
              ? `<strong>${itemTitle}</strong> was marked as returned. Pending your inspection.`
              : `You returned <strong>${itemTitle}</strong>.`
          });
        }

        if (r.completed_at) {
          if (r.deposit_status === 'released') {
             events.push({
               time: new Date(r.completed_at),
               type: 'completed',
               icon: '✅',
               desc: isOwner
                 ? `You released the deposit. Earned <strong>${app.formatCurrency(r.total_price)}</strong> for <strong>${itemTitle}</strong>.`
                 : `Owner released your deposit of ${app.formatCurrency(r.deposit_amount)}. Paid ${app.formatCurrency(r.total_price)}.`
             });
             if (isOwner) totalEarned += r.total_price;
             if (isRenter) totalSpent += r.total_price;
          } else if (r.deposit_status === 'disputed') {
             events.push({
               time: new Date(r.completed_at),
               type: 'dispute',
               icon: '🚨',
               desc: `Dispute opened for <strong>${itemTitle}</strong>.`
             });
          }
        }
      });

      // Update Financial Dashboard
      document.getElementById('dash-earned').textContent = app.formatCurrency(totalEarned);
      document.getElementById('dash-spent').textContent = app.formatCurrency(totalSpent);
      document.getElementById('dash-escrow').textContent = app.formatCurrency(escrowLocked);

      // Sort events newest first
      events.sort((a, b) => b.time - a.time);

      if (events.length === 0) {
        container.innerHTML = `<div class="empty-state">
          <div class="empty-state-icon">💸</div>
          <div class="empty-state-title">No Activity Yet</div>
          <div class="empty-state-desc">Your rental and financial history will appear here.</div>
        </div>`;
        return;
      }

      container.innerHTML = events.map(e => `
        <div class="timeline-event">
          <div class="timeline-dot" style="display:flex;align-items:center;justify-content:center;background:var(--bg-surface);border:1px solid var(--border);font-size:12px;">${e.icon}</div>
          <div class="timeline-card">
            <div style="font-size:0.75rem;color:var(--text-muted);margin-bottom:4px;">${app.formatDate(e.time.toISOString())}</div>
            <div style="font-size:0.9rem;">${e.desc}</div>
          </div>
        </div>
      `).join('');

    } catch(e) {
      container.innerHTML = `<div class="empty-state">Failed to load activity.</div>`;
    }
  },

  /**
   * BROWSE
   */

  autoLocate: async () => {
    app.showToast('Connecting to Google Maps & IP Location services...', 'success');
    try {
      const res = await fetch('http://ip-api.com/json/');
      const data = await res.json();
      if (data.status === 'success') {
        const loc = `${data.city}, ${data.regionName}, ${data.countryCode}`;
        document.getElementById('profile-location-input').value = loc;
        app.showToast('Location automatically detected!', 'success');
      } else {
        throw new Error('API failed');
      }
    } catch (e) {
      document.getElementById('profile-location-input').value = 'New York, NY, USA';
      app.showToast('Mock location loaded (Offline mode).', 'success');
    }
  },

  loadAdminDashboard: async () => {
    if (!app.currentUser || app.currentUser.is_admin !== 1) {
      app.navigateTo('browse');
      return;
    }
    // Static demo dashboard - no fetch required.
  },

  resolveDispute: (winner) => {
    const card = document.getElementById('demo-dispute-card');
    if (!card) return;
    
    let msg = '';
    if (winner === 'owner') {
      msg = 'Dispute resolved in favor of the Owner. ₹12,450 escrow transferred to Maya Lin.';
    } else {
      msg = 'Dispute resolved in favor of the Renter. ₹12,450 escrow refunded to Jordan Lee.';
    }
    
    card.innerHTML = `<div style="text-align: center; padding: 2rem;">
      <div style="font-size: 3rem; margin-bottom: 1rem;">✅</div>
      <h3 style="color: var(--success); margin-bottom: 0.5rem;">Dispute Closed</h3>
      <p style="color: var(--text-secondary);">${msg}</p>
    </div>`;
    
    app.showToast('Escrow funds routed successfully.', 'success');
  },

  loadBrowseItems: async () => {
    const grid = document.getElementById('items-grid');
    grid.innerHTML = `<div class="skeleton skeleton-card"></div><div class="skeleton skeleton-card"></div><div class="skeleton skeleton-card"></div>`;
    
    const catPill = document.querySelector('.pills .pill.active');
    const cat = catPill ? catPill.dataset.category : 'all';
    const q = document.getElementById('browse-search-input')?.value || '';
    
    let url = '/items?available=true';
    if (cat !== 'all') url += `&category=${encodeURIComponent(cat)}`;
    if (q) url += `&q=${encodeURIComponent(q)}`;

    try {
      const items = await app.apiCall(url);
      app.renderItemsGrid(items, 'items-grid');
    } catch (e) {
      grid.innerHTML = `<div class="empty-state">Error loading items</div>`;
    }
  },

  renderItemsGrid: (items, containerId) => {
    const grid = document.getElementById(containerId);
    if (items.length === 0) {
      grid.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">🔭</div>
          <div class="empty-state-title">No equipment found</div>
          <div class="empty-state-desc">Try adjusting your filters or search terms.</div>
        </div>`;
      return;
    }

    grid.innerHTML = items.map(item => `
      <div class="product-card">
        <img src="${app.escapeHtml(item.photo_path)}" alt="${app.escapeHtml(item.title)}" class="product-card-img" onerror="this.src='https://placehold.co/600x400?text=No+Photo'">
        <div class="product-card-body">
          <div class="product-card-meta">
            <span class="badge badge-neutral">${app.escapeHtml(item.category)}</span>
          </div>
          <div class="product-card-title">${app.escapeHtml(item.title)}</div>
          <div class="product-card-desc">${app.escapeHtml(item.description)}</div>
          <div class="product-card-seller">
            <div>Owner: <strong>${app.escapeHtml(item.owner_name) || `User #${item.owner_id}`}</strong></div>
            <div style="font-size:0.8rem;color:var(--text-muted);margin-top:2px;">📍 ${app.escapeHtml(item.owner_dorm) || 'Local Area'}</div>
          </div>
          <div class="product-card-pricing">
            <div>
              <span class="product-price">${app.formatCurrency(item.price_per_day)}</span>
              <span class="product-price-unit">/day</span>
            </div>
            <div class="product-deposit">Deposit: ${app.formatCurrency(item.deposit_amount)}</div>
          </div>
          <div class="product-card-actions">
            <button class="btn btn-primary btn-block" onclick="app.openBorrowModal(${item.id}, ${item.price_per_day}, ${item.deposit_amount}, '${app.escapeHtml(item.title).replace(/'/g, "\'")}')">Borrow</button>
            <div style="display: flex; gap: 0.5rem; margin-top: 0.5rem;">
              <button class="btn btn-secondary btn-block" style="margin-top:0;" onclick="app.openProductModal(${item.id})">Details / History</button>
              <button class="btn btn-secondary btn-block" style="margin-top:0;" onclick="app.contactUser(item.owner_name || 'Owner')">Contact</button>
            </div>
          </div>
        </div>
      </div>
    `).join('');
  },

  /**
   * SMART MATCHING
   */
  setNeedQuery: (query) => {
    document.getElementById('need-query-input').value = query;
    app.handleNeedSearch();
  },

  handleNeedSearch: async () => {
    const q = document.getElementById('need-query-input').value;
    if (!q) return;

    const container = document.getElementById('bundle-results-container');
    const grid = document.getElementById('bundle-items-grid');
    
    container.style.display = 'block';
    document.getElementById('bundle-missing-banner').style.display = 'none';
    grid.innerHTML = `<div class="skeleton skeleton-card"></div><div class="skeleton skeleton-card"></div>`;
    document.getElementById('bundle-title').textContent = "Finding perfect bundle...";

    try {
      const res = await app.apiCall('/matching/match', { method: 'POST', body: { description: q } });
      
      document.getElementById('bundle-title').textContent = `Equipment Bundle: "${app.escapeHtml(q)}"`;
      document.getElementById('bundle-desc').textContent = `Found ${res.bundle.length} items to help you.`;
      
      const totalPrice = res.bundle.reduce((sum, item) => sum + item.price_per_day, 0);
      const totalDep = res.bundle.reduce((sum, item) => sum + item.deposit_amount, 0);
      document.getElementById('bundle-total-price').textContent = `${app.formatCurrency(totalPrice)}/day`;
      document.getElementById('bundle-total-deposit').textContent = app.formatCurrency(totalDep);

      if (res.missing_needs && res.missing_needs.length > 0) {
        const banner = document.getElementById('bundle-missing-banner');
        banner.style.display = 'flex';
        banner.innerHTML = `<strong>Note:</strong> We couldn't find items for: ${app.escapeHtml(res.missing_needs.join(', '))}`;
      }

      app.renderItemsGrid(res.bundle, 'bundle-items-grid');
    } catch (e) {
      grid.innerHTML = `<div class="empty-state">Matching failed.</div>`;
    }
  },

  /**
   * LIST ITEM
   */
  renderChecklistForm: () => {
    const cat = document.getElementById('item-category').value;
    const container = document.getElementById('dynamic-checklist-container');
    
    const templates = {
      'camera gear': ['lens_glass', 'sensor', 'body_scratches', 'battery_health'],
      'tools': ['motor_sound', 'power_cord', 'drill_chuck', 'cleanliness'],
      'camping': ['tent_fabric_tears', 'poles_integrity', 'zippers_working'],
      'projector': ['lamp_hours', 'lens_clarity', 'inputs_working', 'remote_included'],
      'default': ['overall_condition', 'cleanliness', 'accessories_included']
    };
    
    const fields = templates[cat] || templates['default'];
    
    container.innerHTML = fields.map(f => `
      <div class="form-group" style="margin-bottom:var(--sp-3)">
        <label class="form-label" style="text-transform:capitalize">${app.escapeHtml(f.replace(/_/g, ' '))}</label>
        <select class="form-select checklist-input" data-key="${app.escapeHtml(f)}">
          <option value="good">Good (Normal Wear)</option>
          <option value="pristine">Pristine (Like New)</option>
          <option value="fair">Fair (Noticeable Wear)</option>
          <option value="damaged">Damaged</option>
        </select>
      </div>
    `).join('');
  },

  handleListItem: async (e) => {
    e.preventDefault();
    const btn = document.getElementById('list-submit-btn');
    btn.disabled = true;
    btn.textContent = 'Registering Passport...';

    try {
      const checklist = {};
      document.querySelectorAll('.checklist-input').forEach(sel => {
        checklist[sel.dataset.key] = sel.value;
      });

      const formData = new FormData();
      formData.append('title', document.getElementById('item-title').value);
      formData.append('category', document.getElementById('item-category').value);
      formData.append('description', document.getElementById('item-description').value);
      formData.append('value', document.getElementById('item-value').value);
      formData.append('price_per_day', document.getElementById('item-price').value);
      formData.append('deposit_amount', document.getElementById('item-deposit').value);
      formData.append('serial', document.getElementById('item-serial').value);
      formData.append('tags', document.getElementById('item-tags').value);
      formData.append('mode', 'commercial');
      formData.append('condition_checklist', JSON.stringify(checklist));

      const fileField = document.getElementById('item-photo');
      if (fileField.files[0]) formData.append('photo', fileField.files[0]);

      await app.apiCall('/items', { method: 'POST', body: formData });
      app.showToast('Item listed and Passport Genesis Block created!', 'success');
      
      document.getElementById('list-item-form').reset();
      app.navigateTo('browse');
    } catch (e) {
      // toast shown in apiCall
    } finally {
      btn.disabled = false;
      btn.textContent = 'Register & Compute Cryptographic Passport';
    }
  },

  /**
   * BORROW FLOW
   */
  openBorrowModal: (itemId, price, deposit, title) => {
    if (app.currentUser?.id === app.items.find(i => i.id === itemId)?.owner_id) {
      return app.showToast('You cannot borrow your own item', 'warning');
    }
    document.getElementById('borrow-item-id').value = itemId;
    document.getElementById('borrow-modal-title').textContent = `Borrow: ${title}`;
    
    // Store rates for calculation
    document.getElementById('borrow-form').dataset.price = price;
    document.getElementById('borrow-form').dataset.deposit = deposit;
    
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('borrow-start').min = today;
    document.getElementById('borrow-end').min = today;
    document.getElementById('borrow-start').value = '';
    document.getElementById('borrow-end').value = '';
    
    document.getElementById('borrow-availability-msg').innerHTML = 'Select dates to check availability';
    document.getElementById('borrow-availability-msg').style.color = 'inherit';
    document.getElementById('borrow-submit-btn').disabled = true;
    
    app.updateBorrowQuote(0);
    app.openModal('modal-borrow');
  },

  checkBorrowAvailability: async () => {
    const start = document.getElementById('borrow-start').value;
    let end = document.getElementById('borrow-end').value;
    const msg = document.getElementById('borrow-availability-msg');
    const btn = document.getElementById('borrow-submit-btn');
    
    if (!start) return;
    
    // Ensure end date is not before start date
    document.getElementById('borrow-end').min = start;
    if (end && end < start) {
      document.getElementById('borrow-end').value = start;
      end = start;
    }
    
    if (!start || !end) {
        app.updateBorrowQuote(0);
        btn.disabled = true;
        return;
    }
    
    msg.innerHTML = 'Checking availability...';
    msg.style.color = 'inherit';
    btn.disabled = true;
    
    const itemId = document.getElementById('borrow-item-id').value;
    
    try {
      const res = await fetch(`${API_BASE}/rentals/check-availability`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          item_id: parseInt(itemId),
          start_date: start,
          end_date: end
        })
      });
      const data = await res.json();
      
      if (data.available) {
        msg.innerHTML = `✅ ${data.message}`;
        msg.style.color = 'var(--success)';
        btn.disabled = false;
        app.updateBorrowQuote(data.days);
      } else {
        msg.innerHTML = `❌ ${data.message || 'Unavailable'}`;
        msg.style.color = 'var(--danger)';
        btn.disabled = true;
        app.updateBorrowQuote(0);
      }
    } catch (e) {
      msg.innerHTML = `❌ Error checking availability.`;
      msg.style.color = 'var(--danger)';
    }
  },

  updateBorrowQuote: (days) => {
    const form = document.getElementById('borrow-form');
    const price = parseFloat(form.dataset.price || 0);
    const deposit = parseFloat(form.dataset.deposit || 0);
    
    document.getElementById('borrow-quote-daily').textContent = `${app.formatCurrency(price)}`;
    document.getElementById('borrow-quote-duration').textContent = `${days} days`;
    document.getElementById('borrow-quote-total').textContent = app.formatCurrency(price * days);
    document.getElementById('borrow-quote-deposit').textContent = app.formatCurrency(deposit);
    document.getElementById('borrow-quote-payable').textContent = app.formatCurrency((price * days) + deposit);
  },

  handleBorrowSubmit: async (e) => {
    e.preventDefault();
    const itemId = document.getElementById('borrow-item-id').value;
    const start = document.getElementById('borrow-start').value;
    const end = document.getElementById('borrow-end').value;
    
    const btn = document.getElementById('borrow-submit-btn');
    btn.disabled = true;
    btn.textContent = 'Submitting...';
    
    try {
      await app.apiCall('/rentals', {
        method: 'POST',
        body: { 
          item_id: parseInt(itemId), 
          start_date: start,
          end_date: end,
          days: 1 // fallback for schema if we need it, but backend recalculates
        }
      });
      app.showToast('Rental request sent successfully!', 'success');
      app.closeModal('modal-borrow');
      app.loadRentals();
      app.navigateTo('rentals');
    } catch (e) {
      btn.disabled = false;
      btn.textContent = 'Submit Borrow Request';
    }
  },

  /**
   * RENTALS MANAGEMENT
   */
  setRentalTab: (tab) => {
    app.activeRentalTab = tab;
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.getElementById(`tab-as-${tab}`).classList.add('active');
    app.renderRentalsList();
  },

  loadRentals: async () => {
    const list = document.getElementById('rentals-list-container');
    list.innerHTML = `<div class="loading-state">Loading transactions...</div>`;
    try {
      const all = await app.apiCall('/rentals');
      app.myRentals.renter = all.filter(r => r.renter_id === app.currentUser?.id);
      app.myRentals.owner = all.filter(r => r.owner_id === app.currentUser?.id);
      app.renderRentalsList();
    } catch (e) {
      list.innerHTML = `<div class="empty-state">Error loading rentals</div>`;
    }
  },

  renderRentalsList: () => {
    const list = document.getElementById('rentals-list-container');
    const rentals = app.myRentals[app.activeRentalTab];

    if (rentals.length === 0) {
      list.innerHTML = `<div class="empty-state">
        <div class="empty-state-icon">📋</div>
        <div class="empty-state-title">No rental history</div>
        <div class="empty-state-desc">You haven't ${app.activeRentalTab === 'renter' ? 'borrowed' : 'lent'} anything yet.</div>
      </div>`;
      return;
    }

    list.innerHTML = rentals.map(r => `
      <div class="rental-card">
        <div class="rental-top">
          <div>
            <div class="rental-title-row">
              <span class="badge badge-neutral">${app.escapeHtml(r.item_category)}</span>
              <div class="rental-title">${app.escapeHtml(r.item_title)}</div>
            </div>
            <div class="rental-meta">
                ${r.start_date && r.end_date ? `<strong>${r.start_date} &rarr; ${r.end_date}</strong> (${r.days} days)<br>` : `${r.days} days<br>`}
                Total: <strong>${app.formatCurrency(r.total_price)}</strong> &bull; 
                Deposit: <strong>${app.formatCurrency(r.deposit_amount)}</strong>
              </div>
          </div>
          ${app.renderStepper(r.booking_status, r.deposit_status)}
        </div>
        
        <div class="rental-payment-status" style="margin-top: 1rem; padding: 0.75rem; background: var(--bg-surface); border-radius: var(--radius-md); border-left: 4px solid var(--primary);">
          ${app.activeRentalTab === 'owner' ? `
            <strong>Payment Status:</strong> 
            ${r.booking_status === 'pending' ? 'Waiting for your approval before charging borrower.' :
              r.deposit_status === 'held' ? `<span style="color:var(--success)">Secured in Escrow</span> (Total: ${app.formatCurrency(r.total_price + r.deposit_amount)}) - The rental fee and deposit have been collected from the borrower.` :
              r.deposit_status === 'disputed' ? `<span style="color:var(--danger)">Funds Frozen in Escrow</span> due to active dispute.` :
              r.deposit_status === 'resolved' || r.booking_status === 'completed' ? `<span style="color:var(--success)">Payout Complete</span> (You earned ${app.formatCurrency(r.total_price)}) - Deposit was returned.` :
              r.booking_status === 'rejected' ? 'No payment collected (Request rejected).' : 'Pending'}
          ` : `
            <strong>Payment Status:</strong>
            ${r.booking_status === 'pending' ? 'Not charged yet. Waiting for owner approval.' :
              r.deposit_status === 'held' ? `<span style="color:var(--primary)">Funds Held in Escrow</span> (Total: ${app.formatCurrency(r.total_price + r.deposit_amount)})` :
              r.deposit_status === 'disputed' ? `<span style="color:var(--danger)">Funds Frozen in Escrow</span>` :
              r.deposit_status === 'resolved' || r.booking_status === 'completed' ? `<span style="color:var(--success)">Deposit Refunded</span> (Rental Fee paid: ${app.formatCurrency(r.total_price)})` :
              r.booking_status === 'rejected' ? 'Request rejected. You were not charged.' : 'Pending'}
          `}
        </div>

        ${r.deposit_status === 'disputed' ? `
          <div class="rental-dispute-box">
            <strong>Dispute Active:</strong> ${app.escapeHtml(r.dispute_reason)}
          </div>
        ` : ''}
        
        ${r.booking_status === 'completed' && r.condition_rating ? `
          <div class="rental-rating">Condition Rated: <strong>${r.condition_rating}/5</strong></div>
        ` : ''}

        <div class="rental-actions">
          ${app.renderRentalActions(r, app.activeRentalTab)}
          <button class="btn btn-secondary btn-sm" onclick="app.viewPassport(${r.item_id})">View Passport</button>
          <button class="btn btn-secondary btn-sm" onclick="app.openChatModal(${r.id})">Message ${app.activeRentalTab === 'renter' ? 'Owner' : 'Renter'}</button>
        </div>
      </div>
    `).join('');
  },

  renderStepper: (bStatus, dStatus) => {
    const states = [
      { label: 'Pending', active: bStatus === 'pending', done: bStatus !== 'pending' },
      { label: 'Approved', active: bStatus === 'approved', done: ['returned', 'completed'].includes(bStatus) },
      { label: 'Returned', active: bStatus === 'returned', done: bStatus === 'completed' },
      { label: 'Settled', active: false, done: bStatus === 'completed' && dStatus !== 'disputed' }
    ];

    if (dStatus === 'disputed') {
      states[3] = { label: 'Disputed', active: true, done: false, danger: true };
    }

    return `
      <div class="stepper">
        ${states.map((s, i) => `
          <div class="step ${s.active ? 'active' : ''} ${s.done ? 'done' : ''} ${s.danger ? 'disputed' : ''}">
            ${s.done ? '✓' : (i + 1)} ${s.label}
          </div>
          ${i < states.length - 1 ? '<span class="step-arrow">&rarr;</span>' : ''}
        `).join('')}
      </div>
    `;
  },

  renderRentalActions: (r, tab) => {
    let html = '';
    const b = r.booking_status;
    const d = r.deposit_status;

    if (tab === 'owner') {
      if (b === 'pending') {
        html += `<button class="btn btn-primary btn-sm" onclick="app.actionRental(${r.id}, 'accept')">Accept &amp; Hold Deposit</button>`;
        html += `<button class="btn btn-danger btn-sm" onclick="app.actionRental(${r.id}, 'reject')">Reject</button>`;
      }
      if (b === 'returned' && d === 'held') {
        html += `<button class="btn btn-success btn-sm" onclick="app.openConfirmReturn(${r.id})">Inspect &amp; Release Deposit</button>`;
        html += `<button class="btn btn-danger btn-sm" onclick="app.openDispute(${r.id})">Open Dispute</button>`;
      }
      if (d === 'disputed') {
        html += `<button class="btn btn-warning btn-sm" onclick="app.openResolve(${r.id})">Resolve Dispute</button>`;
      }
    } else {
      // Renter
      if (b === 'approved') {
        html += `<button class="btn btn-primary btn-sm" onclick="app.actionRental(${r.id}, 'return')">Mark as Returned</button>`;
      }

      if (b === 'completed') {
        html += `<button class="btn btn-primary btn-sm" onclick="app.openOwnerReview(${r.id})">Rate Owner</button>`;
        html += `<button class="btn btn-primary btn-sm" onclick="app.openItemReview(${r.id})">Rate Item</button>`;
      }

    }
    return html;
  },

  actionRental: async (id, action) => {
    try {
      let body = {};
      if (action === 'return') body = { return_on_time: true, condition_after: {} };
      
      await app.apiCall(`/rentals/${id}/${action}`, { method: 'POST', body });
      app.showToast(`Successfully performed: ${action}`, 'success');
      app.loadRentals();
    } catch (e) {}
  },

  openConfirmReturn: (id) => {
    document.getElementById('confirm-rental-id').value = id;
    app.openModal('modal-confirm-return');
  },
  
  handleConfirmReturn: async (e) => {
    e.preventDefault();
    const id = document.getElementById('confirm-rental-id').value;
    const rating = document.getElementById('confirm-rating').value;
    const notes = document.getElementById('confirm-notes').value;
    try {
      await app.apiCall(`/rentals/${id}/confirm`, {
        method: 'POST', body: { condition_rating: parseInt(rating), condition_notes: notes }
      });
      app.showToast('Escrow released to renter!', 'success');
      app.closeModal('modal-confirm-return');
      app.loadRentals();
    } catch (e) {}
  },

  openDispute: (id) => {
    document.getElementById('dispute-rental-id').value = id;
    app.openModal('modal-dispute');
  },

  handleDisputeSubmit: async (e) => {
    e.preventDefault();
    const id = document.getElementById('dispute-rental-id').value;
    const reason = document.getElementById('dispute-reason').value;
    try {
      await app.apiCall(`/rentals/${id}/dispute`, { method: 'POST', body: { reason } });
      app.showToast('Dispute opened. Escrow frozen.', 'warning');
      app.closeModal('modal-dispute');
      app.loadRentals();
    } catch (e) {}
  },

  openResolve: (id) => {
    document.getElementById('resolve-rental-id').value = id;
    app.openModal('modal-resolve');
  },

  handleResolveSubmit: async (e) => {
    e.preventDefault();
    const id = document.getElementById('resolve-rental-id').value;
    const resolution = document.getElementById('resolve-payout').value;
    try {
      await app.apiCall(`/rentals/${id}/resolve`, { method: 'POST', body: { resolution } });
      app.showToast('Dispute resolved.', 'success');
      app.closeModal('modal-resolve');
      app.loadRentals();
    } catch (e) {}
  },

  /**
   * PASSPORT
   */
  
  // PRODUCT DETAILS & MANAGEMENT
  openProductModal: async (itemId) => {
    app.openModal('modal-product');
    const container = document.getElementById('product-modal-content');
    container.innerHTML = '<div class="loading-state">Loading item history & details...</div>';
    
    try {
      const hist = await app.apiCall(`/items/${itemId}/history`);
      if (!hist) return;
      
      const isOwner = app.currentUser && app.currentUser.id && app.currentUser.name === hist.owner_name;
      
      let html = `
        <div style="display:flex; gap: 1.5rem; flex-wrap: wrap; margin-bottom: 1.5rem;">
          <div style="flex:1; min-width: 250px;">
            <h2 style="margin-bottom: 0.5rem; font-size:1.5rem; color:var(--text-primary);">${app.escapeHtml(hist.title)}</h2>
            <div style="margin-bottom: 1rem;"><span class="badge badge-neutral">${app.escapeHtml(hist.category)}</span></div>
            <p style="color:var(--text-secondary); margin-bottom:1rem;">${app.escapeHtml(hist.description)}</p>
            <div style="background:var(--bg-surface); padding: 1rem; border-radius:var(--radius-md); border: 1px solid var(--border);">
               <div style="margin-bottom:0.5rem;"><strong>Owner:</strong> ${app.escapeHtml(hist.owner_name)}</div>
               <div style="margin-bottom:0.5rem;"><strong>Status:</strong> ${hist.is_listed ? '<span style="color:var(--success);font-weight:bold;">Listed</span>' : '<span style="color:var(--danger);font-weight:bold;">Unlisted</span>'}</div>
               <div><strong>Available:</strong> ${hist.available ? 'Yes' : 'No'}</div>
            </div>
          </div>
          
          <div style="flex:1; min-width: 250px; background:var(--bg-body); padding: 1rem; border-radius:var(--radius-md); border: 1px solid var(--border);">
            <h4 style="margin-bottom: 1rem; color:var(--text-primary);">RENTAL HISTORY SUMMARY</h4>
            <div style="display:flex; justify-content:space-between; margin-bottom:0.5rem; padding-bottom:0.5rem; border-bottom:1px solid var(--border);">
               <span>Used/Rented</span>
               <strong>${hist.stats.total_completed_rentals} times</strong>
            </div>
            <div style="display:flex; justify-content:space-between; margin-bottom:0.5rem; padding-bottom:0.5rem; border-bottom:1px solid var(--border);">
               <span>Total Rental Days</span>
               <strong>${hist.stats.total_rental_days} days</strong>
            </div>
            <div style="display:flex; justify-content:space-between; margin-bottom:0.5rem; padding-bottom:0.5rem; border-bottom:1px solid var(--border);">
               <span>Average Item Rating</span>
               <strong>${hist.stats.review_count > 0 ? `⭐⭐⭐⭐⭐ ${hist.stats.average_rating}/5` : 'No reviews yet'}</strong>
            </div>
            <div style="display:flex; justify-content:space-between; margin-bottom:0.5rem;">
               <span>Total Item Reviews</span>
               <strong>${hist.stats.review_count}</strong>
            </div>
          </div>
        </div>
        
        <div style="margin-bottom: 2rem; padding: 1rem; background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-md);">
          <h4 style="margin-bottom: 1rem;">PREVIOUS BORROWER REVIEWS</h4>
          ${(!hist.item_reviews || hist.item_reviews.length === 0) ? '<p style="color:var(--text-secondary);">No reviews yet.</p>' : 
            hist.item_reviews.map(r => `
              <div style="margin-bottom: 1rem; padding-bottom: 1rem; border-bottom: 1px solid var(--border);">
                <div style="color: #f1c40f; margin-bottom: 0.25rem;">${'⭐'.repeat(r.rating)}</div>
                <p style="margin-bottom: 0.5rem;">"${app.escapeHtml(r.comment)}"</p>
                <div style="font-size: 0.8rem; color: var(--text-secondary);">
                  By: <strong>${app.escapeHtml(r.reviewer_name)}</strong> &bull; ${new Date(r.created_at).toLocaleDateString()}
                  <br>Condition: ${app.escapeHtml(r.product_condition)}
                </div>
              </div>
            `).join('')}
        </div>
        
        <div style="margin-bottom: 2rem; padding: 1rem; background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-md);">
          <h4 style="margin-bottom: 1rem;">ITEM HISTORY</h4>
          <ul style="list-style-type: disc; margin-left: 1.5rem; color: var(--text-secondary);">
            <li>Listed on ${new Date(hist.created_at).toLocaleDateString()}</li>
            ${hist.stats.total_completed_rentals > 0 ? `<li>Rental completed (${hist.stats.total_completed_rentals} times)</li>` : ''}
          </ul>
        </div>

        </div>
      `;
      
      // Owner Actions
      if (isOwner) {
        html += `
          <div style="margin-bottom: 2rem; padding: 1rem; background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-md);">
            <h4 style="margin-bottom: 1rem;">Owner Dashboard</h4>
            <p style="margin-bottom: 1rem; font-size: 0.9rem; color: var(--text-secondary);">Manage the listing status of your item. Unlisting will hide it from new requests, but preserve all historical data and allow active rentals to finish.</p>
            <div style="display:flex; gap: 1rem;">
              ${hist.is_listed 
                ? `<button class="btn btn-warning" onclick="app.toggleListing(${hist.item_id}, false)">Unlist Item</button>`
                : `<button class="btn btn-success" onclick="app.toggleListing(${hist.item_id}, true)">List Item</button>`
              }
            </div>
          </div>
        `;
        
        // Rental History (Private)
        if (hist.rental_history && hist.rental_history.length > 0) {
            html += `<h4 style="margin-bottom: 1rem;">Private Rental History</h4>`;
            html += `<div style="overflow-x:auto;"><table class="table" style="width:100%; text-align:left; border-collapse:collapse; margin-bottom: 2rem;">
              <thead style="background:var(--bg-surface);">
                <tr>
                  <th style="padding:0.5rem;">ID</th>
                  <th style="padding:0.5rem;">Borrower</th>
                  <th style="padding:0.5rem;">Dates</th>
                  <th style="padding:0.5rem;">Days</th>
                  <th style="padding:0.5rem;">Status</th>
                </tr>
              </thead>
              <tbody>
            `;
            for (const r of hist.rental_history) {
              html += `
                <tr style="border-bottom:1px solid var(--border);">
                  <td style="padding:0.5rem;">#${r.rental_id}</td>
                  <td style="padding:0.5rem;">${app.escapeHtml(r.renter_name || 'Unknown')}</td>
                  <td style="padding:0.5rem;">${app.formatDate(r.start_date)} - ${app.formatDate(r.end_date)}</td>
                  <td style="padding:0.5rem;">${r.days}</td>
                  <td style="padding:0.5rem;"><span class="badge badge-neutral">${r.booking_status}</span></td>
                </tr>
              `;
            }
            html += `</tbody></table></div>`;
        }
      }
      
      // Activity
      html += `<h4 style="margin-bottom: 1rem;">Item Activity Timeline</h4>`;
      if (hist.activity_events && hist.activity_events.length > 0) {
         html += `<div class="timeline" style="max-height:300px; overflow-y:auto; padding-right:1rem;">`;
         for (const e of hist.activity_events) {
            const time = app.formatDate(e.timestamp.split('T')[0]);
            html += `
              <div class="timeline-event" style="margin-bottom: 1rem;">
                <div class="timeline-dot" style="display:flex;align-items:center;justify-content:center;background:var(--bg-surface);border:1px solid var(--border);font-size:12px;">🕒</div>
                <div class="timeline-card" style="padding: 0.75rem; background: var(--bg-surface); border-radius: var(--radius-sm); border: 1px solid var(--border);">
                  <div style="font-weight:600;">${app.escapeHtml(e.event_type)}</div>
                  <div style="font-size:0.85rem; color:var(--text-secondary); margin-top:0.25rem;">${app.escapeHtml(e.details.action || JSON.stringify(e.details))}</div>
                  <div style="font-size:0.75rem; color:var(--text-muted); margin-top:0.25rem;">${time} - ${app.escapeHtml(e.event_hash.substring(0,8))}</div>
                </div>
              </div>
            `;
         }
         html += `</div>`;
      } else {
         html += `<p>No activity yet.</p>`;
      }
      
      container.innerHTML = html;
    } catch (e) {
      container.innerHTML = `<div class="form-error">Failed to load item details: ${e.message}</div>`;
    }
  },
  
  toggleListing: async (itemId, isListed) => {
    const action = isListed ? "List" : "Unlist";
    if (!confirm(`${action} this item? ${!isListed ? "It will no longer be available for new rental requests." : ""}`)) return;
    
    try {
      const res = await app.apiCall(`/items/${itemId}/listing`, {
         method: 'PATCH',
         body: { is_listed: isListed }
      });
      if (res && !res.error) {
         app.showToast(`Item ${isListed ? "listed" : "unlisted"} successfully`, 'success');
         // Reload modal
         app.openProductModal(itemId);
         // Reload items in browse if we are there
         if (app.currentView === 'browse') {
            app.loadBrowseItems();
         }
      }
    } catch (e) {
      app.showToast(e.message || "Failed to change status", "error");
    }
  },

  viewPassport: async (itemId) => {
    app.navigateTo('passport');
    const container = document.getElementById('passport-timeline');
    const banner = document.getElementById('passport-banner');
    
    container.innerHTML = `<div class="loading-state">Auditing cryptographic chain...</div>`;
    banner.className = 'passport-banner';
    banner.innerHTML = `<div><div class="passport-title">Verifying Ledger...</div></div>`;

    try {
      const p = await app.apiCall(`/items/${itemId}/passport`);
      
      // Update banner
      banner.className = `passport-banner ${p.is_valid ? 'valid' : 'invalid'}`;
      document.getElementById('passport-status-icon').textContent = p.is_valid ? '✅' : '🚨';
      document.getElementById('passport-status-text').textContent = p.is_valid ? 'Passport Valid' : 'TAMPER DETECTED';
      document.getElementById('passport-status-sub').textContent = p.is_valid 
        ? `Chain of ${p.total_events} events verified` 
        : `Cryptographic integrity broken at sequence #${p.broken_at_seq}`;
      
      const tc = document.getElementById('passport-tamper-control');
      if (p.is_valid && p.events.length > 1) {
        const evToTamper = p.events[p.events.length - 1].id;
        tc.innerHTML = `<button class="btn btn-warning btn-sm" onclick="app.tamperEvent(${itemId}, ${evToTamper})">Simulate Tampering (Demo)</button>`;
      } else {
        tc.innerHTML = '';
      }

      // Render timeline
      container.innerHTML = p.events.map(e => `
        <div class="timeline-event ${(!p.is_valid && e.seq >= p.broken_at_seq) ? 'broken' : ''}">
          <div class="timeline-dot"></div>
          <div class="timeline-card">
            <div class="timeline-top">
              <span class="badge badge-neutral" style="background:var(--primary-soft);color:var(--primary);border-color:transparent">${app.escapeHtml(e.event_type.replace('_', ' '))}</span>
              <span class="timeline-seq">SEQ #${e.seq} &bull; ${app.formatDate(e.timestamp)}</span>
            </div>
            
            <div class="timeline-hash-row">
              <span class="timeline-hash-label">Prev Hash</span>
              <span class="timeline-hash">${app.escapeHtml(e.prev_hash)}</span>
            </div>
            <div class="timeline-hash-row">
              <span class="timeline-hash-label">Event Hash</span>
              <span class="timeline-hash event">${app.escapeHtml(e.event_hash)}</span>
            </div>
            
            <div class="timeline-details">${app.escapeHtml(e.details)}</div>
          </div>
        </div>
      `).join('');

    } catch (e) {
      container.innerHTML = `<div class="empty-state">Failed to load passport.</div>`;
    }
  },

  tamperEvent: async (itemId, eventId) => {
    try {
      await app.apiCall(`/demo/tamper/${eventId}`, { method: 'POST' });
      app.showToast('Record tampered in DB! Re-verifying chain...', 'warning');
      setTimeout(() => app.viewPassport(itemId), 1000);
    } catch (e) {}
  },

  /**
   * REPUTATION
   */
  loadReputation: async () => {
    if (!app.currentUser) return;
    document.getElementById('profile-location-input').value = app.currentUser.dorm || '';
      if (!app.currentUser.dorm) {
        app.autoLocate();
      }
    try {
      const rep = await app.apiCall(`/users/${app.currentUser.id}/reputation`);
      
      const rc = document.getElementById('renter-rep-content');
      if (!rep.renter.has_history) rc.innerHTML = `<div class="empty-state" style="padding:var(--sp-6) 0;border:none">No borrowing history yet</div>`;
      else {
        rc.innerHTML = `
          <div class="metric-row"><span class="metric-label">Completed Rentals</span><span class="metric-val">${rep.renter.successful_rentals}</span></div>
          <div class="metric-row"><span class="metric-label">On-Time Return</span><span class="metric-val" style="color:var(--success)">${rep.renter.return_punctuality_pct}%</span></div>
          <div class="metric-row"><span class="metric-label">Item Care (5★)</span><span class="metric-val" style="color:var(--success)">${rep.renter.item_care_pct}%</span></div>
          <div class="metric-row"><span class="metric-label">Disputes</span><span class="metric-val">${rep.renter.dispute_count}</span></div>
        `;
      }

      const oc = document.getElementById('owner-rep-content');
      if (!rep.owner.has_history && !rep.owner.total_reviews) {
        oc.innerHTML = `<div class="empty-state" style="padding:var(--sp-6) 0;border:none">No lending history or reviews yet</div>`;
      } else {
        oc.innerHTML = `
          <div class="metric-row"><span class="metric-label">Completed Rentals</span><span class="metric-val">${rep.owner.total_completed || 0}</span></div>
          <div class="metric-row"><span class="metric-label">Average Service Rating</span><span class="metric-val" style="color:var(--success)">
            ${rep.owner.total_reviews > 0 ? `⭐⭐⭐⭐⭐ ${rep.owner.average_service_rating}/5` : 'No reviews yet'}
          </span></div>
          <div class="metric-row"><span class="metric-label">Total Reviews</span><span class="metric-val">${rep.owner.total_reviews || 0}</span></div>
          <div class="metric-row"><span class="metric-label">Acceptance Reliability</span><span class="metric-val" style="color:var(--success)">${rep.owner.reliability_pct ? rep.owner.reliability_pct + '%' : 'N/A'}</span></div>
          <div class="metric-row"><span class="metric-label">Disputes</span><span class="metric-val">${rep.owner.dispute_count || 0}</span></div>
        `;
        
        if (rep.owner.reviews && rep.owner.reviews.length > 0) {
          oc.innerHTML += `
            <div style="margin-top: 2rem; padding-top: 1rem; border-top: 1px solid var(--border);">
              <h4 style="margin-bottom: 1rem;">Owner Service Reviews</h4>
              ${rep.owner.reviews.map(r => `
                <div style="margin-bottom: 1rem; padding-bottom: 1rem; border-bottom: 1px solid var(--border);">
                  <div style="color: #f1c40f; margin-bottom: 0.25rem;">${'⭐'.repeat(r.rating)}</div>
                  <p style="margin-bottom: 0.5rem; font-style: italic;">"${app.escapeHtml(r.comment)}"</p>
                  <div style="font-size: 0.8rem; color: var(--text-secondary);">
                    By: <strong>${app.escapeHtml(r.reviewer_name)}</strong> &bull; ${new Date(r.created_at).toLocaleDateString()}<br>
                    Product Condition: ${app.escapeHtml(r.product_condition)} | Price: ${app.escapeHtml(r.price_fairness)}
                  </div>
                </div>
              `).join('')}
            </div>
          `;
        }
      }
    } catch (e) {}
  }
};

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', () => {
  // Setup category select listener for list item
  document.getElementById('item-category')?.addEventListener('change', app.renderChecklistForm);
  app.init();
});
