"""
Flask Application
Main web server responsible for routing and serving the chart data
Includes Twitch OAuth integration for user authentication
"""
from flask import Flask, render_template, jsonify, request, redirect, session, url_for
from data_processor import ChartDataProcessor
from comment_manager import CommentManager
import os
import sys
import requests
from datetime import timedelta
from functools import wraps
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-change-this')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

# Twitch OAuth configuration
TWITCH_CLIENT_ID = os.getenv('TWITCH_CLIENT_ID')
TWITCH_CLIENT_SECRET = os.getenv('TWITCH_CLIENT_SECRET')
TWITCH_REDIRECT_URI = os.getenv('TWITCH_REDIRECT_URI', 'https://qr-chart-web.onrender.com/auth/callback')
TWITCH_AUTH_BASE_URL = 'https://id.twitch.tv/oauth2/authorize'
TWITCH_TOKEN_URL = 'https://id.twitch.tv/oauth2/token'
TWITCH_API_URL = 'https://api.twitch.tv/helix/users'

# Get data file from command line argument or use default
data_file = "Chart.xlsx"
print(f"📂 Using default data file: {data_file}")

# Initialize data processor
processor = ChartDataProcessor(data_file)
comment_manager = CommentManager()

# Load data on startup
if os.environ.get('WERKZEUG_RUN_MAIN') == 'true' or not app.debug:
    success, message = processor.process_chart_data()
    print(message)
    
    if not success:
        print("⚠️  Warning: Starting server without data. Please fix the data file.")
else:
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

def get_top_spot(song_data):
    """Get the best (lowest) position achieved by a song"""
    positions = [pos for pos in song_data["positions"].values() if pos is not None]
    return min(positions) if positions else None

def calculate_song_stats(song_data):
    """Calculate statistics for a song"""
    positions = [pos for pos in song_data["positions"].values() if pos is not None]
    
    if not positions:
        return {
            "total_charts": 0,
            "avg_position": 0,
            "best_position": 0,
            "worst_position": 0
        }
    
    return {
        "total_charts": len(positions),
        "avg_position": sum(positions) / len(positions),
        "best_position": min(positions),
        "worst_position": max(positions)
    }

# ============ AUTHENTICATION ROUTES ============

@app.route('/auth/login')
def auth_login():
    """Redirect user to Twitch OAuth login page"""
    auth_url = f"{TWITCH_AUTH_BASE_URL}?client_id={TWITCH_CLIENT_ID}&redirect_uri={TWITCH_REDIRECT_URI}&response_type=code&scope=user:read:email"
    return redirect(auth_url)

@app.route('/auth/callback')
def auth_callback():
    """Handle Twitch OAuth callback - exchange code for access token and retrieve user info"""
    code = request.args.get('code')
    
    if not code:
        return "Error: No authorization code received", 400
    
    try:
        # Exchange code for access token
        token_response = requests.post(
            TWITCH_TOKEN_URL,
            data={
                'client_id': TWITCH_CLIENT_ID,
                'client_secret': TWITCH_CLIENT_SECRET,
                'code': code,
                'grant_type': 'authorization_code',
                'redirect_uri': TWITCH_REDIRECT_URI
            }
        )
        
        if token_response.status_code != 200:
            return "Error: Failed to exchange code for token", 400
        
        token_data = token_response.json()
        access_token = token_data.get('access_token')
        
        # Get user info from Twitch API (includes display_name with proper casing)
        user_response = requests.get(
            TWITCH_API_URL,
            headers={
                'Authorization': f'Bearer {access_token}',
                'Client-ID': TWITCH_CLIENT_ID
            }
        )
        
        if user_response.status_code != 200:
            return "Error: Failed to get user info", 400
        
        user_data = user_response.json()
        # Use display_name (properly cased) instead of login (lowercase)
        username = user_data['data'][0]['display_name']
        profile_pic = user_data['data'][0]['profile_image_url']
        
        # Store in session
        session.permanent = True
        session['user'] = username
        session['profile_pic'] = profile_pic
        session['access_token'] = access_token
        
        print(f"✅ User '{username}' logged in via Twitch")
        
        # Redirect back to main page
        return redirect('/')
        
    except Exception as e:
        print(f"❌ OAuth error: {e}")
        return f"Error: {str(e)}", 400

@app.route('/auth/logout', methods=['POST'])
def auth_logout():
    """Logout user and clear session"""
    if 'user' in session:
        username = session.get('user')
        session.clear()
        print(f"ℹ️  User '{username}' logged out")
    return jsonify({"success": True}), 200

@app.route('/api/auth/status')
def auth_status():
    """Check if user is logged in and return user info"""
    user = session.get('user')
    profile_pic = session.get('profile_pic')
    if user:
        return jsonify({
            "logged_in": True,
            "username": user,
            "profile_pic": profile_pic
        })
    return jsonify({
        "logged_in": False,
        "username": None,
        "profile_pic": None
    })

# ============ MAIN ROUTES ============

@app.route('/')
def index():
    """Render the main page"""
    return render_template('index.html', 
                         num_charts=processor.num_charts,
                         has_data=success)

@app.route('/song/<path:song_title>')
def song_page(song_title):
    """Render the song detail page"""
    if not success:
        return "No data available", 500
    
    # Verify song exists
    song = processor.get_song_history(song_title)
    if song is None:
        return "Song not found", 404
    
    return render_template('song.html', song_title=song_title)

# ============ API ROUTES ============

