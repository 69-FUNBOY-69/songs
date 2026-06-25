from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from sqlalchemy import text, inspect
import os
import csv
import io
import pandas as pd
from werkzeug.utils import secure_filename

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'secret-key-123')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

database_url = os.getenv('DATABASE_URL')
if database_url:
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = (
        f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
        f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
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

    def to_dict(self):
        return {
            'id': self.id,
            'song_display_name': self.song_display_name,
            'track_duration': self.track_duration,
            'music_author': self.music_author,
            'lyrics_author': self.lyrics_author,
            'genre': self.genre,
            'artist_text': self.artist_text,
            'phonogram_manufacturer': self.phonogram_manufacturer
        }


with app.app_context():
    db.create_all()
    max_id = db.session.execute(text("SELECT COALESCE(MAX(id), 0) FROM songs;")).scalar()
    db.session.execute(text(f"SELECT setval('songs_id_seq', {max_id + 1}, false);"))
    db.session.commit()
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
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '', type=str)
    per_page = request.args.get('per_page', 50, type=int)
    sort_by = request.args.get('sort_by', 'id', type=str)
    sort_order = request.args.get('sort_order', 'asc', type=str)
    return render_template('song.html', song=song, page=page, search=search, per_page=per_page, sort_by=sort_by, sort_order=sort_order)


@app.route('/add', methods=['GET', 'POST'])
def add_song():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '', type=str)
    per_page = request.args.get('per_page', 50, type=int)
    sort_by = request.args.get('sort_by', 'id', type=str)
    sort_order = request.args.get('sort_order', 'asc', type=str)

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
        
        max_id = db.session.execute(text("SELECT COALESCE(MAX(id), 0) FROM songs;")).scalar()
        db.session.execute(text(f"SELECT setval('songs_id_seq', {max_id + 1}, false);"))
        db.session.commit()
        
        total = db.session.execute(text("SELECT COUNT(*) FROM songs;")).scalar()
        total_pages = (total + per_page - 1) // per_page
        last_page = total_pages if total_pages > 0 else 1
        
        return redirect(url_for('index', page=last_page, search=search, per_page=per_page, sort_by=sort_by, sort_order=sort_order))

    return render_template('add.html', page=page, search=search, per_page=per_page, sort_by=sort_by, sort_order=sort_order)
 

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit_song(id):
    song = Song.query.get_or_404(id)
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '', type=str)
    per_page = request.args.get('per_page', 50, type=int)
    sort_by = request.args.get('sort_by', 'id', type=str)
    sort_order = request.args.get('sort_order', 'asc', type=str)

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
        return redirect(url_for('index', page=page, search=search, per_page=per_page, sort_by=sort_by, sort_order=sort_order))

    return render_template('edit.html', song=song, page=page, search=search, per_page=per_page, sort_by=sort_by, sort_order=sort_order)


@app.route('/delete/<int:id>', methods=['POST'])
def delete_song(id):
    song = Song.query.get_or_404(id)
    db.session.delete(song)
    db.session.commit()
    max_id = db.session.execute(text("SELECT COALESCE(MAX(id), 0) FROM songs;")).scalar()
    db.session.execute(text(f"SELECT setval('songs_id_seq', {max_id + 1}, false);"))
    db.session.commit()
    return jsonify({'success': True})


@app.route('/delete_mass', methods=['POST'])
def delete_mass():
    ids = request.json.get('ids', [])
    if ids:
        Song.query.filter(Song.id.in_(ids)).delete(synchronize_session=False)
        db.session.commit()
        max_id = db.session.execute(text("SELECT COALESCE(MAX(id), 0) FROM songs;")).scalar()
        db.session.execute(text(f"SELECT setval('songs_id_seq', {max_id + 1}, false);"))
        db.session.commit()
    return jsonify({'success': True, 'deleted': len(ids)})


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


