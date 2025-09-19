from flask import Flask, render_template, request, jsonify, make_response
import json
import os
from werkzeug.exceptions import NotFound

app = Flask(__name__)

PORT = 3202
HOST = '0.0.0.0'

# Path to the database file
DATABASE_PATH = './databases/times.json'

def load_schedule():
    """Load schedule data from JSON file"""
    try:
        with open(DATABASE_PATH, "r") as jsf:
            return json.load(jsf)["schedule"]
    except FileNotFoundError:
        return []
    except json.JSONDecodeError:
        return []

def save_schedule(schedule_data):
    """Save schedule data to JSON file"""
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
        data = {"schedule": schedule_data}
        with open(DATABASE_PATH, "w") as jsf:
            json.dump(data, jsf, indent=2)
    except Exception as e:
        print(f"Error saving schedule: {e}")
        raise

def validate_date_format(date):
    """Validate date format (YYYYMMDD)"""
    if len(date) != 8 or not date.isdigit():
        return False
    return True

# Load initial schedule data
schedule = load_schedule()

@app.route("/", methods=['GET'])
def home():
    return "<h1 style='color:blue'>Welcome to the Showtime service!</h1>"

# GET: Retrieve all schedules
@app.route("/showmovies", methods=['GET'])
def get_all_schedules():
    """Get all schedule entries"""
    return make_response(jsonify(schedule), 200)

# GET: Retrieve schedule by date
@app.route("/showmovies/<date>", methods=['GET'])
def get_schedule_by_date(date):
    """Get schedule for a specific date"""
    if not validate_date_format(date):
        return make_response(jsonify({"error": "Invalid date format. Use YYYYMMDD"}), 400)
    
    for schedule_entry in schedule:
        if schedule_entry["date"] == date:
            return make_response(jsonify(schedule_entry), 200)
    return make_response(jsonify({"error": "Schedule not found for date: " + date}), 404)

# POST: Create a new schedule entry
@app.route("/showmovies/<date>", methods=['POST'])
def add_schedule_entry(date):
    """Add a new schedule entry for a specific date"""
    global schedule
    
    if not validate_date_format(date):
        return make_response(jsonify({"error": "Invalid date format. Use YYYYMMDD"}), 400)
    
    # Check if schedule already exists for this date
    for schedule_entry in schedule:
        if schedule_entry["date"] == date:
            return make_response(jsonify({"error": "Schedule already exists for date: " + date}), 409)
    
    # Get movies from request JSON
    request_data = request.get_json()
    if not request_data or "movies" not in request_data:
        return make_response(jsonify({"error": "Missing 'movies' in request body"}), 400)
    
    if not isinstance(request_data["movies"], list):
        return make_response(jsonify({"error": "Movies must be an array"}), 400)
    
    # Validate that movies are strings (UUIDs)
    for movie in request_data["movies"]:
        if not isinstance(movie, str) or len(movie.strip()) == 0:
            return make_response(jsonify({"error": "All movie entries must be non-empty strings"}), 400)
    
    # Create new schedule entry
    new_entry = {
        "date": date,
        "movies": request_data["movies"]
    }
    
    # Add to schedule and save
    try:
        schedule.append(new_entry)
        save_schedule(schedule)
        return make_response(jsonify(new_entry), 201)
    except Exception as e:
        return make_response(jsonify({"error": "Failed to save schedule"}), 500)

# PUT: Update an existing schedule entry
@app.route("/showmovies/<date>", methods=['PUT'])
def update_schedule_entry(date):
    """Update an existing schedule entry for a specific date"""
    global schedule
    
    if not validate_date_format(date):
        return make_response(jsonify({"error": "Invalid date format. Use YYYYMMDD"}), 400)
    
    # Find the schedule entry to update
    for i, schedule_entry in enumerate(schedule):
        if schedule_entry["date"] == date:
            # Get movies from request JSON
            request_data = request.get_json()
            if not request_data or "movies" not in request_data:
                return make_response(jsonify({"error": "Missing 'movies' in request body"}), 400)
            
            if not isinstance(request_data["movies"], list):
                return make_response(jsonify({"error": "Movies must be an array"}), 400)
            
            # Validate that movies are strings (UUIDs)
            for movie in request_data["movies"]:
                if not isinstance(movie, str) or len(movie.strip()) == 0:
                    return make_response(jsonify({"error": "All movie entries must be non-empty strings"}), 400)
            
            # Update the schedule entry
            try:
                schedule[i]["movies"] = request_data["movies"]
                save_schedule(schedule)
                return make_response(jsonify(schedule[i]), 200)
            except Exception as e:
                return make_response(jsonify({"error": "Failed to save schedule"}), 500)
    
    return make_response(jsonify({"error": "Schedule not found for date: " + date}), 404)

# DELETE: Remove a schedule entry
@app.route("/showmovies/<date>", methods=['DELETE'])
def delete_schedule_entry(date):
    """Delete a schedule entry for a specific date"""
    global schedule
    
    if not validate_date_format(date):
        return make_response(jsonify({"error": "Invalid date format. Use YYYYMMDD"}), 400)
    
    # Find and remove the schedule entry
    for i, schedule_entry in enumerate(schedule):
        if schedule_entry["date"] == date:
            try:
                deleted_entry = schedule.pop(i)
                save_schedule(schedule)
                return make_response(jsonify({"message": "Schedule deleted for date: " + date, "deleted_entry": deleted_entry}), 200)
            except Exception as e:
                return make_response(jsonify({"error": "Failed to save schedule"}), 500)
    
    return make_response(jsonify({"error": "Schedule not found for date: " + date}), 404)

if __name__ == "__main__":
   print("Server running in port %s"%(PORT))
   app.run(host=HOST, port=PORT)

