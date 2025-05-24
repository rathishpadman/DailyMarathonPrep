import pandas as pd
import logging
from datetime import datetime
from typing import List, Dict, Optional
from config import Config

logger = logging.getLogger(__name__)

class ExcelReader:
    """Class for reading and processing training plan Excel files"""
    
    def __init__(self, file_path: str = None):
        self.file_path = file_path or Config.TRAINING_PLAN_FILE
    
    def read_training_plan(self) -> Optional[pd.DataFrame]:
        """Read the training plan from Excel file"""
        try:
            # Read Excel file
            df = pd.read_excel(self.file_path)
            
            # Validate required columns
            required_columns = [
                'Date', 'AthleteName', 'PlannedDistanceKM', 
                'PlannedPaceMinPerKM', 'WorkoutType', 'Notes'
            ]
            
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                logger.error(f"Missing required columns in Excel file: {missing_columns}")
                return None
            
            # Convert Date column to datetime
            df['Date'] = pd.to_datetime(df['Date'])
            
            # Clean and validate data
            df = self._clean_training_data(df)
            
            logger.info(f"Successfully read training plan with {len(df)} entries")
            return df
            
        except FileNotFoundError:
            logger.error(f"Training plan file not found: {self.file_path}")
            return None
        except Exception as e:
            logger.error(f"Failed to read training plan: {e}")
            return None
    
    def _clean_training_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean and validate training plan data"""
        try:
            # Remove rows with missing essential data
            df = df.dropna(subset=['Date', 'AthleteName', 'PlannedDistanceKM'])
            
            # Ensure numeric columns are properly formatted
            df['PlannedDistanceKM'] = pd.to_numeric(df['PlannedDistanceKM'], errors='coerce')
            df['PlannedPaceMinPerKM'] = pd.to_numeric(df['PlannedPaceMinPerKM'], errors='coerce')
            
            # Fill missing values
            df['WorkoutType'] = df['WorkoutType'].fillna('Regular Run')
            df['Notes'] = df['Notes'].fillna('')
            
            # Remove rows with invalid numeric values
            df = df.dropna(subset=['PlannedDistanceKM', 'PlannedPaceMinPerKM'])
            
            logger.info(f"Cleaned training data: {len(df)} valid entries")
            return df
            
        except Exception as e:
            logger.error(f"Failed to clean training data: {e}")
            return df
    
    def get_workouts_for_date(self, target_date: datetime, athlete_name: str = None) -> List[Dict]:
        """Get planned workouts for a specific date"""
        try:
            df = self.read_training_plan()
            if df is None:
                return []
            
            # Filter by date
            target_date_str = target_date.strftime('%Y-%m-%d')
            date_filter = df['Date'].dt.strftime('%Y-%m-%d') == target_date_str
            filtered_df = df[date_filter]
            
            # Filter by athlete if specified
            if athlete_name:
                filtered_df = filtered_df[filtered_df['AthleteName'] == athlete_name]
            
            # Convert to list of dictionaries
            workouts = []
            for _, row in filtered_df.iterrows():
                workout = {
                    'athlete_name': row['AthleteName'],
                    'workout_date': row['Date'],
                    'planned_distance_km': row['PlannedDistanceKM'],
                    'planned_pace_min_per_km': row['PlannedPaceMinPerKM'],
                    'workout_type': row['WorkoutType'],
                    'notes': row['Notes']
                }
                workouts.append(workout)
            
            logger.info(f"Found {len(workouts)} workouts for {target_date_str}")
            return workouts
            
        except Exception as e:
            logger.error(f"Failed to get workouts for date: {e}")
            return []
    
    def get_athletes_list(self) -> List[str]:
        """Get list of unique athletes from the training plan"""
        try:
            df = self.read_training_plan()
            if df is None:
                return []
            
            athletes = df['AthleteName'].unique().tolist()
            logger.info(f"Found {len(athletes)} athletes in training plan")
            return athletes
            
        except Exception as e:
            logger.error(f"Failed to get athletes list: {e}")
            return []
    
    def validate_excel_format(self) -> Dict[str, bool]:
        """Validate the format of the Excel file"""
        validation_results = {
            'file_exists': False,
            'required_columns': False,
            'data_types': False,
            'data_quality': False
        }
        
        try:
            # Check if file exists
            df = pd.read_excel(self.file_path)
            validation_results['file_exists'] = True
            
            # Check required columns
            required_columns = [
                'Date', 'AthleteName', 'PlannedDistanceKM', 
                'PlannedPaceMinPerKM', 'WorkoutType', 'Notes'
            ]
            has_all_columns = all(col in df.columns for col in required_columns)
            validation_results['required_columns'] = has_all_columns
            
            if has_all_columns:
                # Check data types
                df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
                df['PlannedDistanceKM'] = pd.to_numeric(df['PlannedDistanceKM'], errors='coerce')
                df['PlannedPaceMinPerKM'] = pd.to_numeric(df['PlannedPaceMinPerKM'], errors='coerce')
                
                # Check if conversions were successful
                valid_dates = df['Date'].notna().sum()
                valid_distances = df['PlannedDistanceKM'].notna().sum()
                valid_paces = df['PlannedPaceMinPerKM'].notna().sum()
                
                total_rows = len(df)
                if total_rows > 0:
                    validation_results['data_types'] = (
                        valid_dates / total_rows > 0.8 and
                        valid_distances / total_rows > 0.8 and
                        valid_paces / total_rows > 0.8
                    )
                    
                    validation_results['data_quality'] = (
                        df['AthleteName'].notna().sum() / total_rows > 0.8
                    )
            
        except Exception as e:
            logger.error(f"Excel validation failed: {e}")
        
        return validation_results
