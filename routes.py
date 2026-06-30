import os
import xml.etree.ElementTree as ET

import requests
from flask import Blueprint, jsonify, request, render_template
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from sqlalchemy import and_, func
from werkzeug.security import generate_password_hash, check_password_hash

from extensions import db
from models import Trail, User, Favorite, CompletedTrail, Review, TrailImage


WEATHER_API_KEY = "4f0f33ace93848dab35154943261005"
GOOGLE_CLIENT_ID = "460937994747-jvvl9h9l3ui31qfbo9udma3bbhc1fusk.apps.googleusercontent.com"

main = Blueprint("main", __name__)


@main.route("/")
def home():
    return render_template("home.html")


@main.route("/trails-page")
def trails_page():
    return render_template("trails.html")


@main.route("/login-page")
def login_page():
    return render_template("login.html")


@main.route("/trails/<int:trail_id>/page")
def trail_detail_page(trail_id):
    return render_template("trail_detail.html", trail_id=trail_id)


@main.route("/profile-page")
def profile_page():
    return render_template("profile.html")


@main.route("/admin-page")
def admin_page():
    return render_template("admin.html")


@main.route("/trails", methods=["GET"])
def get_trails():
    difficulty = request.args.get("difficulty")
    sort = request.args.get("sort")
    search = request.args.get("search")

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)

    query = Trail.query.filter_by(is_active=True)

    if difficulty:
        query = query.filter(Trail.difficulty.ilike(difficulty))

    if search:
        words = search.strip().split()

        words = [
            word.replace("ă", "a")
            .replace("â", "a")
            .replace("î", "i")
            .replace("ș", "s")
            .replace("ş", "s")
            .replace("ț", "t")
            .replace("ţ", "t")
            for word in words
        ]

        conditions = [
            func.unaccent(Trail.title).ilike(
                f"%{word}%"
            )
            for word in words
        ]

        query = query.filter(and_(*conditions))

    if sort == "rating":
        query = query.order_by(Trail.average_rating.desc())

    elif sort == "distance":
        query = query.order_by(Trail.distance_km.asc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    trails = pagination.items

    result = [trail.to_dict() for trail in trails]

    return jsonify({
        "trails": result,
        "page": page,
        "per_page": per_page,
        "total": pagination.total,
        "pages": pagination.pages
    })


@main.route("/trails/<int:trail_id>", methods=["GET"])
def get_trail_by_id(trail_id):
    trail = Trail.query.filter_by(id=trail_id, is_active=True).first()

    if not trail:
        return jsonify({"error": "Traseul nu a fost găsit"}), 404

    return jsonify(trail.to_dict())


@main.route("/trails/<int:trail_id>/similar", methods=["GET"])
def get_similar_trails(trail_id):
    current_trail = Trail.query.filter_by(id=trail_id, is_active=True).first()

    if not current_trail:
        return jsonify({"error": "Traseul nu a fost găsit"}), 404

    candidates = Trail.query.filter(
        Trail.id != trail_id,
        Trail.is_active == True,
        Trail.difficulty == current_trail.difficulty
    ).all()

    scored_trails = []

    for trail in candidates:
        distance_score = abs(float(trail.distance_km) - float(current_trail.distance_km))
        duration_score = abs(float(trail.duration_hours) - float(current_trail.duration_hours))

        score = distance_score + duration_score

        scored_trails.append({
            "trail": trail,
            "score": score
        })

    scored_trails.sort(key=lambda item: item["score"])

    result = [item["trail"].to_dict() for item in scored_trails[:3]]

    return jsonify(result), 200


@main.route("/trails/<int:trail_id>/reviews", methods=["GET"])
def get_trail_reviews(trail_id):
    trail = Trail.query.get(trail_id)

    if not trail:
        return jsonify({"error": "Traseu inexistent"}), 404

    reviews = Review.query.filter_by(trail_id=trail_id).all()
    result = [review.to_dict() for review in reviews]

    return jsonify(result)


@main.route("/trails/<int:trail_id>/weather", methods=["GET"])
def get_trail_weather(trail_id):
    trail = Trail.query.filter_by(id=trail_id, is_active=True).first()

    if not trail:
        return jsonify({"error": "Traseul nu a fost găsit"}), 404

    if trail.start_latitude is None or trail.start_longitude is None:
        return jsonify({"error": "Traseul nu are coordonate pentru vreme"}), 400

    latitude = float(trail.start_latitude)
    longitude = float(trail.start_longitude)

    weather_url = (
        f"http://api.weatherapi.com/v1/forecast.json"
        f"?key={WEATHER_API_KEY}"
        f"&q={latitude},{longitude}"
        f"&days=3"
        f"&aqi=no"
        f"&alerts=no"
    )

    response = requests.get(weather_url)

    if response.status_code != 200:
        return jsonify({"error": "Nu s-a putut obține vremea"}), 500

    data = response.json()

    return jsonify(data), 200


@main.route("/users", methods=["POST"])
def create_user():
    data = request.get_json()

    name = data.get("name")
    email = data.get("email")
    password = data.get("password")

    if not name or not email or not password:
        return jsonify({"error": "Lipsesc câmpuri obligatorii"}), 400

    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        return jsonify({"error": "Email deja folosit"}), 400

    user = User(
        name=name,
        email=email,
        password_hash=generate_password_hash(password)
    )

    db.session.add(user)
    db.session.commit()

    return jsonify({"message": "User creat cu succes"}), 201


@main.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Email și parola sunt obligatorii"}), 400

    user = User.query.filter_by(email=email).first()

    if not user:
        return jsonify({"error": "User inexistent"}), 404

    if not user.password_hash or not check_password_hash(user.password_hash, password):
        return jsonify({"error": "Parolă incorectă"}), 401

    access_token = create_access_token(identity=str(user.id))

    return jsonify({
        "message": "Login reușit",
        "access_token": access_token,
        "user": user.to_dict()
    })


@main.route("/google-login", methods=["POST"])
def google_login():
    data = request.get_json()
    token = data.get("token")

    if not token:
        return jsonify({"error": "Token lipsă"}), 400

    try:
        user_info = id_token.verify_oauth2_token(
            token,
            google_requests.Request(),
            GOOGLE_CLIENT_ID
        )

        email = user_info.get("email")
        name = user_info.get("name")
        google_user_id = user_info.get("sub")

        user = User.query.filter_by(email=email).first()

        if not user:
            user = User(
                name=name,
                email=email,
                password_hash=None,
                auth_provider="google",
                provider_user_id=google_user_id,
                role="user"
            )

            db.session.add(user)
            db.session.commit()

        access_token = create_access_token(identity=str(user.id))

        return jsonify({
            "access_token": access_token,
            "user": user.to_dict()
        }), 200

    except Exception:
        return jsonify({"error": "Token Google invalid"}), 401


@main.route("/users/<int:user_id>", methods=["GET"])
@jwt_required()
def get_user(user_id):
    current_user_id = int(get_jwt_identity())

    if current_user_id != user_id and not is_admin(current_user_id):
        return jsonify({"error": "Acces interzis"}), 403

    user = User.query.get(user_id)

    if not user:
        return jsonify({"error": "User inexistent"}), 404

    return jsonify({
        "message": "Profil utilizator",
        "user": user.to_dict()
    }), 200


@main.route("/me", methods=["GET"])
@jwt_required()
def get_me():
    current_user_id = int(get_jwt_identity())

    user = User.query.get(current_user_id)
    if not user:
        return jsonify({"error": "User inexistent"}), 404

    return jsonify(user.to_dict()), 200


@main.route("/me", methods=["PUT"])
@jwt_required()
def update_me():
    current_user_id = int(get_jwt_identity())
    user = User.query.get(current_user_id)

    if not user:
        return jsonify({"error": "User inexistent"}), 404

    data = request.get_json()

    name = data.get("name")
    email = data.get("email")
    password = data.get("password")

    if email and email != user.email:
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return jsonify({"error": "Email deja folosit"}), 400

    if name:
        user.name = name

    if email:
        user.email = email

    if password:
        user.password_hash = generate_password_hash(password)

    db.session.commit()

    return jsonify({
        "message": "Profil actualizat cu succes",
        "user": user.to_dict()
    }), 200


@main.route("/me/change-password", methods=["PUT"])
@jwt_required()
def change_my_password():
    current_user_id = int(get_jwt_identity())
    user = User.query.get(current_user_id)

    if not user:
        return jsonify({"error": "User inexistent"}), 404

    if user.auth_provider == "google":
        return jsonify({
            "error": "Contul este autentificat cu Google. Parola este gestionată de Google."
        }), 400

    data = request.get_json()

    current_password = data.get("current_password")
    new_password = data.get("new_password")

    if not current_password or not new_password:
        return jsonify({"error": "Parola actuală și parola nouă sunt obligatorii"}), 400

    if not check_password_hash(user.password_hash, current_password):
        return jsonify({"error": "Parola actuală este incorectă"}), 401

    user.password_hash = generate_password_hash(new_password)
    db.session.commit()

    return jsonify({"message": "Parola a fost schimbată cu succes"}), 200


@main.route("/me/progress", methods=["GET"])
@jwt_required()
def get_my_progress():
    current_user_id = int(get_jwt_identity())

    completed_trails = CompletedTrail.query.filter_by(user_id=current_user_id).all()

    total_points = 0
    total_distance = 0
    total_duration = 0

    for completed in completed_trails:
        trail = Trail.query.get(completed.trail_id)

        if trail:
            if trail.difficulty == "easy":
                base_points = 10
            elif trail.difficulty == "medium":
                base_points = 25
            elif trail.difficulty == "hard":
                base_points = 45
            else:
                base_points = 0

            duration_bonus = int(float(trail.duration_hours) * 2)

            total_points += base_points + duration_bonus
            total_distance += float(trail.distance_km)
            total_duration += float(trail.duration_hours)

    if total_points < 100:
        level = "Începător"
        next_level = "Intermediar"
        progress_percent = int((total_points / 100) * 100)

    elif total_points < 250:
        level = "Intermediar"
        next_level = "Avansat"
        progress_percent = int(((total_points - 100) / 150) * 100)

    else:
        level = "Avansat"
        next_level = None
        progress_percent = 100

    return jsonify({
        "points": total_points,
        "level": level,
        "next_level": next_level,
        "progress_percent": progress_percent,
        "total_distance": round(total_distance, 2),
        "total_duration": round(total_duration, 2),
        "completed_count": len(completed_trails)
    }), 200


@main.route("/favorites", methods=["POST"])
@jwt_required()
def add_favorite():
    data = request.get_json()

    current_user_id = int(get_jwt_identity())

    trail_id = data.get("trail_id")

    if not trail_id:
        return jsonify({"error": "trail_id este obligatoriu"}), 400

    trail = Trail.query.get(trail_id)
    if not trail:
        return jsonify({"error": "Traseu inexistent"}), 404

    existing_favorite = Favorite.query.filter_by(
        user_id=current_user_id,
        trail_id=trail_id
    ).first()

    if existing_favorite:
        return jsonify({"error": "Traseul este deja la favorite"}), 400

    favorite = Favorite(
        user_id=current_user_id,
        trail_id=trail_id
    )

    db.session.add(favorite)
    db.session.commit()

    return jsonify({"message": "Traseu adăugat la favorite"}), 201


@main.route("/favorites", methods=["DELETE"])
@jwt_required()
def delete_favorite():
    data = request.get_json()

    current_user_id = int(get_jwt_identity())
    trail_id = data.get("trail_id")

    if not trail_id:
        return jsonify({"error": "trail_id este obligatoriu"}), 400

    favorite = Favorite.query.filter_by(
        user_id=current_user_id,
        trail_id=trail_id
    ).first()

    if not favorite:
        return jsonify({"error": "Favoritul nu există"}), 404

    db.session.delete(favorite)
    db.session.commit()

    return jsonify({"message": "Traseu șters din favorite"}), 200


@main.route("/me/favorites", methods=["GET"])
@jwt_required()
def get_my_favorites():
    current_user_id = int(get_jwt_identity())

    favorites = Favorite.query.filter_by(user_id=current_user_id).all()

    result = []

    for fav in favorites:
        trail = Trail.query.get(fav.trail_id)

        if trail:
            result.append(trail.to_dict())

    return jsonify(result), 200


@main.route("/completed_trails", methods=["POST"])
@jwt_required()
def add_completed_trail():
    data = request.get_json()

    current_user_id = int(get_jwt_identity())

    trail_id = data.get("trail_id")

    if not trail_id:
        return jsonify({"error": "trail_id este obligatoriu"}), 400

    trail = Trail.query.get(trail_id)
    if not trail:
        return jsonify({"error": "Traseu inexistent"}), 404

    existing_completed = CompletedTrail.query.filter_by(
        user_id=current_user_id,
        trail_id=trail_id
    ).first()

    if existing_completed:
        return jsonify({"error": "Traseul este deja marcat ca parcurs"}), 400

    completed_trail = CompletedTrail(
        user_id=current_user_id,
        trail_id=trail_id
    )

    db.session.add(completed_trail)
    db.session.commit()

    return jsonify({"message": "Traseu marcat ca parcurs"}), 201


@main.route("/completed_trails", methods=["DELETE"])
@jwt_required()
def delete_completed_trail():
    data = request.get_json()

    current_user_id = int(get_jwt_identity())
    trail_id = data.get("trail_id")

    if not trail_id:
        return jsonify({"error": "trail_id este obligatoriu"}), 400

    completed_trail = CompletedTrail.query.filter_by(
        user_id=current_user_id,
        trail_id=trail_id
    ).first()

    if not completed_trail:
        return jsonify({"error": "Traseul parcurs nu există"}), 404

    db.session.delete(completed_trail)
    db.session.commit()

    return jsonify({"message": "Traseu șters din lista de trasee parcurse"}), 200


@main.route("/me/completed_trails", methods=["GET"])
@jwt_required()
def get_my_completed_trails():
    current_user_id = int(get_jwt_identity())

    completed_trails = CompletedTrail.query.filter_by(user_id=current_user_id).all()

    result = []

    for completed in completed_trails:
        trail = Trail.query.get(completed.trail_id)

        if trail:
            result.append(trail.to_dict())

    return jsonify(result), 200


@main.route("/reviews", methods=["POST"])
@jwt_required()
def add_review():
    data = request.get_json()

    current_user_id = int(get_jwt_identity())

    trail_id = data.get("trail_id")
    rating = data.get("rating")
    comment = data.get("comment")

    comment = comment.strip() if comment else comment

    if not trail_id or rating is None or not comment:
        return jsonify({"error": "trail_id, rating și comment sunt obligatorii"}), 400

    if rating < 1 or rating > 5:
        return jsonify({"error": "Ratingul trebuie să fie între 1 și 5"}), 400

    trail = Trail.query.get(trail_id)
    if not trail:
        return jsonify({"error": "Traseu inexistent"}), 404

    existing_review = Review.query.filter_by(
        user_id=current_user_id,
        trail_id=trail_id
    ).first()

    if existing_review:
        return jsonify({"error": "Ai adăugat deja un review pentru acest traseu"}), 400

    review = Review(
        user_id=current_user_id,
        trail_id=trail_id,
        rating=rating,
        comment=comment
    )

    db.session.add(review)
    db.session.commit()

    reviews_for_trail = Review.query.filter_by(trail_id=trail_id).all()
    total = sum(r.rating for r in reviews_for_trail)
    average = total / len(reviews_for_trail)

    trail.average_rating = round(average, 2)
    db.session.commit()

    return jsonify({"message": "Review adăugat cu succes"}), 201


@main.route("/reviews", methods=["PUT"])
@jwt_required()
def update_review():
    data = request.get_json()

    current_user_id = int(get_jwt_identity())
    trail_id = data.get("trail_id")
    rating = data.get("rating")
    comment = data.get("comment")

    comment = comment.strip() if comment else comment

    if not trail_id or rating is None or not comment:
        return jsonify({"error": "trail_id, rating și comment sunt obligatorii"}), 400

    if rating < 1 or rating > 5:
        return jsonify({"error": "Ratingul trebuie să fie între 1 și 5"}), 400

    review = Review.query.filter_by(
        user_id=current_user_id,
        trail_id=trail_id
    ).first()

    if not review:
        return jsonify({"error": "Review-ul nu există"}), 404

    review.rating = rating
    review.comment = comment

    db.session.commit()

    trail = Trail.query.get(trail_id)
    reviews_for_trail = Review.query.filter_by(trail_id=trail_id).all()
    total = sum(r.rating for r in reviews_for_trail)
    average = total / len(reviews_for_trail)

    trail.average_rating = round(average, 2)
    db.session.commit()

    return jsonify({"message": "Review actualizat cu succes"}), 200


@main.route("/reviews", methods=["DELETE"])
@jwt_required()
def delete_review():
    data = request.get_json()

    current_user_id = int(get_jwt_identity())
    trail_id = data.get("trail_id")

    if not trail_id:
        return jsonify({"error": "trail_id este obligatoriu"}), 400

    review = Review.query.filter_by(
        user_id=current_user_id,
        trail_id=trail_id
    ).first()

    if not review:
        return jsonify({"error": "Review-ul nu există"}), 404

    db.session.delete(review)
    db.session.commit()

    trail = Trail.query.get(trail_id)
    remaining_reviews = Review.query.filter_by(trail_id=trail_id).all()

    if remaining_reviews:
        total = sum(r.rating for r in remaining_reviews)
        average = total / len(remaining_reviews)
        trail.average_rating = round(average, 2)
    else:
        trail.average_rating = 0.0

    db.session.commit()

    return jsonify({"message": "Review șters cu succes"}), 200


def is_admin(user_id):
    user = User.query.get(user_id)
    return user and user.role == "admin"


@main.route("/trails", methods=["POST"])
@jwt_required()
def create_trail():
    current_user_id = int(get_jwt_identity())

    if not is_admin(current_user_id):
        return jsonify({"error": "Acces interzis"}), 403

    data = request.get_json()

    title = data.get("title")
    slug = data.get("slug")
    description = data.get("description")
    region = data.get("region")
    start_point_name = data.get("start_point_name")
    end_point_name = data.get("end_point_name")
    difficulty = data.get("difficulty")
    trail_type = data.get("trail_type")
    duration_hours = data.get("duration_hours")
    equipment_needed = data.get("equipment_needed")
    season_recommendation = data.get("season_recommendation")
    access_restrictions = data.get("access_restrictions")
    gps_track_file = data.get("gps_track_file")
    cover_image = data.get("cover_image")

    start_latitude = None
    start_longitude = None
    distance_km = 0
    elevation_gain = 0

    if gps_track_file:
        gpx_data = get_gpx_data(gps_track_file)

        if gpx_data:
            start_latitude = gpx_data["start_latitude"]
            start_longitude = gpx_data["start_longitude"]
            distance_km = gpx_data["distance_km"]
            elevation_gain = gpx_data["elevation_gain"]

    if not title or not slug or not description or not region or not start_point_name or not difficulty or not trail_type or duration_hours is None:
        return jsonify({"error": "Lipsesc câmpuri obligatorii"}), 400

    existing_trail = Trail.query.filter_by(slug=slug).first()
    if existing_trail:
        return jsonify({"error": "Există deja un traseu cu acest slug"}), 400

    trail = Trail(
        title=title,
        slug=slug,
        description=description,
        region=region,
        start_point_name=start_point_name,
        end_point_name=end_point_name,
        difficulty=difficulty,
        trail_type=trail_type,
        distance_km=distance_km,
        elevation_gain=elevation_gain,
        duration_hours=duration_hours,
        equipment_needed=equipment_needed,
        season_recommendation=season_recommendation,
        access_restrictions=access_restrictions,
        gps_track_file=gps_track_file,
        start_latitude=start_latitude,
        start_longitude=start_longitude
    )

    db.session.add(trail)
    db.session.commit()

    if cover_image:
        image = TrailImage(
            trail_id=trail.id,
            image_path=cover_image,
            is_cover=True
        )

        db.session.add(image)
        db.session.commit()

    return jsonify({
        "message": "Traseu creat cu succes",
        "trail": trail.to_dict()
    }), 201


@main.route("/trails/<int:trail_id>", methods=["PUT"])
@jwt_required()
def update_trail(trail_id):
    current_user_id = int(get_jwt_identity())

    if not is_admin(current_user_id):
        return jsonify({"error": "Acces interzis"}), 403

    trail = Trail.query.get(trail_id)

    if not trail:
        return jsonify({"error": "Traseu inexistent"}), 404

    data = request.get_json()

    title = data.get("title")
    slug = data.get("slug")
    description = data.get("description")
    region = data.get("region")
    start_point_name = data.get("start_point_name")
    end_point_name = data.get("end_point_name")
    difficulty = data.get("difficulty")
    trail_type = data.get("trail_type")
    distance_km = data.get("distance_km")
    elevation_gain = data.get("elevation_gain")
    duration_hours = data.get("duration_hours")
    equipment_needed = data.get("equipment_needed")
    season_recommendation = data.get("season_recommendation")
    access_restrictions = data.get("access_restrictions")
    gps_track_file = data.get("gps_track_file")
    cover_image = data.get("cover_image")
    start_latitude = data.get("start_latitude")
    start_longitude = data.get("start_longitude")
    is_active = data.get("is_active")

    if gps_track_file:
        gpx_data = get_gpx_data(gps_track_file)

        if gpx_data:
            start_latitude = gpx_data["start_latitude"]
            start_longitude = gpx_data["start_longitude"]
            distance_km = gpx_data["distance_km"]
            elevation_gain = gpx_data["elevation_gain"]

    if slug and slug != trail.slug:
        existing_trail = Trail.query.filter_by(slug=slug).first()
        if existing_trail:
            return jsonify({"error": "Există deja un traseu cu acest slug"}), 400

    if title:
        trail.title = title
    if slug:
        trail.slug = slug
    if description:
        trail.description = description
    if region:
        trail.region = region
    if start_point_name:
        trail.start_point_name = start_point_name
    if end_point_name is not None:
        trail.end_point_name = end_point_name
    if difficulty:
        trail.difficulty = difficulty
    if trail_type:
        trail.trail_type = trail_type
    if distance_km is not None:
        trail.distance_km = distance_km
    if elevation_gain is not None:
        trail.elevation_gain = elevation_gain
    if duration_hours is not None:
        trail.duration_hours = duration_hours
    if equipment_needed is not None:
        trail.equipment_needed = equipment_needed
    if season_recommendation is not None:
        trail.season_recommendation = season_recommendation
    if access_restrictions is not None:
        trail.access_restrictions = access_restrictions
    if gps_track_file is not None:
        trail.gps_track_file = gps_track_file
    if start_latitude is not None:
        trail.start_latitude = start_latitude
    if start_longitude is not None:
        trail.start_longitude = start_longitude
    if is_active is not None:
        trail.is_active = is_active

    if cover_image is not None:
        existing_cover = TrailImage.query.filter_by(
            trail_id=trail.id,
            is_cover=True
        ).first()

        if existing_cover:
            existing_cover.image_path = cover_image
        else:
            new_cover = TrailImage(
                trail_id=trail.id,
                image_path=cover_image,
                is_cover=True
            )

            db.session.add(new_cover)

    db.session.commit()

    return jsonify({
        "message": "Traseu actualizat cu succes",
        "trail": trail.to_dict()
    }), 200


@main.route("/trails/<int:trail_id>", methods=["DELETE"])
@jwt_required()
def delete_trail(trail_id):
    current_user_id = int(get_jwt_identity())

    if not is_admin(current_user_id):
        return jsonify({"error": "Acces interzis"}), 403

    trail = Trail.query.get(trail_id)

    if not trail:
        return jsonify({"error": "Traseu inexistent"}), 404

    db.session.delete(trail)
    db.session.commit()

    return jsonify({"message": "Traseu șters cu succes"}), 200


def get_gpx_data(gps_track_file):
    if not gps_track_file:
        return None

    file_path = os.path.join("static", gps_track_file)

    if not os.path.exists(file_path):
        return None

    tree = ET.parse(file_path)
    root = tree.getroot()

    points = root.findall(".//{*}trkpt")

    if not points:
        return None

    coordinates = []
    elevations = []

    for point in points:
        lat = float(point.attrib["lat"])
        lon = float(point.attrib["lon"])

        ele_tag = point.find("{*}ele")
        ele = float(ele_tag.text) if ele_tag is not None else None

        coordinates.append((lat, lon))

        if ele is not None:
            elevations.append(ele)

    start_latitude = coordinates[0][0]
    start_longitude = coordinates[0][1]

    total_distance = 0

    for i in range(1, len(coordinates)):
        total_distance += calculate_distance(
            coordinates[i - 1][0],
            coordinates[i - 1][1],
            coordinates[i][0],
            coordinates[i][1]
        )

    elevation_gain = 0

    for i in range(1, len(elevations)):
        difference = elevations[i] - elevations[i - 1]

        if difference > 0:
            elevation_gain += difference

    return {
        "start_latitude": round(start_latitude, 6),
        "start_longitude": round(start_longitude, 6),
        "distance_km": round(total_distance, 2),
        "elevation_gain": int(round(elevation_gain))
    }


def calculate_distance(lat1, lon1, lat2, lon2):
    from math import radians, sin, cos, sqrt, atan2

    radius = 6371

    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)

    a = (
        sin(d_lat / 2) * sin(d_lat / 2)
        + cos(radians(lat1))
        * cos(radians(lat2))
        * sin(d_lon / 2)
        * sin(d_lon / 2)
    )

    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return radius * c