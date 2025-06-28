from flask import Flask, request, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///styleswap.db'
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['UPLOAD_FOLDER'] = 'uploads'
db = SQLAlchemy(app)
migrate = Migrate(app, db)

#Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    profile_picture = db.Column(db.String(120))
    outfits = db.relationship('Outfit', backref='user', lazy=True)
    ratings = db.relationship('Rating', backref='user', lazy=True)

class Outfit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(50))
    image = db.Column(db.String(120))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    ratings = db.relationship('Rating', backref='outfit', lazy=True)

class Rating(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    score = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    outfit_id = db.Column(db.Integer, db.ForeignKey('outfit.id'), nullable=False)

#Authentication Routes
@app.route('/api/signup', methods=['POST'])
def signup():
    data = request.get_json()
    user = User(username=data['username'], password=data['password'])
    db.session.add(user)
    db.session.commit()
    return jsonify({'message': 'User created'}), 201

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(username=data['username'], password=data['password']).first()
    if user:
        session['user_id'] = user.id
        return jsonify({'message': 'Login successful', 'user_id': user.id})
    return jsonify({'error': 'Invalid credentials'}), 401

#Outfit Routes
@app.route('/api/outfits', methods=['GET', 'POST'])
def outfits():
    if request.method == 'GET':
        outfits = Outfit.query.all()
        return jsonify([{'id': o.id, 'title': o.title, 'description': o.description, 'category': o.category, 'image': o.image, 'user_id': o.user_id} for o in outfits])
    elif request.method == 'POST':
        if 'user_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
        file = request.files.get('image')
        data = request.form
        filename = secure_filename(file.filename) if file else None
        if file:
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        outfit = Outfit(
            title=data['title'],
            description=data['description'],
            category=data['category'],
            image=filename,
            user_id=session['user_id']
        )
        db.session.add(outfit)
        db.session.commit()
        return jsonify({'message': 'Outfit created'}), 201

@app.route('/api/outfits/<int:id>', methods=['GET', 'PUT', 'DELETE'])
def outfit(id):
    outfit = Outfit.query.get_or_404(id)
    if request.method == 'GET':
        return jsonify({'id': outfit.id, 'title': outfit.title, 'description': outfit.description, 'category': outfit.category, 'image': outfit.image, 'user_id': outfit.user_id})
    elif request.method == 'PUT':
        if 'user_id' not in session or session['user_id'] != outfit.user_id:
            return jsonify({'error': 'Unauthorized'}), 401
        data = request.form
        file = request.files.get('image')
        if file:
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            outfit.image = filename
        outfit.title = data['title']
        outfit.description = data['description']
        outfit.category = data['category']
        db.session.commit()
        return jsonify({'message': 'Outfit updated'})
    elif request.method == 'DELETE':
        if 'user_id' not in session or session['user_id'] != outfit.user_id:
            return jsonify({'error': 'Unauthorized'}), 401
        db.session.delete(outfit)
        db.session.commit()
        return jsonify({'message': 'Outfit deleted'})

#Rating Route
@app.route('/api/ratings', methods=['POST'])
def create_rating():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json()
    rating = Rating(score=data['score'], user_id=session['user_id'], outfit_id=data['outfit_id'])
    db.session.add(rating)
    db.session.commit()
    return jsonify({'message': 'Rating submitted'}), 201

if __name__ == 'main':
    app.run(port=5000)

