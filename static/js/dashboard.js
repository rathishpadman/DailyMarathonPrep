// Dashboard JavaScript functionality for Marathon Training Dashboard

// Global variables
var chartInstances = chartInstances || {};

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
    // Handle period filter changes for summary table
    const periodButtons = document.querySelectorAll('.period-filter');
    periodButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            const period = this.getAttribute('data-period');
            updateSummaryData(period);
        });
    });

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

// Individual athlete summary filtering (replaces old summary data functions)
function filterSummaryByAthlete(athleteId) {
    const summaryRows = document.querySelectorAll('#summaryTableBody tr');
    summaryRows.forEach(row => {
        const rowAthleteId = row.getAttribute('data-athlete-id');
        if (!athleteId || rowAthleteId === athleteId) {
            row.style.display = '';
        } else {
            row.style.display = 'none';
        }
    });
}

/**
 * Update summary statistics
 */
function updateSummaryStats(data) {
    // Update total planned
    const totalPlannedElement = document.querySelector('[data-stat="total-planned"]');
    if (totalPlannedElement) {
        totalPlannedElement.textContent = `${data.total_planned.toFixed(1)} km`;
    }

    // Update total actual
    const totalActualElement = document.querySelector('[data-stat="total-actual"]');
    if (totalActualElement) {
        totalActualElement.textContent = `${data.total_actual.toFixed(1)} km`;
    }

    // Update variance
    const varianceElement = document.querySelector('[data-stat="variance"]');
    if (varianceElement) {
        const variance = data.variance_percent;
        varianceElement.textContent = `${variance >= 0 ? '+' : ''}${variance.toFixed(1)}%`;
        varianceElement.className = variance >= 0 ? 'text-success' : 'text-danger';
    }

    // Update completion rate
    const completionElement = document.querySelector('[data-stat="completion"]');
    if (completionElement) {
        completionElement.textContent = `${data.avg_completion_rate.toFixed(1)}%`;
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
    button.innerHTML = '<i data-feather="loader" class="me-1"></i> Syncing from May 19th...';
    feather.replace();

    const requestData = targetDate ? { date: targetDate, type: 'single' } : { type: 'range' };

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
            showAlert(`${data.message} Dashboard updated with latest activities.`, 'success');
            // Reload the page to show updated data
            setTimeout(() => {
                location.reload();
            }, 2000);
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

    // Update dashboard tiles
    updateDashboardTiles(data.period_stats);

    // Example: Update team summary cards
    updateTeamSummaryCards(data.team_summary);

    // Example: Update charts
    if (data.weekly_trends) {
        updateWeeklyTrendsChart(data.weekly_trends);
    }
}

/**
 * Update dashboard tiles with filtered data
 */
function updateDashboardTiles(periodStats) {
    if (!periodStats) return;

    // Update total athletes
    const totalAthletesElement = document.getElementById('tile-total-athletes');
    if (totalAthletesElement) {
        totalAthletesElement.textContent = periodStats.total_athletes || 0;
    }

    // Update total planned
    const totalPlannedElement = document.getElementById('tile-total-planned');
    if (totalPlannedElement) {
        totalPlannedElement.textContent = `${(periodStats.total_planned || 0).toFixed(1)} km`;
    }

    // Update total actual
    const totalActualElement = document.getElementById('tile-total-actual');
    if (totalActualElement) {
        totalActualElement.textContent = `${(periodStats.total_actual || 0).toFixed(1)} km`;
    }

    // Update completion rate
    const completionRateElement = document.getElementById('tile-completion-rate');
    if (completionRateElement) {
        completionRateElement.textContent = `${(periodStats.completion_rate || 0).toFixed(1)}%`;
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
    updateSummaryData,
    createWeeklyTrendsChart,
    createStatusBreakdownChart
};

document.addEventListener('DOMContentLoaded', function() {
    console.log('Initializing Marathon Training Dashboard...');

    // Initialize feather icons
    if (typeof feather !== 'undefined') {
        feather.replace();
    }

    // Set up auto-refresh for real-time data
    setupAutoRefresh();

    // Initialize chart if on dashboard page
    if (document.getElementById('weeklyTrendsChart')) {
        initializeWeeklyTrends();
    }

    // Initialize athlete progress filters
    initializeProgressFilters();
});

// Athlete Progress Filtering Functions
let athleteProgressData = [];
let filteredData = [];
let originalProgressData = [];
let currentProgressData = [];
let currentSortColumn = null;
let currentSortDirection = 'asc';

function initializeProgressFilters() {
    // Load initial athlete progress data with additional metrics
    loadAthleteProgressData();
    initializePerformanceCharts();
}

function loadAthleteProgressData() {
    fetch('/api/athlete-progress-data')
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                athleteProgressData = data.athletes;
                originalProgressData = [...athleteProgressData];
                currentProgressData = [...athleteProgressData];
                populateProgressTable(currentProgressData);
                populateAthleteFilter(data.athletes);
            } else {
                console.error('Error loading athlete progress data:', data.message);
                showNotification('Error loading athlete progress data: ' + data.message, 'error');
            }
        })
        .catch(error => {
            console.error('Error fetching athlete progress data:', error);
            showNotification('Failed to load athlete progress data', 'error');
        });
}

