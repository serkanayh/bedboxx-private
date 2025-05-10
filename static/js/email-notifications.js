/**
 * Real-time Email Notifications System
 * 
 * This script provides real-time notifications for new emails using a polling approach.
 */

class EmailNotificationSystem {
    constructor(options = {}) {
        // Default configuration
        this.config = {
            checkInterval: options.checkInterval || 30000, // 30 seconds default
            notificationTimeout: options.notificationTimeout || 7000, // 7 seconds default
            apiEndpoint: options.apiEndpoint || '/emails/api/check-new-emails/',
            notificationSound: options.notificationSound || '/static/sounds/notification.mp3',
            enableSound: options.enableSound !== undefined ? options.enableSound : true,
            lastCheckTime: null,
            maxNotifications: options.maxNotifications || 5,
            autoRefresh: options.autoRefresh !== undefined ? options.autoRefresh : false,
            onNewEmail: options.onNewEmail || null
        };

        // Internal state
        this.isPolling = false;
        this.intervalId = null;
        this.totalUnread = 0;
        this.notificationQueue = [];
        this.audioElement = null;

        // Initialize the notification system
        this.init();
    }

    init() {
        // Create audio element if sound is enabled
        if (this.config.enableSound) {
            this.audioElement = new Audio(this.config.notificationSound);
        }

        // Initialize notification container if not exists
        if (!document.getElementById('email-notification-container')) {
            const container = document.createElement('div');
            container.id = 'email-notification-container';
            container.style.cssText = `
                position: fixed;
                right: 20px;
                bottom: 20px;
                z-index: 9999;
                width: 350px;
                max-width: 100%;
            `;
            document.body.appendChild(container);
        }

        // Set the last check time to now
        this.config.lastCheckTime = new Date().toISOString();

        // Update unread count badge if it exists
        this.updateUnreadBadge();

        console.log('Email notification system initialized');
    }

    /**
     * Start polling for new emails
     */
    startPolling() {
        if (this.isPolling) return;

        this.isPolling = true;
        this.checkForNewEmails(); // Check immediately on start

        // Set up interval for regular checking
        this.intervalId = setInterval(() => {
            this.checkForNewEmails();
        }, this.config.checkInterval);

        console.log('Email polling started');
    }

    /**
     * Stop polling for new emails
     */
    stopPolling() {
        if (!this.isPolling) return;

        clearInterval(this.intervalId);
        this.intervalId = null;
        this.isPolling = false;

        console.log('Email polling stopped');
    }

    /**
     * Check for new emails since last check
     */
    checkForNewEmails() {
        // Use AJAX to check for new emails
        const url = `${this.config.apiEndpoint}?last_check=${encodeURIComponent(this.config.lastCheckTime)}`;
        
        fetch(url)
            .then(response => response.json())
            .then(data => {
                if (data.success && data.new_emails_count > 0) {
                    this.handleNewEmails(data.new_emails);
                    this.config.lastCheckTime = data.server_time;
                }
            })
            .catch(error => {
                console.error('Error checking for new emails:', error);
            });
    }

    /**
     * Handle new emails that were found
     */
    handleNewEmails(emails) {
        if (!emails || emails.length === 0) return;

        // Update total unread count
        this.totalUnread += emails.length;
        this.updateUnreadBadge();

        // Process each new email
        emails.forEach(email => {
            // Show notification for the email
            this.showNotification(email);
            
            // Call the onNewEmail callback if provided
            if (typeof this.config.onNewEmail === 'function') {
                this.config.onNewEmail(email);
            }
        });

        // Play notification sound
        if (this.config.enableSound && this.audioElement) {
            this.audioElement.play().catch(e => {
                console.warn('Could not play notification sound:', e);
            });
        }

        // Auto refresh the page if configured
        if (this.config.autoRefresh && window.location.pathname === '/emails/') {
            window.location.reload();
        }
    }

