from flask import Flask, render_template, request, jsonify, make_response
import json
from datetime import datetime


app = Flask(__name__)

PORT = 3203
HOST = '0.0.0.0'

# Ouvre fichier json -> charge en dict Python -> extrait la liste d'utilisateurs
with open('{}/databases/users.json'.format("."), "r") as jsf:
   users = json.load(jsf)["users"]

def now_iso():
    return datetime.utcnow().isoformat()

@app.route("/", methods=['GET'])
def profil():
   return "<h1 style='color:blue'>Welcome to the User service!</h1>"

@app.route("/adduser/<userid>", methods=['POST'])
def add_user(userid):
   req = request.get_json(silent=True) #vérifie format

   if req is None: # si pas de JSON ou invalide
      req = {}
   req["id"] = str(userid) #injecte id de l’URL dans le corps JSON pour avoir le champs
   req["last_active"] = now_iso()


   for user in users:
        if str(user["id"]) == str(userid):
            return make_response(jsonify({"error":"user ID already exists"}),409)
   users.append(req)
   write(users)
   res = make_response(jsonify({"message":"user added"}),200)
   return res


def write(users):
    with open('{}/databases/users.json'.format("."), 'w') as f:
        json.dump({"users": users}, f, ensure_ascii=False, indent=2)



@app.route("/users/<userid>/<name>", methods=['PUT'])
def update_user_name(userid, name):
    for user in users:
        if str(user["id"]) == str(userid):
            user["name"] = name
            user["last_active"] = now_iso()
            write(users)
            res = make_response(jsonify(user),200)
            return res

    res = make_response(jsonify({"error":"user ID not found"}),201)
    return res


@app.route("/users/<userid>", methods=['DELETE'])
def del_user(userid):
   for user in users:
      if str(user["id"]) == str(userid):
         users.remove(user)
         write(users) # permet d'update le ficheir json
         return make_response(jsonify(user),200)

   res = make_response(jsonify({"error":"user ID not found"}),400)
   return res


if __name__ == "__main__":
   print("Server running in port %s"%(PORT))
   app.run(host=HOST, port=PORT)
