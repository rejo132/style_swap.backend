from flask import Flask, request, jsonify, session, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timezone
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'  # Replace with a secure key
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'styleswap.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'Uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg'}

# Enable CORS with credentials support for multiple origins
CORS(app, resources={r"/api/*": {"origins": ["http://localhost:3000", "http://localhost:3001"]}}, supports_credentials=True)

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    profile_picture = db.Column(db.String(120), nullable=True)
    outfits = db.relationship('Outfit', backref='user', lazy=True)
    ratings = db.relationship('Rating', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Outfit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    image = db.Column(db.String(120), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    ratings = db.relationship('Rating', backref='outfit', lazy=True, cascade='all, delete-orphan')

class Rating(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    score = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    outfit_id = db.Column(db.Integer, db.ForeignKey('outfit.id'), nullable=False)

# Helper function for allowed file extensions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# Root route to prevent 404
@app.route('/', methods=['GET'])
def home():
    return jsonify({'message': 'StyleSwap API is running. Use /api/* endpoints for functionality.'})

# Routes
@app.route('/api/check-auth', methods=['GET'])
def check_auth():
    user_id = session.get('user_id')
    if user_id:
        user = User.query.get(user_id)
        if user:
            return jsonify({
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'profile_picture': user.profile_picture
                }
            })
    return jsonify({'user': None}), 401

@app.route('/api/signup', methods=['POST'])
def signup():
    try:
        data = request.form
        file = request.files.get('profile_picture')
        username = data.get('username')
        password = data.get('password')

        if not username or not password:
            return jsonify({'error': 'Username and password are required'}), 400
        if not file or not allowed_file(file.filename):
            return jsonify({'error': 'Valid profile picture (PNG/JPEG) is required'}), 400
        if User.query.filter_by(username=username).first():
            return jsonify({'error': 'Username already exists'}), 400

        filename = f"{datetime.now(timezone.utc).timestamp()}_{secure_filename(file.filename)}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        user = User(username=username, profile_picture=filename)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        session['user_id'] = user.id
        return jsonify({
            'user': {
                'id': user.id,
                'username': user.username,
                'profile_picture': filename
            }
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    user = User.query.filter_by(username=username).first()
    if user and user.check_password(password):
        session['user_id'] = user.id
        return jsonify({
            'user': {
                'id': user.id,
                'username': user.username,
                'profile_picture': user.profile_picture
            }
        })
    return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    session.pop('user_id', None)
    return jsonify({'message': 'Logged out'})

@app.route('/api/outfits', methods=['GET', 'POST'])
def outfits():
    if request.method == 'GET':
        search = request.args.get('search', '')
        if search:
            outfits = Outfit.query.filter(
                (Outfit.title.ilike(f'%{search}%')) | (Outfit.description.ilike(f'%{search}%'))
            ).all()
        else:
            outfits = Outfit.query.all()
        return jsonify({
            'outfits': [{
                'id': o.id,
                'title': o.title,
                'description': o.description,
                'category': o.category,
                'image': o.image,
                'user_id': o.user_id,
                'average_rating': sum(r.score for r in o.ratings) / len(o.ratings) if o.ratings else None
            } for o in outfits]
        })
    elif request.method == 'POST':
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'Unauthorized'}), 401
        data = request.form
        file = request.files.get('image')
        if not all([data.get('title'), data.get('description'), data.get('category')]):
            return jsonify({'error': 'Missing required fields'}), 400
        if not file or not allowed_file(file.filename):
            return jsonify({'error': 'Valid image (PNG/JPEG) is required'}), 400

        filename = f"{user_id}_{datetime.now(timezone.utc).timestamp()}_{secure_filename(file.filename)}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        outfit = Outfit(
            title=data['title'],
            description=data['description'],
            category=data['category'],
            image=filename,
            user_id=user_id
        )
        db.session.add(outfit)
        db.session.commit()
        return jsonify({
            'id': outfit.id,
            'title': outfit.title,
            'description': outfit.description,
            'category': outfit.category,
            'image': outfit.image,
            'user_id': outfit.user_id
        }), 201

@app.route('/api/outfits/<int:id>', methods=['GET', 'PUT', 'DELETE'])
def outfit(id):
    outfit = Outfit.query.get_or_404(id)
    if request.method == 'GET':
        ratings = Rating.query.filter_by(outfit_id=id).all()
        avg_rating = sum(r.score for r in ratings) / len(ratings) if ratings else None
        return jsonify({
            'id': outfit.id,
            'title': outfit.title,
            'description': outfit.description,
            'category': outfit.category,
            'image': outfit.image,
            'user_id': outfit.user_id,
            'average_rating': avg_rating
        })
    elif request.method == 'PUT':
        user_id = session.get('user_id')
        if not user_id or outfit.user_id != user_id:
            return jsonify({'error': 'Unauthorized'}), 401
        data = request.form
        file = request.files.get('image')
        try:
            outfit.title = data.get('title', outfit.title)
            outfit.description = data.get('description', outfit.description)
            outfit.category = data.get('category', outfit.category)
            if file and allowed_file(file.filename):
                if outfit.image:
                    old_image_path = os.path.join(app.config['UPLOAD_FOLDER'], outfit.image)
                    if os.path.exists(old_image_path):
                        try:
                            os.remove(old_image_path)
                        except OSError as e:
                            print(f"Warning: Could not delete old image {old_image_path}: {e}")
                filename = f"{user_id}_{datetime.now(timezone.utc).timestamp()}_{secure_filename(file.filename)}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                outfit.image = filename
            db.session.commit()
            return jsonify({
                'message': 'Outfit updated',
                'id': outfit.id,
                'title': outfit.title,
                'description': outfit.description,
                'category': outfit.category,
                'image': outfit.image,
                'user_id': outfit.user_id
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500
    elif request.method == 'DELETE':
        user_id = session.get('user_id')
        if not user_id or outfit.user_id != user_id:
            return jsonify({'error': 'Unauthorized'}), 401
        try:
            if outfit.image:
                image_path = os.path.join(app.config['UPLOAD_FOLDER'], outfit.image)
                if os.path.exists(image_path):
                    try:
                        os.remove(image_path)
                    except OSError as e:
                        print(f"Warning: Could not delete image {image_path}: {e}")
            db.session.delete(outfit)
            db.session.commit()
            return jsonify({'message': 'Outfit deleted'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500

@app.route('/api/users/<int:id>/outfits', methods=['GET'])
def user_outfits(id):
    user_id = session.get('user_id')
    if not user_id or user_id != id:
        return jsonify({'error': 'Unauthorized'}), 401
    category = request.args.get('category', '')
    query = Outfit.query.filter_by(user_id=id)
    if category:
        query = query.filter_by(category=category)
    outfits = query.all()
    return jsonify([{
        'id': o.id,
        'title': o.title,
        'description': o.description,
        'category': o.category,
        'image': o.image,
        'user_id': o.user_id
    } for o in outfits])

@app.route('/api/ratings', methods=['POST'])
def ratings():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json()
    score = data.get('score')
    outfit_id = data.get('outfit_id')
    if not all([score, outfit_id]):
        return jsonify({'error': 'Score and outfit_id are required'}), 400
    if not isinstance(score, int) or score < 1 or score > 5:
        return jsonify({'error': 'Score must be an integer between 1 and 5'}), 400
    rating = Rating(score=score, user_id=user_id, outfit_id=outfit_id)
    db.session.add(rating)
    db.session.commit()
    return jsonify({'message': 'Rating submitted'}), 201

@app.route('/api/search', methods=['GET'])
def search():
    query = request.args.get('q', '')
    if not query:
        return jsonify({'error': 'Search query is required'}), 400
    users = User.query.filter(User.username.ilike(f'%{query}%')).all()
    outfits = Outfit.query.filter(
        (Outfit.title.ilike(f'%{query}%')) | (Outfit.description.ilike(f'%{query}%'))
    ).all()
    return jsonify({
        'users': [{'id': u.id, 'username': u.username, 'profile_picture': u.profile_picture} for u in users],
        'outfits': [{
            'id': o.id,
            'title': o.title,
            'description': o.description,
            'category': o.category,
            'image': o.image,
            'user_id': o.user_id,
            'created_at': o.created_at.isoformat()
        } for o in outfits]
    })

@app.route('/Uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    app.run(debug=True, port=5000)