from flask import Flask, request, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timezone
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///styleswap.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'Uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg'}

CORS(app)  # Enable CORS for frontend integration

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Ensure upload folder exists
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

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
    ratings = db.relationship('Rating', backref='outfit', lazy=True)

class Rating(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    score = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    outfit_id = db.Column(db.Integer, db.ForeignKey('outfit.id'), nullable=False)

# Helper function for allowed file extensions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# Root Route
@app.route('/')
def index():
    return jsonify({'message': 'StyleSwap API is running'})

# Authentication Routes
@app.route('/api/signup', methods=['POST'])
def signup():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({'error': 'Username already exists'}), 400

    user = User(username=username)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    session['user_id'] = user.id
    return jsonify({'message': 'User created', 'user': {'id': user.id, 'username': user.username}}), 201

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    user = User.query.filter_by(username=username).first()
    if user and user.check_password(password):
        session['user_id'] = user.id
        return jsonify({'message': 'Login successful', 'user': {'id': user.id, 'username': user.username}})
    return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    session.pop('user_id', None)
    return jsonify({'message': 'Logged out'})

# Outfit Routes
@app.route('/api/outfits', methods=['GET', 'POST'])
def outfits():
    if request.method == 'GET':
        outfits = Outfit.query.all()
        return jsonify([{
            'id': o.id,
            'title': o.title,
            'description': o.description,
            'category': o.category,
            'image': o.image,
            'user_id': o.user_id,
            'created_at': o.created_at.isoformat()
        } for o in outfits])
    elif request.method == 'POST':
        if 'user_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
        if 'image' not in request.files:
            return jsonify({'error': 'No image file provided'}), 400
        file = request.files['image']
        data = request.form
        if not all([data.get('title'), data.get('description'), data.get('category')]):
            return jsonify({'error': 'Missing required fields'}), 400
        if file and allowed_file(file.filename):
            filename = f"{datetime.now(timezone.utc).timestamp()}_{secure_filename(file.filename)}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            outfit = Outfit(
                title=data['title'],
                description=data['description'],
                category=data['category'],
                image=filename,
                user_id=session['user_id']
            )
            db.session.add(outfit)
            db.session.commit()
            return jsonify({'message': 'Outfit created', 'outfit': {
                'id': outfit.id,
                'title': outfit.title,
                'description': outfit.description,
                'category': outfit.category,
                'image': outfit.image,
                'user_id': outfit.user_id,
                'created_at': outfit.created_at.isoformat()
            }}), 201
        return jsonify({'error': 'Invalid file type'}), 400

@app.route('/api/outfits/<int:id>', methods=['GET', 'PUT', 'DELETE'])
def outfit(id):
    outfit = Outfit.query.get_or_404(id)
    if request.method == 'GET':
        return jsonify({
            'id': outfit.id,
            'title': outfit.title,
            'description': outfit.description,
            'category': outfit.category,
            'image': outfit.image,
            'user_id': outfit.user_id,
            'created_at': outfit.created_at.isoformat()
        })
    elif request.method == 'PUT':
        if 'user_id' not in session or session['user_id'] != outfit.user_id:
            return jsonify({'error': 'Unauthorized'}), 401
        data = request.form
        file = request.files.get('image')
        outfit.title = data.get('title', outfit.title)
        outfit.description = data.get('description', outfit.description)
        outfit.category = data.get('category', outfit.category)
        if file and allowed_file(file.filename):
            filename = f"{datetime.now(timezone.utc).timestamp()}_{secure_filename(file.filename)}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            outfit.image = filename
        db.session.commit()
        return jsonify({'message': 'Outfit updated', 'outfit': {
            'id': outfit.id,
            'title': outfit.title,
            'description': outfit.description,
            'category': outfit.category,
            'image': outfit.image,
            'user_id': outfit.user_id,
            'created_at': outfit.created_at.isoformat()
        }})
    elif request.method == 'DELETE':
        if 'user_id' not in session or session['user_id'] != outfit.user_id:
            return jsonify({'error': 'Unauthorized'}), 401
        db.session.delete(outfit)
        db.session.commit()
        return jsonify({'message': 'Outfit deleted'})

# Rating Route
@app.route('/api/ratings', methods=['POST'])
def create_rating():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json()
    score = data.get('score')
    outfit_id = data.get('outfit_id')
    if not all([score, outfit_id]):
        return jsonify({'error': 'Missing required fields'}), 400
    if not isinstance(score, int) or score < 1 or score > 5:
        return jsonify({'error': 'Score must be an integer between 1 and 5'}), 400
    rating = Rating(score=score, user_id=session['user_id'], outfit_id=outfit_id)
    db.session.add(rating)
    db.session.commit()
    return jsonify({'message': 'Rating submitted', 'rating': {
        'id': rating.id,
        'score': rating.score,
        'user_id': rating.user_id,
        'outfit_id': rating.outfit_id
    }}), 201

# Profile Route
@app.route('/api/profile', methods=['GET'])
def get_profile():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    user = User.query.get_or_404(session['user_id'])
    outfits = Outfit.query.filter_by(user_id=user.id).all()
    return jsonify({
        'user': {
            'id': user.id,
            'username': user.username,
            'profile_picture': user.profile_picture
        },
        'outfits': [{
            'id': o.id,
            'title': o.title,
            'description': o.description,
            'category': o.category,
            'image': o.image,
            'created_at': o.created_at.isoformat()
        } for o in outfits]
    })

# Search Route
@app.route('/api/search', methods=['GET'])
def search():
    query = request.args.get('q', '')
    if not query:
        return jsonify({'error': 'Search query is required'}), 400
    users = User.query.filter(User.username.ilike(f'%{query}%')).all()
    outfits = Outfit.query.filter(
        (Outfit.title.ilike(f'%{query}%')) | (Outfit.category.ilike(f'%{query}%'))
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

# Share Route
@app.route('/api/outfits/<int:id>/share', methods=['GET'])
def share_outfit(id):
    outfit = Outfit.query.get_or_404(id)
    share_url = f"https://styleswap.example.com/outfits/{id}"
    return jsonify({'message': 'Share link generated', 'share_url': share_url})

if __name__ == '__main__':
    app.run(debug=True, port=5000)