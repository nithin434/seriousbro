/* 
LinkedIn Profile Roast Widget for Dashboard
Add this to your dash.html in the bottom right corner
*/

// CSS for the roast widget (add to your stylesheet)
const roastWidgetCSS = `
.roast-widget {
    position: fixed;
    bottom: 20px;
    right: 20px;
    width: 350px;
    max-height: 500px;
    background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
    border-radius: 16px;
    box-shadow: 0 10px 25px rgba(0, 0, 0, 0.3);
    z-index: 1000;
    transition: all 0.3s ease;
    overflow: hidden;
    border: 1px solid #475569;
}

.roast-widget.collapsed {
    height: 60px;
    width: 200px;
}

.roast-widget.expanded {
    height: auto;
    max-height: 500px;
}

.roast-header {
    background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
    color: white;
    padding: 12px 16px;
    cursor: pointer;
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-weight: 600;
    font-size: 14px;
}

.roast-header:hover {
    background: linear-gradient(135deg, #dc2626 0%, #b91c1c 100%);
}

.roast-icon {
    font-size: 18px;
    margin-right: 8px;
}

.roast-content {
    padding: 16px;
    color: #e2e8f0;
    max-height: 400px;
    overflow-y: auto;
}

.roast-input-section {
    margin-bottom: 16px;
}

.roast-input {
    width: 100%;
    padding: 10px;
    border: 1px solid #475569;
    border-radius: 8px;
    background: #374151;
    color: #e2e8f0;
    font-size: 12px;
    margin-bottom: 8px;
}

.roast-input::placeholder {
    color: #9ca3af;
}

.roast-button {
    width: 100%;
    padding: 10px;
    background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
    color: white;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    font-weight: 600;
    font-size: 12px;
    transition: all 0.3s ease;
}

.roast-button:hover {
    background: linear-gradient(135deg, #dc2626 0%, #b91c1c 100%);
    transform: translateY(-1px);
}

.roast-button:disabled {
    background: #6b7280;
    cursor: not-allowed;
    transform: none;
}

.roast-result {
    background: #1f2937;
    border-radius: 8px;
    padding: 12px;
    margin-top: 12px;
    border-left: 4px solid #ef4444;
}

.roast-level {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 10px;
    font-weight: 600;
    margin-bottom: 8px;
}

.roast-level.mild { background: #22c55e; color: white; }
.roast-level.witty { background: #f59e0b; color: white; }
.roast-level.savage { background: #ef4444; color: white; }
.roast-level.nuclear { background: #7c3aed; color: white; }

.roast-text {
    font-size: 13px;
    line-height: 1.4;
    margin-bottom: 10px;
}

.roast-quote {
    font-style: italic;
    color: #fbbf24;
    font-size: 12px;
    border-top: 1px solid #374151;
    padding-top: 8px;
    margin-top: 8px;
}

.roast-actions {
    display: flex;
    gap: 8px;
    margin-top: 12px;
}

.roast-action-btn {
    flex: 1;
    padding: 6px;
    background: #374151;
    color: #e2e8f0;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    font-size: 11px;
    transition: background 0.3s ease;
}

.roast-action-btn:hover {
    background: #4b5563;
}

.loading-spinner {
    display: inline-block;
    width: 16px;
    height: 16px;
    border: 2px solid #374151;
    border-radius: 50%;
    border-top-color: #ef4444;
    animation: spin 1s ease-in-out infinite;
}

@keyframes spin {
    to { transform: rotate(360deg); }
}

.error-message {
    color: #fca5a5;
    font-size: 12px;
    margin-top: 8px;
}

.success-message {
    color: #86efac;
    font-size: 12px;
    margin-top: 8px;
}

/* Mobile responsive */
@media (max-width: 768px) {
    .roast-widget {
        width: 300px;
        right: 10px;
        bottom: 10px;
    }
    
    .roast-widget.collapsed {
        width: 180px;
    }
}
`;

// JavaScript for the roast widget
class LinkedInRoastWidget {
    constructor() {
        this.isExpanded = false;
        this.isLoading = false;
        this.currentRoast = null;
        this.init();
    }

