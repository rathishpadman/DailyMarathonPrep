
let trainingPlanData = [];
let athletesList = [];

// Initialize the training plan editor
document.addEventListener('DOMContentLoaded', function() {
    loadTrainingPlan();
    loadAthletes();
});

function loadTrainingPlan() {
    fetch('/api/training-plan-data')
        .then(response => response.json())
        .then(data => {
            trainingPlanData = data.workouts || [];
            renderTrainingPlanTable();
        })
        .catch(error => {
            console.error('Error loading training plan:', error);
            renderTrainingPlanTable(); // Render empty table
        });
}

function loadAthletes() {
    fetch('/api/athletes-list')
        .then(response => response.json())
        .then(data => {
            athletesList = data.athletes || [];
        })
        .catch(error => {
            console.error('Error loading athletes:', error);
        });
}

function renderTrainingPlanTable() {
    const tbody = document.getElementById('trainingPlanBody');
    tbody.innerHTML = '';
    
    trainingPlanData.forEach((workout, index) => {
        const row = createWorkoutRow(workout, index);
        tbody.appendChild(row);
    });
    
    // Add empty row if no data
    if (trainingPlanData.length === 0) {
        addNewRow();
    }
}

function createWorkoutRow(workout, index) {
    const row = document.createElement('tr');
    row.innerHTML = `
        <td>
            <select class="form-select form-select-sm" onchange="updateWorkoutData(${index}, 'athlete_name', this.value)">
                <option value="">Select Athlete</option>
                ${athletesList.map(athlete => 
                    `<option value="${athlete.name}" ${workout.athlete_name === athlete.name ? 'selected' : ''}>${athlete.name}</option>`
                ).join('')}
            </select>
        </td>
        <td>
            <input type="date" class="form-control form-control-sm" 
                   value="${workout.date || ''}" 
                   onchange="updateWorkoutData(${index}, 'date', this.value)">
        </td>
        <td>
            <input type="number" class="form-control form-control-sm" 
                   value="${workout.distance_km || ''}" 
                   step="0.1" min="0"
                   onchange="updateWorkoutData(${index}, 'distance_km', this.value)">
        </td>
        <td>
            <input type="number" class="form-control form-control-sm" 
                   value="${workout.pace_min_per_km || ''}" 
                   step="0.1" min="0"
                   onchange="updateWorkoutData(${index}, 'pace_min_per_km', this.value)">
        </td>
        <td>
            <select class="form-select form-select-sm" onchange="updateWorkoutData(${index}, 'workout_type', this.value)">
                <option value="Easy Run" ${workout.workout_type === 'Easy Run' ? 'selected' : ''}>Easy Run</option>
                <option value="Tempo Run" ${workout.workout_type === 'Tempo Run' ? 'selected' : ''}>Tempo Run</option>
                <option value="Interval Training" ${workout.workout_type === 'Interval Training' ? 'selected' : ''}>Interval Training</option>
                <option value="Long Run" ${workout.workout_type === 'Long Run' ? 'selected' : ''}>Long Run</option>
                <option value="Recovery Run" ${workout.workout_type === 'Recovery Run' ? 'selected' : ''}>Recovery Run</option>
                <option value="Rest Day" ${workout.workout_type === 'Rest Day' ? 'selected' : ''}>Rest Day</option>
            </select>
        </td>
        <td>
            <input type="text" class="form-control form-control-sm" 
                   value="${workout.notes || ''}" 
                   onchange="updateWorkoutData(${index}, 'notes', this.value)">
        </td>
        <td>
            <button class="btn btn-sm btn-outline-danger" onclick="removeRow(${index})">
                <i data-feather="trash-2"></i>
            </button>
        </td>
    `;
    return row;
}

function updateWorkoutData(index, field, value) {
    if (!trainingPlanData[index]) {
        trainingPlanData[index] = {};
    }
    trainingPlanData[index][field] = value;
}

function addNewRow() {
    const newWorkout = {
        athlete_name: '',
        date: '',
        distance_km: '',
        pace_min_per_km: '',
        workout_type: 'Easy Run',
        notes: ''
    };
    
    trainingPlanData.push(newWorkout);
    const index = trainingPlanData.length - 1;
    const row = createWorkoutRow(newWorkout, index);
    document.getElementById('trainingPlanBody').appendChild(row);
    feather.replace();
}

function removeRow(index) {
    if (confirm('Are you sure you want to remove this workout?')) {
        trainingPlanData.splice(index, 1);
        renderTrainingPlanTable();
        feather.replace();
    }
}

function saveTrainingPlan() {
    const button = event.target;
    const originalText = button.innerHTML;
    
    button.disabled = true;
    button.innerHTML = '<i data-feather="loader" class="me-1"></i> Saving...';
    feather.replace();
    
    fetch('/api/save-training-plan', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            workouts: trainingPlanData.filter(workout => 
                workout.athlete_name && workout.date && workout.distance_km
            )
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAlert('Training plan saved successfully!', 'success');
        } else {
            showAlert(`Error saving training plan: ${data.message}`, 'danger');
        }
    })
    .catch(error => {
        console.error('Error saving training plan:', error);
        showAlert('Failed to save training plan. Please try again.', 'danger');
    })
    .finally(() => {
        button.disabled = false;
        button.innerHTML = originalText;
        feather.replace();
    });
}

function copyAthleteData() {
    const sourceAthlete = prompt('Enter source athlete name:');
    const targetAthlete = prompt('Enter target athlete name:');
    
    if (!sourceAthlete || !targetAthlete) return;
    
    const sourceWorkouts = trainingPlanData.filter(w => w.athlete_name === sourceAthlete);
    
    if (sourceWorkouts.length === 0) {
        alert('No workouts found for source athlete');
        return;
    }
    
    sourceWorkouts.forEach(workout => {
        const newWorkout = {...workout};
        newWorkout.athlete_name = targetAthlete;
        trainingPlanData.push(newWorkout);
    });
    
    renderTrainingPlanTable();
    feather.replace();
    showAlert(`Copied ${sourceWorkouts.length} workouts from ${sourceAthlete} to ${targetAthlete}`, 'success');
}

function duplicateAthlete() {
    const sourceAthlete = prompt('Enter athlete name to duplicate:');
    const newAthleteName = prompt('Enter new athlete name:');
    
    if (!sourceAthlete || !newAthleteName) return;
    
    const sourceWorkouts = trainingPlanData.filter(w => w.athlete_name === sourceAthlete);
    
    if (sourceWorkouts.length === 0) {
        alert('No workouts found for source athlete');
        return;
    }
    
    sourceWorkouts.forEach(workout => {
        const newWorkout = {...workout};
        newWorkout.athlete_name = newAthleteName;
        trainingPlanData.push(newWorkout);
    });
    
    renderTrainingPlanTable();
    feather.replace();
    showAlert(`Duplicated ${sourceWorkouts.length} workouts for ${newAthleteName}`, 'success');
}

function showAlert(message, type) {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    const container = document.querySelector('.container');
    container.insertBefore(alertDiv, container.firstChild);
    
    setTimeout(() => {
        alertDiv.remove();
    }, 5000);
}
</new_str>
