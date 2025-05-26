// Dashboard JavaScript functionality for Marathon Training Dashboard

// Global variables
let chartInstances = {};

// Initialize dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initializeDashboard();
    initializeFeatherIcons();
    setupEventListeners();
});

/**
 * Initialize dashboard components
 */
function initializeDashboard() {
    console.log('Initializing Marathon Training Dashboard...');

    // Initialize any existing charts
    initializeCharts();

    // Setup auto-refresh for live data (optional)
    // setupAutoRefresh();

    // Initialize tooltips and popovers
    initializeBootstrapComponents();
}

/**
 * Initialize Feather icons
 */
function initializeFeatherIcons() {
    if (typeof feather !== 'undefined') {
        feather.replace();
    }
}

/**
 * Setup event listeners
 */
function setupEventListeners() {
    // Handle manual sync button clicks
    const manualSyncButtons = document.querySelectorAll('[onclick*="runManualTask"]');
    manualSyncButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            runManualTask();
        });
    });

    // Handle athlete toggle buttons
    const toggleButtons = document.querySelectorAll('[onclick*="toggleAthlete"]');
    toggleButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            const athleteId = this.getAttribute('onclick').match(/\d+/)[0];
            toggleAthlete(athleteId);
        });
    });

    // Handle date selector changes
    const dateSelector = document.getElementById('dateSelector');
    if (dateSelector) {
        dateSelector.addEventListener('change', function() {
            changeDashboardDate(this.value);
        });
    }
}

/**
 * Initialize Bootstrap components
 */
function initializeBootstrapComponents() {
    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Initialize popovers
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
}

/**
 * Initialize charts if Chart.js is available
 */
function initializeCharts() {
    if (typeof Chart === 'undefined') {
        console.log('Chart.js not loaded, skipping chart initialization');
        return;
    }

    // Set Chart.js defaults for dark theme
    Chart.defaults.color = '#ffffff';
    Chart.defaults.borderColor = '#374151';
    Chart.defaults.backgroundColor = 'rgba(75, 192, 192, 0.2)';
}

/**
 * Create a weekly trends chart
 */
function createWeeklyTrendsChart(canvasId, data) {
    const ctx = document.getElementById(canvasId);
    if (!ctx || typeof Chart === 'undefined') return null;

    // Destroy existing chart if it exists
    if (chartInstances[canvasId]) {
        chartInstances[canvasId].destroy();
    }

    chartInstances[canvasId] = new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.weeks || [],
            datasets: [{
                label: 'Completion Rate (%)',
                data: data.completion_rates || [],
                borderColor: 'rgb(75, 192, 192)',
                backgroundColor: 'rgba(75, 192, 192, 0.2)',
                tension: 0.4,
                yAxisID: 'y'
            }, {
                label: 'Total Distance (km)',
                data: data.total_distances || [],
                borderColor: 'rgb(255, 99, 132)',
                backgroundColor: 'rgba(255, 99, 132, 0.2)',
                tension: 0.4,
                yAxisID: 'y1'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            scales: {
                y: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    title: {
                        display: true,
                        text: 'Completion Rate (%)'
                    },
                    min: 0,
                    max: 100
                },
                y1: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    title: {
                        display: true,
                        text: 'Distance (km)'
                    },
                    grid: {
                        drawOnChartArea: false,
                    },
                }
            },
            plugins: {
                legend: {
                    position: 'top',
                },
                tooltip: {
                    callbacks: {
                        afterLabel: function(context) {
                            if (context.datasetIndex === 0) {
                                return 'Completion Rate';
                            } else {
                                return 'Team Distance';
                            }
                        }
                    }
                }
            }
        }
    });

    return chartInstances[canvasId];
}

/**
 * Create a status breakdown chart (doughnut)
 */
function createStatusBreakdownChart(canvasId, statusData) {
    const ctx = document.getElementById(canvasId);
    if (!ctx || typeof Chart === 'undefined') return null;

    // Destroy existing chart if it exists
    if (chartInstances[canvasId]) {
        chartInstances[canvasId].destroy();
    }

    const labels = Object.keys(statusData);
    const data = Object.values(statusData);

    const backgroundColors = [
        '#28a745', // On Track - green
        '#17a2b8', // Over-performed - info
        '#ffc107', // Under-performed - warning
        '#dc3545', // Missed Workout - danger
        '#007bff', // Extra Activity - primary
        '#6c757d'  // Other - secondary
    ];

    chartInstances[canvasId] = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: data,
                backgroundColor: backgroundColors.slice(0, labels.length),
                borderWidth: 2,
                borderColor: '#374151'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        padding: 20,
                        usePointStyle: true
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const label = context.label || '';
                            const value = context.parsed;
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const percentage = ((value / total) * 100).toFixed(1);
                            return `${label}: ${value} (${percentage}%)`;
                        }
                    }
                }
            }
        }
    });

    return chartInstances[canvasId];
}