@app.route('/export')
def export():
    format_type = request.args.get('format', 'csv')
    ids_param = request.args.get('ids', '')
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '', type=str)
    per_page = request.args.get('per_page', 50, type=int)
    sort_by = request.args.get('sort_by', 'id', type=str)
    sort_order = request.args.get('sort_order', 'asc', type=str)

    allowed_sort_fields = ['id', 'song_display_name', 'track_duration', 'music_author', 'lyrics_author', 'artist_text', 'phonogram_manufacturer']

    if ids_param:
        ids = [int(x) for x in ids_param.split(',') if x]
        songs = Song.query.filter(Song.id.in_(ids)).all()
    else:
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
        if sort_by in allowed_sort_fields:
            if sort_order == 'asc':
                query = query.order_by(getattr(Song, sort_by).asc())
            else:
                query = query.order_by(getattr(Song, sort_by).desc())
        songs = query.all()

    data = []
    for idx, song in enumerate(songs, 1):
        data.append({
            'ID': idx,
            'Название произведения': song.song_display_name or '',
            'Название фонограммы': song.track_duration or '',
            'Автор музыки': song.music_author or '',
            'Автор текста': song.lyrics_author or '',
            'Жанр': song.genre or '',
            'Исполнитель': song.artist_text or '',
            'Изготовитель фонограммы': song.phonogram_manufacturer or ''
        })

    if format_type == 'csv':
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=data[0].keys() if data else [])
        writer.writeheader()
        writer.writerows(data)
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8-sig')),
            mimetype='text/csv',
            as_attachment=True,
            download_name='songs_export.csv'
        )
    elif format_type == 'xlsx':
        df = pd.DataFrame(data)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Songs')
            worksheet = writer.sheets['Songs']
            
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if cell.value and len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 4, 80)
                worksheet.column_dimensions[column_letter].width = adjusted_width
            
            for row in worksheet.iter_rows():
                for cell in row:
                    cell.alignment = cell.alignment.copy(wrap_text=True)
        
        output.seek(0)
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='songs_export.xlsx'
        )
    elif format_type == 'txt':
        output = io.StringIO()
        headers = list(data[0].keys()) if data else []
        output.write(','.join(headers) + '\n')
        for row in data:
            row_values = [str(row[h]) for h in headers]
            output.write(','.join(row_values) + '\n')
        
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8-sig')),
            mimetype='text/plain',
            as_attachment=True,
            download_name='songs_export.txt'
        )
    return redirect(url_for('index', page=page, search=search, per_page=per_page, sort_by=sort_by, sort_order=sort_order))


@app.route('/import', methods=['POST'])
def import_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    filename = secure_filename(file.filename)
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    
    songs_added = 0
    errors = []
    
    try:
        if ext == 'csv':
            content = file.read().decode('utf-8-sig')
            reader = csv.DictReader(io.StringIO(content))
            for row in reader:
                try:
                    artist = row.get('Исполнитель', '').strip() or row.get('artist_text', '').strip()
                    track = row.get('Название фонограммы', '').strip() or row.get('track_duration', '').strip()
                    song = Song(
                        song_display_name=f"{artist} - {track}" if artist and track else track or artist or '',
                        track_duration=track,
                        music_author=row.get('Автор музыки', '').strip() or row.get('music_author', '').strip(),
                        lyrics_author=row.get('Автор текста', '').strip() or row.get('lyrics_author', '').strip(),
                        genre=row.get('Жанр', 'CHR').strip() or row.get('genre', 'CHR').strip(),
                        artist_text=artist,
                        phonogram_manufacturer=row.get('Изготовитель фонограммы', '').strip() or row.get('phonogram_manufacturer', '').strip()
                    )
                    db.session.add(song)
                    songs_added += 1
                except Exception as e:
                    errors.append(str(e))
            db.session.commit()
            
        elif ext in ['xlsx', 'xls']:
            df = pd.read_excel(file)
            for _, row in df.iterrows():
                try:
                    artist = str(row.get('Исполнитель', '')).strip() or str(row.get('artist_text', '')).strip()
                    track = str(row.get('Название фонограммы', '')).strip() or str(row.get('track_duration', '')).strip()
                    song = Song(
                        song_display_name=f"{artist} - {track}" if artist and track else track or artist or '',
                        track_duration=track,
                        music_author=str(row.get('Автор музыки', '')).strip() or str(row.get('music_author', '')).strip(),
                        lyrics_author=str(row.get('Автор текста', '')).strip() or str(row.get('lyrics_author', '')).strip(),
                        genre=str(row.get('Жанр', 'CHR')).strip() or str(row.get('genre', 'CHR')).strip(),
                        artist_text=artist,
                        phonogram_manufacturer=str(row.get('Изготовитель фонограммы', '')).strip() or str(row.get('phonogram_manufacturer', '')).strip()
                    )
                    db.session.add(song)
                    songs_added += 1
                except Exception as e:
                    errors.append(str(e))
            db.session.commit()
            
        elif ext == 'txt':
            content = file.read().decode('utf-8-sig')
            reader = csv.DictReader(io.StringIO(content))
            for row in reader:
                try:
                    artist = row.get('Исполнитель', '').strip()
                    track = row.get('Название фонограммы', '').strip()
                    song = Song(
                        song_display_name=f"{artist} - {track}" if artist and track else track or artist or '',
                        track_duration=track,
                        music_author=row.get('Автор музыки', '').strip(),
                        lyrics_author=row.get('Автор текста', '').strip(),
                        genre=row.get('Жанр', 'CHR').strip(),
                        artist_text=artist,
                        phonogram_manufacturer=row.get('Изготовитель фонограммы', '').strip()
                    )
                    db.session.add(song)
                    songs_added += 1
                except Exception as e:
                    errors.append(str(e))
            db.session.commit()
        else:
            return jsonify({'error': f'Unsupported file format: {ext}'}), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
    max_id = db.session.execute(text("SELECT COALESCE(MAX(id), 0) FROM songs;")).scalar()
    db.session.execute(text(f"SELECT setval('songs_id_seq', {max_id + 1}, false);"))
    db.session.commit()
    
    return jsonify({
        'success': True,
        'added': songs_added,
        'errors': errors
    })


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
