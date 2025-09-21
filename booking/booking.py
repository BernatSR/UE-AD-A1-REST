from flask import Flask, request, jsonify, make_response
import requests
import json
import re
from datetime import datetime

app = Flask(__name__)

PORT = 3201
HOST = "0.0.0.0"


with open("./databases/bookings.json", "r", encoding="utf-8") as jsf:
    bookings = json.load(jsf)["bookings"]

# --- Utilitaires simples ---

DATE_RX = re.compile(r"^\d{8}$")

def write():
    """Sauvegarde le fichier bookings.json"""
    with open("./databases/bookings.json", "w", encoding="utf-8") as f:
        json.dump({"bookings": bookings}, f, ensure_ascii=False, indent=2)

def validate_date_str(date_str: str) -> bool:
    """Vérifie format YYYYMMDD et que la date est valide"""
    if not DATE_RX.match(date_str):
        return False
    try:
        datetime.strptime(date_str, "%Y%m%d")
        return True
    except ValueError:
        return False

def error(msg: str, code: int):
    """Réponse JSON d’erreur simple"""
    return make_response(jsonify({"error": msg}), code)

def find_user_booking(userid: str):
    """Retourne l'entrée de réservation d'un user ou None"""
    for booking in bookings:
        if str(booking["userid"]) == str(userid):
            return booking
    return None

def find_date_entry(user_entry, date_str: str):
    """Retourne l'entrée d'une date pour ce user ou None"""
    for date_entry in user_entry["dates"]:
        if date_entry["date"] == date_str:
            return date_entry
    return None

def get_movie(movie_id: str):
    """Fetch un film depuis le service Movie, ou None si absent/erreur"""
    try:
        r = requests.get(f"http://localhost:3200/movies/{movie_id}", timeout=3)
        if r.status_code == 200:
            return r.json()
        return None
    except requests.RequestException:
        return None

def check_schedule(date_str, movie_ids):

    try:
        url = "http://localhost:3202/schedule/" + date_str
        r = requests.get(url, timeout=3)
    except requests.RequestException:
        return False, [], "schedule service unreachable"

    # La date doit exister
    if r.status_code != 200:
        return False, [], "date not found in schedule"

    # Vérifier les films
    day = r.json()                
    allowed_movies = day.get("movies", [])

    not_allowed = []
    for movie_id in movie_ids:
        if movie_id not in allowed_movies:
            not_allowed.append(movie_id)

    if len(not_allowed) == 0:
        return True, [], None
    else:
        return False, not_allowed, None

# --- Routes ---

@app.route("/", methods=["GET"])
def home():
    return "<h1 style='color:blue'>Welcome to the Booking service!</h1>"

@app.route("/bookings", methods=["GET"])
def list_all_booking():
    # Vérifie si admin avec X-Admin: true
    if request.headers.get("X-Admin", "false").lower() != "true":
        return error("admin only", 403)
    return make_response(jsonify(bookings), 200)

@app.route("/bookings/<userid>", methods=["GET"])
def get_user_booking(userid):
    entry = find_user_booking(userid)
    if entry is None:
        # Réponse cohérente même si vide
        return make_response(jsonify({"userid": userid, "dates": []}), 200)
    return make_response(jsonify(entry), 200)

@app.route("/bookings/<userid>/details", methods=["GET"])
def get_user_bookings_detailed(userid):
    entry = find_user_booking(userid)
    if entry is None:
        return make_response(jsonify({"userid": userid, "dates": []}), 200)

    detailed = {"userid": userid, "dates": []}

    for d in entry["dates"]:
        movies_detailed = []
        # Récupérer les infos de chaque film
        for movie_id in d.get("movies", []):
            info_movie = get_movie(movie_id)
            if info_movie:
                movies_detailed.append(info_movie)
            else:
                movies_detailed.append({"id": movie_id, "error": "movie not found"})
        detailed["dates"].append({"date": d["date"], "movies": movies_detailed})

    return make_response(jsonify(detailed), 200)

