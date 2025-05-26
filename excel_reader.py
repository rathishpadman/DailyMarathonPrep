import pandas as pd
import logging
import os
from datetime import datetime
from typing import List, Dict, Optional
from config import Config
from openpyxl.utils.exceptions import InvalidFileException

logger = logging.getLogger(__name__)

class ExcelReader:
    """Class for reading and processing training plan Excel and CSV files"""

    def __init__(self, file_path: Optional[str] = None):
        self.file_path: str = file_path or Config.TRAINING_PLAN_FILE

    def read_training_plan(self) -> Optional[pd.DataFrame]:
        """Read the training plan from Excel or CSV file"""
        try:
            logger.info(f"Reading training plan from {self.file_path}")

            # Determine if the file is Excel or CSV based on the extension
            if self.file_path.lower().endswith(('.xlsx', '.xls')):
                df: pd.DataFrame = pd.read_excel(self.file_path, engine='openpyxl')
            elif self.file_path.lower().endswith('.csv'):
                df: pd.DataFrame = pd.read_csv(self.file_path)
            else:
                logger.error("Unsupported file format. Please provide an Excel or CSV file.")
                return None

            required_columns = [
                'Date',
                'AthleteName',
                'PlannedDistanceKM',
                'PlannedPaceMinPerKM',
                'WorkoutType',
                'Notes',
            ]

            missing_columns = [
                col for col in required_columns if col not in df.columns
            ]
            if missing_columns:
                logger.error(
                    f"Missing required columns in training plan: {missing_columns}"
                )
                return None

            df['Date'] = pd.to_datetime(df['Date'], errors='coerce', dayfirst=True)

            if df['Date'].isna().any():
                logger.warning(
                    "Some dates in the training plan could not be parsed."
                )

            if not pd.api.types.is_datetime64_any_dtype(df['Date']):
                logger.error(
                    "Date column is invalid. Ensure it is in datetime format.")
                return None

            cleaned_df: pd.DataFrame = self._clean_training_data(df)

            if cleaned_df.empty:
                logger.warning(
                    "No valid training plan entries found after cleaning.")
                return None

            logger.info(
                f"Successfully read training plan with {len(cleaned_df)} entries."
            )
            return cleaned_df

        except FileNotFoundError:
            logger.error(f"Training plan file not found: {self.file_path}")
            return None
        except InvalidFileException as e:
            logger.error(f"Invalid Excel file format: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to read training plan: {e}")
            return None

    def _clean_training_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean and validate training plan data"""
        try:
            df_clean: pd.DataFrame = df.dropna(
                subset=['Date', 'AthleteName', 'PlannedDistanceKM'])

            df_clean['PlannedDistanceKM'] = pd.to_numeric(
                df_clean['PlannedDistanceKM'], errors='coerce')
            df_clean['PlannedPaceMinPerKM'] = pd.to_numeric(
                df_clean['PlannedPaceMinPerKM'], errors='coerce')

            df_clean['WorkoutType'].fillna('Regular Run', inplace=True)
            df_clean['Notes'].fillna('', inplace=True)

            df_clean = df_clean.dropna(
                subset=['PlannedDistanceKM', 'PlannedPaceMinPerKM'])

            if df_clean.empty:
                logger.warning("No data remaining after cleaning process.")
                return df_clean

            logger.info(
                f"Cleaned training data: {len(df_clean)} valid entries.")
            return df_clean

        except Exception as e:
            logger.error(f"Failed to clean training data: {e}")
            return pd.DataFrame()

    def get_workouts_for_date(
            self,
            target_date: datetime,
            athlete_name: Optional[str] = None) -> List[Dict]:
        """Get planned workouts for a specific date"""
        try:
            df = self.read_training_plan()
            if df is None or df.empty:
                return []

            if 'Date' not in df.columns or not pd.api.types.is_datetime64_any_dtype(
                    df['Date']):
                logger.error(
                    "Date column is missing or invalid in the DataFrame.")
                return []

            # Normalize target date
            if isinstance(target_date, datetime):
                target_date_only = target_date.date()
            else:
                logger.error(f"Invalid target_date type: {type(target_date)}")
                return []

            filtered_df = df[df['Date'].dt.date == target_date_only].copy()
            if athlete_name:
                filtered_df = filtered_df[filtered_df['AthleteName'] ==
                                          athlete_name].copy()

            workouts: List[Dict] = []
            for _, row in filtered_df.iterrows():
                workout = {
                    'athlete_name':
                    str(row['AthleteName'])
                    if pd.notna(row['AthleteName']) else '',
                    'workout_date':
                    row['Date'].date() if pd.notna(row['Date']) else None,
                    'planned_distance_km':
                    row['PlannedDistanceKM']
                    if pd.notna(row['PlannedDistanceKM']) else 0.0,
                    'planned_pace_min_per_km':
                    row['PlannedPaceMinPerKM']
                    if pd.notna(row['PlannedPaceMinPerKM']) else 0.0,
                    'workout_type':
                    str(row['WorkoutType'])
                    if pd.notna(row['WorkoutType']) else 'N/A',
                    'notes':
                    str(row['Notes']) if pd.notna(row['Notes']) else '',
                }
                workouts.append(workout)

            logger.info(
                f"Found {len(workouts)} workouts for {target_date_only}")
            return workouts

        except Exception as e:
            logger.error(f"Failed to get workouts for date {target_date}: {e}")
            return []

    def get_athletes_list(self) -> List[str]:
        """Get list of unique athletes from the training plan"""
        try:
            df = self.read_training_plan()
            if df is None or df.empty:
                return []

            if 'AthleteName' not in df.columns:
                logger.warning("AthleteName column is missing.")
                return []

            athletes = df['AthleteName'].dropna().astype(str).unique().tolist()
            logger.info(f"Found {len(athletes)} unique athletes.")
            return athletes

        except Exception as e:
            logger.error(f"Failed to get athletes list: {e}")
            return []

    def validate_excel_format(self) -> Dict[str, bool]:
        """Validate the format of the Excel or CSV file"""
        validation_results = {
            'file_exists': False,
            'required_columns': False,
            'data_types': False,
            'data_quality': False,
        }

        try:
            # Log the file path being validated
            logger.info(f"Validating format for file: {self.file_path}")
            
            # Check if file exists first
            if not os.path.exists(self.file_path):
                logger.error(f"File does not exist: {self.file_path}")
                return validation_results
            
            # Try to read the file based on extension
            df: pd.DataFrame = None
            if self.file_path.lower().endswith(('.xlsx', '.xls')):
                df = pd.read_excel(self.file_path, engine='openpyxl')
            elif self.file_path.lower().endswith('.csv'):
                df = pd.read_csv(self.file_path)
            else:
                logger.error("Unsupported file format. Please provide an Excel or CSV file.")
                return validation_results

            validation_results['file_exists'] = True

            required_columns = [
                'Date',
                'AthleteName',
                'PlannedDistanceKM',
                'PlannedPaceMinPerKM',
                'WorkoutType',
                'Notes',
            ]

            has_all_columns = all(col in df.columns for col in required_columns)
            validation_results['required_columns'] = has_all_columns

            if has_all_columns:
                # Check data types and quality
                try:
                    # Test date parsing with flexible format
                    pd.to_datetime(df['Date'].head(), errors='coerce', dayfirst=True)
                    
                    # Test numeric columns
                    pd.to_numeric(df['PlannedDistanceKM'].head(), errors='coerce')
                    pd.to_numeric(df['PlannedPaceMinPerKM'].head(), errors='coerce')
                    
                    validation_results['data_types'] = True
                    validation_results['data_quality'] = True
                    
                except Exception as e:
                    logger.warning(f"Data validation issues: {e}")
                    validation_results['data_types'] = False
                    validation_results['data_quality'] = False

        except FileNotFoundError:
            logger.error(f"Validation failed: File not found at {self.file_path}")
        except InvalidFileException as e:
            logger.error(f"Invalid file format: {e}")
        except Exception as e:
            logger.error(f"Unexpected error during validation: {e}")

        return validation_results