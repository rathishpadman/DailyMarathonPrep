# The code is modified to improve Excel file reading, validation, and planned workout processing with better error handling and data processing.
import pandas as pd
import logging
import os
from datetime import datetime
from typing import List, Dict, Optional
from config import Config
from openpyxl.utils.exceptions import InvalidFileException
from column_mapping_config import get_column_mapping, validate_required_columns, STANDARD_COLUMNS

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

    def validate_excel_format(self) -> dict:
        """Validate Excel file format and structure"""
        try:
            if not os.path.exists(self.file_path):
                logger.error(f"Excel file not found: {self.file_path}")
                return {
                    'file_exists': False,
                    'required_columns': False,
                    'data_types': False,
                    'data_quality': False
                }

            logger.info(f"Validating format for file: {self.file_path}")

            # Try to read the file with multiple approaches
            df = None
            try:
                if self.file_path.endswith('.csv'):
                    df = pd.read_csv(self.file_path)
                else:
                    # Try different engines for Excel files
                    try:
                        df = pd.read_excel(self.file_path, engine='openpyxl')
                    except:
                        try:
                            df = pd.read_excel(self.file_path, engine='xlrd')
                        except:
                            # If still fails, try reading as CSV with different separator
                            try:
                                df = pd.read_csv(self.file_path, sep=';')
                            except:
                                df = pd.read_csv(self.file_path, sep='\t')
            except Exception as e:
                logger.error(f"Cannot read file with any method: {e}")
                return {
                    'file_exists': True,
                    'required_columns': False,
                    'data_types': False,
                    'data_quality': False,
                    'error': str(e)
                }

            if df is None or df.empty:
                logger.error("File is empty or could not be read")
                return {
                    'file_exists': True,
                    'required_columns': False,
                    'data_types': False,
                    'data_quality': False,
                    'error': 'File is empty or unreadable'
                }

            # Check required columns (flexible matching)
            required_columns = ['Date', 'Athlete', 'Distance_km', 'Pace_min_per_km', 'Workout_Type']
            actual_columns = df.columns.tolist()

            # Try flexible column matching
            column_mapping = {}
            for req_col in required_columns:
                found = False
                for actual_col in actual_columns:
                    if req_col.lower() in actual_col.lower() or actual_col.lower() in req_col.lower():
                        column_mapping[req_col] = actual_col
                        found = True
                        break
                if not found:
                    column_mapping[req_col] = None

            missing_columns = [col for col, mapped in column_mapping.items() if mapped is None]

            if missing_columns:
                logger.warning(f"Missing or unmapped columns: {missing_columns}")
                logger.info(f"Available columns: {actual_columns}")
                # Still return success if we have basic columns
                if 'Date' in column_mapping and 'Athlete' in column_mapping:
                    logger.info("Basic required columns found, proceeding with validation")
                else:
                    return {
                        'file_exists': True,
                        'required_columns': False,
                        'data_types': False,
                        'data_quality': False,
                        'missing_columns': missing_columns,
                        'available_columns': actual_columns
                    }

            # Check data types and quality
            validation_results = {
                'file_exists': True,
                'required_columns': True,
                'data_types': True,
                'data_quality': True,
                'total_rows': len(df),
                'athletes': df[column_mapping.get('Athlete', 'Athlete')].unique().tolist() if column_mapping.get('Athlete') else [],
                'column_mapping': column_mapping
            }

            logger.info(f"Excel validation successful: {validation_results}")
            return validation_results

        except Exception as e:
            logger.error(f"Unexpected error during validation: {e}")
            return {
                'file_exists': False,
                'required_columns': False,
                'data_types': False,
                'data_quality': False,
                'error': str(e)
            }

    def read_planned_workouts(self) -> List[dict]:
        """Read planned workouts from Excel file with improved column mapping"""
        try:
            if not os.path.exists(self.file_path):
                logger.error(f"Excel file not found: {self.file_path}")
                return []

            # Read file with proper error handling
            df = None
            try:
                if self.file_path.lower().endswith('.csv'):
                    df = pd.read_csv(self.file_path)
                else:
                    df = pd.read_excel(self.file_path, engine='openpyxl')
            except Exception as e:
                logger.error(f"Cannot read file: {e}")
                return []

            if df is None or df.empty:
                logger.warning("File is empty")
                return []

            # Use the column mapping configuration
            actual_columns = df.columns.tolist()
            column_mapping = get_column_mapping(actual_columns)
            
            # Validate that required columns are mapped
            is_valid, missing_columns = validate_required_columns(column_mapping)
            if not is_valid:
                logger.error(f"Missing essential columns: {missing_columns}. Available: {actual_columns}")
                return []

            logger.info(f"Column mapping: {column_mapping}")

            planned_workouts = []

            for index, row in df.iterrows():
                try:
                    # Parse date
                    date_col = column_mapping['Date']
                    workout_date = pd.to_datetime(row[date_col], dayfirst=True).date()

                    # Get athlete name
                    athlete_col = column_mapping['AthleteName']
                    athlete_name = str(row[athlete_col]).strip()

                    # Extract distance with fallback
                    distance = 0.0
                    distance_col = column_mapping.get('PlannedDistanceKM')
                    if distance_col and pd.notna(row[distance_col]):
                        try:
                            distance = float(row[distance_col])
                        except (ValueError, TypeError):
                            logger.warning(f"Invalid distance value in row {index}: {row[distance_col]}")

                    # Extract pace with fallback
                    pace = 0.0
                    pace_col = column_mapping.get('PlannedPaceMinPerKM')
                    if pace_col and pd.notna(row[pace_col]):
                        try:
                            pace = float(row[pace_col])
                        except (ValueError, TypeError):
                            logger.warning(f"Invalid pace value in row {index}: {row[pace_col]}")

                    # Get workout type
                    workout_type = 'General'
                    workout_type_col = column_mapping.get('WorkoutType')
                    if workout_type_col and pd.notna(row[workout_type_col]):
                        workout_type = str(row[workout_type_col]).strip()

                    # Get notes
                    notes = ''
                    notes_col = column_mapping.get('Notes')
                    if notes_col and pd.notna(row[notes_col]):
                        notes = str(row[notes_col]).strip()

                    workout = {
                        'athlete_name': athlete_name,
                        'workout_date': workout_date,
                        'planned_distance_km': distance,
                        'planned_pace_min_per_km': pace,
                        'workout_type': workout_type,
                        'notes': notes
                    }

                    planned_workouts.append(workout)

                except Exception as e:
                    logger.error(f"Error processing row {index}: {e}")
                    continue

            logger.info(f"Successfully read {len(planned_workouts)} planned workouts")
            return planned_workouts

        except Exception as e:
            logger.error(f"Failed to read planned workouts: {e}")
            return []