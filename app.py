from flask import Flask, render_template, request, redirect, url_for, flash, send_file, send_from_directory
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import threading
import os
import logging
from datetime import datetime
from queue import Queue
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Queue for background tasks
upload_queue = Queue()


# Initialize Flask app and configuration
app = Flask(__name__)
app.secret_key = 'ZDIOFIOHHIO87324FHç&é_jOIFEJHOIJF564153'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Ensuring folders exist
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Flask-Login setup
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

# Logging setup
logging.basicConfig(filename='server.log', level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')


# Define User model for SQLAlchemy
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(100), nullable=False)
    folder = db.Column(db.String(100), unique=True, nullable=False)
    storage_quota = db.Column(db.Integer, nullable=False, default=15)  # Quota in GB
    is_admin = db.Column(db.Boolean, nullable=False, default=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

def send_email(sender_email, sender_password, recipient_email, subject, body):
    try:
        # Create the email
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Subject'] = subject

        # Attach the body with the msg instance
        msg.attach(MIMEText(body, 'plain'))

        # Setup the SMTP server
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()  # Secure the connection
        server.login(sender_email, sender_password)  # Login to the email account

        # Send the email
        text = msg.as_string()
        server.sendmail(sender_email, recipient_email, text)

        # Quit the server
        server.quit()

        print("Email sent successfully!")

    except Exception as e:
        print(f"Failed to send email. Error: {e}")


def get_user_files_info(user_folder):
    user_path = os.path.join(app.config['UPLOAD_FOLDER'], user_folder)
    if not os.path.exists(user_path):
        return 0, 0  # No files, size is 0

    total_size = 0
    num_files = 0
    for root, dirs, files in os.walk(user_path):
        for file in files:
            num_files += 1
            total_size += os.path.getsize(os.path.join(root, file))
    return num_files, total_size


# Fonction pour créer les tables de base de données si elles n'existent pas
def create_db():
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(email='manchec.serguei@gmail.com').first():
            admin = User(email='manchec.serguei@gmail.com', folder='admin', is_admin=True)
            admin.set_password('gazerbim')
            db.session.add(admin)
            db.session.commit()


# Charger l'utilisateur depuis la base de données pour Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# Page d'accueil
@app.route('/')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    else:
        return render_template('home.html')


# Page d'accueil après connexion
@app.route('/index')
@login_required
def index():
    user_folder = current_user.folder
    user_files = []
    user_folder_path = os.path.join(app.config['UPLOAD_FOLDER'], user_folder)

    for file_name in os.listdir(user_folder_path):
        file_path = os.path.join(user_folder_path, file_name)
        if os.path.isfile(file_path):
            file_size = os.path.getsize(file_path)
            modification_timestamp = os.path.getmtime(file_path)
            modification_date_str = datetime.fromtimestamp(modification_timestamp).strftime('%Y-%m-%d %H:%M:%S')
            user_files.append({
                'name': file_name,
                'size': file_size / (1000 * 1000),
                'modification_date': modification_date_str,
                'type': file_name.split('.')[-1].lower()
            })

    sort_by = request.args.get('sort_by', 'name')
    sort_order = request.args.get('sort_order', 'asc')

    if sort_by == 'name':
        user_files.sort(key=lambda x: x['name'].lower(), reverse=(sort_order == 'desc'))
    elif sort_by == 'size':
        user_files.sort(key=lambda x: x['size'], reverse=(sort_order == 'desc'))
    elif sort_by == 'modification_date':
        user_files.sort(key=lambda x: datetime.strptime(x['modification_date'], '%Y-%m-%d %H:%M:%S'), reverse=(sort_order == 'desc'))

    num_files, total_size = get_user_files_info(user_folder)
    total_size_mb = total_size / (1000 * 1000)
    storage_percentage = (total_size_mb / (current_user.storage_quota * 1000)) * 100

    return render_template(
        'index.html',
        files=user_files,
        total_size_mb=total_size_mb,
        storage_percentage=storage_percentage,
        sort_by=sort_by,
        sort_order=sort_order,
        storage_quota_mb=current_user.storage_quota * 1000  # Ajout de la taille maximale du cloud
    )



@app.route('/uploads/<path:filename>')
@login_required
def serve_file(filename):
    user_folder = current_user.folder
    folder_path = os.path.join(app.config['UPLOAD_FOLDER'], user_folder)

    # Vérifiez que le fichier existe
    if not os.path.isfile(os.path.join(folder_path, filename)):
        print(filename)
        print(404)

    return send_from_directory(folder_path, filename)

def save_file(content, path):
    with open(path, 'wb') as f:
        f.write(content)


def upload_file_in_background(content, user_folder, filename):
    upload_path = os.path.join(UPLOAD_FOLDER, user_folder, filename)
    with open(upload_path, 'wb') as f:
        f.write(content)
    logging.info("File uploaded: %s/%s", user_folder, filename)


def process_upload_queue():
    while not upload_queue.empty():
        content, user_folder, filename = upload_queue.get()
        upload_file_in_background(content, user_folder, filename)


# Route pour gérer l'upload de fichiers
@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    if 'file' not in request.files:
        flash("Aucun fichier sélectionné.")
        return redirect(url_for('index'))

    file = request.files['file']
    if file.filename == '':
        flash("Aucun fichier sélectionné.")
        return redirect(url_for('index'))

    user_folder = current_user.folder
    upload_path = os.path.join(app.config['UPLOAD_FOLDER'], user_folder)

    if not os.path.exists(upload_path):
        os.makedirs(upload_path)

    file_size = len(file.read())
    file.seek(0)
    num_files, total_size = get_user_files_info(user_folder)
    total_size_mb = total_size / (1000 * 1000)  # Convertir la taille totale en Mo
    storage_quota_mb = current_user.storage_quota * 1000  # Convertir le quota en Mo
    if (total_size_mb + file_size / (1000 * 1000)) > storage_quota_mb:
        flash("Espace insuffisant pour télécharger ce fichier.")
        return redirect(url_for('index'))

    filename = file.filename
    file_content = file.read()

    # Ajouter la tâche à la queue
    upload_queue.put((file_content, user_folder, filename))

    # Démarrer un thread qui traite la queue
    thread = threading.Thread(target=process_upload_queue)
    thread.start()

    flash("Téléversement en cours pour le fichier '{}'.".format(filename))
    return redirect(url_for('index'))


@app.route('/update_quota/<int:user_id>', methods=['POST'])
@login_required
def update_quota(user_id):
    if not current_user.is_admin:
        flash('Permission refusée.')
        return redirect(url_for('index'))

    new_quota = request.form.get('new_quota')
    if not new_quota:
        flash('Le quota est requis.')
        return redirect(url_for('user_management'))

    try:
        new_quota = float(new_quota)  # Convertir en float au lieu de int
        user = User.query.get(user_id)
        if user:
            user.storage_quota = new_quota
            db.session.commit()
            flash(f'Quota de stockage mis à jour pour {user.email}.')
        else:
            flash('Utilisateur non trouvé.')
    except ValueError:
        flash('Le quota doit être un nombre valide.')

    return redirect(url_for('user_management'))




# Route pour télécharger un fichier
@app.route('/download/<filename>', methods=['GET'])
@login_required
def download_file(filename):
    user_folder = current_user.folder
    return send_file(os.path.join(app.config['UPLOAD_FOLDER'], user_folder, filename), as_attachment=True)


# Route pour supprimer un fichier
@app.route('/delete/<filename>', methods=['POST'])
@login_required
def delete_file(filename):
    user_folder = current_user.folder
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], user_folder, filename)

    if os.path.exists(file_path):
        os.remove(file_path)
        logging.info("File deleted: %s/%s", user_folder, filename)
        flash('Fichier supprimé avec succès')
    else:
        flash('Le fichier spécifié n\'existe pas')

    return redirect(url_for('index'))


