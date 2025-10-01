"""
Data Processor Module
Responsible for reading and processing the Excel/CSV chart data
"""
import pandas as pd
import re
import unicodedata
import os
from typing import Dict, List, Tuple, Optional

class ChartDataProcessor:
    def __init__(self, data_path: str = "Chart.xlsx"):
        self.data_path = data_path
        self.chart_data = {}
        self.songs = []
        self.num_charts = 0
        
    def normalize_song_title(self, title: str) -> str:
        """
        Normalize song titles by removing extra spaces and special characters
        """
        if pd.isna(title) or title == "":
            return ""
        
        # Convert to string and strip whitespace
        title = str(title).strip()
        
        # Remove emojis and other special unicode characters
        title = ''.join(char for char in title if unicodedata.category(char)[0] != 'S')
        
        # Remove multiple spaces
        title = re.sub(r'\s+', ' ', title)
        
        # Remove weird symbols but keep basic punctuation
        title = re.sub(r'[^\w\s\-\.,:;&\(\)\'\"]+', '', title)
        
        return title.strip()
    
    def find_chart_columns(self, df: pd.DataFrame) -> List[Tuple[str, int]]:
        """
        Find chart columns (1-19) regardless of their data type in the Excel/CSV file
        Returns list of tuples: (column_name, chart_number)
        """
        chart_columns = []
        
        print("🔍 Analyzing column headers...")
        print(f"📋 Found columns: {list(df.columns)}")
        
        for col in df.columns:
            # Convert column name to string for analysis
            col_str = str(col).strip()
            
            # Try to match numbers 1-99 (extended range for flexibility)
            try:
                # Handle different possible formats
                if col_str.isdigit():
                    chart_num = int(col_str)
                elif isinstance(col, (int, float)):
                    chart_num = int(col)
                else:
                    # Try to extract number from string
                    number_match = re.match(r'^(\d+)$', col_str)
                    if number_match:
                        chart_num = int(number_match.group(1))
                    else:
                        continue
                
                # Check if it's in a reasonable range
                if 1 <= chart_num <= 99:
                    chart_columns.append((col, chart_num))
                    print(f"✅ Found chart column: '{col}' -> Chart {chart_num}")
            
            except (ValueError, TypeError):
                # Skip columns that can't be converted to numbers
                continue
        
        # Sort by chart number to ensure proper order
        chart_columns.sort(key=lambda x: x[1])
        
        return chart_columns
    
    def find_song_column(self, df: pd.DataFrame) -> Optional[str]:
        """
        Find the song column, handling different possible names
        """
        possible_song_columns = ['Song', 'song', 'SONG', 'Title', 'title', 'TITLE', 'Track', 'track', 'TRACK']
        
        for col in df.columns:
            col_str = str(col).strip()
            if col_str in possible_song_columns:
                print(f"✅ Found song column: '{col}'")
                return col
        
        # If exact match not found, try partial matches
        for col in df.columns:
            col_str = str(col).strip().lower()
            if 'song' in col_str or 'title' in col_str or 'track' in col_str:
                print(f"✅ Found song column (partial match): '{col}'")
                return col
        
        return None
    
    def read_data_file(self) -> pd.DataFrame:
        """
        Read data from Excel or CSV file based on file extension
        """
        file_ext = os.path.splitext(self.data_path)[1].lower()
        
        if file_ext in ['.xlsx', '.xls']:
            print(f"📊 Reading Excel file: {self.data_path}")
            # Try to read with sheet name 'Chart' first, then fall back to first sheet
            try:
                df = pd.read_excel(self.data_path, sheet_name="Chart")
            except:
                # If 'Chart' sheet doesn't exist, read the first sheet
                df = pd.read_excel(self.data_path)
                print(f"ℹ️ Using first sheet from Excel file")
        elif file_ext == '.csv':
            print(f"📊 Reading CSV file: {self.data_path}")
            df = pd.read_csv(self.data_path)
        else:
            raise ValueError(f"Unsupported file format: {file_ext}. Please use .xlsx, .xls, or .csv files.")
        
        return df
    
    def process_chart_data(self) -> Tuple[bool, str]:
        """
        Read and process the Excel/CSV chart data
        Returns: (success, message)
        """
        try:
            # Read data file (Excel or CSV)
            df = self.read_data_file()
            
            print(f"📊 Sheet dimensions: {df.shape[0]} rows × {df.shape[1]} columns")
            
            # Find song column
            song_column = self.find_song_column(df)
            if song_column is None:
                return False, "❌ Error: Song column not found. Expected columns like 'Song', 'Title', or 'Track'"
            
            # Find chart columns
            chart_columns = self.find_chart_columns(df)
            
            if not chart_columns:
                print("❌ No chart columns found!")
                print("🔍 Available columns:", list(df.columns))
                print("🔍 Column types:", [f"{col}: {type(col)}" for col in df.columns])
                return False, "❌ Error: No chart columns (numbered columns) found in the data file"
            
            self.num_charts = len(chart_columns)
            print(f"✅ Found {self.num_charts} chart editions: {[f'Chart {num}' for _, num in chart_columns]}")
            
            # Process each song
            processed_songs = 0
            skipped_rows = 0
            
            for idx, row in df.iterrows():
                song_title = self.normalize_song_title(row.get(song_column, ""))
                
                if not song_title:
                    skipped_rows += 1
                    continue
                
                song_data = {
                    "title": song_title,
                    "positions": {}
                }
                
                # Process positions for each chart
                for col_name, chart_num in chart_columns:
                    position = row.get(col_name)
                    
                    # Handle different representations of missing data
                    if pd.isna(position) or position == "--" or position == "" or position == " ":
                        song_data["positions"][chart_num] = None
                    else:
                        try:
                            # Convert to integer position
                            position_val = str(position).strip()
                            if position_val == "--" or position_val == "":
                                song_data["positions"][chart_num] = None
                            else:
                                song_data["positions"][chart_num] = int(float(position_val))
                        except (ValueError, TypeError):
                            print(f"⚠️  Warning: Invalid position value '{position}' for song '{song_title}' in chart {chart_num}")
                            song_data["positions"][chart_num] = None
                
                # Calculate total charts appeared in
                song_data["total_charts"] = sum(
                    1 for pos in song_data["positions"].values() 
                    if pos is not None
                )
                
                # Only include songs that appear in at least one chart
                if song_data["total_charts"] > 0:
                    self.songs.append(song_data)
                    processed_songs += 1
                else:
                    skipped_rows += 1
            
            print(f"✅ Successfully processed {processed_songs} songs")
            print(f"⏭️  Skipped {skipped_rows} rows (empty or no chart positions)")
            print(f"📈 Total charts: {self.num_charts}")
            
            # Show some sample data for verification
            if processed_songs > 0:
                print(f"\n📋 Sample processed songs:")
                for i, song in enumerate(self.songs[:3]):  # Show first 3 songs
                    chart_positions = [f"Chart {num}: {pos if pos else '--'}" 
                                     for num, pos in sorted(song["positions"].items())[:5]]  # Show first 5 charts
                    print(f"   {i+1}. '{song['title']}' - {', '.join(chart_positions)}... (appears in {song['total_charts']} charts)")
            
            file_type = "Excel" if os.path.splitext(self.data_path)[1].lower() in ['.xlsx', '.xls'] else "CSV"
            return True, f"Successfully loaded {processed_songs} songs from {self.num_charts} charts ({file_type} file)"
            
        except FileNotFoundError:
            return False, f"❌ Error: Data file '{self.data_path}' not found"
        except ValueError as e:
            if "Worksheet named 'Chart' not found" in str(e):
                return False, f"❌ Error: Sheet 'Chart' not found in the Excel file. Available sheets might have different names."
            else:
                return False, f"❌ Error reading data file: {str(e)}"
        except Exception as e:
            return False, f"❌ Unexpected error: {str(e)}"
    
    def get_chart_data(self, chart_number: int) -> List[Dict]:
        """
        Get data for a specific chart number, sorted by position
        """
        chart_data = []
        
        for song in self.songs:
            position = song["positions"].get(chart_number)
            
            if position is not None:
                # Get previous position
                prev_position = None
                if chart_number > 1:
                    # Find the previous chart number that exists
                    for prev_num in range(chart_number - 1, 0, -1):
                        if prev_num in song["positions"]:
                            prev_position = song["positions"].get(prev_num)
                            break
                
                chart_data.append({
                    "position": position,
                    "prev_position": prev_position,
                    "title": song["title"],
                    "total_charts": song["total_charts"]
                })
        
        # Sort by position
        chart_data.sort(key=lambda x: x["position"])
        
        return chart_data
    
    def get_song_history(self, song_title: str) -> Dict:
        """
        Get the complete chart history for a specific song
        """
        for song in self.songs:
            if song["title"].lower() == song_title.lower():
                return {
                    "title": song["title"],
                    "positions": song["positions"],
                    "total_charts": song["total_charts"]
                }
        return None
    
    def get_all_songs_data(self) -> List[Dict]:
        """
        Get all songs with their complete data
        """
        return self.songs