// Remove the old populateProgressTable function since we're using updateProgressTable

// Global variables for athlete data

// Update progress view based on filters
// Filter Functions
function updateProgressView() {
    const metric = document.getElementById('metricFilter')?.value || 'total_distance';
    const debug = document.getElementById('debugFilter')?.checked || false;

    // Re-populate table with current filter
    if (currentProgressData && currentProgressData.length > 0) {
        populateProgressTable(currentProgressData);
    }

    console.log('Progress view updated with metric:', metric, 'debug:', debug);
}

function updateMetricDisplay() {
    const metric = document.getElementById('metricFilter')?.value || 'total_distance';
    updateProgressView();
}

function sortProgressTable(column) {
    if (!currentProgressData || currentProgressData.length === 0) return;

    // Toggle sort direction
    if (currentSortColumn === column) {
        currentSortDirection = currentSortDirection === 'asc' ? 'desc' : 'asc';
    } else {
        currentSortColumn = column;
        currentSortDirection = 'asc';
    }

    // Sort data
    currentProgressData.sort((a, b) => {
        let aVal = a[column];
        let bVal = b[column];

        // Handle null/undefined values
        if (aVal == null) aVal = 0;
        if (bVal == null) bVal = 0;

        // Handle different data types
        if (typeof aVal === 'string' && typeof bVal === 'string') {
            aVal = aVal.toLowerCase();
            bVal = bVal.toLowerCase();
        }

        if (currentSortDirection === 'asc') {
            return aVal > bVal ? 1 : -1;
        } else {
            return aVal < bVal ? 1 : -1;
        }
    });

    populateProgressTable(currentProgressData);
}

function filterByAthlete() {
    const athleteFilter = document.getElementById('athleteFilterProgress')?.value;

    if (!athleteFilter || athleteFilter === 'all') {
        currentProgressData = [...originalProgressData];
        populateProgressTable(currentProgressData);
        updateChartsForAthlete('all');
        return;
    }

    currentProgressData = originalProgressData.filter(athlete => 
        athlete.id == athleteFilter
    );

    populateProgressTable(currentProgressData);
    updateChartsForAthlete(athleteFilter);
}

