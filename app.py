from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from sqlalchemy import text, inspect
import os

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'secret-key-123')

database_url = os.getenv('DATABASE_URL')
if database_url:
    if '?' in database_url:
        app.config['SQLALCHEMY_DATABASE_URI'] = database_url + '&sslmode=require'
    else:
        app.config['SQLALCHEMY_DATABASE_URI'] = database_url + '?sslmode=require'
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = (
        f"postgresql://postgres:102030@localhost:5432/songs"
    )

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


class Song(db.Model):
    __tablename__ = 'songs'

    id = db.Column(db.Integer, primary_key=True)
    song_display_name = db.Column(db.String(500))
    track_duration = db.Column(db.String(100))
    music_author = db.Column(db.String(500))
    lyrics_author = db.Column(db.String(500))
    genre = db.Column(db.String(50))
    artist_text = db.Column(db.String(500))
    phonogram_manufacturer = db.Column(db.String(500))

    def __repr__(self):
        return f'<Song {self.song_display_name}>'


with app.app_context():
    db.create_all()
    print("✅ Таблицы созданы (или уже существуют)")


@app.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '', type=str)
    per_page = request.args.get('per_page', 50, type=int)
    sort_by = request.args.get('sort_by', 'id', type=str)
    sort_order = request.args.get('sort_order', 'asc', type=str)

    allowed_sort_fields = ['id', 'song_display_name', 'track_duration', 'music_author', 'lyrics_author', 'artist_text', 'phonogram_manufacturer']
    if sort_by not in allowed_sort_fields:
        sort_by = 'id'

    if sort_order == 'asc':
        order = getattr(Song, sort_by).asc()
    else:
        order = getattr(Song, sort_by).desc()

    query = Song.query

    if search:
        search_pattern = f'%{search}%'
        query = query.filter(
            db.or_(
                Song.song_display_name.ilike(search_pattern),
                Song.artist_text.ilike(search_pattern),
                Song.music_author.ilike(search_pattern),
                Song.lyrics_author.ilike(search_pattern)
            )
        )

    total = query.count()
    songs = query.order_by(order).offset((page - 1) * per_page).limit(per_page).all()
    total_pages = (total + per_page - 1) // per_page

    return render_template(
        'index.html',
        songs=songs,
        page=page,
        total_pages=total_pages,
        total=total,
        search=search,
        per_page=per_page,
        sort_by=sort_by,
        sort_order=sort_order
    )


@app.route('/song/<int:id>')
def view_song(id):
    song = Song.query.get_or_404(id)
    return render_template('song.html', song=song)


@app.route('/add', methods=['GET', 'POST'])
def add_song():
    if request.method == 'POST':
        artist = request.form.get('artist_text', '')
        track = request.form.get('track_duration', '')
        song_display_name = f"{artist} - {track}" if artist and track else track or artist or ''

        song = Song(
            song_display_name=song_display_name,
            track_duration=track,
            music_author=request.form.get('music_author'),
            lyrics_author=request.form.get('lyrics_author'),
            genre=request.form.get('genre', 'CHR'),
            artist_text=artist,
            phonogram_manufacturer=request.form.get('phonogram_manufacturer', '')
        )
        db.session.add(song)
        db.session.commit()
        return redirect(url_for('index'))

    return render_template('add.html')


@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit_song(id):
    song = Song.query.get_or_404(id)

    if request.method == 'POST':
        artist = request.form.get('artist_text', '')
        track = request.form.get('track_duration', '')
        song_display_name = f"{artist} - {track}" if artist and track else track or artist or ''

        song.song_display_name = song_display_name
        song.track_duration = track
        song.music_author = request.form.get('music_author')
        song.lyrics_author = request.form.get('lyrics_author')
        song.genre = request.form.get('genre', 'CHR')
        song.artist_text = artist
        song.phonogram_manufacturer = request.form.get('phonogram_manufacturer', '')

        db.session.commit()
        return redirect(url_for('index'))

    return render_template('edit.html', song=song)


@app.route('/delete/<int:id>', methods=['POST'])
def delete_song(id):
    song = Song.query.get_or_404(id)
    db.session.delete(song)
    db.session.commit()
    return redirect(url_for('index'))


@app.route('/fix_names', methods=['GET', 'POST'])
def fix_names():
    songs = Song.query.all()
    count = 0
    for song in songs:
        if song.artist_text and song.track_duration:
            song.song_display_name = f"{song.artist_text} - {song.track_duration}"
            count += 1
        elif song.track_duration:
            song.song_display_name = song.track_duration
            count += 1
        elif song.artist_text:
            song.song_display_name = song.artist_text
            count += 1
    db.session.commit()
    return f"""
    <html>
        <head>
            <style>
                body {{
                    font-family: 'Segoe UI', Arial, sans-serif;
                    background: #ffffff;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                }}
                .container {{
                    background: white;
                    padding: 40px;
                    border-radius: 16px;
                    box-shadow: 0 20px 60px rgba(0,0,0,0.1);
                    text-align: center;
                    max-width: 500px;
                }}
                .btn {{
                    display: inline-block;
                    padding: 12px 30px;
                    background: #4a90d9;
                    color: white;
                    text-decoration: none;
                    border-radius: 8px;
                    margin-top: 20px;
                    transition: all 0.2s;
                }}
                .btn:hover {{
                    background: #357abd;
                    transform: translateY(-2px);
                    box-shadow: 0 4px 15px rgba(74, 144, 217, 0.4);
                }}
                .count {{
                    font-size: 48px;
                    font-weight: bold;
                    color: #4a90d9;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>✅ Готово!</h1>
                <p>Обновлено названий: <span class="count">{count}</span></p>
                <a href="/" class="btn">← Вернуться на главную</a>
            </div>
        </body>
    </html>
    """


@app.route('/health')
def health():
    return "OK", 200


if __name__ == '__main__':
    with app.app_context():
        try:
            inspector = inspect(db.engine)
            if 'songs' in inspector.get_table_names():
                max_id = db.session.execute(text("SELECT COALESCE(MAX(id), 0) FROM songs;")).scalar()
                db.session.execute(text(f"SELECT setval('songs_id_seq', {max_id + 1}, false);"))
                db.session.commit()
        except Exception as e:
            print(f"Ошибка при проверке таблицы: {e}")
            db.create_all()
    
    port = int(os.getenv('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