# Route pour modifier un fichier texte
@app.route('/edit/<filename>', methods=['GET', 'POST'])
@login_required
def edit_file(filename):
    user_folder = current_user.folder
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], user_folder, filename)

    if request.method == 'POST':
        content = request.form['content']
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(content.replace('\r\n', '\n'))
        flash('Fichier sauvegardé avec succès')
        return redirect(url_for('index'))

    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()

    return render_template('edit_file.html', filename=filename, content=content)


# Route pour sauvegarder un texte
@app.route('/save/<filename>', methods=['POST'])
@login_required
def save_file(filename):
    user_folder = current_user.folder
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], user_folder, filename)

    if not os.path.exists(file_path):
        flash('Le fichier spécifié n\'existe pas')
        return redirect(url_for('index'))

    new_content = request.form['content']
    with open(file_path, 'w') as file:
        file.write(new_content)

    flash('Fichier modifié avec succès')
    return redirect(url_for('index'))


# Route pour la page de gestion des utilisateurs
@app.route('/user_management')
@login_required
def user_management():
    if current_user.is_admin:
        print(f"admin connexion by {current_user.email}")
        users = User.query.all()
        user_info = []

        for user in users:
            num_files, total_size = get_user_files_info(user.folder)
            total_size_mb = total_size / (1000 * 1000)  # Conversion en Mo
            user_info.append({
                'id': user.id,
                'username': user.email,
                'num_files': num_files,
                'total_size': total_size_mb,
                'storage_quota': user.storage_quota
            })

        return render_template('user_management.html', user_info=user_info)
    return redirect(url_for('index'))