// Populate Athlete Progress Table
function populateProgressTable(athletes) {
    const tableBody = document.querySelector('#athleteProgressTable tbody');
    if (!tableBody) return;

    if (!athletes || athletes.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="6" class="text-center">No athlete data available</td></tr>';
        return;
    }

    tableBody.innerHTML = '';

    athletes.forEach(athlete => {
        const row = document.createElement('tr');

        // Get current week data (last 7 days from today)
        const today = new Date();
        const weekAgo = new Date(today.getTime() - (7 * 24 * 60 * 60 * 1000));
        const twoWeeksAgo = new Date(today.getTime() - (14 * 24 * 60 * 60 * 1000));

        // Calculate current and previous week (placeholder - would need actual activity data)
        const currentWeek = (athlete.total_distance / 4) || 0; // Estimated
        const previousWeek = (athlete.total_distance / 5) || 0; // Estimated

        row.innerHTML = `
            <td>
                <div class="d-flex align-items-center">
                    <div class="athlete-avatar me-2">
                        ${athlete.name.charAt(0).toUpperCase()}
                    </div>
                    <div>
                        <div class="fw-semibold">${athlete.name}</div>
                        <small class="text-muted">${athlete.activity_count || 0} activities</small>
                    </div>
                </div>
            </td>
            <td>
                <span class="fw-semibold text-primary">${(athlete.total_distance || 0).toFixed(1)} km</span>
            </td>
            <td>
                <span class="fw-semibold">${(athlete.avg_pace || 0).toFixed(1)} min/km</span>
            </td>
            <td>
                <span class="fw-semibold text-danger">${Math.round(athlete.avg_heart_rate || 0)} bpm</span>
            </td>
            <td>
                <span class="fw-semibold text-success">${Math.round(athlete.total_elevation || 0)} m</span>
            </td>
            <td>
                <div class="d-flex justify-content-between align-items-center">
                    <small>Current: ${currentWeek.toFixed(1)} km</small>
                    <small>Previous: ${previousWeek.toFixed(1)} km</small>
                </div>
                <div class="progress mt-1" style="height: 4px;">
                    <div class="progress-bar" role="progressbar" 
                         style="width: ${Math.min(100, (currentWeek / (previousWeek || 1)) * 100)}%"></div>
                </div>
            </td>
        `;
        tableBody.appendChild(row);
    });
}

// Update progress chart based on metric
function updateProgressChart(metric) {
    // This will be implemented when chart functionality is added
    console.log('Updating progress chart for metric:', metric);
}

function updateProgressView() {
    const metric = document.getElementById('progress_metric').value;
    const period = document.getElementById('progress_period').value;
    const sortOrder = document.getElementById('progress_sort').value;

    updateMetricDisplay(metric);
    updatePeriodDisplay(period);
    sortProgressTable(metric, sortOrder);
}

function updateMetricDisplay(metric) {
    const header = document.getElementById('metric_header');
    const metricCells = document.querySelectorAll('.metric-value');

    // Update header
    const headers = {
        'mileage': 'Total Distance (km)',
        'pace': 'Average Pace (min/km)',
        'elevation': 'Elevation Gain (m)',
        'heart_rate': 'Avg Heart Rate (bpm)'
    };
    header.textContent = headers[metric];

    // Update cell values
    metricCells.forEach(cell => {
        const value = cell.getAttribute(`data-${metric}`);
        let displayValue = value;

        if (metric === 'mileage') {
            displayValue = `<span class="badge bg-primary">${value} km</span>`;
        } else if (metric === 'pace') {
            const paceValue = parseFloat(value);
            if (!isNaN(paceValue) && paceValue > 0) {
                const minutes = Math.floor(paceValue);
                const seconds = Math.round((paceValue - minutes) * 60);
                displayValue = `<span class="badge bg-info">${minutes}:${seconds.toString().padStart(2, '0')} min/km</span>`;
            } else {
                displayValue = `<span class="badge bg-secondary">N/A</span>`;
            }
        } else if (metric === 'elevation') {
            displayValue = `<span class="badge bg-warning">${value} m</span>`;
        } else if (metric === 'heart_rate') {
            const hrValue = parseFloat(value);
            if (!isNaN(hrValue) && hrValue > 0) {
                let badgeClass = 'bg-success';
                if (hrValue > 170) badgeClass = 'bg-danger';
                else if (hrValue > 160) badgeClass = 'bg-warning';
                displayValue = `<span class="badge ${badgeClass}">${hrValue} bpm</span>`;
            } else {
                displayValue = `<span class="badge bg-secondary">N/A</span>`;
            }
        }

        cell.innerHTML = displayValue;
    });
}

