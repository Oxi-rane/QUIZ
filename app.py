from flask import Flask, render_template,request,redirect,session,jsonify,flash 
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash




db=mysql.connector.connect(host="localhost",user="root",password="#HM@mysql",database="quizdb")
cursor=db.cursor()
app=Flask(__name__)
app.secret_key="quiz_random_key@672309"
@app.route("/")
def home():
    return render_template("login.html")



@app.route('/login', methods=['GET','POST'])
def login():
   
    if request.method == 'POST':
        identifier = request.form["identifier"]

        password = request.form['password']

        query = "SELECT user_id,password FROM users WHERE username=%s or email=%s"
        cursor.execute(query,(identifier,identifier))

        user = cursor.fetchone()

        if user and check_password_hash(user[1], password):
            session['user_id']=user[0]
            return redirect('/dashboard')
        
        else:
            flash("Invalid username or password")
            return redirect('/login')

    return render_template("login.html")


@app.route('/register', methods=['GET','POST'])
def register():

    if request.method == 'POST':

        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        hashed_password = generate_password_hash(password)

        cursor.execute("SELECT user_id FROM users WHERE username=%s or email=%s", (username,email))
        existing = cursor.fetchone()
        if existing:
            flash("An account with the username or email already exists")
            return redirect('/register')
            
        cursor.execute("INSERT INTO users (username, email, password) VALUES (%s, %s, %s)",
        (username, email, hashed_password))

        db.commit()

        return redirect('/login')

    return render_template("register.html")

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    query = "SELECT username,total_score FROM users WHERE user_id=%s"
    cursor.execute(query,(user_id,))
    user = cursor.fetchone()

    categories_with_quizzes = []

    cursor.execute("SELECT category_id, name FROM categories where name not like 'Dail%'")
    categories = cursor.fetchall()

    for cat in categories:
        cat_id = cat[0]
        cursor.execute("SELECT quiz_id, title FROM quizzes WHERE category_id=%s", (cat_id,))
        quizzes = cursor.fetchall()
    
        categories_with_quizzes.append({
            'id': cat_id,            
            'name': cat[1],
            'quizzes': [{'quiz_id': q[0], 'title': q[1]} for q in quizzes]
        })
    
    cursor.execute("SELECT question_id, question_text FROM questions where quiz_id=1 ")
    daily_quiz = cursor.fetchall()
    dailies=[]

    for ques in daily_quiz:
        ques_id=ques[0]
        ques_text=ques[1]
        cursor.execute("Select option_id,option_text from ques_options where question_id=%s",(ques_id,))
        options=cursor.fetchall()
        all_options=[]
        for opt in options:
            opt_id=opt[0]
            opt_text=opt[1]
            all_options.append({"id":opt_id,"text":opt_text})

        dailies.append({
            "id":ques_id,
            "text":ques_text,
            "options":all_options
            })
    cursor.execute("""
        SELECT question_id, selected_option
        FROM attempt_answers
        WHERE user_id=%s
        """,(session["user_id"],))
    rows = cursor.fetchall()
    

    answers = {}

    for r in rows:
        answers[r[0]] = r[1]
    
    cursor.execute(
    """
    SELECT quiz_id, MAX(score) AS score
    FROM attempts
    WHERE quiz_id != 1 AND user_id = %s
    GROUP BY quiz_id
    ORDER BY score DESC
    LIMIT 5
    """,
    (session['user_id'],)
    )
    scores=cursor.fetchall()
    attempts=[]
    for quiz_id,score in scores:
        cursor.execute('select title from quizzes where quiz_id=%s',(quiz_id,))
        title=cursor.fetchone()[0]
        attempts.append({'title':title,'score':score})
    
    return render_template('dashboard.html',username=user[0],score=user[1], categories=categories_with_quizzes,dailies=dailies,answers=answers,attempts=attempts)

    
@app.route("/profile")
def profile():

    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    query = "SELECT username, email FROM users WHERE user_id=%s"
    cursor.execute(query, (user_id,))
    user = cursor.fetchone()
    
    return render_template("profile.html", user=user)
@app.route("/settings")
def settings():

    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    query = "SELECT username, email FROM users WHERE user_id=%s"
    cursor.execute(query, (user_id,))
    user = cursor.fetchone()

    return render_template("settings.html", user=user)

from werkzeug.security import check_password_hash, generate_password_hash

