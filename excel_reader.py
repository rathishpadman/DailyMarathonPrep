import pandas as pd
import logging
from datetime import datetime, date
from typing import List, Dict, Optional
from config import Config
from openpyxl.utils.exceptions import InvalidFileException

logger = logging.getLogger(__name__)


class ExcelReader:
    """Class for reading and processing training plan Excel files"""

    def __init__(self, file_path: Optional[str] = None):
        self.file_path: str = file_path or Config.TRAINING_PLAN_FILE

    def read_training_plan(self) -> Optional[pd.DataFrame]:
        """Read the training plan from Excel file"""
        try:
            df: pd.DataFrame = pd.read_excel(self.file_path, engine='openpyxl')

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
                    f"Missing required columns in Excel file: {missing_columns}"
                )
                return None

            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')

            if bool(df['Date'].isna().any()):
                logger.warning(
                    "Some dates in the Excel 'Date' column could not be parsed and were set to NaT."
                )

            if not pd.api.types.is_datetime64_any_dtype(df['Date']):
                logger.error(
                    "Date column could not be fully converted to datetime format."
                )
                return None

            cleaned_df: pd.DataFrame = self._clean_training_data(df)

            if cleaned_df.empty:
                logger.warning(
                    "No valid training plan entries after cleaning.")
                return None

            logger.info(
                f"Successfully read training plan with {len(cleaned_df)} entries."
            )
            return cleaned_df

        except FileNotFoundError:
            logger.error(f"Training plan file not found: {self.file_path}")
            return None
        except InvalidFileException as e:
            logger.error(
                f"Excel validation failed: Invalid .xlsx file. Error: {e}")
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

            df_clean['WorkoutType'] = df_clean['WorkoutType'].fillna(
                'Regular Run')
            df_clean['Notes'] = df_clean['Notes'].fillna('')

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
                logger.error("Date column is missing or not of datetime type.")
                return []

            if isinstance(target_date, datetime):
                target_date_only = target_date.date()
            elif isinstance(target_date, date):
                target_date_only = target_date
            else:
                try:
                    target_date_only = datetime.strptime(
                        str(target_date), '%Y-%m-%d').date()
                except ValueError:
                    logger.error(f"Invalid target_date format: {target_date}")
                    return []

            filtered_df = df[df['Date'].dt.date == target_date_only].copy()

            if athlete_name:
                if 'AthleteName' not in filtered_df.columns:
                    logger.warning(
                        "AthleteName column missing in filtered data.")
                    return []
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
                    float(row['PlannedDistanceKM'])
                    if pd.notna(row['PlannedDistanceKM']) else 0.0,
                    'planned_pace_min_per_km':
                    float(row['PlannedPaceMinPerKM'])
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
        """Validate the format of the Excel file"""
        validation_results = {
            'file_exists': False,
            'required_columns': False,
            'data_types': False,
            'data_quality': False,
        }

        try:
            df: pd.DataFrame = pd.read_excel(self.file_path, engine='openpyxl')
            validation_results['file_exists'] = True

            required_columns = [
                'Date',
                'AthleteName',
                'PlannedDistanceKM',
                'PlannedPaceMinPerKM',
                'WorkoutType',
                'Notes',
            ]

            has_all_columns = all(col in df.columns
                                  for col in required_columns)
            validation_results['required_columns'] = has_all_columns

            if has_all_columns:
                df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
                df['PlannedDistanceKM'] = pd.to_numeric(
                    df['PlannedDistanceKM'], errors='coerce')
                df['PlannedPaceMinPerKM'] = pd.to_numeric(
                    df['PlannedPaceMinPerKM'], errors='coerce')

                total_rows = len(df)
                if total_rows > 0:
                    valid_dates = df['Date'].notna().sum()
                    valid_distances = df['PlannedDistanceKM'].notna().sum()
                    valid_paces = df['PlannedPaceMinPerKM'].notna().sum()

                    validation_results['data_types'] = (
                        valid_dates / total_rows > 0.8
                        and valid_distances / total_rows > 0.8
                        and valid_paces / total_rows > 0.8)

                    validation_results['data_quality'] = df[
                        'AthleteName'].notna().sum() / total_rows > 0.8
                else:
                    validation_results['data_types'] = False
                    validation_results['data_quality'] = False

        except FileNotFoundError:
            logger.error(
                f"Excel validation failed: File not found at {self.file_path}")
        except InvalidFileException as e:
            logger.error(
                f"Excel validation failed: The file is not a valid .xlsx file. Error: {e}"
            )
        except Exception as e:
            logger.error(f"Unexpected error during Excel validation: {e}")

        return validation_results