@app.route('/create_password', methods=['GET', 'POST'])
def create_password():
    email = request.args.get('email')
    token = request.args.get('token')

    if not email or not token:
        flash('Lien invalide.')
        return redirect(url_for('home'))

    if request.method == 'POST':
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if not new_password or not confirm_password:
            flash('Les champs de mot de passe sont requis.')
        elif new_password != confirm_password:
            flash('Les mots de passe ne correspondent pas.')
        else:
            # Vérifier le token
            if check_password_hash(token, email + app.secret_key):
                user = User.query.filter_by(email=email).first()
                if user:
                    user.set_password(new_password)
                    db.session.commit()
                    flash('Votre mot de passe a été mis à jour avec succès.')
                else:
                    # Cas où l'utilisateur n'existe pas encore (inscription initiale)
                    user_folder = email.split('@')[0]  # Crée un dossier basé sur l'email de l'utilisateur
                    new_user = User(email=email, folder=user_folder)
                    new_user.set_password(new_password)
                    db.session.add(new_user)
                    db.session.commit()
                    # Créer le dossier utilisateur
                    user_folder_path = os.path.join('uploads', user_folder)
                    try:
                        os.makedirs(user_folder_path, exist_ok=True)
                    except OSError as e:
                        flash(f'Erreur lors de la création du dossier utilisateur: {e}')
                        return redirect(url_for('register'))
                    flash('Inscription réussie. Vous pouvez maintenant vous connecter.')

                return redirect(url_for('login'))
            else:
                flash('Lien invalide ou expiré.')

    return render_template('create_password.html', email=email, token=token)




@app.route('/demand_email_confirmation')
def demand_conf():
    return render_template('demand_conf.html')


@app.route('/email_confirmation', methods=['GET', 'POST'])
def confirm_email():
    email = request.args.get('email')
    password = request.args.get('password')
    print(f"email = {email}, pass = {password}")
    user_folder = email.split('@')[0]  # Crée un dossier basé sur l'email de l'utilisateur
    new_user = User(email=email, folder=user_folder)
    new_user.set_password(password)
    db.session.add(new_user)
    db.session.commit()
    # Créer le dossier utilisateur
    user_folder_path = os.path.join('uploads', user_folder)
    try:
        os.makedirs(user_folder_path, exist_ok=True)
    except OSError as e:
        flash(f'Erreur lors de la création du dossier utilisateur: {e}')
        return redirect(url_for('register'))
    flash('Inscription réussie. Vous pouvez maintenant vous connecter.')
    return redirect(url_for('login'))



@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')

        if not email:
            flash('Email requis.')
            return redirect(url_for('register'))

        if User.query.filter_by(email=email).first():
            flash('Un compte avec cet email existe déjà.')
            return redirect(url_for('register'))

        # Générer un token unique pour l'utilisateur
        token = generate_password_hash(email + app.secret_key)
        reset_link = url_for('create_password', email=email, token=token, _external=True)

        # Envoyer l'email de confirmation
        send_email('serguei.manchec@gmail.com', 'mnfb qcaa sdqw pdqn', email, 'Création de mot de passe Mon Cloud',
                   f"Veuillez cliquer sur ce lien pour créer votre mot de passe : {reset_link}")

        flash('Un email a été envoyé pour créer votre mot de passe.')
        return render_template('demand_conf.html')

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            logging.info("User logged in: %s", email)
            return redirect(url_for('index'))
        else:
            flash('Email ou mot de passe incorrect.')

    return render_template('login.html')