@app.route("/change_password", methods=["GET","POST"])
def change_password():

    if request.method == "POST":

        current_password = request.form["current_password"]
        new_password = request.form["new_password"]
        confirm_password = request.form["confirm_password"]

        user_id = session["user_id"]

       
        query = "SELECT password FROM users WHERE user_id=%s"
        cursor.execute(query,(user_id,))
        user = cursor.fetchone()

        if not check_password_hash(user[0], current_password):
            flash("Incorrect Password")
            return redirect('/settings')
        if new_password != confirm_password:
            flash("Password do not match")
            return redirect('/settings')

        new_hash = generate_password_hash(new_password)

        update = "UPDATE users SET password=%s WHERE user_id=%s"
        cursor.execute(update,(new_hash,user_id))
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
    
   

   
    cursor.execute("""
        INSERT IGNORE INTO attempt_answers
        (user_id, question_id, selected_option)
        VALUES (%s,%s,%s)
        """,(session["user_id"], qid, answer))

    db.commit()

    query="select option_id from ques_options where question_id=%s and is_correct=True"
    cursor.execute(query,(qid,))
    correct=cursor.fetchone()[0]
    if correct==answer:
        cursor.execute("""
            UPDATE attempts
            SET score = score + 10
            WHERE user_id=%s AND quiz_id=1
        """, (session['user_id'],))
        cursor.execute("""
            UPDATE users
            SET total_score = total_score + 10
            WHERE user_id=%s
            """,(session["user_id"],))

        db.commit()
        return jsonify({"correct": True,"correct_option":correct})
    else:
        cursor.execute("""
            UPDATE attempts
            SET score = score - 5
            WHERE user_id=%s AND quiz_id=1
        """, (session['user_id'],))
        cursor.execute("""
            UPDATE users
            SET total_score = Greatest(total_score - 5,0)
            WHERE user_id=%s
            """,(session["user_id"],))
        return jsonify({"correct":False,"correct_option":correct})
@app.route("/show_answer", methods=["POST"])
def show_answer():

    data = request.get_json()

    qid = data["question_id"]
    answer = data["answer"]
    
   

   
    cursor.execute("""
        INSERT IGNORE INTO attempt_answers
        (user_id, question_id, selected_option)
        VALUES (%s,%s,%s)
        """,(session["user_id"], qid, answer))

    db.commit()

    query="select option_id from ques_options where question_id=%s and is_correct=True"
    cursor.execute(query,(qid,))
    correct=cursor.fetchone()[0]
    if correct==answer:
        return jsonify({"correct": True,"correct_option":correct})
    else:
        return jsonify({"correct":False,"correct_option":correct})
@app.route("/get_quiz/<int:quiz_id>")
def get_quiz(quiz_id):

    cursor.execute("SELECT title FROM quizzes WHERE quiz_id=%s", (quiz_id,))
    title = cursor.fetchone()[0]

    cursor.execute(
        "SELECT question_id, question_text FROM questions WHERE quiz_id=%s",
        (quiz_id,)
    )
    questions = cursor.fetchall()

    quiz_questions = []

    for q in questions:
        ques_id, ques_text = q  

        cursor.execute(
            "SELECT option_id, option_text FROM ques_options WHERE question_id=%s",
            (ques_id,)
        )
        options = cursor.fetchall()
        all_options = [{"id": opt[0], "text": opt[1]} for opt in options]

        quiz_questions.append({
            "id": ques_id,
            "text": ques_text,
            "options": all_options
        })

    return jsonify({
        "quiz_id": quiz_id,
        "title": title,
        "questions": quiz_questions
    })
@app.route("/submit_quiz", methods=["POST"])
def submit_quiz():
    print("entered submit quiz")
    data = request.get_json()
    answers = data["answers"]
    quiz_id = list(answers.keys())[0]
    user_id = session["user_id"]
    print(quiz_id)
    score = 0
    wrong = 0
    correct_answers = {}
   
    for question_id, selected_option in answers[quiz_id].items():

        cursor.execute("""
            SELECT option_id
            FROM ques_options
            WHERE question_id=%s AND is_correct=1
        """, (question_id,))

        correct_option = cursor.fetchone()[0]
        correct_answers[question_id] = correct_option

        if int(selected_option) == correct_option:
            score += 10
        
        else:
            score=max(score-5,0)
            wrong += 1

    cursor.execute("""
        INSERT INTO attempts (user_id, quiz_id, score, wrong_attempts)
        VALUES (%s,%s,%s,%s)
    """, (user_id, quiz_id, max(score,0), wrong))

    db.commit()

    return jsonify({
        'quiz_id':quiz_id,
        "score": score,
        "wrong": wrong,
        "correct_answers": correct_answers
    })
if __name__=="__main__":
   app.run(host="0.0.0.0", debug=True)