function updatePeriodDisplay(period) {
    // Update period-specific columns based on selection
    const actualCells = document.querySelectorAll('.period-actual');
    const plannedCells = document.querySelectorAll('.period-planned');

    // This would typically fetch different data based on period
    // For now, we'll just update labels
    actualCells.forEach(cell => {
        if (period === 'month') {
            cell.textContent = cell.textContent.replace('km', 'km (month)');
        } else if (period === 'total') {
            cell.textContent = cell.textContent.replace('km', 'km (total)');
        }
    });
}

function sortProgressTable(metric, sortOrder) {
    const tbody = document.getElementById('progress_tbody');
    const rows = Array.from(tbody.querySelectorAll('tr'));

    rows.sort((a, b) => {
        if (sortOrder === 'name') {
            const nameA = a.querySelector('strong').textContent;
            const nameB = b.querySelector('strong').textContent;
            return nameA.localeCompare(nameB);
        }

        const valueA = parseFloat(a.querySelector('.metric-value').getAttribute(`data-${metric}`)) || 0;
        const valueB = parseFloat(b.querySelector('.metric-value').getAttribute(`data-${metric}`)) || 0;

        if (sortOrder === 'asc') {
            return valueA - valueB;
        } else {
            return valueB - valueA;
        }
    });

    // Clear and re-append sorted rows
    tbody.innerHTML = '';
    rows.forEach(row => tbody.appendChild(row));
}

function filterByAthlete() {
    const selectedAthleteId = document.getElementById('athlete_filter').value;
    const rows = document.querySelectorAll('#progress_tbody tr');

    rows.forEach(row => {
        const athleteId = row.getAttribute('data-athlete-id');
        if (!selectedAthleteId || athleteId === selectedAthleteId) {
            row.style.display = '';
        } else {
            row.style.display = 'none';
        }
    });
}

function resetProgressFilters() {
    document.getElementById('athlete_filter').value = '';
    document.getElementById('progress_metric').value = 'mileage';
    document.getElementById('progress_period').value = 'month';
    filterByAthlete();
    updateProgressView();
}

// Initialize charts for athlete selection
function updateChartsForAthlete(athleteId) {
    console.log('Updating charts for athlete:', athleteId);
    // This will be implemented when chart data is properly loaded
}

// Filter athlete progress from training summary clicks
function filterAthleteProgress(athleteId) {
    // Scroll to athlete progress section
    const progressSection = document.querySelector('#athlete-progress-section');
    if (progressSection) {
        progressSection.scrollIntoView({ behavior: 'smooth' });
    }

    // Set the filter and update view
    setTimeout(() => {
        const progressFilter = document.getElementById('progressAthleteFilter');
        if (progressFilter) {
            progressFilter.value = athleteId;
            updateProgressView();
        }
    }, 500);
}

// Performance Charts Functions
window.charts = {};

async function initializePerformanceCharts() {
    if (typeof Chart === 'undefined') {
        console.log('Chart.js not loaded, skipping chart initialization');
        return;
    }

    // Load Chart.js if not already loaded
    if (!window.Chart) {
        const script = document.createElement('script');
        script.src = 'https://cdn.jsdelivr.net/npm/chart.js';
        script.onload = () => createPerformanceCharts();
        document.head.appendChild(script);
    } else {
        createPerformanceCharts();
    }
}

function createPerformanceCharts() {
    const chartConfigs = {
        distance: {
            canvas: 'distanceChart',
            label: 'Distance (km)',
            color: 'rgb(75, 192, 192)'
        },
        heartRate: {
            canvas: 'heartRateChart',
            label: 'Heart Rate (bpm)',
            color: 'rgb(255, 99, 132)'
        },
        pace: {
            canvas: 'paceChart',
            label: 'Pace (min/km)',
            color: 'rgb(54, 162, 235)'
        },
        elevation: {
            canvas: 'elevationChart',
            label: 'Elevation (m)',
            color: 'rgb(255, 205, 86)'
        }
    };

    Object.keys(chartConfigs).forEach(chartType => {
        const config = chartConfigs[chartType];
        const ctx = document.getElementById(config.canvas);

        if (ctx) {
            window.charts[chartType] = new Chart(ctx, {
                type: chartType === 'elevation' ? 'bar' : 'line',
                data: {
                    labels: ['Day 1', 'Day 2', 'Day 3', 'Day 4', 'Day 5', 'Day 6', 'Day 7'],
                    datasets: [{
                        label: config.label,
                        data: [],
                        borderColor: config.color,
                        backgroundColor: config.color + '20',
                        tension: 0.4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: false
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true
                        }
                    }
                }
            });
        }
    });

    updatePerformanceCharts();
}

