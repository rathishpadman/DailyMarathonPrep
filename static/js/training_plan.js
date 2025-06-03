// Training Plan JavaScript

let currentTrainingData = [];
let availableAthletes = [];

document.addEventListener('DOMContentLoaded', function() {
    console.log('Training Plan page loaded');

    // Initialize the page
    initFileUpload();
    loadAthletesList();
    loadTrainingPlanData();
});

function initFileUpload() {
    const fileInput = document.getElementById('training_file');
    if (fileInput) {
        fileInput.addEventListener('change', function(e) {
            const file = e.target.files[0];
            if (file) {
                console.log('File selected:', file.name);
            }
        });
    }
}

async function loadAthletesList() {
    try {
        const response = await fetch('/api/athletes-list');
        const data = await response.json();

        if (data.success) {
            availableAthletes = data.athletes;
            populateAthleteSelector();
        }
    } catch (error) {
        console.error('Error loading athletes:', error);
    }
}

function populateAthleteSelector() {
    const selector = document.getElementById('athlete_selector');
    if (selector) {
        selector.innerHTML = '<option value="">Select athlete to filter...</option>';
        availableAthletes.forEach(athlete => {
            const option = document.createElement('option');
            option.value = athlete.name;
            option.textContent = athlete.name;
            selector.appendChild(option);
        });

        selector.addEventListener('change', filterByAthlete);
    }
}

async function loadTrainingPlanData() {
    const loadingDiv = document.getElementById('training_plan_loading');
    const tableBody = document.getElementById('training_plan_tbody');

    if (loadingDiv) loadingDiv.style.display = 'block';

    try {
        const response = await fetch('/api/training-plan-data');
        const data = await response.json();

        if (data.success) {
            currentTrainingData = data.workouts;
            renderTrainingPlanTable();
        } else {
            showAlert('error', 'Failed to load training plan data: ' + data.message);
        }
    } catch (error) {
        console.error('Error loading training plan:', error);
        showAlert('error', 'Error loading training plan data');
    } finally {
        if (loadingDiv) loadingDiv.style.display = 'none';
    }
}

function renderTrainingPlanTable() {
    const tableBody = document.getElementById('training_plan_tbody');
    if (!tableBody) {
        console.error('Training plan table body not found');
        return;
    }

    tableBody.innerHTML = '';

    if (currentTrainingData.length === 0) {
        const row = document.createElement('tr');
        row.innerHTML = '<td colspan="7" class="text-center text-muted">No training plan data found. Upload a plan or add rows manually.</td>';
        tableBody.appendChild(row);
        return;
    }

    currentTrainingData.forEach((workout, index) => {
        const row = createTrainingPlanRow(workout, index);
        tableBody.appendChild(row);
    });

    // Re-initialize feather icons
    setTimeout(() => feather.replace(), 100);
}

function createTrainingPlanRow(workout, index) {
    const row = document.createElement('tr');
    row.innerHTML = `
        <td>
            <input type="date" class="form-control form-control-sm" 
                   value="${workout.date}" 
                   onchange="updateWorkoutData(${index}, 'date', this.value)">
        </td>
        <td>
            <select class="form-control form-control-sm" 
                    onchange="updateWorkoutData(${index}, 'athlete_name', this.value)">
                ${getAthleteOptions(workout.athlete_name)}
            </select>
        </td>
        <td>
            <input type="number" class="form-control form-control-sm" 
                   value="${workout.distance_km}" step="0.1" min="0"
                   onchange="updateWorkoutData(${index}, 'distance_km', this.value)">
        </td>
        <td>
            <input type="number" class="form-control form-control-sm" 
                   value="${workout.pace_min_per_km}" step="0.1" min="0"
                   onchange="updateWorkoutData(${index}, 'pace_min_per_km', this.value)">
        </td>
        <td>
            <select class="form-control form-control-sm" 
                    onchange="updateWorkoutData(${index}, 'workout_type', this.value)">
                ${getWorkoutTypeOptions(workout.workout_type)}
            </select>
        </td>
        <td>
            <input type="text" class="form-control form-control-sm" 
                   value="${workout.notes}" 
                   onchange="updateWorkoutData(${index}, 'notes', this.value)">
        </td>
        <td>
            <button type="button" class="btn btn-danger btn-sm" 
                    onclick="removeRow(${index})" title="Remove">
                <i data-feather="trash-2"></i>
            </button>
        </td>
    `;

    // Re-initialize feather icons for the new row
    setTimeout(() => feather.replace(), 0);

    return row;
}