/**
 * Run manual Strava sync
 */
function runManualStravaSync(targetDate = null) {
    const button = event.target.closest('button');
    const originalText = button.innerHTML;

    // Show loading state
    button.disabled = true;
    button.innerHTML = '<i data-feather="loader" class="me-1"></i> Syncing...';
    feather.replace();

    const requestData = targetDate ? { date: targetDate } : {};

    fetch('/api/manual-run', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAlert('Strava sync completed successfully! Dashboard updated with latest activities.', 'success');
            // Reload the page to show updated data
            setTimeout(() => {
                location.reload();
            }, 1500);
        } else {
            showAlert(`Sync error: ${data.message}`, 'danger');
        }
    })
    .catch(error => {
        console.error('Sync error:', error);
        showAlert('Failed to sync Strava data. Please try again.', 'danger');
    })
    .finally(() => {
        // Restore button state
        button.disabled = false;
        button.innerHTML = originalText;
        feather.replace();
    });
}

/**
 * Run manual task execution (legacy function)
 */
function runManualTask(targetDate = null) {
    const button = event?.target?.closest('button');
    const originalText = button?.innerHTML;

    // Show loading state
    if (button) {
        button.disabled = true;
        button.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Running...';
    }

    const payload = targetDate ? { date: targetDate } : {};

    fetch('/api/manual-run', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAlert('Manual sync completed successfully!', 'success');
            // Optionally reload the page to show updated data
            setTimeout(() => {
                window.location.reload();
            }, 2000);
        } else {
            showAlert('Manual sync failed: ' + data.message, 'danger');
        }
    })
    .catch(error => {
        console.error('Error running manual sync:', error);
        showAlert('Error running manual sync: ' + error.message, 'danger');
    })
    .finally(() => {
        // Restore button state
        if (button) {
            button.disabled = false;
            button.innerHTML = originalText;
            feather.replace();
        }
    });
}

/**
 * Toggle athlete active status
 */
function toggleAthlete(athleteId) {
    const button = event?.target?.closest('button');
    const originalContent = button?.innerHTML;

    if (button) {
        button.disabled = true;
        button.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
    }

    fetch(`/api/athlete/${athleteId}/toggle`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAlert('Athlete status updated successfully!', 'success');
            // Reload the page to update the UI
            setTimeout(() => {
                window.location.reload();
            }, 1000);
        } else {
            showAlert('Error updating athlete status: ' + data.message, 'danger');
            if (button) {
                button.disabled = false;
                button.innerHTML = originalContent;
            }
        }
    })
    .catch(error => {
        console.error('Error toggling athlete status:', error);
        showAlert('Error updating athlete status: ' + error.message, 'danger');
        if (button) {
            button.disabled = false;
            button.innerHTML = originalContent;
        }
    });
}

/**
 * Change dashboard date
 */
function changeDashboardDate(newDate) {
    if (newDate) {
        window.location.href = `/dashboard/${newDate}`;
    }
}

/**
 * Show alert message
 */
function showAlert(message, type = 'info', duration = 5000) {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.setAttribute('role', 'alert');
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;

    // Find container to prepend alert
    const container = document.querySelector('.container') || document.body;
    container.insertBefore(alertDiv, container.firstChild);

    // Auto-dismiss after duration
    if (duration > 0) {
        setTimeout(() => {
            if (alertDiv.parentNode) {
                alertDiv.remove();
            }
        }, duration);
    }

    return alertDiv;
}

/**
 * Format pace for display
 */
function formatPace(paceMinPerKm) {
    if (!paceMinPerKm || paceMinPerKm <= 0) {
        return 'N/A';
    }

    const minutes = Math.floor(paceMinPerKm);
    const seconds = Math.round((paceMinPerKm - minutes) * 60);
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
}

/**
 * Format distance for display
 */
function formatDistance(distanceKm) {
    if (!distanceKm || distanceKm <= 0) {
        return '0.0 km';
    }

    return `${distanceKm.toFixed(1)} km`;
}

/**
 * Format variance percentage
 */
function formatVariance(variance) {
    if (variance === null || variance === undefined) {
        return '0.0%';
    }

    const sign = variance >= 0 ? '+' : '';
    return `${sign}${variance.toFixed(1)}%`;
}

/**
 * Get status badge class based on status
 */