@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')

        user = User.query.filter_by(email=email).first()
        if user:
            # Générer un token unique pour l'utilisateur
            token = generate_password_hash(email + app.secret_key)
            reset_link = url_for('create_password', email=email, token=token, _external=True)

            # Envoyer l'email de réinitialisation de mot de passe
            send_email('serguei.manchec@gmail.com', 'mnfb qcaa sdqw pdqn', email, 'Réinitialisation du mot de passe',
                       f"Veuillez cliquer sur ce lien pour réinitialiser votre mot de passe : {reset_link}")
            flash('Un lien de réinitialisation de mot de passe a été envoyé à votre adresse email.')
            return render_template('demand_conf.html')
        else:
            flash('Aucun compte trouvé avec cet email.')

    return render_template('forgot_password.html')

@app.route('/confirm_delete_account')
def confirm_delete_account():
    email = request.args.get('email')
    token = request.args.get('token')

    if not email or not token:
        flash('Lien invalide.')
        return redirect(url_for('home'))

    user = User.query.filter_by(email=email).first()
    if user and check_password_hash(token, email + app.secret_key):
        # Supprimer le dossier de l'utilisateur
        user_folder_path = os.path.join(app.config['UPLOAD_FOLDER'], user.folder)
        if os.path.exists(user_folder_path):
            for root, dirs, files in os.walk(user_folder_path, topdown=False):
                for file in files:
                    os.remove(os.path.join(root, file))
                for dir in dirs:
                    os.rmdir(os.path.join(root, dir))
            os.rmdir(user_folder_path)

        # Supprimer l'utilisateur de la base de données
        db.session.delete(user)
        db.session.commit()

        logout_user()
        flash('Votre compte a été supprimé avec succès.')
        return redirect(url_for('home'))
    else:
        flash('Lien invalide ou expiré.')
        return redirect(url_for('index'))

@app.route('/delete_account', methods=['GET', 'POST'])
@login_required
def delete_account():
    if request.method == 'POST':
        # Générer un token unique pour l'utilisateur
        token = generate_password_hash(current_user.email + app.secret_key)
        confirmation_link = url_for('confirm_delete_account', email=current_user.email, token=token, _external=True)

        # Envoyer l'email de confirmation
        send_email('serguei.manchec@gmail.com', 'mnfb qcaa sdqw pdqn', current_user.email,
                   'Confirmation de suppression de compte Mon Cloud',
                   f"Veuillez cliquer sur ce lien pour confirmer la suppression de votre compte. Attention, en cliquant sur ce lien, votre compte sera définitivement supprimé !: {confirmation_link}")

        flash('Un email de confirmation a été envoyé à votre adresse email.')
        return redirect(url_for('index'))

    return render_template('delete_account.html')

@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    email = request.args.get('email')
    if not email:
        flash('Email manquant.')
        return redirect(url_for('home'))

    if request.method == 'POST':
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if not new_password or not confirm_password:
            flash('Les champs de mot de passe sont requis.')
        elif new_password != confirm_password:
            flash('Les mots de passe ne correspondent pas.')
        else:
            user = User.query.filter_by(email=email).first()
            if user:
                user.set_password(new_password)
                db.session.commit()
                flash('Votre mot de passe a été mis à jour avec succès.')
                return redirect(url_for('login'))
            else:
                flash('Aucun compte trouvé avec cet email.')

    return render_template('reset_password.html', email=email)



@app.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    logging.info("User logged out: %s", current_user.email)
    logout_user()
    return redirect('/login')

"""
# Route pour mettre à jour le mot de passe
@app.route('/update_password', methods=['POST'])
def update_password():
    email = request.form.get('email')
    new_password = request.form.get('new_password')

    user = User.query.filter_by(email=email).first()
    if user:
        user.set_password(new_password)
        db.session.commit()
        flash('Mot de passe mis à jour avec succès.')
    else:
        flash('Utilisateur non trouvé.')

    return redirect(url_for('home'))
"""

if __name__ == '__main__':
    create_db()
    app.run(debug=True, host='0.0.0.0', port=15000)