function getAthleteOptions(selectedAthlete) {
    let options = '<option value="">Select athlete...</option>';
    availableAthletes.forEach(athlete => {
        const selected = athlete.name === selectedAthlete ? 'selected' : '';
        options += `<option value="${athlete.name}" ${selected}>${athlete.name}</option>`;
    });
    return options;
}

function getWorkoutTypeOptions(selectedType) {
    const workoutTypes = ['Easy Run', 'Tempo Run', 'Interval Training', 'Long Run', 'Recovery Run', 'Cross Training', 'Rest Day'];
    let options = '';

    workoutTypes.forEach(type => {
        const selected = type === selectedType ? 'selected' : '';
        options += `<option value="${type}" ${selected}>${type}</option>`;
    });

    return options;
}

function updateWorkoutData(index, field, value) {
    if (currentTrainingData[index]) {
        currentTrainingData[index][field] = value;
    }
}

function addNewRow() {
    const newWorkout = {
        id: null,
        athlete_name: '',
        date: new Date().toISOString().split('T')[0],
        distance_km: 0,
        pace_min_per_km: 0,
        workout_type: 'Easy Run',
        notes: ''
    };

    currentTrainingData.push(newWorkout);
    renderTrainingPlanTable();
}

function removeRow(index) {
    if (confirm('Are you sure you want to remove this workout?')) {
        currentTrainingData.splice(index, 1);
        renderTrainingPlanTable();
    }
}

function duplicateAthlete() {
    const selectedAthlete = document.getElementById('athlete_selector').value;
    if (!selectedAthlete) {
        showAlert('warning', 'Please select an athlete to duplicate');
        return;
    }

    const athleteWorkouts = currentTrainingData.filter(w => w.athlete_name === selectedAthlete);
    if (athleteWorkouts.length === 0) {
        showAlert('warning', 'No workouts found for selected athlete');
        return;
    }

    const newAthleteName = prompt('Enter name for the new athlete:');
    if (!newAthleteName) return;

    const duplicatedWorkouts = athleteWorkouts.map(workout => ({
        ...workout,
        id: null,
        athlete_name: newAthleteName
    }));

    currentTrainingData.push(...duplicatedWorkouts);
    renderTrainingPlanTable();
    showAlert('success', `Duplicated ${duplicatedWorkouts.length} workouts for ${newAthleteName}`);
}

async function saveTrainingPlan() {
    const saveButton = document.querySelector('button[onclick="saveTrainingPlan()"]');
    if (!saveButton) return;
    
    const originalText = saveButton.innerHTML;

    // Validate data before saving
    const validWorkouts = currentTrainingData.filter(workout => 
        workout.athlete_name && workout.date && workout.distance_km > 0
    );

    if (validWorkouts.length === 0) {
        showAlert('warning', 'No valid workouts to save. Please ensure all rows have athlete name, date, and distance > 0.');
        return;
    }

    saveButton.innerHTML = '<i data-feather="loader" class="me-1"></i> Saving...';
    saveButton.disabled = true;

    try {
        const response = await fetch('/api/save-training-plan', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                workouts: validWorkouts
            })
        });

        const data = await response.json();

        if (response.ok && data.success) {
            showAlert('success', `✅ ${data.message}`);
            await loadTrainingPlanData(); // Reload data to show updated IDs
        } else {
            showAlert('error', `❌ Failed to save: ${data.message || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error saving training plan:', error);
        showAlert('error', '❌ Network error while saving training plan');
    } finally {
        saveButton.innerHTML = originalText;
        saveButton.disabled = false;
        feather.replace();
    }
}

function filterByAthlete() {
    const selectedAthlete = document.getElementById('athlete_selector').value;
    const rows = document.querySelectorAll('#training_plan_tbody tr');

    rows.forEach(row => {
        if (!selectedAthlete) {
            row.style.display = '';
        } else {
            const athleteSelect = row.querySelector('select');
            const athleteName = athleteSelect ? athleteSelect.value : '';
            row.style.display = athleteName === selectedAthlete ? '' : 'none';
        }
    });
}

function resetFilters() {
    document.getElementById('athlete_selector').value = '';
    filterByAthlete();
}

function showAlert(type, message) {
    // Create and show bootstrap alert
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;

    // Insert at top of card body
    const cardBody = document.querySelector('.card-body');
    cardBody.insertBefore(alertDiv, cardBody.firstChild);

    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (alertDiv.parentNode) {
            alertDiv.remove();
        }
    }, 5000);
}