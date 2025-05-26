
"""
Column mapping configuration for training plan files
"""

# Standard column names used internally
STANDARD_COLUMNS = {
    'DATE': 'Date',
    'ATHLETE_NAME': 'AthleteName', 
    'PLANNED_DISTANCE': 'PlannedDistanceKM',
    'PLANNED_PACE': 'PlannedPaceMinPerKM',
    'WORKOUT_TYPE': 'WorkoutType',
    'NOTES': 'Notes'
}

# Mapping of possible column variations to standard columns
COLUMN_MAPPING = {
    'Date': [
        'date', 'workout_date', 'training_date', 'Date', 'DATE',
        'activity_date', 'schedule_date'
    ],
    'AthleteName': [
        'athletename', 'athlete_name', 'athlete', 'name', 'AthleteName',
        'ATHLETE_NAME', 'participant', 'runner'
    ],
    'PlannedDistanceKM': [
        'planneddistancekm', 'planned_distance_km', 'distance_km', 'distance',
        'PlannedDistanceKM', 'PLANNED_DISTANCE_KM', 'target_distance',
        'planned_distance', 'Distance', 'DISTANCE'
    ],
    'PlannedPaceMinPerKM': [
        'plannedpaceminperkm', 'planned_pace_min_per_km', 'pace_min_per_km', 'pace',
        'PlannedPaceMinPerKM', 'PLANNED_PACE_MIN_PER_KM', 'target_pace',
        'planned_pace', 'Pace', 'PACE'
    ],
    'WorkoutType': [
        'workouttype', 'workout_type', 'type', 'WorkoutType', 'WORKOUT_TYPE',
        'activity_type', 'training_type', 'Type', 'TYPE'
    ],
    'Notes': [
        'notes', 'note', 'description', 'Notes', 'NOTES',
        'comments', 'remarks', 'Description', 'DESCRIPTION'
    ]
}

def get_column_mapping(actual_columns):
    """
    Get mapping from actual file columns to standard columns
    
    Args:
        actual_columns: List of actual column names from the file
        
    Returns:
        Dictionary mapping standard columns to actual column names
    """
    mapping = {}
    
    for standard_col, possible_names in COLUMN_MAPPING.items():
        mapping[standard_col] = None
        
        # First try exact match
        for actual_col in actual_columns:
            if actual_col == standard_col:
                mapping[standard_col] = actual_col
                break
        
        # If no exact match, try fuzzy matching
        if not mapping[standard_col]:
            for actual_col in actual_columns:
                for possible_name in possible_names:
                    if possible_name.lower() in actual_col.lower():
                        mapping[standard_col] = actual_col
                        break
                if mapping[standard_col]:
                    break
    
    return mapping

def validate_required_columns(column_mapping):
    """
    Validate that required columns are mapped
    
    Args:
        column_mapping: Dictionary from get_column_mapping()
        
    Returns:
        Tuple of (is_valid, missing_columns)
    """
    required_columns = ['Date', 'AthleteName']
    missing_columns = []
    
    for col in required_columns:
        if not column_mapping.get(col):
            missing_columns.append(col)
    
    return len(missing_columns) == 0, missing_columns
