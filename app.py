"""
Flask Application
Main web server responsible for routing and serving the chart data
"""
from flask import Flask, render_template, jsonify, request
from data_processor import ChartDataProcessor
import os

app = Flask(__name__)

# Initialize data processor
processor = ChartDataProcessor()

# Load data on startup - check if we're in the reloader process
if os.environ.get('WERKZEUG_RUN_MAIN') == 'true' or not app.debug:
    success, message = processor.process_chart_data()
    print(message)
    
    if not success:
        print("⚠️  Warning: Starting server without data. Please fix the Excel file.")
else:
    # In the reloader parent process, just set minimal values
    success = False
    print("🔄 Skipping data load in reloader parent process...")

def calculate_total_points(song_data):
    """Calculate total points for a song across all charts"""
    total_points = 0
    for position in song_data["positions"].values():
        if position is not None and position <= 100:
            total_points += (101 - position)
    return total_points

def count_number_ones(song_data):
    """Count how many times a song reached #1"""
    count = 0
    for position in song_data["positions"].values():
        if position == 1:
            count += 1
    return count

@app.route('/')
def index():
    """Render the main page"""
    return render_template('index.html', 
                         num_charts=processor.num_charts,
                         has_data=success)

@app.route('/api/chart/<int:chart_number>')
def get_chart(chart_number):
    """
    API endpoint to get data for a specific chart
    """
    if not success:
        return jsonify({"error": "No data available"}), 500
    
    if chart_number < 0 or chart_number > processor.num_charts:
        return jsonify({"error": "Invalid chart number"}), 400
    
    # Special case for "All Songs" (chart_number = 0)
    if chart_number == 0:
        formatted_data = []
        movement_counts = {
            "new": 0,
            "riser": 0,
            "faller": 0,
            "same": 0,
            "reentry": 0
        }
        
        for song in processor.songs:
            # Use position from most recent chart (19) if available
            latest_position = song["positions"].get(processor.num_charts)
            if latest_position is None:
                # Find the most recent chart where this song appeared
                for i in range(processor.num_charts, 0, -1):
                    if song["positions"].get(i) is not None:
                        latest_position = song["positions"].get(i)
                        break
            
            # Calculate total points
            total_points = calculate_total_points(song)
            
            # Count #1 positions
            number_ones = count_number_ones(song)
            
            formatted_data.append({
                "position": latest_position if latest_position else 999,
                "prev_position": "--",
                "title": song["title"],
                "total_charts": song["total_charts"],
                "movement_type": "same",
                "movement_value": 0,
                "total_points": total_points,
                "number_ones": number_ones
            })
        
        # Sort by total points (descending)
        formatted_data.sort(key=lambda x: x["total_points"], reverse=True)
        
        # Update positions based on points ranking
        for idx, item in enumerate(formatted_data, 1):
            item["position"] = idx
        
        return jsonify({
            "chart_number": 0,
            "data": formatted_data,
            "movement_counts": movement_counts
        })
    
    # Regular chart processing
    chart_data = processor.get_chart_data(chart_number)
    
    # Initialize movement counts
    movement_counts = {
        "new": 0,
        "riser": 0,
        "faller": 0,
        "same": 0,
        "reentry": 0
    }
    
    # Format data for frontend with additional metadata
    formatted_data = []
    for item in chart_data:
        # Calculate total points and #1 count for this song
        for song in processor.songs:
            if song["title"] == item["title"]:
                total_points = calculate_total_points(song)
                number_ones = count_number_ones(song)
                break
        
        # Determine movement type for coloring
        movement_type = "same"
        movement_value = 0
        
        if item["prev_position"] is None:
            # Check if this is a new entry or re-entry
            is_reentry = False
            if chart_number > 1:
                # Check if song appeared in any previous charts
                for song in processor.songs:
                    if song["title"] == item["title"]:
                        for chart_num in range(1, chart_number):
                            if song["positions"].get(chart_num) is not None:
                                is_reentry = True
                                break
                        break
            
            movement_type = "reentry" if is_reentry else "new"
        else:
            movement_value = item["prev_position"] - item["position"]
            if movement_value >= 1:
                movement_type = "riser"
            elif movement_value <= -1:
                movement_type = "faller"
            else:
                movement_type = "same"
        
        # Update counts
        movement_counts[movement_type] += 1
        
        formatted_data.append({
            "position": item["position"],
            "prev_position": item["prev_position"] if item["prev_position"] else "--",
            "title": item["title"],
            "total_charts": item["total_charts"],
            "movement_type": movement_type,
            "movement_value": movement_value,
            "total_points": total_points,
            "number_ones": number_ones
        })
    
    return jsonify({
        "chart_number": chart_number,
        "data": formatted_data,
        "movement_counts": movement_counts
    })

@app.route('/api/info')
def get_info():
    """Get general information about the charts"""
    return jsonify({
        "num_charts": processor.num_charts,
        "num_songs": len(processor.songs),
        "has_data": success
    })

if __name__ == '__main__':
    print("\n🎵 Music Chart Website Generator")
    print("="*40)
    print(f"🌐 Starting server at http://127.0.0.1:5000")
    print("="*40 + "\n")
    
    app.run(debug=True, port=5000)