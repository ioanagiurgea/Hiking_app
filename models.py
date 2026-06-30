from extensions import db
from datetime import datetime


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.Text)
    auth_provider = db.Column(db.String(50), nullable=False, default="local")
    provider_user_id = db.Column(db.String(255))
    profile_picture = db.Column(db.Text)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    role = db.Column(db.String(20), nullable=False, default="user")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "profile_picture": self.profile_picture,
            "is_active": self.is_active,
            "role": self.role,
            "auth_provider": self.auth_provider,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class Trail(db.Model):
    __tablename__ = "trails"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    slug = db.Column(db.String(180), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=False)
    region = db.Column(db.String(100), nullable=False)
    start_point_name = db.Column(db.String(150), nullable=False)
    end_point_name = db.Column(db.String(150))
    difficulty = db.Column(db.String(20), nullable=False)
    trail_type = db.Column(db.String(50), nullable=False)
    distance_km = db.Column(db.Numeric(6, 2), nullable=False)
    elevation_gain = db.Column(db.Integer, nullable=False)
    duration_hours = db.Column(db.Numeric(4, 2), nullable=False)
    equipment_needed = db.Column(db.Text)
    season_recommendation = db.Column(db.String(100))
    access_restrictions = db.Column(db.Text)
    gps_track_file = db.Column(db.Text)
    start_latitude = db.Column(db.Numeric(9, 6), nullable=False)
    start_longitude = db.Column(db.Numeric(9, 6), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    average_rating = db.Column(db.Numeric(3, 2), default=0.00)
    images = db.relationship(
        "TrailImage",
        backref="trail",
        lazy=True,
        cascade="all, delete-orphan"
    )

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "slug": self.slug,
            "description": self.description,
            "region": self.region,
            "start_point_name": self.start_point_name,
            "end_point_name": self.end_point_name,
            "difficulty": self.difficulty,
            "trail_type": self.trail_type,
            "distance_km": float(self.distance_km),
            "elevation_gain": self.elevation_gain,
            "duration_hours": float(self.duration_hours),
            "equipment_needed": self.equipment_needed,
            "season_recommendation": self.season_recommendation,
            "access_restrictions": self.access_restrictions,
            "gps_track_file": self.gps_track_file,
            "start_latitude": float(self.start_latitude),
            "start_longitude": float(self.start_longitude),
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "average_rating": float(self.average_rating) if self.average_rating is not None else 0,
            "cover_image": next(
                (
                    image.image_path
                    for image in self.images
                    if image.is_cover
                ),
                None
            ),
            "images": [
                {
                    "id": image.id,
                    "image_path": image.image_path,
                    "is_cover": image.is_cover
                }
                for image in self.images
            ]

        }


class TrailImage(db.Model):
    __tablename__ = "trail_images"

    id = db.Column(db.Integer, primary_key=True)
    trail_id = db.Column(db.Integer, db.ForeignKey("trails.id", ondelete="CASCADE"), nullable=False)
    is_cover = db.Column(db.Boolean, nullable=False, default=False)
    image_path = db.Column(db.Text, nullable=False)


class Favorite(db.Model):
    __tablename__ = "favorites"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    trail_id = db.Column(db.Integer, db.ForeignKey("trails.id", ondelete="CASCADE"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("user_id", "trail_id", name="uq_favorites_user_trail"),
    )


class CompletedTrail(db.Model):
    __tablename__ = "completed_trails"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    trail_id = db.Column(db.Integer, db.ForeignKey("trails.id", ondelete="CASCADE"), nullable=False)
    completed_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("user_id", "trail_id", name="uq_completed_user_trail"),
    )


class Review(db.Model):
    __tablename__ = "reviews"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    trail_id = db.Column(db.Integer, db.ForeignKey("trails.id", ondelete="CASCADE"), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("user_id", "trail_id", name="uq_reviews_user_trail"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "trail_id": self.trail_id,
            "rating": self.rating,
            "comment": self.comment,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }