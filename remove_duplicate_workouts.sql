
-- SQL Script to Remove Duplicate Planned Workouts
-- Keeps the most recent record (highest ID) for each athlete_id + workout_date combination

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

-- Create a temporary table with the IDs to keep (highest ID for each group)
CREATE TEMPORARY TABLE workouts_to_keep AS
SELECT 
    athlete_id,
    DATE(workout_date) as workout_date,
    MAX(id) as keep_id
FROM planned_workout 
GROUP BY athlete_id, DATE(workout_date);

-- Delete duplicate records (keep only the most recent one)
DELETE pw FROM planned_workout pw
LEFT JOIN workouts_to_keep wtk ON pw.id = wtk.keep_id
WHERE wtk.keep_id IS NULL
AND EXISTS (
    SELECT 1 FROM workouts_to_keep wtk2 
    WHERE wtk2.athlete_id = pw.athlete_id 
    AND wtk2.workout_date = DATE(pw.workout_date)
);

-- Clean up temporary table
DROP TEMPORARY TABLE workouts_to_keep;

-- Verify the cleanup - this should return no rows if successful
SELECT 
    athlete_id,
    DATE(workout_date) as workout_date,
    COUNT(*) as remaining_count
FROM planned_workout 
GROUP BY athlete_id, DATE(workout_date)
HAVING COUNT(*) > 1;

-- Optional: Show summary of remaining records
SELECT 
    COUNT(*) as total_planned_workouts,
    COUNT(DISTINCT athlete_id) as unique_athletes,
    COUNT(DISTINCT DATE(workout_date)) as unique_dates
FROM planned_workout;