function getStatusBadgeClass(status) {
    const statusMap = {
        'On Track': 'bg-success',
        'Over-performed': 'bg-info',
        'Under-performed': 'bg-warning',
        'Missed Workout': 'bg-danger',
        'Extra Activity': 'bg-primary',
        'Partially Completed': 'bg-secondary'
    };

    return statusMap[status] || 'bg-secondary';
}

/**
 * Setup auto-refresh for live data (optional)
 */
function setupAutoRefresh(intervalMinutes = 30) {
    const interval = intervalMinutes * 60 * 1000; // Convert to milliseconds

    setInterval(() => {
        // Only refresh if user is on dashboard page and tab is visible
        if (window.location.pathname.includes('/dashboard') && !document.hidden) {
            console.log('Auto-refreshing dashboard data...');

            // Fetch updated data without full page reload
            const currentDate = document.getElementById('dateSelector')?.value || 
                               new Date().toISOString().split('T')[0];

            fetch(`/api/dashboard-data/${currentDate}`)
                .then(response => response.json())
                .then(data => {
                    if (data && !data.error) {
                        updateDashboardData(data);
                        showAlert('Dashboard data refreshed', 'info', 2000);
                    }
                })
                .catch(error => {
                    console.error('Auto-refresh failed:', error);
                });
        }
    }, interval);
}

/**
 * Update dashboard data without full page reload
 */
function updateDashboardData(data) {
    // This function would update specific parts of the dashboard
    // Implementation depends on specific UI elements that need updating
    console.log('Updating dashboard data:', data);

    // Example: Update team summary cards
    updateTeamSummaryCards(data.team_summary);

    // Example: Update charts
    if (data.weekly_trends) {
        updateWeeklyTrendsChart(data.weekly_trends);
    }
}

/**
 * Update team summary cards
 */
function updateTeamSummaryCards(teamSummary) {
    if (!teamSummary) return;

    // Update individual card values
    const cards = {
        'total_athletes': teamSummary.total_athletes || 0,
        'completed_workouts': teamSummary.completed_workouts || 0,
        'completion_rate': `${teamSummary.completion_rate || 0}%`,
        'average_distance_variance': `${(teamSummary.average_distance_variance || 0).toFixed(1)}%`
    };

    Object.entries(cards).forEach(([key, value]) => {
        const element = document.querySelector(`[data-metric="${key}"]`);
        if (element) {
            element.textContent = value;
        }
    });
}

/**
 * Update weekly trends chart
 */
function updateWeeklyTrendsChart(weeklyTrends) {
    const chartId = 'weeklyTrendsChart';
    if (chartInstances[chartId]) {
        // Update existing chart
        chartInstances[chartId].data.labels = weeklyTrends.weeks || [];
        chartInstances[chartId].data.datasets[0].data = weeklyTrends.completion_rates || [];
        chartInstances[chartId].data.datasets[1].data = weeklyTrends.total_distances || [];
        chartInstances[chartId].update();
    } else {
        // Create new chart
        createWeeklyTrendsChart(chartId, weeklyTrends);
    }
}

/**
 * Handle page visibility changes
 */
document.addEventListener('visibilitychange', function() {
    if (document.hidden) {
        console.log('Page hidden, pausing auto-refresh');
    } else {
        console.log('Page visible, resuming auto-refresh');
    }
});

/**
 * Handle window resize for charts
 */
window.addEventListener('resize', function() {
    Object.values(chartInstances).forEach(chart => {
        if (chart && typeof chart.resize === 'function') {
            chart.resize();
        }
    });
});

/**
 * Clean up charts when page unloads
 */
window.addEventListener('beforeunload', function() {
    Object.values(chartInstances).forEach(chart => {
        if (chart && typeof chart.destroy === 'function') {
            chart.destroy();
        }
    });
});

// Export functions for global access
window.DashboardApp = {
    runManualTask,
    toggleAthlete,
    changeDashboardDate,
    showAlert,
    formatPace,
    formatDistance,
    formatVariance,
    getStatusBadgeClass,
    createWeeklyTrendsChart,
    createStatusBreakdownChart
};

function runManualSync() {
    if (confirm('Run manual sync for today?')) {
        fetch('/api/manual-run', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({})
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                showAlert('Manual sync completed successfully', 'success');
                // Refresh the page after a short delay
                setTimeout(() => location.reload(), 2000);
            } else {
                showAlert('Manual sync failed: ' + data.message, 'error');
            }
        })
        .catch(error => {
            console.error('Error running manual sync:', error);
            showAlert('Error running manual sync: ' + error.message, 'error');
        });
    }
}