# import module
from flask import Flask, render_template, request, redirect, url_for, flash
from datetime import date, datetime, timedelta

from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

import utenti_dao
import raccolte_dao
#import donazioni_dao

from models import User

from PIL import Image
#import PIL.Image

PROFILE_IMG_HEIGHT = 130
POST_IMG_WIDTH = 300

# create the application
app = Flask(__name__)

app.config['SECRET_KEY'] = 'Secret key del sito'

login_manager = LoginManager()
login_manager.init_app(app)

# define the homepage
@app.route('/')
def home():
    
    '''Interroga il database, richiedi tutte le raccolte attive con le rispettive informazioni,
       ordinale mostrando prima quelle più vicine alla scadenza.
       Quando si raggiunge questa pagina deve avvenire un controllo su tutte le raccolte in corso
       per verificare che siano ancora valide'''

    now = datetime.now()  # Get the current date and time
    current_date = now.date()  # Get the current date
    current_hour = now.hour  # Get the current hour
    current_minute = now.minute  # Get the current minute

    # display all the posts
    raccolte_db = raccolte_dao.get_raccolte()

    return render_template('home.html', raccolte=raccolte_db)

# restituisci solo la pagina per iscriversi
@app.route('/iscriviti')
def iscriviti():
    return render_template('iscriviti.html')

# ricevi i dati dal form di iscrizione, controlla se l'utente esiste già, se non
# esiste aggiungi i dati al database
@app.route('/iscriviti', methods=['POST'])
def iscriviti_post():

    # dati del nuovo utente compilati nel form da essere inseriti nel database
    nuovo_utente_form = request.form.to_dict()

    # controlla se l'utente esiste già
    user_in_db = utenti_dao.get_user_by_email(nuovo_utente_form.get('email'))

    # se l'utente esiste già reindirizza alla stessa pagine per iscriversi
    if user_in_db:
        flash('C\'è già un utente registrato con questa email', 'danger')
        return redirect(url_for('iscriviti'))
    else:
        img_profilo = ''
        usr_image = request.files['immagine_utente']
        if usr_image:
            # Open the user-provided image using the Image module
            img = Image.open(usr_image)

            # Get the width and height of the image
            width, height = img.size

            # Calculate the new width while maintaining the aspect ratio
            new_width = PROFILE_IMG_HEIGHT * width / height

            # Define the size for thumbnail creation with the desired height and calculated width
            size = new_width, PROFILE_IMG_HEIGHT
            img.thumbnail(size, Image.Resampling.LANCZOS)

            # Calculate the coordinates for cropping the image to a square shape
            left = (new_width/2 - PROFILE_IMG_HEIGHT/2)
            top = 0
            right = (new_width/2 + PROFILE_IMG_HEIGHT/2)
            bottom = PROFILE_IMG_HEIGHT

            # Crop the image using the calculated coordinates to create a square image
            img = img.crop((left, top, right, bottom))

            # Extracting file extension from the image filename
            ext = usr_image.filename.split('.')[-1]

            # Saving the image with a unique filename in the 'static' directory
            img.save('static/' + nuovo_utente_form.get('nome').lower() + '_' + nuovo_utente_form.get('cognome').lower() + '.' + ext)

            img_profilo = nuovo_utente_form.get('nome').lower() + '_' + nuovo_utente_form.get('cognome').lower() + '.' + ext

        nuovo_utente_form['password'] = generate_password_hash(nuovo_utente_form.get('password'))
        # Updating the 'immagine_utnete' field in the user dictionary with the image filename
        nuovo_utente_form['immagine_utente'] = img_profilo

        success = utenti_dao.add_user(nuovo_utente_form)

        if success:
            flash('Utente creato correttamente', 'success')
            return redirect(url_for('home'))
        else:
            flash('Errore nella creazione del utente: riprova!', 'danger')

    return redirect(url_for('iscriviti'))

# ricevi i dati dal form per  il login situato nella homepage
#se l'utente è già registrato e i dati coincidono consenti l'accesso

@app.route('/login', methods=['POST'])
def login():

  utente_form = request.form.to_dict()

  utente_db = utenti_dao.get_user_by_email(utente_form['email'])

    # se in fase di login l'email o la password sono sbagliati printare errore
  if not utente_db or not check_password_hash(utente_db['password'], utente_form['password']):
    flash('Credenziali non valide, riprova', 'danger')
    return redirect(url_for('home'))
  else:
    new = User(id_utente=utente_db['id_utente'], nome=utente_db['nome'], cognome=utente_db['cognome'], email=utente_db['email'], password=utente_db['password'], immagine_utente=utente_db['immagine_utente'] )
    login_user(new, True)
    flash('Bentornato ' + utente_db['nome'] + ' ' + utente_db['cognome'] + '!', 'success')

    return redirect(url_for('home'))

# define the current user
@login_manager.user_loader
def load_user(user_id):

    db_user = utenti_dao.get_user_by_id(user_id)
    if db_user is not None:
        user = User(id_utente=db_user['id_utente'], nome=db_user['nome'], cognome=db_user['cognome'], email=db_user['email'], password=db_user['password'], immagine_utente=db_user['immagine_utente'])
    else:
        user = None

    return user

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