    /**
     * Show a notification for a new email
     */
    showNotification(email) {
        const container = document.getElementById('email-notification-container');
        if (!container) return;

        // Create notification element
        const notification = document.createElement('div');
        notification.className = 'email-notification';
        notification.style.cssText = `
            background-color: #fff;
            border-left: 4px solid #4a6bdf;
            border-radius: 4px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-top: 10px;
            padding: 15px;
            opacity: 0;
            transform: translateX(50px);
            transition: all 0.3s ease;
        `;

        // Create notification content
        notification.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                <h5 style="margin: 0; font-size: 16px; font-weight: 600; color: #333;">New Email</h5>
                <button class="close-notification" style="background: none; border: none; color: #999; cursor: pointer;">
                    <i class="bi bi-x"></i>
                </button>
            </div>
            <p style="margin: 8px 0 10px; font-size: 14px; color: #555; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                <span style="font-weight: 500;">${email.subject}</span>
            </p>
            <div style="font-size: 12px; color: #777;">
                <span>${email.sender}</span>
                <span style="margin-left: 10px;">${this.formatTimestamp(email.received_date)}</span>
            </div>
            <div style="margin-top: 10px;">
                <a href="${email.url}" class="view-email" style="color: #4a6bdf; text-decoration: none; font-size: 13px; font-weight: 500;">
                    View Email <i class="bi bi-arrow-right"></i>
                </a>
            </div>
        `;

        // Add to container
        container.appendChild(notification);

        // Limit the number of visible notifications
        this.manageNotificationQueue(notification);

        // Add event listener to close button
        const closeButton = notification.querySelector('.close-notification');
        closeButton.addEventListener('click', e => {
            e.preventDefault();
            this.removeNotification(notification);
        });

        // Add event listener to view email link
        const viewEmailLink = notification.querySelector('.view-email');
        viewEmailLink.addEventListener('click', e => {
            e.preventDefault(); // Prevent default link behavior
            this.removeNotification(notification);
            window.location.href = e.currentTarget.href; // Navigate in the same tab
        });

        // Show notification with animation
        setTimeout(() => {
            notification.style.opacity = '1';
            notification.style.transform = 'translateX(0)';
        }, 10);

        // Auto dismiss after timeout
        setTimeout(() => {
            this.removeNotification(notification);
        }, this.config.notificationTimeout);
    }

    /**
     * Remove a notification with animation
     */
    removeNotification(notification) {
        notification.style.opacity = '0';
        notification.style.transform = 'translateX(50px)';
        
        setTimeout(() => {
            notification.remove();
            
            // Remove from queue
            const index = this.notificationQueue.indexOf(notification);
            if (index !== -1) {
                this.notificationQueue.splice(index, 1);
            }
        }, 300);
    }

    /**
     * Manage notification queue to limit the number of visible notifications
     */
    manageNotificationQueue(notification) {
        this.notificationQueue.push(notification);
        
        // If we have too many notifications, remove the oldest one
        if (this.notificationQueue.length > this.config.maxNotifications) {
            const oldestNotification = this.notificationQueue.shift();
            this.removeNotification(oldestNotification);
        }
    }

    /**
     * Update the unread emails badge
     */
    updateUnreadBadge() {
        const badge = document.getElementById('unread-email-badge');
        if (badge) {
            if (this.totalUnread > 0) {
                badge.textContent = this.totalUnread;
                badge.style.display = 'inline-block';
            } else {
                badge.style.display = 'none';
            }
        }
    }

    /**
     * Reset the unread count (e.g., when user views the emails)
     */
    resetUnreadCount() {
        this.totalUnread = 0;
        this.updateUnreadBadge();
    }

    /**
     * Format a timestamp for display
     */
    formatTimestamp(timestamp) {
        const date = new Date(timestamp);
        const now = new Date();
        
        // If it's today, just show the time
        if (date.toDateString() === now.toDateString()) {
            return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        }
        
        // Otherwise show the date
        return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }
}

// Make available globally
window.EmailNotificationSystem = EmailNotificationSystem; 