    init() {
        this.injectCSS();
        this.createWidget();
        this.bindEvents();
    }

    injectCSS() {
        const style = document.createElement('style');
        style.textContent = roastWidgetCSS;
        document.head.appendChild(style);
    }

    createWidget() {
        const widget = document.createElement('div');
        widget.className = 'roast-widget collapsed';
        widget.id = 'roast-widget';
        
        widget.innerHTML = `
            <div class="roast-header" onclick="roastWidget.toggle()">
                <span><span class="roast-icon">🔥</span>LinkedIn Roaster</span>
                <span id="toggle-icon">▼</span>
            </div>
            <div class="roast-content" id="roast-content">
                <div class="roast-input-section">
                    <input 
                        type="text" 
                        class="roast-input" 
                        id="linkedin-url-input"
                        placeholder="Paste LinkedIn profile URL here..."
                    >
                    <button 
                        class="roast-button" 
                        id="roast-button"
                        onclick="roastWidget.roastProfile()"
                    >
                        🔥 Roast This Profile
                    </button>
                </div>
                <div id="roast-results"></div>
            </div>
        `;
        
        document.body.appendChild(widget);
        this.widget = widget;
    }

    bindEvents() {
        // Enter key on input
        document.getElementById('linkedin-url-input').addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !this.isLoading) {
                this.roastProfile();
            }
        });

        // Auto-expand on focus
        document.getElementById('linkedin-url-input').addEventListener('focus', () => {
            if (!this.isExpanded) {
                this.toggle();
            }
        });
    }

    toggle() {
        this.isExpanded = !this.isExpanded;
        const widget = document.getElementById('roast-widget');
        const icon = document.getElementById('toggle-icon');
        
        if (this.isExpanded) {
            widget.classList.remove('collapsed');
            widget.classList.add('expanded');
            icon.textContent = '▲';
        } else {
            widget.classList.remove('expanded');
            widget.classList.add('collapsed');
            icon.textContent = '▼';
        }
    }

    async roastProfile() {
        const urlInput = document.getElementById('linkedin-url-input');
        const button = document.getElementById('roast-button');
        const resultsDiv = document.getElementById('roast-results');
        
        const url = urlInput.value.trim();
        if (!url) {
            this.showError('Please enter a LinkedIn profile URL');
            return;
        }

        if (!url.includes('linkedin.com')) {
            this.showError('Please enter a valid LinkedIn URL');
            return;
        }

        this.isLoading = true;
        button.disabled = true;
        button.innerHTML = '<span class="loading-spinner"></span> Roasting...';
        
        try {
            // First check for cached roast
            const cachedResponse = await fetch(`/api/get-cached-roast?profile_url=${encodeURIComponent(url)}`);
            const cachedData = await cachedResponse.json();
            
            if (cachedData.success && cachedData.cached) {
                this.displayRoast(cachedData.data, true);
            } else {
                // Generate new roast
                const response = await fetch('/api/roast-profile', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        profile_url: url,
                        user_interests: [],
                        tone: 'witty'
                    })
                });

                const data = await response.json();
                
                if (data.success) {
                    this.displayRoast(data, false);
                } else {
                    this.showError(data.error || 'Failed to roast profile');
                }
            }
        } catch (error) {
            console.error('Roast error:', error);
            this.showError('Network error. Please try again.');
        } finally {
            this.isLoading = false;
            button.disabled = false;
            button.innerHTML = '🔥 Roast This Profile';
        }
    }

    displayRoast(data, fromCache) {
        const resultsDiv = document.getElementById('roast-results');
        const roast = data.roast || data;
        
        const cacheIndicator = fromCache ? '<span style="color: #86efac; font-size: 10px;">📱 From cache</span>' : '';
        
        resultsDiv.innerHTML = `
            <div class="roast-result">
                <div class="roast-level ${roast.roast_level || 'witty'}">${roast.roast_level || 'witty'}</div>
                ${cacheIndicator}
                
                <div class="roast-text">
                    ${this.truncateText(roast.complete_roast_summary || roast.overall_verdict, 300)}
                </div>
                
                <div class="roast-quote">
                    💎 "${roast.comedy_gold_quote || 'No quote available'}"
                </div>
                
                <div class="roast-actions">
                    <button class="roast-action-btn" onclick="roastWidget.shareRoast()">Share 📤</button>
                    <button class="roast-action-btn" onclick="roastWidget.newRoast()">New 🔄</button>
                    <button class="roast-action-btn" onclick="roastWidget.showFullRoast()">Full 📖</button>
                </div>
            </div>
        `;
        
        this.currentRoast = data;
        this.showSuccess('Profile roasted successfully! 🔥');
    }

    truncateText(text, maxLength) {
        if (!text) return 'No roast available';
        if (text.length <= maxLength) return text;
        return text.substring(0, maxLength) + '...';
    }

    shareRoast() {
        if (!this.currentRoast) return;
        
        const roast = this.currentRoast.roast || this.currentRoast;
        const text = `Check out this LinkedIn profile roast! 🔥\n\n"${roast.comedy_gold_quote}"\n\nGenerated by SYNTEXA`;
        
        if (navigator.share) {
            navigator.share({
                title: 'LinkedIn Profile Roast',
                text: text,
                url: window.location.href
            });
        } else {
            // Fallback to clipboard
            navigator.clipboard.writeText(text).then(() => {
                this.showSuccess('Roast copied to clipboard! 📋');
            });
        }
    }

    newRoast() {
        document.getElementById('linkedin-url-input').value = '';
        document.getElementById('roast-results').innerHTML = '';
        this.currentRoast = null;
    }

    showFullRoast() {
        if (!this.currentRoast) return;
        
        const roast = this.currentRoast.roast || this.currentRoast;
        const modal = document.createElement('div');
        modal.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0,0,0,0.8);
            z-index: 10000;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        `;
        
        modal.innerHTML = `
            <div style="
                background: #1f2937;
                border-radius: 16px;
                padding: 24px;
                max-width: 600px;
                max-height: 80vh;
                overflow-y: auto;
                color: #e2e8f0;
                position: relative;
            ">
                <button onclick="this.parentElement.parentElement.remove()" style="
                    position: absolute;
                    top: 12px;
                    right: 12px;
                    background: none;
                    border: none;
                    color: #9ca3af;
                    font-size: 24px;
                    cursor: pointer;
                ">×</button>
                
                <h3 style="color: #ef4444; margin-bottom: 16px;">🔥 Full LinkedIn Roast</h3>
                
                <div style="margin-bottom: 16px;">
                    <span class="roast-level ${roast.roast_level}">${roast.roast_level || 'witty'}</span>
                </div>
                
                <div style="line-height: 1.6; margin-bottom: 20px;">
                    ${roast.complete_roast_summary || 'No full roast available'}
                </div>
                
                <div style="background: #374151; padding: 12px; border-radius: 8px; font-style: italic; color: #fbbf24;">
                    "${roast.comedy_gold_quote || 'No quote available'}"
                </div>
                
                <div style="margin-top: 20px; padding-top: 16px; border-top: 1px solid #374151;">
                    <button onclick="roastWidget.shareRoast()" style="
                        background: #ef4444;
                        color: white;
                        border: none;
                        padding: 8px 16px;
                        border-radius: 6px;
                        cursor: pointer;
                        margin-right: 8px;
                    ">Share This Roast 📤</button>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        // Close on outside click
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.remove();
            }
        });
    }

    showError(message) {
        const resultsDiv = document.getElementById('roast-results');
        resultsDiv.innerHTML = `<div class="error-message">❌ ${message}</div>`;
    }

    showSuccess(message) {
        const content = document.getElementById('roast-content');
        const existingSuccess = content.querySelector('.success-message');
        if (existingSuccess) existingSuccess.remove();
        
        const successDiv = document.createElement('div');
        successDiv.className = 'success-message';
        successDiv.textContent = `✅ ${message}`;
        content.appendChild(successDiv);
        
        setTimeout(() => successDiv.remove(), 3000);
    }
}

// Initialize the widget when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.roastWidget = new LinkedInRoastWidget();
    });
} else {
    window.roastWidget = new LinkedInRoastWidget();
}

// Export for manual initialization
window.LinkedInRoastWidget = LinkedInRoastWidget;
