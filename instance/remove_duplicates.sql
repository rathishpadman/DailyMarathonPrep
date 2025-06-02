-- SQL Script to Remove Duplicate Planned Workouts
-- First, let's see what duplicates exist
SELECT 
    athlete_id,
    DATE(workout_date) as workout_date,
    COUNT(*) as duplicate_count,
    GROUP_CONCAT(id ORDER BY id) as all_ids
FROM planned_workout 
GROUP BY athlete_id, DATE(workout_date)
HAVING COUNT(*) > 1
ORDER BY athlete_id, workout_date;

-- Create a temporary table to keep the most recent records
CREATE TEMPORARY TABLE workouts_to_keep AS
SELECT 
    athlete_id,
    DATE(workout_date) as workout_date,
    MAX(id) as keep_id
FROM planned_workout 
GROUP BY athlete_id, DATE(workout_date);

-- Delete duplicate records (keep only the most recent one)
DELETE FROM planned_workout 
WHERE id NOT IN (
    SELECT keep_id FROM workouts_to_keep
);

-- Clean up temporary table
DROP TABLE workouts_to_keep;

-- Verify the cleanup - this should show no duplicates if successful
SELECT 
    athlete_id,
    DATE(workout_date) as workout_date,
    COUNT(*) as remaining_count
FROM planned_workout 
GROUP BY athlete_id, DATE(workout_date)
HAVING COUNT(*) > 1;