@app.route('/api/chart/<int:chart_number>')
def get_chart(chart_number):
    """API endpoint to get data for a specific chart"""
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
            latest_position = song["positions"].get(processor.num_charts)
            if latest_position is None:
                for i in range(processor.num_charts, 0, -1):
                    if song["positions"].get(i) is not None:
                        latest_position = song["positions"].get(i)
                        break
            
            total_points = calculate_total_points(song)
            number_ones = count_number_ones(song)
            top_spot = get_top_spot(song)
            
            formatted_data.append({
                "position": latest_position if latest_position else 999,
                "prev_position": "--",
                "title": song["title"],
                "total_charts": song["total_charts"],
                "movement_type": "same",
                "movement_value": 0,
                "total_points": total_points,
                "number_ones": number_ones,
                "top_spot": top_spot
            })
        
        formatted_data.sort(key=lambda x: x["total_points"], reverse=True)
        
        for idx, item in enumerate(formatted_data, 1):
            item["position"] = idx
        
        return jsonify({
            "chart_number": 0,
            "data": formatted_data,
            "movement_counts": movement_counts
        })
    
    # Regular chart processing
    chart_data = processor.get_chart_data(chart_number)
    
    movement_counts = {
        "new": 0,
        "riser": 0,
        "faller": 0,
        "same": 0,
        "reentry": 0
    }
    
    formatted_data = []
    for item in chart_data:
        total_points = 0
        number_ones = 0
        top_spot = None
        for song in processor.songs:
            if song["title"] == item["title"]:
                total_points = calculate_total_points(song)
                number_ones = count_number_ones(song)
                top_spot = get_top_spot(song)
                break
        
        movement_type = "same"
        movement_value = 0
        
        if item["prev_position"] is None:
            is_reentry = False
            if chart_number > 1:
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
        
        movement_counts[movement_type] += 1
        
        formatted_data.append({
            "position": item["position"],
            "prev_position": item["prev_position"] if item["prev_position"] else "--",
            "title": item["title"],
            "total_charts": item["total_charts"],
            "movement_type": movement_type,
            "movement_value": movement_value,
            "total_points": total_points,
            "number_ones": number_ones,
            "top_spot": top_spot
        })
    
    return jsonify({
        "chart_number": chart_number,
        "data": formatted_data,
        "movement_counts": movement_counts
    })

@app.route('/api/song/<path:song_title>')
def get_song(song_title):
    """API endpoint to get complete song data including history and stats"""
    if not success:
        return jsonify({"error": "No data available"}), 500
    
    song_history = processor.get_song_history(song_title)
    
    if song_history is None:
        return jsonify({"error": "Song not found"}), 404
    
    chart_data = []
    for chart_num in range(1, processor.num_charts + 1):
        position = song_history["positions"].get(chart_num)
        if position is not None:
            chart_data.append({
                "chart": chart_num,
                "position": position
            })
    
    stats = calculate_song_stats(song_history)
    
    return jsonify({
        "title": song_history["title"],
        "chart_data": chart_data,
        "stats": stats
    })

@app.route('/api/song-history/<path:song_title>')
def get_song_history(song_title):
    """API endpoint to get the chart history for a specific song"""
    if not success:
        return jsonify({"error": "No data available"}), 500
    
    song_history = processor.get_song_history(song_title)
    
    if song_history is None:
        return jsonify({"error": "Song not found"}), 404
    
    chart_data = []
    for chart_num in range(1, processor.num_charts + 1):
        position = song_history["positions"].get(chart_num)
        if position is not None:
            chart_data.append({
                "chart": chart_num,
                "position": position
            })
    
    return jsonify({
        "title": song_history["title"],
        "chart_data": chart_data,
        "total_charts": song_history["total_charts"]
    })

@app.route('/api/comments/<path:song_title>', methods=['GET'])
def get_comments(song_title):
    """API endpoint to get comments for a song"""
    comments = comment_manager.get_comments(song_title)
    return jsonify({"comments": comments})

@app.route('/api/comments', methods=['POST'])
def add_comment():
    """API endpoint to add a comment to a song"""
    data = request.json
    
    if not data or 'song_title' not in data or 'user' not in data or 'text' not in data:
        return jsonify({"error": "Missing required fields"}), 400
    
    # Get profile pic from session if user is logged in
    profile_pic = session.get('profile_pic', None)
    
    comment_manager.add_comment(
        data['song_title'],
        data['user'],
        data['text'],
        profile_pic
    )
    
    return jsonify({"success": True}), 201

@app.route('/api/info')
def get_info():
    """API endpoint to get general information about the charts"""
    return jsonify({
        "num_charts": processor.num_charts,
        "num_songs": len(processor.songs),
        "has_data": success
    })

if __name__ == '__main__':
    print("\n🎵 Music Chart Website Generator")
    print("="*40)
    print(f"📂 Data file: {data_file}")
    print(f"🌐 Starting server at http://127.0.0.1:5001")
    
    if TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET:
        print(f"🎮 Twitch OAuth enabled")
    else:
        print(f"⚠️  Twitch OAuth not configured (set TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET)")
    
    print("="*40 + "\n")
    
    # Check if we should run in debug mode
    debug_mode = '--debug' in sys.argv
    
    if debug_mode:
        print("🔧 Running in DEBUG mode")
        app.run(port=5001, debug=True)
    else:
        print("🚀 Running in PRODUCTION mode")
        app.run(host='0.0.0.0', port=5001, debug=False)