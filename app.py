from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime

# Flask app inicializálása
app = Flask(__name__)
app.secret_key = "secret_key_for_flask"  # Flash üzenetekhez
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Adatbázis inicializálása
db = SQLAlchemy(app)

# Flask-Login beállítása
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Felhasználó modell
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)

# Óraállás modell
class GasMeterReading(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, unique=True)  # Dátum egyedi
    reading = db.Column(db.Float, nullable=False)

# Adatbázis inicializálása (ha még nem létezik)
with app.app_context():
    db.create_all()

# Bejelentkezés kezelése
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Kezdőoldal (rögzítés) – csak bejelentkezett felhasználóknak
@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    if request.method == "POST":
        date_str = request.form.get("date")
        reading = request.form.get("reading")

        if not date_str or not reading:
            flash("Minden mezőt ki kell tölteni!", "danger")
        else:
            try:
                date = datetime.strptime(date_str, "%Y-%m-%d").date()
                reading = float(reading)

                # Ellenőrzés: Van-e már rögzítés ugyanarra a hónapra
                existing_reading = GasMeterReading.query.filter(
                    db.extract('year', GasMeterReading.date) == date.year,
                    db.extract('month', GasMeterReading.date) == date.month
                ).first()

                if existing_reading:
                    flash(f"Ebben a hónapban már van rögzített óraállás ({existing_reading.reading} m³).", "warning")
                else:
                    new_reading = GasMeterReading(date=date, reading=reading)
                    db.session.add(new_reading)
                    db.session.commit()
                    flash("Óraállás sikeresen rögzítve!", "success")
            except ValueError:
                flash("Érvényes adatokat adj meg!", "danger")

        return redirect(url_for("index"))

    readings = GasMeterReading.query.order_by(GasMeterReading.date.desc()).all()
    return render_template("index.html", readings=readings)

# Bejelentkezési oldal
@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        user = User.query.filter_by(username=username).first()

        if user and user.password == password:  # Ebben az esetben szöveges jelszót ellenőrzünk
            login_user(user)
            flash("Sikeres bejelentkezés!", "success")
            return redirect(url_for("index"))
        else:
            flash("Hibás felhasználónév vagy jelszó.", "danger")

    return render_template("login.html")

# Kijelentkezés kezelése
@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Sikeres kijelentkezés!", "success")
    return redirect(url_for("login"))

# Óraállás szerkesztése
@app.route("/edit/<int:id>", methods=["GET", "POST"])
def edit(id):
    reading = GasMeterReading.query.get_or_404(id)

    if request.method == "POST":
        date_str = request.form.get("date")
        new_reading = request.form.get("reading")

        if not date_str or not new_reading:
            flash("Minden mezőt ki kell tölteni!", "danger")
        else:
            try:
                date = datetime.strptime(date_str, "%Y-%m-%d").date()
                new_reading = float(new_reading)

                # Ellenőrzés: Van-e másik rögzítés ugyanarra a hónapra
                existing_reading = GasMeterReading.query.filter(
                    db.extract('year', GasMeterReading.date) == date.year,
                    db.extract('month', GasMeterReading.date) == date.month,
                    GasMeterReading.id != id
                ).first()

                if existing_reading:
                    flash(f"Ebben a hónapban már van rögzített óraállás ({existing_reading.reading} m³).", "warning")
                else:
                    reading.date = date
                    reading.reading = new_reading
                    db.session.commit()
                    flash("Óraállás sikeresen frissítve!", "success")
                    return redirect(url_for("index"))
            except ValueError:
                flash("Érvényes adatokat adj meg!", "danger")

    return render_template("edit.html", reading=reading)

# Riport oldal
@app.route("/report", methods=["GET", "POST"])
def report():
    consumption = None
    year, month = None, None

    if request.method == "POST":
        year = request.form.get("year")
        month = request.form.get("month")

        if not year or not month:
            flash("Minden mezőt ki kell tölteni!", "danger")
        else:
            try:
                year = int(year)
                month = int(month)

                # Keresési időszak meghatározása
                start_date = datetime(year, month, 1)
                if month == 12:
                    end_date = datetime(year + 1, 1, 1)
                else:
                    end_date = datetime(year, month + 1, 30)

                # Lekérdezések az adott időszakra
                readings = GasMeterReading.query.filter(
                    GasMeterReading.date >= start_date,
                    GasMeterReading.date < end_date
                ).order_by(GasMeterReading.date).all()

                if len(readings) >= 2:
                    consumption = readings[-1].reading - readings[0].reading
                else:
                    flash("Nincs elég adat az adott időszakra.", "warning")

            except ValueError:
                flash("Érvényes év és hónap kell!", "danger")

    return render_template("report.html", consumption=consumption, year=year, month=month)

# Alkalmazás futtatása
if __name__ == "__main__":
    app.run(debug=True)