# define the new post endpoint
@app.route('/raccolte/new', methods=['POST'])
@login_required
def nuova_raccolta():

    '''I campi presenti nel form sono:
        - titolo_raccolta
        - descrizione
        - immagine_raccolta
        - cifra_da_raggiungere
        - importo minimo
        - tipo_raccolta
        
    Quindi si devono aggiungere anche:
        - cifra_attuale = 0 perchè la raccolta è stata appena creata
        - organizzatore_raccolta = current_user
        - data creazione da definire al momento della sottomissione del form
        - data_termine da definire in base a tipo_raccolta'''
            
    raccolta = request.form.to_dict()

    if raccolta['titolo_raccolta'] == '':
        flash('Il titolo non può essere vuoto', 'danger')
        app.logger.error('Il titolo non può essere vuoto')
        return redirect(url_for('home'))

    # controlla che la descrizione non sia vuota
    if raccolta['descrizione'] == '':
        app.logger.error('La descrizione non può essere vuota!')
        return redirect(url_for('home'))
    
    # controlla che la cifra da raggiungere non sia vuota
    if raccolta['cifra_da_raggiungere'] == '':
        app.logger.error('La cifra da raggiungere non può essere vuota!')
        return redirect(url_for('home'))
    
    # controlla che l'importo minimo non sia vuoto
    if raccolta['importo_minimo'] == '':
        app.logger.error('L\' importo minimo non può essere vuoto!')
        return redirect(url_for('home'))
    
    # il tipo di raccolta: lampo o normale
    
    tipo_raccolta = raccolta.get('tipo_raccolta', 'off')  # 'off' as default if not present
    if tipo_raccolta == 'on':
        raccolta['tipo_raccolta'] = 'lampo'
    else:
        raccolta['tipo_raccolta'] = 'normale'

    # Get the current date and time
    now = datetime.now()

    # Extract the date, hour, minute
    current_date, current_hour, current_minute = now.date(), now.hour, now.minute

    # data di creazione della raccolta
    raccolta['data_creazione'] = now.strftime("%Y-%m-%d %H:%M")

    # data del termine della raccolta, dipende da tipo_raccolta
    if raccolta['tipo_raccolta'] == 'lampo':
        raccolta['data_termine'] = now + timedelta(minutes=5)
    else:
        raccolta['data_termine'] =  now + timedelta(days=14)

    # alla sua creazione, la cifra raggiunta della raccolta è zero
    raccolta['cifra_attuale'] = 0

    raccolta['organizzatore_raccolta'] = current_user.id_utente
    
    # verifica se è stata ricevuta un'immagine, in caso affermativo
    # ridimensionala e poi salvala con un nome che includa quello del creatore della raccolta
    # ovvero il current user
    immagine_raccolta = request.files['immagine_raccolta']
    if immagine_raccolta:

        # Open the user-provided image using the Image module
        img = Image.open(immagine_raccolta)

        # Get the width and height of the image
        width, height = img.size

        # Calculate the new height while maintaining the aspect ratio based on the desired width
        new_height = height/width * POST_IMG_WIDTH

        # Define the size for thumbnail creation with the desired width and calculated height
        size = POST_IMG_WIDTH, new_height
        img.thumbnail(size, Image.Resampling.LANCZOS)

        # Extracting file extension from the image filename
        ext = immagine_raccolta.filename.split('.')[-1]
        # Getting the current timestamp in seconds
        secondi = int(datetime.now().timestamp())       

        # Saving the image with a unique filename in the 'static' directory
        img.save('static/@' + current_user.nome.lower() + current_user.cognome.lower() + '-' + str(secondi) + '.' + ext)

        # Updating the 'immagine_post' field in the post dictionary with the image filename
        raccolta['immagine_raccolta'] = '@' + current_user.nome.lower() + current_user.cognome.lower() + str(secondi) + '.' + ext

    # add the new post to the posts database
    success = raccolte_dao.add_raccolta(raccolta)

    if success:
        flash('Raccolta fondi creata correttamente', 'success')
        app.logger.info('Raccolta fondi creata correttamente')
    else:
        flash('Errore nella creazione della raccolta fondi: riprova!', 'danger')
        app.logger.error('Errore nella creazione della raccolta fondi: riprova!')

    return redirect(url_for('home'))

# pagina con le raccolte terminate
@app.route('/raccolte_terminate')
def raccolte_terminate():
    
    # interroga il database e richiedi tutte le raccolte con lo status "terminata", ordina in ordine
    # decrescente di data, quindi mostrando prima quelle finite più di recente
  
    return render_template('raccolte_terminate.html')

# pagina con tutte le raccolte dell'utente
@app.route('/le_mie_raccolte')
def le_mie_raccolte():

    return render_template('le_mie_raccolte.html')


@app.route('/about')
def about():
    author_picture = 'mattia_antonini.jpg'
    return render_template('about.html', picture = author_picture)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=3000, debug=True)