async function updatePerformanceCharts() {
    try {
        const response = await fetch('/api/athlete-performance-charts');
        const data = await response.json();

        if (data.success) {
            Object.keys(window.charts).forEach(chartType => {
                if (data[chartType] && window.charts[chartType]) {
                    window.charts[chartType].data = data[chartType];
                    window.charts[chartType].update();
                }
            });
        }
    } catch (error) {
        console.error('Error updating performance charts:', error);
        // Load with sample data if API fails
        loadSampleChartData();
    }
}

function loadSampleChartData() {
    if (!athleteProgressData.length) return;

    const sampleData = {
        distance: { labels: [], datasets: [] },
        heartRate: { labels: [], datasets: [] },
        pace: { labels: [], datasets: [] },
        elevation: { labels: [], datasets: [] }
    };

    // Generate labels for last 7 days
    const labels = [];
    for (let i = 6; i >= 0; i--) {
        const date = new Date();
        date.setDate(date.getDate() - i);
        labels.push(date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }));
    }

    sampleData.distance.labels = labels;
    sampleData.heartRate.labels = labels;
    sampleData.pace.labels = labels;
    sampleData.elevation.labels = labels;

    // Generate sample data for each athlete
    athleteProgressData.slice(0, 3).forEach((athlete, index) => {
        const colors = ['rgb(75, 192, 192)', 'rgb(255, 99, 132)', 'rgb(54, 162, 235)'];
        const color = colors[index % colors.length];

        // Distance data
        const distanceData = Array.from({length: 7}, () => Math.random() * 5 + 8);
        sampleData.distance.datasets.push({
            label: athlete.name,
            data: distanceData,
            borderColor: color,
            backgroundColor: color + '20',
            tension: 0.4
        });

        // Heart rate data
        const hrData = Array.from({length: 7}, () => Math.random() * 20 + parseInt(athlete.avg_heart_rate || 160));
        sampleData.heartRate.datasets.push({
            label: athlete.name,
            data: hrData,
            borderColor: color,
            backgroundColor: color + '20',
            tension: 0.4
        });

        // Pace data
        const paceData = Array.from({length: 7}, () => Math.random() * 1 + parseFloat(athlete.avg_pace || 5));
        sampleData.pace.datasets.push({
            label: athlete.name,
            data: paceData,
            borderColor: color,
            backgroundColor: color + '20',
            tension: 0.4
        });

        // Elevation data
        const elevationData = Array.from({length: 7}, () => Math.random() * 200 + parseInt(athlete.total_elevation || 300));
        sampleData.elevation.datasets.push({
            label: athlete.name,
            data: elevationData,
            backgroundColor: color
        });
    });

    // Update charts with sample data
    Object.keys(window.charts).forEach(chartType => {
        if (sampleData[chartType] && window.charts[chartType]) {
            window.charts[chartType].data = sampleData[chartType];
            window.charts[chartType].update();
        }
    });
}

/**
 * Quick sync for last 2 days only
 */
function runQuickSync() {
    const button = document.querySelector('button[onclick="runQuickSync()"]');
    if (!button) return;

    const originalText = button.innerHTML;
    button.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Syncing...';
    button.disabled = true;

    fetch('/api/sync-current', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAlert('success', data.message);
            // Refresh the page after successful sync
            setTimeout(() => {
                window.location.reload();
            }, 2000);
        } else {
            showAlert('error', data.message);
        }
    })
    .catch(error => {
        console.error('Sync error:', error);
        showAlert('error', 'An error occurred during sync');
    })
    .finally(() => {
        button.innerHTML = originalText;
        button.disabled = false;
        // Re-initialize feather icons
        if (window.feather) {
            feather.replace();
        }
    });
}