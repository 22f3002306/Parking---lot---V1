from flask import Flask, render_template, request, redirect, url_for, session, flash
from models import db, User, ParkingLot, ParkingSpot, Reservation
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///parking.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'secret-key' 

db.init_app(app)

with app.app_context():
    db.create_all()
    if not User.query.filter_by(role='admin').first():
        admin = User(username='admin', password=generate_password_hash('admin'), role='admin')
        db.session.add(admin)
        db.session.commit()

@app.route('/')
def home():
    return render_template('base.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return redirect(url_for('register'))
        user = User(username=username, password=generate_password_hash(password), role='user')
        db.session.add(user)
        db.session.commit()
        flash('Registration successful! Please log in.')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['role'] = user.role
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('user_dashboard'))
        flash('Invalid credentials')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/admin')
def admin_dashboard():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    lots = ParkingLot.query.all()
    users = User.query.filter_by(role='user').all()
    return render_template('admin_dashboard.html', lots=lots, users=users)

@app.route('/user')
def user_dashboard():
    if session.get('role') != 'user':
        return redirect(url_for('login'))
    lots = ParkingLot.query.all()
    return render_template('user_dashboard.html', lots=lots)

@app.route('/admin/create_lot', methods=['GET', 'POST'])
def create_lot():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    if request.method == 'POST':
        name = request.form['prime_location_name']
        price = float(request.form['price'])
        address = request.form['address']
        pin_code = int(request.form['pin_code'])
        max_spots = int(request.form['maximum_number_of_spots'])
        lot = ParkingLot(prime_location_name=name, price=price, address=address, pin_code=pin_code, maximum_number_of_spots=max_spots)
        db.session.add(lot)
        db.session.commit()
        for _ in range(max_spots):
            spot = ParkingSpot(lot_id=lot.id, status='A')
            db.session.add(spot)
        db.session.commit()
        return redirect(url_for('admin_dashboard'))
    return render_template('create_lot.html')

@app.route('/admin/edit_lot/<int:lot_id>', methods=['GET', 'POST'])
def edit_lot(lot_id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    lot = ParkingLot.query.get_or_404(lot_id)
    if request.method == 'POST':
        lot.prime_location_name = request.form['prime_location_name']
        lot.price = float(request.form['price'])
        lot.address = request.form['address']
        lot.pin_code = int(request.form['pin_code'])
        db.session.commit()
        return redirect(url_for('admin_dashboard'))
    return render_template('edit_lot.html', lot=lot)

@app.route('/admin/delete_lot/<int:lot_id>')
def delete_lot(lot_id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    lot = ParkingLot.query.get_or_404(lot_id)
    if any(spot.status == 'O' for spot in lot.spots):
        flash('Cannot delete lot: some spots are occupied.')
        return redirect(url_for('admin_dashboard'))
    for spot in lot.spots:
        db.session.delete(spot)
    db.session.delete(lot)
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/reserve/<int:lot_id>', methods=['GET', 'POST'])
def reserve(lot_id):
    if session.get('role') != 'user':
        return redirect(url_for('login'))
    lot = ParkingLot.query.get_or_404(lot_id)
    available_spot = ParkingSpot.query.filter_by(lot_id=lot_id, status='A').first()
    if not available_spot:
        flash('No available spots in this lot.')
        return redirect(url_for('user_dashboard'))
    if request.method == 'POST':
        available_spot.status = 'O'
        reservation = Reservation(
            spot_id=available_spot.id,
            user_id=session['user_id'],
            parking_timestamp=datetime.now(),
            parking_cost_per_unit_time=lot.price
        )
        db.session.add(reservation)
        db.session.commit()
        flash('Spot reserved!')
        return redirect(url_for('my_reservations'))
    return render_template('reserve.html', lot=lot, spot=available_spot)

@app.route('/my_reservations', methods=['GET', 'POST'])
def my_reservations():
    if session.get('role') != 'user':
        return redirect(url_for('login'))
    reservations = Reservation.query.filter_by(user_id=session['user_id']).all()
    if request.method == 'POST':
        res_id = int(request.form['res_id'])
        action = request.form['action']
        reservation = Reservation.query.get(res_id)
        if action == 'release' and reservation.leaving_timestamp is None:
            reservation.leaving_timestamp = datetime.now()
            reservation.spot.status = 'A'
            db.session.commit()
    return render_template('my_reservations.html', reservations=reservations)

if __name__ == '__main__':
    app.run(debug=True) 