@app.route("/bookings/<userid>/<date>", methods=["POST"])
def add_booking(userid, date):

    if not validate_date_str(date):
        return error("invalid date format, expected YYYYMMDD", 400)

    # Corps JSON
    payload = request.get_json(silent=True)
    if payload is None:
        payload = {}

    # Construire la liste des films à ajouter
    to_add_movie = []
    if "movie" in payload and isinstance(payload["movie"], str):
        to_add_movie.append(payload["movie"])
    if "movies" in payload and isinstance(payload["movies"], list):
        for item in payload["movies"]:
            if isinstance(item, str):
                to_add_movie.append(item)

    if len(to_add_movie) == 0:
        return error("provide movie or movies in JSON body", 400)

    # Vérifier auprès de Schedule (date + films programmés)
    ok, not_allowed, reason = check_schedule(date, to_add_movie)
    if not ok:
        if reason == "schedule service unreachable":
            return error(reason, 503)
        if reason == "date not found in schedule":
            return error(reason, 409)
        # Films non programmés
        return make_response(jsonify({
            "error": "some movies are not scheduled for this date",
            "date": date,
            "not_allowed_movies": not_allowed
        }), 409)

    # Trouver / créer l'entrée utilisateur
    entry = find_user_booking(userid)
    if entry is None:
        entry = {"userid": userid, "dates": []}
        bookings.append(entry)

    # Trouver / créer l'entrée pour la date
    dentry = find_date_entry(entry, date)
    if dentry is None:
        dentry = {"date": date, "movies": []}
        entry["dates"].append(dentry)

    # Ajouter sans doublon + garder la liste de ce qu'on ajoute
    added = []
    for mid in to_add_movie:
        if mid not in dentry["movies"]:
            dentry["movies"].append(mid)
            added.append(mid)

    write()
    return make_response(jsonify({
        "message": "booking added",
        "userid": userid,
        "date": date,
        "added_movies": added,
        "current_movies": dentry["movies"]
    }), 200)

@app.route("/bookings/<userid>/<date>/<movieid>", methods=["DELETE"])
def delete_booking(userid, date, movieid):
    entry = find_user_booking(userid)
    if entry is None:
        return error("user has no bookings", 404)

    date_entry = find_date_entry(entry, date)
    if date_entry is None:
        return error("no bookings for this date", 404)

    # Retirer le film de la liste de cette date
    try:
        date_entry["movies"].remove(movieid)
    except ValueError:
        return error("movie not booked on this date", 404)

    # Nettoyage: retirer dates vides
    new_dates = []
    for d in entry["dates"]:
        if len(d["movies"]) > 0:
            new_dates.append(d)
    entry["dates"] = new_dates

    # Nettoyage: retirer l'utilisateur s'il n'a plus aucune date
    if len(entry["dates"]) == 0:
        new_bookings = []
        for b in bookings:
            if b["userid"] != userid:
                new_bookings.append(b)
        bookings[:] = new_bookings

    write()
    return make_response(jsonify({
        "message": "booking deleted",
        "userid": userid,
        "date": date,
        "movie": movieid
    }), 200)



@app.route("/stats/date/<date>/movies", methods=["GET"])
def stats_movies_for_date(date):
    if not validate_date_str(date):
        return error("invalid date format, expected YYYYMMDD", 400)

    # Compter les réservations par film
    counts = {} 
    for booking in bookings:
        for d in booking.get("dates", []):
            if d.get("date") == date:
                for movie_id in d.get("movies", []):
                    if movie_id in counts:
                        counts[movie_id] += 1
                    else:
                        counts[movie_id] = 1

    # Construire la liste de sortie avec détails films
    items = []
    for movie_id, n in counts.items():
        info = get_movie(movie_id)
        if info:
            items.append({
                "movie": info,  
                "count": n
            })
        else:
            items.append({
                "movie": {"id": movie_id, "error": "movie not found"},
                "count": n
            })

    # Ordonner par count décroissant
    items_sorted = items[:]

    for i in range(len(items_sorted)):
        # Chercher l'élément avec le plus grand "count" dans le reste de la liste
        max_index = i
        for j in range(i + 1, len(items_sorted)):
            if items_sorted[j]["count"] > items_sorted[max_index]["count"]:
                max_index = j
        # Échanger avec la position courante
        items_sorted[i], items_sorted[max_index] = items_sorted[max_index], items_sorted[i]


    return make_response(jsonify({
        "date": date,
        "movies": items_sorted
    }), 200)


if __name__ == "__main__":
    print(f"Server running in port {PORT}")
    app.run(host=HOST, port=PORT)