from flask import Flask, render_template, request, redirect, session, jsonify, flash, g
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "quiz_random_key@672309"
DATABASE = "quizdb.db"

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db is not None:
        db.close()

@app.route("/")
def home():
    return render_template("login.html")


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identifier = request.form["identifier"]
        password = request.form['password']

        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT user_id, password FROM users WHERE username=? OR email=?", (identifier, identifier))
        user = cursor.fetchone()

        if user and check_password_hash(user[1], password):
            session['user_id'] = user[0]
            return redirect('/dashboard')
        else:
            flash("Invalid username or password")
            return redirect('/login')

    return render_template("login.html")


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        hashed_password = generate_password_hash(password)

        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT user_id FROM users WHERE username=? OR email=?", (username, email))
        existing = cursor.fetchone()
        if existing:
            flash("An account with the username or email already exists")
            return redirect('/register')

        cursor.execute("INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
                       (username, email, hashed_password))
        db.commit()
        return redirect('/login')

    return render_template("register.html")


@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]
    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT username, total_score FROM users WHERE user_id=?", (user_id,))
    user = cursor.fetchone()

    cursor.execute("SELECT category_id, name FROM categories WHERE name NOT LIKE 'Dail%'")
    categories = cursor.fetchall()

    categories_with_quizzes = []
    for cat in categories:
        cat_id = cat[0]
        cursor.execute("SELECT quiz_id, title FROM quizzes WHERE category_id=?", (cat_id,))
        quizzes = cursor.fetchall()
        categories_with_quizzes.append({
            'id': cat_id,
            'name': cat[1],
            'quizzes': [{'quiz_id': q[0], 'title': q[1]} for q in quizzes]
        })

    cursor.execute("SELECT question_id, question_text FROM questions WHERE quiz_id=1")
    daily_quiz = cursor.fetchall()
    dailies = []
    for ques in daily_quiz:
        ques_id = ques[0]
        ques_text = ques[1]
        cursor.execute("SELECT option_id, option_text FROM ques_options WHERE question_id=?", (ques_id,))
        options = cursor.fetchall()
        all_options = [{"id": opt[0], "text": opt[1]} for opt in options]
        dailies.append({"id": ques_id, "text": ques_text, "options": all_options})

    cursor.execute("""
        SELECT question_id, selected_option
        FROM attempt_answers
        WHERE user_id=?
    """, (user_id,))
    rows = cursor.fetchall()
    answers = {r[0]: r[1] for r in rows}

    cursor.execute("""
        SELECT quiz_id, MAX(score) as score FROM attempts
        WHERE quiz_id != 1 AND user_id=?
        GROUP BY quiz_id
        ORDER BY score DESC LIMIT 5
        """, (user_id,))
    scores = cursor.fetchall()
    attempts = []
    for quiz_id, score in scores:
        cursor.execute("SELECT title FROM quizzes WHERE quiz_id=?", (quiz_id,))
        title = cursor.fetchone()[0]
        attempts.append({'title': title, 'score': score})
    cursor.execute("SELECT COUNT(DISTINCT quiz_id) FROM attempts WHERE user_id=? AND quiz_id != 1", (user_id,))
    quiz_count = cursor.fetchone()[0]
    return render_template('dashboard.html', username=user[0], score=user[1],
                            categories=categories_with_quizzes, dailies=dailies,
                           answers=answers, attempts=attempts,quiz_count=quiz_count)


@app.route("/profile")
@app.route("/profile")
def profile():
    if "user_id" not in session:
        return redirect("/login")
    db = get_db()
    cursor = db.cursor()

    user_id = session["user_id"]
    cursor.execute("SELECT username, email, total_score FROM users WHERE user_id=?", (user_id,))
    user = cursor.fetchone()

    # user's rank
    cursor.execute("""
        SELECT COUNT(*) FROM users 
        WHERE total_score > (SELECT total_score FROM users WHERE user_id=?)
    """, (user_id,))
    rank = cursor.fetchone()[0] + 1

    # top 5 leaderboard
    cursor.execute("""
        SELECT username, total_score FROM users
        ORDER BY total_score DESC LIMIT 5
    """)
    leaderboard = cursor.fetchall()

    # user's best quiz score
    cursor.execute("""
        SELECT MAX(score) FROM attempts WHERE user_id=? AND quiz_id != 1
    """, (user_id,))
    best = cursor.fetchone()[0] or 0

    return render_template("profile.html", user=user, rank=rank, leaderboard=leaderboard, best=best)



@app.route("/settings")
def settings():
    if "user_id" not in session:
        return redirect("/login")

    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT username, email FROM users WHERE user_id=?", (session["user_id"],))
    user = cursor.fetchone()
    return render_template("settings.html", user=user)


@app.route("/change_password", methods=["GET", "POST"])
def change_password():
    if request.method == "POST":
        current_password = request.form["current_password"]
        new_password = request.form["new_password"]
        confirm_password = request.form["confirm_password"]
        user_id = session["user_id"]

        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT password FROM users WHERE user_id=?", (user_id,))
        user = cursor.fetchone()

        if not check_password_hash(user[0], current_password):
            flash("Incorrect Password")
            return redirect('/settings')
        if new_password != confirm_password:
            flash("Password do not match")
            return redirect('/settings')

        new_hash = generate_password_hash(new_password)
        cursor.execute("UPDATE users SET password=? WHERE user_id=?", (new_hash, user_id))
        db.commit()
        flash("Password Updated")
        return redirect('/settings')


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


@app.route("/check_answer", methods=["POST"])
def check_answer():
    data = request.get_json()
    qid = data["question_id"]
    answer = data["answer"]
    user_id = session["user_id"]

    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        INSERT OR IGNORE INTO attempt_answers (user_id, question_id, selected_option)
        VALUES (?, ?, ?)
    """, (user_id, qid, answer))
    db.commit()

    cursor.execute("SELECT option_id FROM ques_options WHERE question_id=? AND is_correct=1", (qid,))
    correct = cursor.fetchone()[0]

    if correct == answer:
        cursor.execute("UPDATE attempts SET score = score + 10 WHERE user_id=? AND quiz_id=1", (user_id,))
        cursor.execute("UPDATE users SET total_score = total_score + 10 WHERE user_id=?", (user_id,))
        
        db.commit()
        cursor.execute("select total_score from users WHERE user_id=?", (user_id,))
        new_score=cursor.fetchone()[0]
        print(new_score)
        
        return jsonify({ "new_score":new_score,"correct": True, "correct_option": correct})
    else:
        cursor.execute("UPDATE attempts SET score = score - 5 WHERE user_id=? AND quiz_id=1", (user_id,))
        cursor.execute("UPDATE users SET total_score = MAX(total_score - 5, 0) WHERE user_id=?", (user_id,))
        db.commit()
        cursor.execute("select total_score from users WHERE user_id=?", (user_id,))
        new_score=cursor.fetchone()[0]
        return jsonify({"new_score":new_score,"correct": False, "correct_option": correct})


@app.route("/show_answer", methods=["POST"])
def show_answer():
    data = request.get_json()
    qid = data["question_id"]
    answer = data["answer"]
    user_id = session["user_id"]

    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        INSERT OR IGNORE INTO attempt_answers (user_id, question_id, selected_option)
        VALUES (?, ?, ?)
    """, (user_id, qid, answer))
    db.commit()

    cursor.execute("SELECT option_id FROM ques_options WHERE question_id=? AND is_correct=1", (qid,))
    correct = cursor.fetchone()[0]

    if correct == answer:
        return jsonify({"correct": True, "correct_option": correct})
    else:
        return jsonify({"correct": False, "correct_option": correct})


@app.route("/get_quiz/<int:quiz_id>")
def get_quiz(quiz_id):
    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT title FROM quizzes WHERE quiz_id=?", (quiz_id,))
    title = cursor.fetchone()[0]

    cursor.execute("SELECT question_id, question_text FROM questions WHERE quiz_id=?", (quiz_id,))
    questions = cursor.fetchall()

    quiz_questions = []
    for q in questions:
        ques_id, ques_text = q[0], q[1]
        cursor.execute("SELECT option_id, option_text FROM ques_options WHERE question_id=?", (ques_id,))
        options = cursor.fetchall()
        all_options = [{"id": opt[0], "text": opt[1]} for opt in options]
        quiz_questions.append({"id": ques_id, "text": ques_text, "options": all_options})

    return jsonify({"quiz_id": quiz_id, "title": title, "questions": quiz_questions})


@app.route("/submit_quiz", methods=["POST"])
def submit_quiz():
    data = request.get_json()
    answers = data["answers"]
    quiz_id = list(answers.keys())[0]
    user_id = session["user_id"]

    db = get_db()
    cursor = db.cursor()

    score = 0
    wrong = 0
    correct_answers = {}

    for question_id, selected_option in answers[quiz_id].items():
        cursor.execute("""
            SELECT option_id FROM ques_options
            WHERE question_id=? AND is_correct=1
        """, (question_id,))
        correct_option = cursor.fetchone()[0]
        correct_answers[question_id] = correct_option

        if int(selected_option) == correct_option:
            score += 10
        else:
            score = max(score-5,0)
            wrong += 1

    cursor.execute("""
        INSERT INTO attempts (user_id, quiz_id, score, wrong_attempts)
        VALUES (?, ?, ?, ?)
    """, (user_id, quiz_id, max(score, 0), wrong))
    db.commit()
    return jsonify({
        'quiz_id': quiz_id,
        
        "score": score,
        "wrong": wrong,
        "correct_answers": correct_answers
    })


if __name__ == "__main__":
    app.run(debug=True)
